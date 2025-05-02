import json
import re
from typing import Any, Dict, List, Optional

import yaml
from utils.exceptions import KubeAgentError, ResourceNotFoundError, ValidationError
from utils.cluster_connector import k8s_cluster_connector
from monitoring.agent_logger import get_logger

connector = k8s_cluster_connector
logger = get_logger(__name__)

class DeploymentTools:
    """Tools for working with Kubernetes Deployments"""
    
    @staticmethod
    def get_deployment(name: str, 
                            namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve information about a specific Deployment.
        
        Args:
            name: Name of the Deployment to retrieve
            namespace: Namespace where the Deployment is located (default: connector's default namespace)
            
        Returns:
            Dict containing the Deployment information
            
        Raises:
            ResourceNotFoundError: If the Deployment doesn't exist
            KubeAgentError: If an error occurs during retrieval
        """
        namespace = namespace or connector.namespace
        
        try:
            # Validate inputs
            DeploymentTools._validate_name(name, "deployment")
            DeploymentTools._validate_name(namespace, "namespace")
            
            result = connector.execute_kubectl_command(
                ["get", "deployment", name, "-n", namespace, "-o", "json"]
            )
            
            if not result.get("success", False):
                if "not found" in result.get("error", "").lower():
                    raise ResourceNotFoundError(f"Deployment '{name}' not found in namespace '{namespace}'")
                raise KubeAgentError(f"Failed to get Deployment '{name}': {result.get('error', 'Unknown error')}")
            
            return json.loads(result.get("output", "{}"))
        except json.JSONDecodeError:
            raise KubeAgentError(f"Failed to parse Deployment information for '{name}'")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving Deployment '{name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error retrieving Deployment: {str(e)}")
    
    @staticmethod
    def list_deployments(namespace: Optional[str] = None, 
                              label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all Deployments in the specified namespace, optionally filtered by labels.
        
        Args:
            namespace: Namespace to list Deployments from (default: connector's default namespace)
            label_selector: Label selector to filter Deployments (e.g. "app=nginx")
            
        Returns:
            List of dictionaries containing Deployment information
            
        Raises:
            KubeAgentError: If an error occurs during the operation
        """
        namespace = namespace or connector.namespace
        
        try:
            # Validate namespace
            DeploymentTools._validate_name(namespace, "namespace")
            
            # Validate label selector if provided
            if label_selector:
                DeploymentTools._validate_label_selector(label_selector)
            
            # Build command
            command = ["get", "deployments", "-n", namespace, "-o", "json"]
            if label_selector:
                command.extend(["-l", label_selector])
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to list Deployments: {result.get('error', 'Unknown error')}")
            
            deployments_json = json.loads(result.get("output", "{}"))
            return deployments_json.get("items", [])
        except Exception as e:
            logger.error(f"Error listing Deployments in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error listing Deployments: {str(e)}")
    
    @staticmethod
    def create_deployment(deployment_manifest: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new Deployment from a manifest.
        
        Args:
            deployment_manifest: Dictionary containing the deployment manifest
            
        Returns:
            Dict containing the created Deployment information
            
        Raises:
            ValidationError: If the Deployment manifest is invalid
            KubeAgentError: If Deployment creation fails
        """
        try:
            # Validate deployment manifest
            if not isinstance(deployment_manifest, dict):
                raise ValidationError("Deployment manifest must be a dictionary")
            
            # Basic manifest validation
            required_fields = ["apiVersion", "kind", "metadata", "spec"]
            for field in required_fields:
                if field not in deployment_manifest:
                    raise ValidationError(f"Deployment manifest missing required field: {field}")
            
            if deployment_manifest["kind"] != "Deployment":
                raise ValidationError(f"Expected kind 'Deployment', got '{deployment_manifest['kind']}'")
            
            if "name" not in deployment_manifest["metadata"]:
                raise ValidationError("Deployment manifest missing metadata.name")
            
            deployment_name = deployment_manifest["metadata"]["name"]
            DeploymentTools._validate_name(deployment_name, "deployment")
            
            # Get namespace, defaulting to connector's default if not specified
            namespace = deployment_manifest["metadata"].get("namespace", connector.namespace)
            DeploymentTools._validate_name(namespace, "namespace")
            
            # Convert manifest to YAML
            deployment_yaml = yaml.dump(deployment_manifest)
            
            # Create the Deployment
            result = connector.execute_kubectl_command(
                ["apply", "-f", "-", "-n", namespace],
                stdin=deployment_yaml
            )
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to create Deployment: {result.get('error', 'Unknown error')}")
            
            # Retrieve the created Deployment
            return DeploymentTools.get_deployment(deployment_name, namespace)
        except Exception as e:
            logger.error(f"Error creating Deployment: {str(e)}")
            raise KubeAgentError(f"Error creating Deployment: {str(e)}")
    
    # Other Deployment-related methods would be implemented here
    
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