import json
import re
from typing import Any, Dict, List, Optional
from utils.exceptions import KubeAgentError, ResourceNotFoundError, ValidationError
from utils.cluster_connector import k8s_cluster_connector
from monitoring.agent_logger import get_logger

connector = k8s_cluster_connector
logger = get_logger(__name__)

class PodTools:
    """Tools for working with Kubernetes Pods"""
    
    @staticmethod
    def get_pod(name: str, 
                     namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve detailed information about a specific Pod.
        
        Args:
            name: Name of the Pod to retrieve
            namespace: Namespace where the Pod is located (default: connector's default namespace)
            
        Returns:
            Dict containing the Pod information
            
        Raises:
            ResourceNotFoundError: If the Pod doesn't exist
            KubeAgentError: If an error occurs during retrieval
        """
        # Set default namespace if not provided
        if namespace is None:
            namespace = connector.namespace
        
        try:
            # Validate inputs
            PodTools._validate_name(name, "pod")
            PodTools._validate_name(namespace, "namespace")
            
            result = connector.execute_kubectl_command(
                ["get", "pod", name, "-n", namespace, "-o", "json"]
            )
            
            if not result.get("success", False):
                if "not found" in result.get("error", "").lower():
                    raise ResourceNotFoundError(f"Pod '{name}' not found in namespace '{namespace}'")
                raise KubeAgentError(f"Failed to get Pod '{name}': {result.get('error', 'Unknown error')}")
            
            return json.loads(result.get("output", "{}"))
        except json.JSONDecodeError:
            raise KubeAgentError(f"Failed to parse Pod information for '{name}'")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving Pod '{name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error retrieving Pod: {str(e)}")
    
    @staticmethod
    def list_pods(namespace: Optional[str] = None,
                       label_selector: Optional[str] = None,
                       field_selector: Optional[str] = None,
                       show_all: bool = False) -> List[Dict[str, Any]]:
        """
        List all Pods in the specified namespace, optionally filtered by labels or fields.
        
        Args:
            namespace: Namespace to list Pods from (default: connector's default namespace)
            label_selector: Label selector to filter Pods (e.g. "app=nginx")
            field_selector: Field selector to filter Pods (e.g. "status.phase=Running")
            show_all: Whether to show terminated Pods (default: False)
            
        Returns:
            List of dictionaries containing Pod information
            
        Raises:
            KubeAgentError: If an error occurs during the operation
        """
        # Set default namespace if not provided
        if namespace is None:
            namespace = connector.namespace
        
        try:
            # Validate namespace
            PodTools._validate_name(namespace, "namespace")
            
            # Validate label selector if provided
            if label_selector:
                PodTools._validate_label_selector(label_selector)
            
            # Build command
            command = ["get", "pods", "-n", namespace, "-o", "json"]
            
            if label_selector:
                command.extend(["-l", label_selector])
            
            if field_selector:
                command.extend(["--field-selector", field_selector])
            
            if show_all:
                command.append("--show-all")
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to list Pods: {result.get('error', 'Unknown error')}")
            
            pods_json = json.loads(result.get("output", "{}"))
            return pods_json.get("items", [])
        except json.JSONDecodeError:
            raise KubeAgentError("Failed to parse Pod list")
        except Exception as e:
            logger.error(f"Error listing Pods in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error listing Pods: {str(e)}")
    
    @staticmethod
    def exec_command(name: str, 
                          command: List[str],
                          namespace: Optional[str] = None,
                          container: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a command in a Pod container.
        
        Args:
            name: Name of the Pod to execute the command in
            command: List of command and arguments to execute
            namespace: Namespace where the Pod is located (default: connector's default namespace)
            container: Name of the container to execute the command in (default: first container)
            
        Returns:
            Dictionary containing the command output, exit code, and error (if any)
            
        Raises:
            ValidationError: If the Pod name, namespace, or command is invalid
            ResourceNotFoundError: If the Pod doesn't exist
            KubeAgentError: If command execution fails
        """
        # Set default namespace if not provided
        if namespace is None:
            namespace = connector.namespace
        
        try:
            # Validate inputs
            PodTools._validate_name(name, "pod")
            PodTools._validate_name(namespace, "namespace")
            
            if not command or not isinstance(command, list):
                raise ValidationError("Command must be a non-empty list")
            
            for arg in command:
                if not isinstance(arg, str):
                    raise ValidationError("All command arguments must be strings")
            
            if container:
                if not isinstance(container, str) or not container:
                    raise ValidationError("Container name must be a non-empty string")
            
            # Build the kubectl command
            kubectl_command = ["exec", name, "-n", namespace]
            
            if container:
                kubectl_command.extend(["-c", container])
            
            kubectl_command.extend(["--", *command])
            
            # First check if the Pod exists and is in Running state
            pod_info_result = connector.execute_kubectl_command(
                ["get", "pod", name, "-n", namespace, "-o", "json"]
            )
            
            if not pod_info_result.get("success", False):
                if "not found" in pod_info_result.get("error", "").lower():
                    raise ResourceNotFoundError(f"Pod '{name}' not found in namespace '{namespace}'")
                raise KubeAgentError(f"Failed to get Pod '{name}' information: {pod_info_result.get('error', 'Unknown error')}")
            
            pod_info = json.loads(pod_info_result.get("output", "{}"))
            pod_phase = pod_info.get("status", {}).get("phase", "")
            
            if pod_phase != "Running":
                raise KubeAgentError(f"Cannot execute command in Pod '{name}': Pod is in '{pod_phase}' state, not 'Running'")
            
            # Execute the command
            result = connector.execute_kubectl_command(kubectl_command)
            
            command_output = {
                "podName": name,
                "namespace": namespace,
                "containerName": container or pod_info.get("spec", {}).get("containers", [{}])[0].get("name", ""),
                "command": command,
                "output": result.get("output", ""),
                "error": result.get("error", ""),
                "success": result.get("success", False),
                "exitCode": 0 if result.get("success", False) else 1
            }
            
            return command_output
        except json.JSONDecodeError:
            raise KubeAgentError(f"Failed to parse Pod information for '{name}'")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error executing command in Pod '{name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error executing command in Pod: {str(e)}")
    
    # Helper methods
    @staticmethod
    def _validate_name(name: str, resource_type: str) -> None:
        """Validate a Kubernetes resource name"""
        if not name or not isinstance(name, str):
            raise ValidationError(f"{resource_type.capitalize()} name must be a non-empty string")
        
        # Less strict validation for real-world names which might not follow ideal patterns
        if not re.match(r'^[a-zA-Z0-9][-a-zA-Z0-9_.]*[a-zA-Z0-9]$', name) and name != "-":
            logger.warning(f"Resource name '{name}' may not conform to Kubernetes naming conventions")
    
    @staticmethod
    def _validate_label_selector(label_selector: str) -> None:
        """Validate a label selector"""
        if not re.match(r'^[a-zA-Z0-9-_./]+(=[a-zA-Z0-9-_./]+)?$', label_selector):
            raise ValidationError(f"Invalid label selector format: '{label_selector}'")