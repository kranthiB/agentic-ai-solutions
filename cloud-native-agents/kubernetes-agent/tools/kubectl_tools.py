import json
import re
from typing import Any, Dict, List, Optional, Union

import yaml
from utils.exceptions import KubeAgentError, ResourceNotFoundError, ValidationError
from utils.cluster_connector import k8s_cluster_connector
from monitoring.agent_logger import get_logger

connector = k8s_cluster_connector
logger = get_logger(__name__)

class KubectlTools:
    """Unified interface for kubectl operations"""
    
    @staticmethod
    def get(resource_type: str, 
                 name: Optional[str] = None,
                 namespace: Optional[str] = None,
                 label_selector: Optional[str] = None,
                 field_selector: Optional[str] = None,
                 all_namespaces: bool = False) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Get Kubernetes resources using kubectl get.
        
        Args:
            resource_type: Type of resource to get
            name: Name of a specific resource to get
            namespace: Namespace for namespaced resources
            label_selector: Label selector for filtering resources
            field_selector: Field selector for filtering resources
            all_namespaces: Whether to get resources across all namespaces
            
        Returns:
            Resource information as dictionary or list of dictionaries
            
        Raises:
            ValidationError: If parameters are invalid
            ResourceNotFoundError: If the resource doesn't exist
            KubeAgentError: If the operation fails
        """
        try:
            # Set default namespace if not provided and not all_namespaces
            if namespace is None and not all_namespaces:
                namespace = connector.namespace
            
            # Validate inputs
            if name:
                KubectlTools._validate_name(name, resource_type)
            if namespace:
                KubectlTools._validate_name(namespace, "namespace")
            if label_selector:
                KubectlTools._validate_label_selector(label_selector)
            
            # Build command
            command = ["get", resource_type]
            
            if name:
                command.append(name)
            
            if all_namespaces:
                command.append("--all-namespaces")
            elif namespace:
                command.extend(["-n", namespace])
            
            if label_selector:
                command.extend(["-l", label_selector])
            
            if field_selector:
                command.extend(["--field-selector", field_selector])
            
            command.extend(["-o", "json"])
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                if "not found" in error_msg.lower() and name:
                    raise ResourceNotFoundError(f"{resource_type.capitalize()} '{name}' not found")
                raise KubeAgentError(f"Failed to get {resource_type}: {error_msg}")
            
            data = json.loads(result.get("output", "{}"))
            
            # Return a list for multiple items, or a single item for a named resource
            if name:
                return data
            else:
                return data.get("items", [])
        except json.JSONDecodeError:
            raise KubeAgentError(f"Failed to parse {resource_type} information")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            scope = f"in namespace '{namespace}'" if namespace else "across all namespaces" if all_namespaces else "(cluster-scoped)"
            resource_desc = f"{resource_type} '{name}'" if name else f"all {resource_type}"
            logger.error(f"Error getting {resource_desc} {scope}: {str(e)}")
            raise KubeAgentError(f"Error getting {resource_desc}: {str(e)}")
    
    @staticmethod
    def describe(resource_type: str,
                      name: str,
                      namespace: Optional[str] = None) -> str:
        """
        Describe a Kubernetes resource using kubectl describe.
        
        Args:
            resource_type: Type of resource to describe
            name: Name of the resource to describe
            namespace: Namespace for namespaced resources
            
        Returns:
            Detailed description of the resource as a string
            
        Raises:
            ValidationError: If parameters are invalid
            ResourceNotFoundError: If the resource doesn't exist
            KubeAgentError: If the operation fails
        """
        try:
            # Set default namespace if not provided
            if namespace is None:
                namespace = connector.namespace
            
            # Validate inputs
            KubectlTools._validate_name(name, resource_type)
            if namespace:
                KubectlTools._validate_name(namespace, "namespace")
            
            # Build command
            command = ["describe", resource_type, name]
            
            if namespace:
                command.extend(["-n", namespace])
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                if "not found" in error_msg.lower():
                    raise ResourceNotFoundError(f"{resource_type.capitalize()} '{name}' not found")
                raise KubeAgentError(f"Failed to describe {resource_type} '{name}': {error_msg}")
            
            return result.get("output", "")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            scope = f"in namespace '{namespace}'" if namespace else "(cluster-scoped)"
            logger.error(f"Error describing {resource_type} '{name}' {scope}: {str(e)}")
            raise KubeAgentError(f"Error describing {resource_type} '{name}': {str(e)}")
    
    @staticmethod
    def create(yaml_content: str,
                    namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a Kubernetes resource from YAML.
        
        Args:
            yaml_content: YAML definition of the resource
            namespace: Namespace override for the resource
            
        Returns:
            Information about the created resource
            
        Raises:
            ValidationError: If parameters are invalid
            KubeAgentError: If the operation fails
        """
        try:
            # Set default namespace if not provided
            if namespace is None:
                namespace = connector.namespace
            
            # Validate namespace if provided
            if namespace:
                KubectlTools._validate_name(namespace, "namespace")
            
            # Parse YAML to extract resource type and name
            resource_data = yaml.safe_load(yaml_content)
            
            if not resource_data:
                raise ValidationError("YAML content is empty or invalid")
            
            resource_kind = resource_data.get("kind")
            if not resource_kind:
                raise ValidationError("YAML missing required 'kind' field")
            
            resource_name = resource_data.get("metadata", {}).get("name")
            if not resource_name:
                raise ValidationError("YAML missing required 'metadata.name' field")
            
            # Set namespace in the resource if it's provided
            if namespace:
                resource_data["metadata"]["namespace"] = namespace
            else:
                # Get namespace from the resource or use default
                namespace = resource_data.get("metadata", {}).get("namespace", connector.namespace)
            
            # Convert resource kind to API resource type
            resource_type = KubectlTools._kind_to_resource_type(resource_kind)
            
            # Convert back to YAML
            updated_yaml = yaml.dump(resource_data)
            
            # Create the resource
            result = connector.execute_kubectl_command(
                ["apply", "-f", "-"],
                stdin=updated_yaml
            )
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to create resource: {result.get('error', 'Unknown error')}")
            
            # Get the created resource
            return KubectlTools.get(resource_type, resource_name, namespace)
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML content: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating resource from YAML: {str(e)}")
            raise KubeAgentError(f"Error creating resource: {str(e)}")
    
    @staticmethod
    def delete(resource_type: str,
                    name: str,
                    namespace: Optional[str] = None,
                    force: bool = False,
                    grace_period: Optional[int] = None) -> bool:
        """
        Delete a Kubernetes resource.
        
        Args:
            resource_type: Type of resource to delete
            name: Name of the resource to delete
            namespace: Namespace for namespaced resources
            force: Whether to force deletion
            grace_period: Grace period in seconds before deletion
            
        Returns:
            True if deletion was successful
            
        Raises:
            ValidationError: If parameters are invalid
            KubeAgentError: If the operation fails
        """
        try:
            # Set default namespace if not provided
            if namespace is None:
                namespace = connector.namespace
            
            # Validate inputs
            KubectlTools._validate_name(name, resource_type)
            if namespace:
                KubectlTools._validate_name(namespace, "namespace")
            
            if grace_period is not None and (not isinstance(grace_period, int) or grace_period < 0):
                raise ValidationError("Grace period must be a non-negative integer")
            
            # Build command
            command = ["delete", resource_type, name]
            
            if namespace:
                command.extend(["-n", namespace])
            
            if force:
                command.append("--force")
            
            if grace_period is not None:
                command.extend(["--grace-period", str(grace_period)])
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                if "not found" in error_msg.lower():
                    # If the resource doesn't exist, consider it a successful deletion
                    return True
                raise KubeAgentError(f"Failed to delete {resource_type} '{name}': {error_msg}")
            
            return True
        except Exception as e:
            scope = f"in namespace '{namespace}'" if namespace else "(cluster-scoped)"
            logger.error(f"Error deleting {resource_type} '{name}' {scope}: {str(e)}")
            raise KubeAgentError(f"Error deleting {resource_type} '{name}': {str(e)}")
    
    @staticmethod
    def apply(yaml_content: str,
                   namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Apply a Kubernetes resource configuration (create or update).
        This is an alias for the create method since both use kubectl apply.
        
        Args:
            yaml_content: YAML definition of the resource
            namespace: Namespace override for the resource
            
        Returns:
            Information about the applied resource
        """
        return KubectlTools.create(yaml_content, namespace)
    
    @staticmethod
    def patch(resource_type: str,
                   name: str,
                   patch_data: Dict[str, Any],
                   namespace: Optional[str] = None,
                   patch_type: str = "strategic") -> Dict[str, Any]:
        """
        Patch a Kubernetes resource.
        
        Args:
            resource_type: Type of resource to patch
            name: Name of the resource to patch
            patch_data: Dictionary containing the patch data
            namespace: Namespace for namespaced resources
            patch_type: Type of patch (strategic, merge, or json)
            
        Returns:
            Information about the patched resource
            
        Raises:
            ValidationError: If parameters are invalid
            ResourceNotFoundError: If the resource doesn't exist
            KubeAgentError: If the operation fails
        """
        try:
            # Set default namespace if not provided
            if namespace is None:
                namespace = connector.namespace
            
            # Validate inputs
            KubectlTools._validate_name(name, resource_type)
            if namespace:
                KubectlTools._validate_name(namespace, "namespace")
            
            if not isinstance(patch_data, dict):
                raise ValidationError("Patch data must be a dictionary")
            
            valid_patch_types = ["strategic", "merge", "json"]
            if patch_type not in valid_patch_types:
                raise ValidationError(f"Patch type must be one of: {', '.join(valid_patch_types)}")
            
            # Convert to kubectl patch type
            kubectl_patch_type = patch_type
            
            # Convert patch data to JSON
            patch_json = json.dumps(patch_data)
            
            # Build command
            command = ["patch", resource_type, name, f"--type={kubectl_patch_type}", "-p", patch_json]
            
            if namespace:
                command.extend(["-n", namespace])
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                if "not found" in error_msg.lower():
                    raise ResourceNotFoundError(f"{resource_type.capitalize()} '{name}' not found")
                raise KubeAgentError(f"Failed to patch {resource_type} '{name}': {error_msg}")
            
            # Get the updated resource
            return KubectlTools.get(resource_type, name, namespace)
        except ResourceNotFoundError:
            raise
        except Exception as e:
            scope = f"in namespace '{namespace}'" if namespace else "(cluster-scoped)"
            logger.error(f"Error patching {resource_type} '{name}' {scope}: {str(e)}")
            raise KubeAgentError(f"Error patching {resource_type} '{name}': {str(e)}")
    
    @staticmethod
    def logs(pod_name: str,
                  namespace: Optional[str] = None,
                  container: Optional[str] = None,
                  previous: bool = False,
                  since: Optional[str] = None,
                  timestamps: bool = False,
                  tail_lines: Optional[int] = None,
                  follow: bool = False) -> Dict[str, Any]:
        """
        Get logs from a pod.
        
        Args:
            pod_name: Name of the pod to get logs from
            namespace: Namespace where the pod is located
            container: Container to get logs from
            previous: Whether to get logs from previous container instance
            since: Only return logs newer than a relative duration
            timestamps: Include timestamps on each line
            tail_lines: Lines of recent log file to display
            follow: Specify if the logs should be streamed
            
        Returns:
            Dictionary containing log content and metadata
            
        Raises:
            ValidationError: If parameters are invalid
            ResourceNotFoundError: If the pod doesn't exist
            KubeAgentError: If the operation fails
        """
        try:
            # Set default namespace if not provided
            if namespace is None:
                namespace = connector.namespace
            
            # Validate inputs
            KubectlTools._validate_name(pod_name, "pod")
            KubectlTools._validate_name(namespace, "namespace")
            
            if container:
                if not isinstance(container, str) or not container:
                    raise ValidationError("Container name must be a non-empty string")
            
            if since:
                if not isinstance(since, str) or not re.match(r'^[0-9]+(s|m|h|d)$', since):
                    raise ValidationError("Since time must be in format like 5s, 2m, 3h, or 1d")
            
            if tail_lines is not None:
                if not isinstance(tail_lines, int) or tail_lines <= 0:
                    raise ValidationError("Tail lines must be a positive integer")
            
            # Build command
            command = ["logs", pod_name, "-n", namespace]
            
            if container:
                command.extend(["-c", container])
            
            if previous:
                command.append("--previous")
            
            if since:
                command.extend(["--since", since])
            
            if timestamps:
                command.append("--timestamps")
            
            if tail_lines is not None:
                command.extend(["--tail", str(tail_lines)])
            
            if follow:
                command.append("--follow")
            
            # First check if the pod exists
            try:
                pod_info = KubectlTools.get("pod", pod_name, namespace)
            except ResourceNotFoundError:
                raise
            
            # Get the logs
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to get logs for pod '{pod_name}': {result.get('error', 'Unknown error')}")
            
            # Extract container names for context
            containers = pod_info.get("spec", {}).get("containers", [])
            init_containers = pod_info.get("spec", {}).get("initContainers", [])
            ephemeral_containers = pod_info.get("spec", {}).get("ephemeralContainers", [])
            
            container_names = [c.get("name") for c in containers]
            init_container_names = [c.get("name") for c in init_containers]
            ephemeral_container_names = [c.get("name") for c in ephemeral_containers]
            
            # Determine which container's logs were retrieved
            container_name = container
            if not container_name and container_names:
                container_name = container_names[0]
            
            log_content = result.get("output", "")
            
            logs_data = {
                "podName": pod_name,
                "namespace": namespace,
                "containerName": container_name,
                "isPreviousLogs": previous,
                "logs": log_content,
                "podInfo": {
                    "status": pod_info.get("status", {}).get("phase", "Unknown"),
                    "containers": container_names,
                    "initContainers": init_container_names,
                    "ephemeralContainers": ephemeral_container_names,
                    "podIP": pod_info.get("status", {}).get("podIP")
                },
                "logSize": len(log_content),
                "lineCount": len(log_content.splitlines()) if log_content else 0
            }
            
            return logs_data
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting logs for pod '{pod_name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error getting pod logs: {str(e)}")
    
    # Additional kubectl operations would follow the same pattern...
    
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
    
    @staticmethod
    def _kind_to_resource_type(kind: str) -> str:
        """Convert a resource kind to its API resource type"""
        # Handle common conversions
        if kind == "Deployment":
            return "deployments"
        elif kind == "Service":
            return "services"
        elif kind == "Pod":
            return "pods"
        elif kind == "ConfigMap":
            return "configmaps"
        elif kind == "Secret":
            return "secrets"
        elif kind == "Namespace":
            return "namespaces"
        elif kind == "Node":
            return "nodes"
        elif kind == "Ingress":
            return "ingresses"
        
        # Default pluralization
        if kind.endswith("y"):
            return kind[:-1].lower() + "ies"
        elif kind.endswith("s"):
            return kind.lower()
        else:
            return kind.lower() + "s"