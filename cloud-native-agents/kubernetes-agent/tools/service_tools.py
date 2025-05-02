import json
import re
from typing import Any, Dict, List, Optional

import yaml
from utils.exceptions import KubeAgentError, ResourceNotFoundError, ValidationError
from utils.cluster_connector import k8s_cluster_connector
from monitoring.agent_logger import get_logger

connector = k8s_cluster_connector
logger = get_logger(__name__)

class ServiceTools:
    """Tools for working with Kubernetes Services"""
    
    @staticmethod
    def get_service(name: str, 
                         namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve detailed information about a specific Service.
        
        Args:
            name: Name of the Service to retrieve
            namespace: Namespace where the Service is located (default: connector's default namespace)
            
        Returns:
            Dict containing the Service information
            
        Raises:
            ResourceNotFoundError: If the Service doesn't exist
            KubeAgentError: If an error occurs during retrieval
        """
        # Set default namespace if not provided
        if namespace is None:
            namespace = connector.namespace
        
        try:
            # Validate inputs
            ServiceTools._validate_name(name, "service")
            ServiceTools._validate_name(namespace, "namespace")
            
            result = connector.execute_kubectl_command(
                ["get", "service", name, "-n", namespace, "-o", "json"]
            )
            
            if not result.get("success", False):
                if "not found" in result.get("error", "").lower():
                    raise ResourceNotFoundError(f"Service '{name}' not found in namespace '{namespace}'")
                raise KubeAgentError(f"Failed to get Service '{name}': {result.get('error', 'Unknown error')}")
            
            return json.loads(result.get("output", "{}"))
        except json.JSONDecodeError:
            raise KubeAgentError(f"Failed to parse Service information for '{name}'")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving Service '{name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error retrieving Service: {str(e)}")
    
    @staticmethod
    def create_service(name: str,
                            selector: Dict[str, str],
                            ports: List[Dict[str, Any]],
                            namespace: Optional[str] = None,
                            service_type: str = "ClusterIP",
                            external_ip: Optional[List[str]] = None,
                            external_name: Optional[str] = None,
                            annotations: Optional[Dict[str, str]] = None,
                            labels: Optional[Dict[str, str]] = None,
                            cluster_ip: Optional[str] = None,
                            session_affinity: str = "None",
                            load_balancer_ip: Optional[str] = None,
                            external_traffic_policy: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new Kubernetes Service.
        
        Args:
            name: Name of the Service to create
            selector: Label selector to determine which Pods the Service targets
            ports: List of port definitions for the Service
            namespace: Namespace for the Service (default: connector's default namespace)
            service_type: Type of Service (ClusterIP, NodePort, LoadBalancer, ExternalName)
            external_ip: External IPs that route to this Service
            external_name: External name for ExternalName type Services
            annotations: Annotations to apply to the Service
            labels: Labels to apply to the Service
            cluster_ip: Fixed ClusterIP for the Service
            session_affinity: Session affinity policy (None or ClientIP)
            load_balancer_ip: IP to use when creating a LoadBalancer Service
            external_traffic_policy: External traffic policy (Local or Cluster)
            
        Returns:
            Dict containing the created Service information
            
        Raises:
            ValidationError: If input parameters are invalid
            KubeAgentError: If Service creation fails
        """
        # Set default namespace if not provided
        if namespace is None:
            namespace = connector.namespace
        
        try:
            # Validate inputs
            ServiceTools._validate_name(name, "service")
            ServiceTools._validate_name(namespace, "namespace")
            
            if not isinstance(selector, dict) or not selector:
                raise ValidationError("Selector must be a non-empty dictionary")
            
            if not isinstance(ports, list) or not ports:
                raise ValidationError("Ports must be a non-empty list")
            
            valid_service_types = ["ClusterIP", "NodePort", "LoadBalancer", "ExternalName"]
            if service_type not in valid_service_types:
                raise ValidationError(f"Service type must be one of: {', '.join(valid_service_types)}")
            
            if service_type == "ExternalName" and not external_name:
                raise ValidationError("ExternalName type Service requires an external_name")
            
            valid_session_affinity = ["None", "ClientIP"]
            if session_affinity not in valid_session_affinity:
                raise ValidationError(f"Session affinity must be one of: {', '.join(valid_session_affinity)}")
            
            if external_traffic_policy and external_traffic_policy not in ["Local", "Cluster"]:
                raise ValidationError("External traffic policy must be 'Local' or 'Cluster'")
            
            # Validate ports
            for port in ports:
                if "port" not in port:
                    raise ValidationError("Each port mapping must include 'port'")
                
                if not isinstance(port["port"], int) or port["port"] <= 0 or port["port"] > 65535:
                    raise ValidationError("Port must be a valid port number (1-65535)")
                
                if "targetPort" in port and isinstance(port["targetPort"], int):
                    if port["targetPort"] <= 0 or port["targetPort"] > 65535:
                        raise ValidationError("Target port must be a valid port number (1-65535)")
                
                if "nodePort" in port and isinstance(port["nodePort"], int):
                    if port["nodePort"] < 30000 or port["nodePort"] > 32767:
                        raise ValidationError("Node port must be in range 30000-32767")
            
            # Create Service manifest
            service_manifest = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": name,
                    "namespace": namespace
                },
                "spec": {
                    "selector": selector,
                    "ports": ports,
                    "type": service_type,
                    "sessionAffinity": session_affinity
                }
            }
            
            # Add optional fields
            if external_ip:
                service_manifest["spec"]["externalIPs"] = external_ip
            
            if external_name and service_type == "ExternalName":
                service_manifest["spec"]["externalName"] = external_name
            
            if labels:
                service_manifest["metadata"]["labels"] = labels
            
            if annotations:
                service_manifest["metadata"]["annotations"] = annotations
            
            if cluster_ip:
                service_manifest["spec"]["clusterIP"] = cluster_ip
            
            if load_balancer_ip and service_type == "LoadBalancer":
                service_manifest["spec"]["loadBalancerIP"] = load_balancer_ip
            
            if external_traffic_policy and service_type in ["NodePort", "LoadBalancer"]:
                service_manifest["spec"]["externalTrafficPolicy"] = external_traffic_policy
            
            # Convert to YAML
            service_yaml = yaml.dump(service_manifest)
            
            # Create the Service
            result = connector.execute_kubectl_command(
                ["apply", "-f", "-", "-n", namespace],
                stdin=service_yaml
            )
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to create Service '{name}': {result.get('error', 'Unknown error')}")
            
            # Retrieve the created Service
            return ServiceTools.get_service(name, namespace)
        except Exception as e:
            logger.error(f"Error creating Service '{name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error creating Service: {str(e)}")
    
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
