import json
import re
from typing import Any, Dict, List, Optional

import yaml
from utils.exceptions import KubeAgentError, ResourceNotFoundError, ValidationError
from utils.cluster_connector import k8s_cluster_connector
from monitoring.agent_logger import get_logger

connector = k8s_cluster_connector
logger = get_logger(__name__)

class NamespaceTools:
    """Tools for managing Kubernetes Namespaces"""
    
    @staticmethod
    def get_namespace(name: str) -> Dict[str, Any]:
        """
        Retrieve detailed information about a specific Namespace.
        
        Args:
            name: Name of the Namespace to retrieve
            
        Returns:
            Dict containing the Namespace information
            
        Raises:
            ResourceNotFoundError: If the Namespace doesn't exist
            KubeAgentError: If an error occurs during retrieval
        """
        try:
            # Validate inputs
            NamespaceTools._validate_name(name, "namespace")
            
            result = connector.execute_kubectl_command(
                ["get", "namespace", name, "-o", "json"]
            )
            
            if not result.get("success", False):
                if "not found" in result.get("error", "").lower():
                    raise ResourceNotFoundError(f"Namespace '{name}' not found")
                raise KubeAgentError(f"Failed to get Namespace '{name}': {result.get('error', 'Unknown error')}")
            
            return json.loads(result.get("output", "{}"))
        except json.JSONDecodeError:
            raise KubeAgentError(f"Failed to parse Namespace information for '{name}'")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving Namespace '{name}': {str(e)}")
            raise KubeAgentError(f"Error retrieving Namespace: {str(e)}")
    
    @staticmethod
    def list_namespaces(label_selector: Optional[str] = None,
                             field_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all Namespaces in the cluster, optionally filtered by labels or fields.
        
        Args:
            label_selector: Label selector to filter Namespaces
            field_selector: Field selector to filter Namespaces
            
        Returns:
            List of dictionaries containing Namespace information
            
        Raises:
            KubeAgentError: If an error occurs during the operation
        """
        try:
            # Validate label selector if provided
            if label_selector:
                NamespaceTools._validate_label_selector(label_selector)
            
            # Build command
            command = ["get", "namespaces", "-o", "json"]
            
            if label_selector:
                command.extend(["-l", label_selector])
            
            if field_selector:
                command.extend(["--field-selector", field_selector])
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to list Namespaces: {result.get('error', 'Unknown error')}")
            
            namespaces_json = json.loads(result.get("output", "{}"))
            return namespaces_json.get("items", [])
        except json.JSONDecodeError:
            raise KubeAgentError("Failed to parse Namespace list")
        except Exception as e:
            logger.error(f"Error listing Namespaces: {str(e)}")
            raise KubeAgentError(f"Error listing Namespaces: {str(e)}")
    
    @staticmethod
    def create_namespace(name: str,
                              labels: Optional[Dict[str, str]] = None,
                              annotations: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Create a new Kubernetes Namespace.
        
        Args:
            name: Name of the Namespace to create
            labels: Labels to apply to the Namespace
            annotations: Annotations to apply to the Namespace
            
        Returns:
            Dict containing the created Namespace information
            
        Raises:
            ValidationError: If the Namespace name, labels, or annotations are invalid
            KubeAgentError: If Namespace creation fails
        """
        try:
            # Validate inputs
            NamespaceTools._validate_name(name, "namespace")
            
            # Create Namespace manifest
            namespace_manifest = {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": name
                }
            }
            
            # Add labels if provided
            if labels:
                namespace_manifest["metadata"]["labels"] = labels
            
            # Add annotations if provided
            if annotations:
                namespace_manifest["metadata"]["annotations"] = annotations
            
            # Convert to YAML
            namespace_yaml = yaml.dump(namespace_manifest)
            
            # Create the Namespace
            result = connector.execute_kubectl_command(
                ["apply", "-f", "-"],
                stdin=namespace_yaml
            )
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to create Namespace '{name}': {result.get('error', 'Unknown error')}")
            
            # Retrieve the created Namespace
            return NamespaceTools.get_namespace(name)
        except Exception as e:
            logger.error(f"Error creating Namespace '{name}': {str(e)}")
            raise KubeAgentError(f"Error creating Namespace: {str(e)}")
    
    @staticmethod
    def delete_namespace(name: str,
                              force: bool = False,
                              grace_period: Optional[int] = None) -> bool:
        """
        Delete a Kubernetes Namespace and all contained resources.
        
        Args:
            name: Name of the Namespace to delete
            force: Whether to force deletion (default: False)
            grace_period: Override the default grace period in seconds (default: None)
            
        Returns:
            True if deletion was successful
            
        Raises:
            ValidationError: If the Namespace name or grace period is invalid
            KubeAgentError: If Namespace deletion fails
        """
        try:
            # Validate inputs
            NamespaceTools._validate_name(name, "namespace")
            
            if grace_period is not None:
                if not isinstance(grace_period, int) or grace_period < 0:
                    raise ValidationError("Grace period must be a non-negative integer")
            
            # Build command
            command = ["delete", "namespace", name]
            
            if force:
                command.append("--force")
            
            if grace_period is not None:
                command.extend(["--grace-period", str(grace_period)])
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                if "not found" in result.get("error", "").lower():
                    # If the Namespace doesn't exist, consider it a successful deletion
                    return True
                raise KubeAgentError(f"Failed to delete Namespace '{name}': {result.get('error', 'Unknown error')}")
            
            return True
        except Exception as e:
            logger.error(f"Error deleting Namespace '{name}': {str(e)}")
            raise KubeAgentError(f"Error deleting Namespace: {str(e)}")
    
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