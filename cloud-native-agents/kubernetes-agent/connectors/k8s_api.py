import json
import tempfile
import subprocess
from typing import Any, Dict, List, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from connectors.base import ClusterConnector
from concurrent.futures import ThreadPoolExecutor

class KubernetesAPIConnector(ClusterConnector):
    """
    Connector that uses the Kubernetes Python client to interact with the cluster.
    This connector provides a more direct programmatic access to the Kubernetes API
    compared to using kubectl.
    """
    
    def __init__(self, 
                 kubeconfig: Optional[str] = None, 
                 context: Optional[str] = None,
                 namespace: str = "default"):
        """
        Initialize the Kubernetes API connector.
        
        Args:
            kubeconfig: Path to kubeconfig file (None for in-cluster config)
            context: Kubernetes context to use (None for current context)
            namespace: Default namespace to use
        """
        super().__init__(kubeconfig, context, namespace)
        self.core_api = None
        self.apps_api = None
        self.batch_api = None
        self.custom_api = None
        self.rbac_api = None
        self.networking_api = None
        self.executor = ThreadPoolExecutor()
        
    def connect(self) -> bool:
        """
        Establish connection to the Kubernetes cluster using the Python client.
        
        Returns:
            True if connection was successful, False otherwise
        """
        try:
            # Load configuration based on provided parameters
            if self.kubeconfig:
                config.load_kube_config(
                    config_file=self.kubeconfig,
                    context=self.context
                )
            else:
                try:
                    # Try to load in-cluster config
                    config.load_incluster_config()
                except config.ConfigException:
                    # Fallback to default kubeconfig
                    config.load_kube_config(context=self.context)
            
            # Initialize API clients
            self.core_api = client.CoreV1Api()
            self.apps_api = client.AppsV1Api()
            self.batch_api = client.BatchV1Api()
            self.custom_api = client.CustomObjectsApi()
            self.rbac_api = client.RbacAuthorizationV1Api()
            self.networking_api = client.NetworkingV1Api()
            
            # Test connection by getting API versions
            version_response = self._run_in_executor(
                client.VersionApi().get_code
            )
            
            self._connected = True
            self.logger.info(f"Successfully connected to Kubernetes cluster version {version_response.git_version}")
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to Kubernetes cluster: {str(e)}")
            self._connected = False
            return False
    
    def execute_kubectl_command(self, 
                                    command: List[str], 
                                    stdin: Optional[str] = None,
                                    background: bool = False,
                                    file_operation: bool = False) -> Dict[str, Any]:
        """
        Execute a kubectl-like command using the Kubernetes Python client.
        This method translates kubectl commands to equivalent Python client API calls.
        
        Args:
            command: kubectl command and arguments as a list
            stdin: Input to provide to the command (used for apply operations)
            background: Whether to run the command in the background (not used in this implementation)
            file_operation: Whether the command involves file operations
            
        Returns:
            Command execution results in a format similar to kubectl output
            
        Note:
            Not all kubectl commands can be directly translated to API calls.
            Complex operations may require multiple API calls or may not be supported.
        """
        try:
            # Ensure we're connected
            if not self._connected:
                success = self.connect()
                if not success:
                    return {
                        "success": False,
                        "error": "Not connected to Kubernetes cluster",
                        "output": "",
                        "returncode": -1
                    }
            
            # Handle different command types
            if not command:
                return {
                    "success": False,
                    "error": "Empty command",
                    "output": "",
                    "returncode": -1
                }
            
            # Extract the main command and arguments
            main_cmd = command[0].lower()
            
            # Handle the most common commands
            if main_cmd == "get":
                return self._handle_get_command(command)
            elif main_cmd == "describe":
                return self._handle_describe_command(command)
            elif main_cmd == "create" or main_cmd == "apply":
                return self._handle_create_command(command, stdin)
            elif main_cmd == "delete":
                return self._handle_delete_command(command)
            elif main_cmd == "version":
                return self._handle_version_command(command)
            elif main_cmd == "cordon" or main_cmd == "uncordon":
                return self._handle_cordon_command(command, main_cmd == "cordon")
            elif main_cmd == "drain":
                return self._handle_drain_command(command)
            elif main_cmd == "top":
                return self._handle_top_command(command)
            elif main_cmd == "logs":
                return self._handle_logs_command(command)
            elif main_cmd == "exec":
                return self._handle_exec_command(command, stdin)
            elif main_cmd == "label":
                return self._handle_label_command(command)
            elif main_cmd == "annotate":
                return self._handle_annotate_command(command)
            elif main_cmd == "taint":
                return self._handle_taint_command(command)
            elif main_cmd == "cluster-info":
                return self._handle_cluster_info_command(command)
            else:
                # For unsupported commands, fallback to subprocess kubectl if available
                self.logger.warning(f"Command {main_cmd} not directly supported by the Python client. Falling back to subprocess kubectl.")
                return self._fallback_to_kubectl(command, stdin, background, file_operation)
        except Exception as e:
            error_msg = f"Error executing command {' '.join(command)}: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "output": "",
                "returncode": -1
            }
    
    def _run_in_executor(self, func, *args, **kwargs):
        """
        Run a blocking function in an executor to avoid blocking the event loop.
        
        Args:
            func: The function to run
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            The result of the function
        """
        future = self.executor.submit(func, *args, **kwargs)
        return future.result()  # Blocks until done
    
    def _handle_get_command(self, command: List[str]) -> Dict[str, Any]:
        """Handle 'kubectl get' command equivalent."""
        try:
            # Parse command arguments
            args = command[1:]
            if not args:
                return {"success": False, "error": "Resource type required", "output": "", "returncode": 1}
            
            resource_type = args[0].lower()
            resource_name = args[1] if len(args) > 1 and not args[1].startswith("-") else None
            
            # Parse flags
            namespace = self.namespace
            output_format = "json"
            label_selector = None
            field_selector = None
            
            i = 1 if resource_name else 0
            while i < len(args):
                if args[i] == "-n" or args[i] == "--namespace":
                    if i + 1 < len(args):
                        namespace = args[i + 1]
                        i += 2
                    else:
                        return {"success": False, "error": "Namespace argument missing", "output": "", "returncode": 1}
                elif args[i] == "-o" or args[i] == "--output":
                    if i + 1 < len(args):
                        output_format = args[i + 1]
                        i += 2
                    else:
                        return {"success": False, "error": "Output format argument missing", "output": "", "returncode": 1}
                elif args[i] == "-l" or args[i] == "--selector":
                    if i + 1 < len(args):
                        label_selector = args[i + 1]
                        i += 2
                    else:
                        return {"success": False, "error": "Label selector argument missing", "output": "", "returncode": 1}
                elif args[i] == "--field-selector":
                    if i + 1 < len(args):
                        field_selector = args[i + 1]
                        i += 2
                    else:
                        return {"success": False, "error": "Field selector argument missing", "output": "", "returncode": 1}
                elif args[i] == "--all-namespaces" or args[i] == "-A":
                    namespace = None  # All namespaces
                    i += 1
                else:
                    i += 1
            
            # Execute the appropriate API call based on resource type
            result = None
            
            # Handle different resource types
            if resource_type == "pod" or resource_type == "pods":
                if resource_name:
                    result = self._run_in_executor(
                        self.core_api.read_namespaced_pod,
                        resource_name, namespace
                    )
                else:
                    result = self._run_in_executor(
                        self.core_api.list_namespaced_pod if namespace else self.core_api.list_pod_for_all_namespaces,
                        namespace, label_selector=label_selector, field_selector=field_selector
                    )
            elif resource_type == "service" or resource_type == "services" or resource_type == "svc":
                if resource_name:
                    result = self._run_in_executor(
                        self.core_api.read_namespaced_service,
                        resource_name, namespace
                    )
                else:
                    result = self._run_in_executor(
                        self.core_api.list_namespaced_service if namespace else self.core_api.list_service_for_all_namespaces,
                        namespace, label_selector=label_selector, field_selector=field_selector
                    )
            elif resource_type == "deployment" or resource_type == "deployments" or resource_type == "deploy":
                if resource_name:
                    result = self._run_in_executor(
                        self.apps_api.read_namespaced_deployment,
                        resource_name, namespace
                    )
                else:
                    result = self._run_in_executor(
                        self.apps_api.list_namespaced_deployment if namespace else self.apps_api.list_deployment_for_all_namespaces,
                        namespace, label_selector=label_selector, field_selector=field_selector
                    )
            elif resource_type == "node" or resource_type == "nodes":
                if resource_name:
                    result = self._run_in_executor(
                        self.core_api.read_node,
                        resource_name
                    )
                else:
                    result = self._run_in_executor(
                        self.core_api.list_node,
                        label_selector=label_selector, field_selector=field_selector
                    )
            elif resource_type == "namespace" or resource_type == "namespaces" or resource_type == "ns":
                if resource_name:
                    result = self._run_in_executor(
                        self.core_api.read_namespace,
                        resource_name
                    )
                else:
                    result = self._run_in_executor(
                        self.core_api.list_namespace,
                        label_selector=label_selector, field_selector=field_selector
                    )
            elif resource_type == "configmap" or resource_type == "configmaps" or resource_type == "cm":
                if resource_name:
                    result = self._run_in_executor(
                        self.core_api.read_namespaced_config_map,
                        resource_name, namespace
                    )
                else:
                    result = self._run_in_executor(
                        self.core_api.list_namespaced_config_map if namespace else self.core_api.list_config_map_for_all_namespaces,
                        namespace, label_selector=label_selector, field_selector=field_selector
                    )
            elif resource_type == "secret" or resource_type == "secrets":
                if resource_name:
                    result = self._run_in_executor(
                        self.core_api.read_namespaced_secret,
                        resource_name, namespace
                    )
                else:
                    result = self._run_in_executor(
                        self.core_api.list_namespaced_secret if namespace else self.core_api.list_secret_for_all_namespaces,
                        namespace, label_selector=label_selector, field_selector=field_selector
                    )
            elif resource_type == "event" or resource_type == "events" or resource_type == "ev":
                result = self._run_in_executor(
                    self.core_api.list_namespaced_event if namespace else self.core_api.list_event_for_all_namespaces,
                    namespace, field_selector=field_selector
                )
            # Add more resource types as needed
            
            # Format the output
            if not result:
                return {
                    "success": False,
                    "error": f"Unsupported resource type: {resource_type}",
                    "output": "",
                    "returncode": 1
                }
            
            # Convert the result to dict and then to JSON
            if hasattr(result, "to_dict"):
                result_dict = result.to_dict()
            else:
                result_dict = result
            
            output = json.dumps(result_dict)
            
            return {
                "success": True,
                "output": output,
                "error": "",
                "returncode": 0
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    "success": False,
                    "error": f"Error: {resource_type} '{resource_name}' not found",
                    "output": "",
                    "returncode": 1
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {str(e)}",
                    "output": "",
                    "returncode": e.status
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error: {str(e)}",
                "output": "",
                "returncode": 1
            }
    
    def _handle_describe_command(self, command: List[str]) -> Dict[str, Any]:
        """Handle 'kubectl describe' command equivalent."""
        # For describe, we'll get the resource and format it in a describe-like format
        try:
            # First get the resource in detail
            get_command = ["get"] + command[1:] + ["-o", "json"]
            result = self._handle_get_command(get_command)
            
            if not result.get("success", False):
                return result
            
            # Parse the JSON output
            resource_data = json.loads(result["output"])
            
            # Format the output in a describe-like format
            # This is a simplified version; kubectl's describe provides more formatted output
            formatted_output = self._format_describe_output(resource_data)
            
            return {
                "success": True,
                "output": formatted_output,
                "error": "",
                "returncode": 0
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error describing resource: {str(e)}",
                "output": "",
                "returncode": 1
            }
    
    def _format_describe_output(self, resource_data: Dict[str, Any]) -> str:
        """Format resource data as describe output."""
        output = []
        
        # Add name and namespace
        kind = resource_data.get("kind", "Resource")
        name = resource_data.get("metadata", {}).get("name", "unknown")
        output.append(f"{kind}:\t{name}")
        
        namespace = resource_data.get("metadata", {}).get("namespace")
        if namespace:
            output.append(f"Namespace:\t{namespace}")
        
        # Add labels
        labels = resource_data.get("metadata", {}).get("labels", {})
        if labels:
            output.append("Labels:")
            for key, value in labels.items():
                output.append(f"\t{key}={value}")
        
        # Add annotations
        annotations = resource_data.get("metadata", {}).get("annotations", {})
        if annotations:
            output.append("Annotations:")
            for key, value in annotations.items():
                output.append(f"\t{key}={value}")
        
        # Add status
        status = resource_data.get("status", {})
        if status:
            output.append("Status:")
            for key, value in status.items():
                if isinstance(value, dict) or isinstance(value, list):
                    output.append(f"\t{key}: {json.dumps(value, indent=2)}")
                else:
                    output.append(f"\t{key}: {value}")
        
        # Add spec
        spec = resource_data.get("spec", {})
        if spec:
            output.append("Spec:")
            for key, value in spec.items():
                if isinstance(value, dict) or isinstance(value, list):
                    output.append(f"\t{key}: {json.dumps(value, indent=2)}")
                else:
                    output.append(f"\t{key}: {value}")
        
        return "\n".join(output)
    
    def _handle_create_command(self, command: List[str], stdin: Optional[str] = None) -> Dict[str, Any]:
        """Handle 'kubectl create' or 'kubectl apply' command equivalent."""
        try:
            # Parse options
            namespace = self.namespace
            filename = None
            
            i = 1
            while i < len(command):
                if command[i] == "-n" or command[i] == "--namespace":
                    if i + 1 < len(command):
                        namespace = command[i + 1]
                        i += 2
                    else:
                        return {"success": False, "error": "Namespace argument missing", "output": "", "returncode": 1}
                elif command[i] == "-f" or command[i] == "--filename":
                    if i + 1 < len(command):
                        filename = command[i + 1]
                        i += 2
                    else:
                        return {"success": False, "error": "Filename argument missing", "output": "", "returncode": 1}
                else:
                    i += 1
            
            # Get resource definition from stdin or file
            resource_data = None
            if stdin:
                resource_data = json.loads(stdin)
            elif filename:
                # This would need to load the file, but for this implementation we'll assume stdin is used
                return {"success": False, "error": "Loading from file not implemented", "output": "", "returncode": 1}
            else:
                return {"success": False, "error": "No resource definition provided", "output": "", "returncode": 1}
            
            # Create or update the resource based on its kind
            kind = resource_data.get("kind", "").lower()
            api_version = resource_data.get("apiVersion", "")
            metadata = resource_data.get("metadata", {})
            name = metadata.get("name", "")
            
            # Create or update based on resource kind
            # This is a simplified implementation
            if kind == "pod":
                result = self._run_in_executor(
                    self.core_api.create_namespaced_pod,
                    namespace, resource_data
                )
            elif kind == "service":
                result = self._run_in_executor(
                    self.core_api.create_namespaced_service,
                    namespace, resource_data
                )
            elif kind == "deployment":
                result = self._run_in_executor(
                    self.apps_api.create_namespaced_deployment,
                    namespace, resource_data
                )
            # Add more resource types as needed
            else:
                return {
                    "success": False,
                    "error": f"Unsupported resource kind: {kind}",
                    "output": "",
                    "returncode": 1
                }
            
            return {
                "success": True,
                "output": f"{kind} '{name}' created",
                "error": "",
                "returncode": 0
            }
        except ApiException as e:
            return {
                "success": False,
                "error": f"API error: {str(e)}",
                "output": "",
                "returncode": e.status
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating resource: {str(e)}",
                "output": "",
                "returncode": 1
            }
    
    def _handle_delete_command(self, command: List[str]) -> Dict[str, Any]:
        """Handle 'kubectl delete' command equivalent."""
        try:
            # Parse command arguments
            args = command[1:]
            if not args:
                return {"success": False, "error": "Resource type required", "output": "", "returncode": 1}
            
            resource_type = args[0].lower()
            resource_name = args[1] if len(args) > 1 and not args[1].startswith("-") else None
            
            if not resource_name:
                return {"success": False, "error": "Resource name required", "output": "", "returncode": 1}
            
            # Parse flags
            namespace = self.namespace
            
            i = 2
            while i < len(args):
                if args[i] == "-n" or args[i] == "--namespace":
                    if i + 1 < len(args):
                        namespace = args[i + 1]
                        i += 2
                    else:
                        return {"success": False, "error": "Namespace argument missing", "output": "", "returncode": 1}
                else:
                    i += 1
            
            # Execute the appropriate API call based on resource type
            if resource_type == "pod" or resource_type == "pods":
                result = self._run_in_executor(
                    self.core_api.delete_namespaced_pod,
                    resource_name, namespace
                )
            elif resource_type == "service" or resource_type == "services" or resource_type == "svc":
                result = self._run_in_executor(
                    self.core_api.delete_namespaced_service,
                    resource_name, namespace
                )
            elif resource_type == "deployment" or resource_type == "deployments" or resource_type == "deploy":
                result = self._run_in_executor(
                    self.apps_api.delete_namespaced_deployment,
                    resource_name, namespace
                )
            elif resource_type == "namespace" or resource_type == "namespaces" or resource_type == "ns":
                result = self._run_in_executor(
                    self.core_api.delete_namespace,
                    resource_name
                )
            # Add more resource types as needed
            else:
                return {
                    "success": False,
                    "error": f"Unsupported resource type: {resource_type}",
                    "output": "",
                    "returncode": 1
                }
            
            return {
                "success": True,
                "output": f"{resource_type} '{resource_name}' deleted",
                "error": "",
                "returncode": 0
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    "success": False,
                    "error": f"Error: {resource_type} '{resource_name}' not found",
                    "output": "",
                    "returncode": 1
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {str(e)}",
                    "output": "",
                    "returncode": e.status
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error deleting resource: {str(e)}",
                "output": "",
                "returncode": 1
            }
    
    def _handle_version_command(self, command: List[str]) -> Dict[str, Any]:
        """Handle 'kubectl version' command equivalent."""
        try:
            # Get client and server version
            version_api = client.VersionApi()
            client_version = self._run_in_executor(version_api.get_code)
            
            # Format output based on flags
            short_output = "--short" in command or "-s" in command
            output_format = "json"
            for i, arg in enumerate(command):
                if arg in ["-o", "--output"] and i + 1 < len(command):
                    output_format = command[i + 1]
                    break
            
            # Format the output
            if short_output:
                output = f"Client Version: {client_version.git_version}\n"
                output += f"Server Version: {client_version.git_version}"
                return {
                    "success": True,
                    "output": output,
                    "error": "",
                    "returncode": 0
                }
            elif output_format == "json":
                version_info = {
                    "clientVersion": {
                        "gitVersion": client_version.git_version,
                        "platform": "python/kubernetes-client"
                    },
                    "serverVersion": client_version.to_dict()
                }
                return {
                    "success": True,
                    "output": json.dumps(version_info),
                    "error": "",
                    "returncode": 0
                }
            else:
                version_info = f"Client Version: {client_version.git_version}\n"
                version_info += f"Server Version: {client_version.git_version}\n"
                version_info += f"Platform: python/kubernetes-client"
                return {
                    "success": True,
                    "output": version_info,
                    "error": "",
                    "returncode": 0
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting version information: {str(e)}",
                "output": "",
                "returncode": 1
            }
    
    def _handle_cordon_command(self, command: List[str], cordon: bool) -> Dict[str, Any]:
        """Handle 'kubectl cordon' or 'kubectl uncordon' command equivalent."""
        try:
            # Parse command arguments
            if len(command) < 2:
                return {"success": False, "error": "Node name required", "output": "", "returncode": 1}
            
            node_name = command[1]
            
            # Get the current node
            node = self._run_in_executor(
                self.core_api.read_node,
                node_name
            )
            
            # Update the node's unschedulable property
            node.spec.unschedulable = cordon
            
            # Patch the node
            result = self._run_in_executor(
                self.core_api.patch_node,
                node_name, node
            )
            
            action = "cordoned" if cordon else "uncordoned"
            return {
                "success": True,
                "output": f"node/{node_name} {action}",
                "error": "",
                "returncode": 0
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    "success": False,
                    "error": f"Error: node '{node_name}' not found",
                    "output": "",
                    "returncode": 1
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {str(e)}",
                    "output": "",
                    "returncode": e.status
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error {command[0]} node: {str(e)}",
                "output": "",
                "returncode": 1
            }
    
    # Placeholder methods for other commands
    # These would be implemented similarly to the methods above
    
    def _handle_drain_command(self, command: List[str]) -> Dict[str, Any]:
        """Handle 'kubectl drain' command equivalent."""
        # This is a complex command that would require multiple API calls
        # For simplicity, we'll fallback to kubectl
        return self._fallback_to_kubectl(command)
    
    def _handle_top_command(self, command: List[str]) -> Dict[str, Any]:
        """Handle 'kubectl top' command equivalent."""
        # This would require accessing the metrics API
        # For simplicity, we'll fallback to kubectl
        return self._fallback_to_kubectl(command)
    
    def _handle_logs_command(self, command: List[str]) -> Dict[str, Any]:
        """Handle 'kubectl logs' command equivalent."""
        try:
            # Parse command arguments
            if len(command) < 2:
                return {"success": False, "error": "Pod name required", "output": "", "returncode": 1}
            
            pod_name = command[1]
            namespace = self.namespace
            container = None
            follow = False
            tail_lines = None
            
            # Parse options
            i = 2
            while i < len(command):
                if command[i] == "-n" or command[i] == "--namespace":
                    if i + 1 < len(command):
                        namespace = command[i + 1]
                        i += 2
                    else:
                        return {"success": False, "error": "Namespace argument missing", "output": "", "returncode": 1}
                elif command[i] == "-c" or command[i] == "--container":
                    if i + 1 < len(command):
                        container = command[i + 1]
                        i += 2
                    else:
                        return {"success": False, "error": "Container name missing", "output": "", "returncode": 1}
                elif command[i] == "-f" or command[i] == "--follow":
                    follow = True
                    i += 1
                elif command[i] == "--tail":
                    if i + 1 < len(command):
                        try:
                            tail_lines = int(command[i + 1])
                            i += 2
                        except ValueError:
                            return {"success": False, "error": "Invalid tail value", "output": "", "returncode": 1}
                    else:
                        return {"success": False, "error": "Tail value missing", "output": "", "returncode": 1}
                else:
                    i += 1
            
            # Get logs
            logs = self._run_in_executor(
                self.core_api.read_namespaced_pod_log,
                pod_name, namespace, container=container, follow=follow,
                tail_lines=tail_lines
            )
            
            return {
                "success": True,
                "output": logs,
                "error": "",
                "returncode": 0
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    "success": False,
                    "error": f"Error: pod '{pod_name}' not found",
                    "output": "",
                    "returncode": 1
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {str(e)}",
                    "output": "",
                    "returncode": e.status
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting logs: {str(e)}",
                "output": "",
                "returncode": 1
            }
    
    def _handle_exec_command(self, command: List[str], stdin: Optional[str] = None) -> Dict[str, Any]:
        """Handle 'kubectl exec' command equivalent."""
        # The Python client has limited support for exec commands
        # For simplicity, we'll fallback to kubectl
        return self._fallback_to_kubectl(command, stdin)
    
    def _handle_label_command(self, command: List[str]) -> Dict[str, Any]:
        """Handle 'kubectl label' command equivalent."""
        try:
            # Parse command arguments
            if len(command) < 3:
                return {"success": False, "error": "Resource type and name required", "output": "", "returncode": 1}
            
            resource_type = command[1].lower()
            resource_name = command[2]
            
            # Labels should start from index 3
            if len(command) < 4:
                return {"success": False, "error": "No labels specified", "output": "", "returncode": 1}
            
            # Parse namespace
            namespace = self.namespace
            overwrite = False
            
            i = 3
            label_args = []
            while i < len(command):
                if command[i] == "-n" or command[i] == "--namespace":
                    if i + 1 < len(command):
                        namespace = command[i + 1]
                        i += 2
                    else:
                        return {"success": False, "error": "Namespace argument missing", "output": "", "returncode": 1}
                elif command[i] == "--overwrite":
                    overwrite = True
                    i += 1
                else:
                    label_args.append(command[i])
                    i += 1
            
            # Parse label arguments (format: key=value)
            labels = {}
            for label_arg in label_args:
                if "=" not in label_arg:
                    return {"success": False, "error": f"Invalid label format: {label_arg}", "output": "", "returncode": 1}
                
                key, value = label_arg.split("=", 1)
                labels[key] = value
            
            # Update the resource with new labels
            # We need to get the resource first, then patch it
            if resource_type == "pod" or resource_type == "pods":
                resource = self._run_in_executor(
                    self.core_api.read_namespaced_pod,
                    resource_name, namespace
                )
                
                # Update labels
                if not resource.metadata.labels:
                    resource.metadata.labels = {}
                
                for key, value in labels.items():
                    if key in resource.metadata.labels and not overwrite:
                        return {
                            "success": False,
                            "error": f"Label '{key}' already exists on {resource_type}/{resource_name}",
                            "output": "",
                            "returncode": 1
                        }
                    resource.metadata.labels[key] = value
                
                # Patch the resource
                result = self._run_in_executor(
                    self.core_api.patch_namespaced_pod,
                    resource_name, namespace, resource
                )
            elif resource_type == "node" or resource_type == "nodes":
                resource = self._run_in_executor(
                    self.core_api.read_node,
                    resource_name
                )
                
                # Update labels
                if not resource.metadata.labels:
                    resource.metadata.labels = {}
                
                for key, value in labels.items():
                    if key in resource.metadata.labels and not overwrite:
                        return {
                            "success": False,
                            "error": f"Label '{key}' already exists on {resource_type}/{resource_name}",
                            "output": "",
                            "returncode": 1
                        }
                    resource.metadata.labels[key] = value
                
                # Patch the resource
                result = self._run_in_executor(
                    self.core_api.patch_node,
                    resource_name, resource
                )
            # Add more resource types as needed
            else:
                return {
                    "success": False,
                    "error": f"Unsupported resource type: {resource_type}",
                    "output": "",
                    "returncode": 1
                }
            
            return {
                "success": True,
                "output": f"{resource_type}/{resource_name} labeled",
                "error": "",
                "returncode": 0
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    "success": False,
                    "error": f"Error: {resource_type} '{resource_name}' not found",
                    "output": "",
                    "returncode": 1
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {str(e)}",
                    "output": "",
                    "returncode": e.status
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error labeling resource: {str(e)}",
                "output": "",
                "returncode": 1
            }
    
    def _handle_annotate_command(self, command: List[str]) -> Dict[str, Any]:
        """Handle 'kubectl annotate' command equivalent."""
        # Similar to label command but for annotations
        # For simplicity, we'll implement a basic version similar to _handle_label_command
        # with annotations instead of labels
        try:
            # Parse command arguments
            if len(command) < 3:
                return {"success": False, "error": "Resource type and name required", "output": "", "returncode": 1}
            
            resource_type = command[1].lower()
            resource_name = command[2]
            
            # Annotations should start from index 3
            if len(command) < 4:
                return {"success": False, "error": "No annotations specified", "output": "", "returncode": 1}
            
            # Parse namespace
            namespace = self.namespace
            overwrite = False
            
            i = 3
            annotation_args = []
            while i < len(command):
                if command[i] == "-n" or command[i] == "--namespace":
                    if i + 1 < len(command):
                        namespace = command[i + 1]
                        i += 2
                    else:
                        return {"success": False, "error": "Namespace argument missing", "output": "", "returncode": 1}
                elif command[i] == "--overwrite":
                    overwrite = True
                    i += 1
                else:
                    annotation_args.append(command[i])
                    i += 1
            
            # Parse annotation arguments (format: key=value)
            annotations = {}
            for annotation_arg in annotation_args:
                if "=" not in annotation_arg:
                    if annotation_arg.endswith("-"):
                        # Handle removal of annotations
                        key = annotation_arg[:-1]
                        annotations[key] = None
                    else:
                        return {"success": False, "error": f"Invalid annotation format: {annotation_arg}", "output": "", "returncode": 1}
                else:
                    key, value = annotation_arg.split("=", 1)
                    annotations[key] = value
            
            # Update the resource with new annotations
            # We need to get the resource first, then patch it
            if resource_type == "pod" or resource_type == "pods":
                resource = self._run_in_executor(
                    self.core_api.read_namespaced_pod,
                    resource_name, namespace
                )
                
                # Update annotations
                if not resource.metadata.annotations:
                    resource.metadata.annotations = {}
                
                for key, value in annotations.items():
                    if value is None:
                        # Remove annotation
                        if key in resource.metadata.annotations:
                            del resource.metadata.annotations[key]
                    else:
                        # Add or update annotation
                        if key in resource.metadata.annotations and not overwrite:
                            return {
                                "success": False,
                                "error": f"Annotation '{key}' already exists on {resource_type}/{resource_name}",
                                "output": "",
                                "returncode": 1
                            }
                        resource.metadata.annotations[key] = value
                
                # Patch the resource
                result = self._run_in_executor(
                    self.core_api.patch_namespaced_pod,
                    resource_name, namespace, resource
                )
            # Add more resource types as needed
            else:
                return {
                    "success": False,
                    "error": f"Unsupported resource type: {resource_type}",
                    "output": "",
                    "returncode": 1
                }
            
            return {
                "success": True,
                "output": f"{resource_type}/{resource_name} annotated",
                "error": "",
                "returncode": 0
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    "success": False,
                    "error": f"Error: {resource_type} '{resource_name}' not found",
                    "output": "",
                    "returncode": 1
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {str(e)}",
                    "output": "",
                    "returncode": e.status
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error annotating resource: {str(e)}",
                "output": "",
                "returncode": 1
            }
    
    def _handle_taint_command(self, command: List[str]) -> Dict[str, Any]:
        """Handle 'kubectl taint' command equivalent."""
        try:
            # Parse command arguments
            if len(command) < 3:
                return {"success": False, "error": "Node name required", "output": "", "returncode": 1}
            
            node_name = command[1]
            
            # Taints should start from index 2
            if len(command) < 3:
                return {"success": False, "error": "No taints specified", "output": "", "returncode": 1}
            
            overwrite = False
            
            i = 2
            taint_args = []
            while i < len(command):
                if command[i] == "--overwrite":
                    overwrite = True
                    i += 1
                else:
                    taint_args.append(command[i])
                    i += 1
            
            # Parse taint arguments (format: key=value:effect or key:effect)
            new_taints = []
            remove_taints = []
            
            for taint_arg in taint_args:
                if taint_arg.endswith("-"):
                    # Handle removal of taints
                    taint_spec = taint_arg[:-1]
                    if ":" not in taint_spec:
                        return {"success": False, "error": f"Invalid taint format: {taint_arg}", "output": "", "returncode": 1}
                    
                    key_part, effect = taint_spec.split(":", 1)
                    if "=" in key_part:
                        key, value = key_part.split("=", 1)
                    else:
                        key, value = key_part, ""
                    
                    remove_taints.append((key, value, effect))
                else:
                    # Add taint
                    if ":" not in taint_arg:
                        return {"success": False, "error": f"Invalid taint format: {taint_arg}", "output": "", "returncode": 1}
                    
                    key_part, effect = taint_arg.split(":", 1)
                    if "=" in key_part:
                        key, value = key_part.split("=", 1)
                    else:
                        key, value = key_part, ""
                    
                    new_taints.append({"key": key, "value": value, "effect": effect})
            
            # Get the current node
            node = self._run_in_executor(
                self.core_api.read_node,
                node_name
            )
            
            # Update taints
            current_taints = node.spec.taints or []
            
            # Remove specified taints
            if remove_taints:
                node.spec.taints = [
                    taint for taint in current_taints
                    if not any(
                        taint.key == rt[0] and (rt[1] == "" or taint.value == rt[1]) and taint.effect == rt[2]
                        for rt in remove_taints
                    )
                ]
            
            # Add new taints
            if new_taints:
                if not node.spec.taints:
                    node.spec.taints = []
                
                for new_taint in new_taints:
                    # Check if taint already exists
                    exists = False
                    for i, taint in enumerate(node.spec.taints):
                        if taint.key == new_taint["key"] and taint.effect == new_taint["effect"]:
                            exists = True
                            if overwrite:
                                # Update existing taint
                                node.spec.taints[i].value = new_taint["value"]
                            else:
                                return {
                                    "success": False,
                                    "error": f"Taint '{new_taint['key']}' already exists with effect '{new_taint['effect']}'",
                                    "output": "",
                                    "returncode": 1
                                }
                            break
                    
                    if not exists:
                        # Add new taint
                        node.spec.taints.append(client.V1Taint(
                            key=new_taint["key"],
                            value=new_taint["value"],
                            effect=new_taint["effect"]
                        ))
            
            # Patch the node
            result = self._run_in_executor(
                self.core_api.patch_node,
                node_name, node
            )
            
            return {
                "success": True,
                "output": f"node/{node_name} tainted",
                "error": "",
                "returncode": 0
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    "success": False,
                    "error": f"Error: node '{node_name}' not found",
                    "output": "",
                    "returncode": 1
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {str(e)}",
                    "output": "",
                    "returncode": e.status
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error tainting node: {str(e)}",
                "output": "",
                "returncode": 1
            }
    
    def _handle_cluster_info_command(self, command: List[str]) -> Dict[str, Any]:
        """Handle 'kubectl cluster-info' command equivalent."""
        try:
            # Get version information
            version_api = client.VersionApi()
            version_info = self._run_in_executor(version_api.get_code)
            
            # Format output
            output = "Kubernetes control plane is running at [API_SERVER_URL]\n"
            output += f"Kubernetes version: {version_info.git_version}\n"
            
            return {
                "success": True,
                "output": output,
                "error": "",
                "returncode": 0
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting cluster info: {str(e)}",
                "output": "",
                "returncode": 1
            }
    
    def _fallback_to_kubectl(self, 
                                  command: List[str], 
                                  stdin: Optional[str] = None,
                                  background: bool = False,
                                  file_operation: bool = False) -> Dict[str, Any]:
        """
        Fallback to using kubectl command line if the Python client doesn't support a command.
        This requires kubectl to be installed on the system.
        """
        self.logger.warning(f"Falling back to kubectl for command: {' '.join(command)}")
        
        # Create a temporary file for kubeconfig if needed
        if self.kubeconfig and isinstance(self.kubeconfig, dict):
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_kubeconfig:
                json.dump(self.kubeconfig, temp_kubeconfig)
                temp_kubeconfig_path = temp_kubeconfig.name
        else:
            temp_kubeconfig_path = self.kubeconfig
        
        try:
            # Prepare kubectl command
            base_command = ["kubectl"]
            
            if temp_kubeconfig_path:
                base_command.extend(["--kubeconfig", temp_kubeconfig_path])
            
            if self.context:
                base_command.extend(["--context", self.context])
            
            # Execute kubectl command
            full_command = base_command + command
            

            process = subprocess.Popen(
                full_command,
                stdin=subprocess.PIPE if stdin else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
                
            if stdin:
                stdout, stderr = process.stdin.write(stdin.encode())
                process.stdin.close()
            else:
                stdout, stderr = process.communicate()
        
            stdout = stdout.decode("utf-8", errors="replace")
            stderr = stderr.decode("utf-8", errors="replace")
            
            success = process.returncode == 0
            
            return {
                "success": success,
                "output": stdout,
                "error": stderr,
                "returncode": process.returncode
            }
        except Exception as e:
            error_msg = f"Error executing kubectl command: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "output": "",
                "returncode": -1
            }
        finally:
            # Clean up temporary kubeconfig file if created
            if self.kubeconfig and isinstance(self.kubeconfig, dict) and temp_kubeconfig_path:
                import os
                try:
                    os.unlink(temp_kubeconfig_path)
                except Exception as e:
                    self.logger.warning(f"Failed to remove temporary kubeconfig file: {str(e)}")