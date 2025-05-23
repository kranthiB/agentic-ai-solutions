# kubernetes_agent/core/agent.py

import os
import time
from typing import Optional
from autogen import ConversableAgent, config_list_from_json, register_function,  LLMConfig

# Import your system prompt
from utils.prompt_templates import KUBERNETES_AGENT_SYSTEM_PROMPT_WITH_GUARDRAILS

# Import all tool modules (classes)
from tools.kubectl_tools import KubectlTools
from tools.pod_tools import PodTools
from tools.deployment_tools import DeploymentTools
from tools.service_tools import ServiceTools
from tools.logging_tools import LoggingTools
from tools.namespace_tools import NamespaceTools
from tools.node_tools import NodeTools
from tools.config_tools import ConfigTools
from tools.resource_tools import ResourceTools
from tools.guardrail_tools import GuardrailTools
from tools.registry import get_tools_registry, Tool

# Import monitoring components
from monitoring.agent_logger import get_logger
from monitoring.cost_tracker import get_cost_tracker
from monitoring.metrics_collector import get_metrics_collector
from monitoring.event_audit_log import get_audit_logger
from monitoring.prometheus_exporter import start_metrics_export

# NEW: Import guardrail service
from services.guardrail.guardrail_service import get_guardrail_service

start_metrics_export()
    
class KubernetesAgent:
    """Central Kubernetes AI agent combining memory, tools, planning, and LLM access."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.cost_tracker = get_cost_tracker()
        self.metrics = get_metrics_collector()
        self.audit = get_audit_logger()
        self.tools_registry = get_tools_registry()

        # NEW: Initialize guardrail service
        self.guardrail_service = get_guardrail_service()

        # Track initialization time
        start_time = time.time()
        
        # Record agent initialization in metrics
        self.metrics.record_tool_call("agent_initialization")

        # Log initialization
        self.logger.info("Initializing Kubernetes Agent")
        # Load LLM Configs
        oai_config_list_path = "configs/OAI_CONFIG_LIST.json"
        self.config_list = config_list_from_json(env_or_file=oai_config_list_path)
        llm_record = next((record for record in self.config_list  if record['api_type'] == os.getenv('LLM_PROVIDER', 'anthropic') ), None)

        # Record agent model information for metrics tracking
        model_name = llm_record.get("model")
        provider = llm_record.get("api_type")
        
        llm_config = LLMConfig(api_type=llm_record.get("api_type"), 
                               api_key=llm_record.get("api_key"),
                               model=llm_record.get("model"),
                               base_url=llm_record.get("base_url")
                               )
        
        # Set metadata about the agent for metrics
        self.metrics.set_task_metadata("agent_initialization", {
            "model": model_name,
            "provider": provider
        })

        with llm_config:
            self.agent = ConversableAgent(
                name="kube_assist",
                system_message=KUBERNETES_AGENT_SYSTEM_PROMPT_WITH_GUARDRAILS,
            )

            # Log agent creation
            self.logger.info("Created main agent with model: %s", model_name)
            
            # Record agent creation success
            self.metrics.record_tool_result("agent_creation", True)
        
        self.executor_agent = ConversableAgent(
            name="executor_agent",
            human_input_mode="NEVER",
        )

        self.logger.info("Created executor agent")
        
        # Record executor agent creation
        self.metrics.record_tool_result("executor_agent_creation", True)

        # Track tool initialization
        self.logger.info("Initializing tools and tool registration")
        tool_init_start = time.time()

        # Initialize all tool classes with the connector
        try:
            # Store count of registered tools for metrics
            tool_count = 0
            
            # Register each tool category and count them
            tool_count += self._register_kubectl_tools()
            tool_count += self._register_node_tools()
            tool_count += self._register_pod_tools()
            tool_count += self._register_deployment_tools()
            tool_count += self._register_service_tools()
            tool_count += self._register_logging_tools()
            tool_count += self._register_namespace_tools()
            tool_count += self._register_config_tools()
            tool_count += self._register_resource_tools()
            tool_count += self._register_guardrail_tools()

            # Log successful tool initialization
            self.logger.info("All tool classes initialized successfully (%d tools total)", tool_count)
            
            # Record tool count in metrics
            if hasattr(self.metrics, 'record_gauge'):
                self.metrics.record_gauge("registered_tools", tool_count)
            
            # Audit log for tool initialization with enhanced data
            self.audit.log_event("tools_initialized", {
                "tool_categories": ["kubectl", "pod", "deployment", "service", 
                                "logging", "node", "namespace", "config", "resource"],
                "total_tool_count": tool_count
            })
            
            # Record tool initialization success
            self.metrics.record_tool_result("tool_initialization", True)
            
            # Record tool initialization time
            tool_init_end = time.time()
            self.metrics.record_task_duration("tool_initialization", tool_init_start, tool_init_end)
        except Exception as e:
            self.logger.error("Failed to initialize tool classes: %s", str(e))
        
            # Record error type for better categorization
            error_type = type(e).__name__
            
            # Record tool initialization failure
            self.metrics.record_tool_result("tool_initialization", False)
            
            self.audit.log_event("initialization_error", {
                "component": "tools",
                "error": str(e),
                "error_type": error_type
            })
            raise
        
        # Record agent initialization complete
        end_time = time.time()
        init_duration = end_time - start_time
        self.metrics.record_task_duration("agent_initialization", start_time, end_time)
        self.logger.info("Agent initialization completed in %.2f seconds", init_duration)
        
        # Record startup metrics
        if hasattr(self.metrics, 'record_gauge'):
            self.metrics.record_gauge("agent_startup_time_seconds", init_duration)

    def _register_resource_tools(self):
        tools_count = 0
        register_function(
            ResourceTools.get_resource,
            caller=self.agent,
            executor=self.executor_agent,
            description="Retrieve detailed info of any Kubernetes resource.",
            name="get_resource",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="get_resource",
            description="Retrieve detailed info of any Kubernetes resource.",
            category="resource"
        ))
        tools_count += 1
        register_function(
            ResourceTools.analyze_resource,
            caller=self.agent,
            executor=self.executor_agent,
            description="Analyze the health and readiness of a Kubernetes resource.",
            name="analyze_resource",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="analyze_resource",
            description="Analyze the health and readiness of a Kubernetes resource.",
            category="resource"
        ))
        tools_count += 1
        # Record category metrics
        self.metrics.record_tool_result("resource_tools_registration", True)

        return tools_count

    def _register_config_tools(self):
        tools_count = 0
        register_function(
            ConfigTools.get_configmap,
            caller=self.agent,
            executor=self.executor_agent,
            description="Retrieve a ConfigMap.",
            name="get_configmap",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="get_configmap",
            description="Retrieve a ConfigMap.",
            category="config"
        ))
        tools_count += 1
        register_function(
            ConfigTools.list_configmaps,
            caller=self.agent,
            executor=self.executor_agent,
            description="List ConfigMaps in a namespace.",
            name="list_configmaps",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="list_configmaps",
            description="List ConfigMaps in a namespace.",
            category="config"
        ))
        tools_count += 1
        register_function(
            ConfigTools.create_configmap,
            caller=self.agent,
            executor=self.executor_agent,
            description="Create a new ConfigMap.",
            name="create_configmap",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="create_configmap",
            description="Create a new ConfigMap.",
            category="config"
        ))
        tools_count += 1
        register_function(
            ConfigTools.update_configmap,
            caller=self.agent,
            executor=self.executor_agent,
            description="Update an existing ConfigMap.",
            name="update_configmap",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="update_configmap",
            description="Update an existing ConfigMap.",
            category="config"
        ))
        tools_count += 1
        register_function(
            ConfigTools.delete_configmap,
            caller=self.agent,
            executor=self.executor_agent,
            description="Delete a ConfigMap.",
            name="delete_configmap",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="delete_configmap",
            description="Delete a ConfigMap.",
            category="config"
        ))
        tools_count += 1

        # Record category metrics
        self.metrics.record_tool_result("config_tools_registration", True)
        return tools_count

    def _register_namespace_tools(self):
        tools_count = 0
        register_function(
            NamespaceTools.get_namespace,
            caller=self.agent,
            executor=self.executor_agent,
            description="Fetch metadata and status of a Kubernetes namespace.",
            name="get_namespace",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="get_namespace",
            description="Fetch metadata and status of a Kubernetes namespace.",
            category="namespace"
        ))
        tools_count += 1
        register_function(
            NamespaceTools.list_namespaces,
            caller=self.agent,
            executor=self.executor_agent,
            description="List all Kubernetes namespaces.",
            name="list_namespaces",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="list_namespaces",
            description="List all Kubernetes namespaces.",
            category="namespace"
        ))
        tools_count += 1
        register_function(
            NamespaceTools.create_namespace,
            caller=self.agent,
            executor=self.executor_agent,
            description="Create a new Kubernetes namespace.",
            name="create_namespace",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="create_namespace",
            description="Create a new Kubernetes namespace.",
            category="namespace"
        ))
        tools_count += 1
        register_function(
            NamespaceTools.delete_namespace,
            caller=self.agent,
            executor=self.executor_agent,
            description="Delete a Kubernetes namespace.",
            name="delete_namespace",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="delete_namespace",
            description="Delete a Kubernetes namespace.",
            category="namespace"
        ))
        tools_count += 1

        # Record category metrics
        self.metrics.record_tool_result("namespace_tools_registration", True)
        return tools_count

    def _register_logging_tools(self):
        tools_count = 0
        register_function(
            LoggingTools.get_pod_logs,
            caller=self.agent,
            executor=self.executor_agent,
            description="Retrieve logs from a Kubernetes pod.",
            name="get_pod_logs",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="get_pod_logs",
            description="Retrieve logs from a Kubernetes pod.",
            category="logging"
        ))
        tools_count += 1
        register_function(
            LoggingTools.analyze_pod_logs,
            caller=self.agent,
            executor=self.executor_agent,
            description="Analyze pod logs for patterns and errors.",
            name="analyze_pod_logs",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="analyze_pod_logs",
            description="Analyze pod logs for patterns and errors.",
            category="logging"
        ))
        tools_count += 1

        # Record category metrics
        self.metrics.record_tool_result("logging_tools_registration", True)
        return tools_count

    def _register_service_tools(self):
        tools_count = 0
        register_function(
            ServiceTools.get_service,
            caller=self.agent,
            executor=self.executor_agent,
            description="Retrieve details of a Kubernetes Service.",
            name="get_service",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="get_service",
            description="Retrieve details of a Kubernetes Service.",
            category="service"
        ))
        tools_count += 1
        register_function(
            ServiceTools.create_service,
            caller=self.agent,
            executor=self.executor_agent,
            description="Create a Kubernetes Service dynamically.",
            name="create_service",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="create_service",
            description="Create a Kubernetes Service dynamically.",
            category="service"
        ))
        tools_count += 1

        # Record category metrics
        self.metrics.record_tool_result("service_tools_registration", True)
        return tools_count


    def _register_pod_tools(self):
        tools_count = 0
        register_function(
            PodTools.get_pod,
            caller=self.agent,
            executor=self.executor_agent,
            description="Retrieve details about a specific pod.",
            name="get_pod",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="get_pod",
            description="Retrieve details about a specific pod.",
            category="pod"
        ))
        tools_count += 1
        register_function(
            PodTools.list_pods,
            caller=self.agent,
            executor=self.executor_agent,
            description="List pods in a namespace with filtering.",
            name="list_pods",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="list_pods",
            description="List pods in a namespace with filtering.",
            category="pod"
        ))
        tools_count += 1
        register_function(
            PodTools.exec_command,
            caller=self.agent,
            executor=self.executor_agent,
            description="Execute a command inside a running pod container.",
            name="exec_command_in_pod",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="exec_command_in_pod",
            description="Execute a command inside a running pod container.",
            category="pod"
        ))
        tools_count += 1

        # Record category metrics
        self.metrics.record_tool_result("pod_tools_registration", True)
        return tools_count

    def _register_kubectl_tools(self):
        tools_count = 0
        register_function(
            KubectlTools.get,
            caller=self.agent,
            executor=self.executor_agent,
            description="Retrieve Kubernetes resources (pods, deployments, services, etc.)",
            name="kubectl_get",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="kubectl_get",
            description="Retrieve Kubernetes resources (pods, deployments, services, etc.)",
            category="kubectl"
        ))
        tools_count += 1
        register_function(
            KubectlTools.describe,
            caller=self.agent,
            executor=self.executor_agent,
            description="Get detailed description of a resource.",
            name="kubectl_describe",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="kubectl_describe",
            description="Get detailed description of a resource.",
            category="kubectl"
        ))
        tools_count += 1
        register_function(
            KubectlTools.create,
            caller=self.agent,
            executor=self.executor_agent,
            description="Create Kubernetes resources from YAML manifests.",
            name="kubectl_create",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="kubectl_create",
            description="Create Kubernetes resources from YAML manifests.",
            category="kubectl"
        ))
        tools_count += 1
        register_function(
            KubectlTools.delete,
            caller=self.agent,
            executor=self.executor_agent,
            description="Delete Kubernetes resources.",
            name="kubectl_delete",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="kubectl_delete",
            description="Delete Kubernetes resources.",
            category="kubectl"
        ))
        tools_count += 1
        register_function(
            KubectlTools.apply,
            caller=self.agent,
            executor=self.executor_agent,
            description="Apply YAML manifests (create/update resources).",
            name="kubectl_apply",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="kubectl_apply",
            description="Apply YAML manifests (create/update resources).",
            category="kubectl"
        ))
        tools_count += 1
        register_function(
            KubectlTools.patch,
            caller=self.agent,
            executor=self.executor_agent,
            description="Patch fields of a Kubernetes resource.",
            name="kubectl_patch",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="kubectl_patch",
            description="Patch fields of a Kubernetes resource.",
            category="kubectl"
        ))
        tools_count += 1
        register_function(
            KubectlTools.logs,
            caller=self.agent,
            executor=self.executor_agent,
            description="Fetch logs from a Kubernetes pod.",
            name="kubectl_logs",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="kubectl_logs",
            description="Fetch logs from a Kubernetes pod.",
            category="kubectl"
        ))
        tools_count += 1

        # Record category metrics
        self.metrics.record_tool_result("kubectl_tools_registration", True)
        return tools_count

    def _register_deployment_tools(self):
        tools_count = 0
        register_function(
            DeploymentTools.get_deployment,
            caller=self.agent,
            executor=self.executor_agent,
            description="Retrieve details of a Kubernetes Deployment.",
            name="get_deployment",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="get_deployment",
            description="Retrieve details of a Kubernetes Deployment.",
            category="deployment"
        ))
        tools_count += 1
        register_function(
            DeploymentTools.list_deployments,
            caller=self.agent,
            executor=self.executor_agent,
            description="List all Deployments.",
            name="list_deployments",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="list_deployments",
            description="List all Deployments.",
            category="deployment"
        ))
        tools_count += 1
        register_function(
            DeploymentTools.create_deployment,
            caller=self.agent,
            executor=self.executor_agent,
            description="Create a Kubernetes Deployment using YAML.",
            name="create_deployment",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="create_deployment",
            description="Create a Kubernetes Deployment using YAML.",
            category="deployment"
        ))
        tools_count += 1

        # Record category metrics
        self.metrics.record_tool_result("deployment_tools_registration", True)
        return tools_count
    
    def _register_node_tools(self):
        tools_count = 0
        register_function(
            NodeTools.list_nodes,
            caller=self.agent,
            executor=self.executor_agent,
            description="List all nodes in the cluster.",
            name="list_nodes",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="list_nodes",
            description="List all nodes in the cluster.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.get_node,
            caller=self.agent,
            executor=self.executor_agent,
            description="Retrieve a Kubernetes node's metadata.",
            name="get_node",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="get_node",
            description="Retrieve a Kubernetes node's metadata.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.describe_node,
            caller=self.agent,
            executor=self.executor_agent,
            description="Detailed description of a node.",
            name="describe_node",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="describe_node",
            description="Detailed description of a node.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.get_node_metrics,
            caller=self.agent,
            executor=self.executor_agent,
            description="Fetch CPU and memory metrics for nodes.",
            name="get_node_metrics",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="get_node_metrics",
            description="Fetch CPU and memory metrics for nodes.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.cordon_node,
            caller=self.agent,
            executor=self.executor_agent,
            description="Mark a node as unschedulable.",
            name="cordon_node",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="cordon_node",
            description="Mark a node as unschedulable.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.uncordon_node,
            caller=self.agent,
            executor=self.executor_agent,
            description="Allow pod scheduling on a node.",
            name="uncordon_node",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="uncordon_node",
            description="Allow pod scheduling on a node.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.drain_node,
            caller=self.agent,
            executor=self.executor_agent,
            description="Evict pods from a node.",
            name="drain_node",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="drain_node",
            description="Evict pods from a node.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.get_pods_on_node,
            caller=self.agent,
            executor=self.executor_agent,
            description="List all pods running on a node.",
            name="get_pods_on_node",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="get_pods_on_node",
            description="List all pods running on a node.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.label_node,
            caller=self.agent,
            executor=self.executor_agent,
            description="Add or update labels on a node.",
            name="label_node",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="label_node",
            description="Add or update labels on a node.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.taint_node,
            caller=self.agent,
            executor=self.executor_agent,
            description="Apply taints to a node.",
            name="taint_node",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="taint_node",
            description="Apply taints to a node.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.remove_node_taint,
            caller=self.agent,
            executor=self.executor_agent,
            description="Remove taints from a node.",
            name="remove_node_taint",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="remove_node_taint",
            description="Remove taints from a node.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.analyze_node,
            caller=self.agent,
            executor=self.executor_agent,
            description="Analyze health of a Kubernetes node.",
            name="analyze_node",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="analyze_node",
            description="Analyze health of a Kubernetes node.",
            category="node"
        ))
        tools_count += 1
        register_function(
            NodeTools.analyze_cluster_nodes,
            caller=self.agent,
            executor=self.executor_agent,
            description="Analyze health of all nodes in the cluster.",
            name="analyze_node",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="analyze_cluster_nodes",
            description="Analyze health of all nodes in the cluster.",
            category="node"
        ))
        tools_count += 1

        # Record category metrics
        self.metrics.record_tool_result("node_tools_registration", True)
        return tools_count

    def _register_guardrail_tools(self):
        """Register guardrail-specific tools"""
        tools_count = 0
        
        # Register a tool to check operation permissions
        register_function(
            GuardrailTools.check_operation_permission,
            caller=self.agent,
            executor=self.executor_agent,
            description="Check if an operation is permitted by the guardrail system.",
            name="check_permission",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="check_permission",
            description="Check if an operation is permitted by the guardrail system.",
            category="security"
        ))
        tools_count += 1
        
        # Register a tool to analyze operation risk
        register_function(
            GuardrailTools.analyze_operation_risk,
            caller=self.agent,
            executor=self.executor_agent,
            description="Analyze the risk level of a Kubernetes operation.",
            name="analyze_risk",
        )
        self.tools_registry.register_tool(tool=Tool(
            name="analyze_risk",
            description="Analyze the risk level of a Kubernetes operation.",
            category="security"
        ))
        tools_count += 1
        
        # Record category metrics
        self.metrics.record_tool_result("guardrail_tools_registration", True)
        
        return tools_count
    
        
    def get_agent(self) -> ConversableAgent:
        """Returns the instantiated Kubernetes Assistant Agent."""
        return self.agent
    
    def get_executor_agent(self) -> ConversableAgent:
        """Returns the executor agent"""
        return self.executor_agent


# Singleton instance
_kubernetes_agent: Optional[KubernetesAgent] = None

def get_kubernetes_agent() -> KubernetesAgent:
    global _kubernetes_agent
    if _kubernetes_agent is None:
        _kubernetes_agent = KubernetesAgent()
    return _kubernetes_agent