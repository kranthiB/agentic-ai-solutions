
import json
import re
from typing import Any, Dict, List, Optional
from utils.exceptions import KubeAgentError, ResourceNotFoundError, ValidationError
from utils.cluster_connector import k8s_cluster_connector
from monitoring.agent_logger import get_logger

connector = k8s_cluster_connector
logger = get_logger(__name__)

class ConfigTools:
    """Tools for working with ConfigMaps and Secrets"""
    
    @staticmethod
    def get_configmap(name: str, 
                           namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve information about a specific ConfigMap.
        
        Args:
            name: Name of the ConfigMap to retrieve
            namespace: Namespace where the ConfigMap is located (default: connector's default namespace)
            
        Returns:
            Dict containing the ConfigMap information
            
        Raises:
            ResourceNotFoundError: If the ConfigMap doesn't exist
            KubeAgentError: If an error occurs during retrieval
        """
        namespace = namespace or connector.namespace
        
        try:
            ConfigTools._validate_name(name, "configmap")
            ConfigTools._validate_name(namespace, "namespace")
            
            result = connector.execute_kubectl_command(
                ["get", "configmap", name, "-n", namespace, "-o", "json"]
            )
            
            if not result.get("success", False):
                if "not found" in result.get("error", "").lower():
                    raise ResourceNotFoundError(f"ConfigMap '{name}' not found in namespace '{namespace}'")
                raise KubeAgentError(f"Failed to get ConfigMap '{name}': {result.get('error', 'Unknown error')}")
            
            return json.loads(result.get("output", "{}"))
        except json.JSONDecodeError:
            raise KubeAgentError(f"Failed to parse ConfigMap information for '{name}'")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving ConfigMap '{name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error retrieving ConfigMap: {str(e)}")
    
    @staticmethod
    def list_configmaps(namespace: Optional[str] = None, 
                             label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all ConfigMaps in the specified namespace, optionally filtered by labels.
        
        Args:
            namespace: Namespace to list ConfigMaps from (default: connector's default namespace)
            label_selector: Label selector to filter ConfigMaps (e.g. "app=nginx")
            
        Returns:
            List of dictionaries containing ConfigMap information
            
        Raises:
            KubeAgentError: If an error occurs during the operation
        """
        namespace = namespace or connector.namespace
        
        try:
            ConfigTools._validate_name(namespace, "namespace")
            
            # Validate label selector if provided
            if label_selector:
                ConfigTools._validate_label_selector(label_selector)
            
            # Build command
            command = ["get", "configmaps", "-n", namespace, "-o", "json"]
            if label_selector:
                command.extend(["-l", label_selector])
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to list ConfigMaps: {result.get('error', 'Unknown error')}")
            
            configmaps_json = json.loads(result.get("output", "{}"))
            return configmaps_json.get("items", [])
        except Exception as e:
            logger.error(f"Error listing ConfigMaps in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error listing ConfigMaps: {str(e)}")
    
    @staticmethod
    def create_configmap(name: str, 
                              data: Dict[str, str], 
                              namespace: Optional[str] = None,
                              labels: Optional[Dict[str, str]] = None,
                              annotations: Optional[Dict[str, str]] = None,
                              from_file: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Create a new ConfigMap.
        
        Args:
            name: Name of the ConfigMap to create
            data: Dictionary containing key-value pairs for the ConfigMap
            namespace: Namespace where the ConfigMap will be created (default: connector's default namespace)
            labels: Labels to apply to the ConfigMap
            annotations: Annotations to apply to the ConfigMap
            from_file: Dictionary mapping keys to file contents, will be merged with data
            
        Returns:
            Dict containing the created ConfigMap information
            
        Raises:
            ValidationError: If the ConfigMap name, namespace, or data is invalid
            KubeAgentError: If ConfigMap creation fails
        """
        namespace = namespace or connector.namespace
        
        try:
            # Validate inputs
            ConfigTools._validate_name(name, "configmap")
            ConfigTools._validate_name(namespace, "namespace")
            
            if not isinstance(data, dict):
                raise ValidationError("ConfigMap data must be a dictionary")
            
            # Initialize command
            command = ["create", "configmap", name, "-n", namespace]
            
            # Add data parameters
            for key, value in data.items():
                command.extend(["--from-literal", f"{key}={value}"])
            
            # Add file data if provided
            if from_file and isinstance(from_file, dict):
                for file_key, file_content in from_file.items():
                    # Use a temporary file to store the content
                    # This would be handled by the connector in a real implementation
                    command.extend(["--from-file", f"{file_key}={file_content}"])
            
            # Add labels if provided
            if labels and isinstance(labels, dict):
                for key, value in labels.items():
                    command.extend(["--labels", f"{key}={value}"])
            
            # Add annotations if provided
            if annotations and isinstance(annotations, dict):
                for key, value in annotations.items():
                    command.extend(["--annotations", f"{key}={value}"])
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to create ConfigMap '{name}': {result.get('error', 'Unknown error')}")
            
            # Retrieve the created ConfigMap
            return ConfigTools.get_configmap(name, namespace)
        except Exception as e:
            logger.error(f"Error creating ConfigMap '{name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error creating ConfigMap: {str(e)}")
    
    @staticmethod
    def update_configmap(name: str, 
                              data: Dict[str, str], 
                              namespace: Optional[str] = None,
                              merge: bool = True) -> Dict[str, Any]:
        """
        Update an existing ConfigMap with new data.
        
        Args:
            name: Name of the ConfigMap to update
            data: Dictionary containing key-value pairs to update
            namespace: Namespace where the ConfigMap is located (default: connector's default namespace)
            merge: If True, merge with existing data; if False, replace all data (default: True)
            
        Returns:
            Dict containing the updated ConfigMap information
            
        Raises:
            ResourceNotFoundError: If the ConfigMap doesn't exist
            ValidationError: If the ConfigMap name, namespace, or data is invalid
            KubeAgentError: If ConfigMap update fails
        """
        namespace = namespace or connector.namespace
        
        try:
            # Validate inputs
            ConfigTools._validate_name(name, "configmap")
            ConfigTools._validate_name(namespace, "namespace")
            
            if not isinstance(data, dict):
                raise ValidationError("ConfigMap data must be a dictionary")
            
            # Check if ConfigMap exists
            try:
                ConfigTools.get_configmap(name, namespace)
            except ResourceNotFoundError:
                raise
            
            # Apply patch to update the ConfigMap
            if merge:
                # Get existing ConfigMap to merge data
                existing_configmap = ConfigTools.get_configmap(name, namespace)
                existing_data = existing_configmap.get("data", {}) or {}
                
                # Merge existing data with new data
                merged_data = {**existing_data, **data}
                
                # Create patch with merged data
                patch = {
                    "data": merged_data
                }
            else:
                # Replace all data
                patch = {
                    "data": data
                }
            
            # Apply patch
            patch_json = json.dumps(patch)
            
            result = connector.execute_kubectl_command(
                ["patch", "configmap", name, "-n", namespace, "--type=merge", "-p", patch_json]
            )
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to update ConfigMap '{name}': {result.get('error', 'Unknown error')}")
            
            # Retrieve the updated ConfigMap
            return ConfigTools.get_configmap(name, namespace)
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error updating ConfigMap '{name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error updating ConfigMap: {str(e)}")
    
    @staticmethod
    def delete_configmap(name: str, 
                              namespace: Optional[str] = None) -> bool:
        """
        Delete a ConfigMap.
        
        Args:
            name: Name of the ConfigMap to delete
            namespace: Namespace where the ConfigMap is located (default: connector's default namespace)
            
        Returns:
            True if deletion was successful
            
        Raises:
            ValidationError: If the ConfigMap name or namespace is invalid
            KubeAgentError: If ConfigMap deletion fails
        """
        namespace = namespace or connector.namespace
        
        try:
            # Validate inputs
            ConfigTools._validate_name(name, "configmap")
            ConfigTools._validate_name(namespace, "namespace")
            
            result = connector.execute_kubectl_command(
                ["delete", "configmap", name, "-n", namespace]
            )
            
            if not result.get("success", False):
                if "not found" in result.get("error", "").lower():
                    # If the ConfigMap doesn't exist, consider it a successful deletion
                    return True
                raise KubeAgentError(f"Failed to delete ConfigMap '{name}': {result.get('error', 'Unknown error')}")
            
            return True
        except Exception as e:
            logger.error(f"Error deleting ConfigMap '{name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error deleting ConfigMap: {str(e)}")
    
    # Similar methods for Secrets would be implemented here
    
    # Helper methods for validation
    @staticmethod
    def _validate_name(name: str, resource_type: str) -> None:
        """Validate a Kubernetes resource name"""
        if not name or not isinstance(name, str):
            raise ValidationError(f"{resource_type.capitalize()} name must be a non-empty string")
        
        # Check if name contains only allowed characters
        if not name.isalnum() and not all(c.isalnum() or c in "-." for c in name):
            raise ValidationError(f"Invalid {resource_type} name: '{name}'. Must consist of alphanumeric characters, '-', or '.'")
    
    @staticmethod
    def _validate_label_selector(label_selector: str) -> None:
        """Validate a label selector"""
        if not re.match(r'^[a-zA-Z0-9-_./]+(=[a-zA-Z0-9-_./]+)?$', label_selector):
            raise ValidationError(f"Invalid label selector format: '{label_selector}'")
