import datetime
import json
import re
from typing import Any, Dict, Optional
from utils.exceptions import KubeAgentError, ResourceNotFoundError, ValidationError
from utils.cluster_connector import k8s_cluster_connector
from monitoring.agent_logger import get_logger

connector = k8s_cluster_connector
logger = get_logger(__name__)

from utils.formatting import format_resource_age

class ResourceTools:
    """Tools for working with generic Kubernetes resources"""
    
    @staticmethod
    def get_resource(resource_type: str,
                          name: str,
                          namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve a specific Kubernetes resource.
        
        Args:
            resource_type: Type of resource (e.g., 'deployment', 'service', 'configmap')
            name: Name of the resource to retrieve
            namespace: Namespace where the resource is located (None for cluster-scoped resources)
            
        Returns:
            Dict containing the resource information
            
        Raises:
            ValidationError: If resource type, name, or namespace is invalid
            ResourceNotFoundError: If the resource doesn't exist
            KubeAgentError: If an error occurs during retrieval
        """
        # Set default namespace for namespaced resources if not provided
        if namespace is None and resource_type.lower() not in ["namespace", "node", "clusterrole", "clusterrolebinding"]:
            namespace = connector.namespace
        
        try:
            # Validate inputs
            ResourceTools._validate_name(name, resource_type)
            if namespace:
                ResourceTools._validate_name(namespace, "namespace")
            
            # Build command
            command = ["get", resource_type, name]
            
            if namespace:
                command.extend(["-n", namespace])
            
            command.extend(["-o", "json"])
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                if "not found" in result.get("error", "").lower():
                    raise ResourceNotFoundError(f"{resource_type.capitalize()} '{name}' not found")
                raise KubeAgentError(f"Failed to get {resource_type} '{name}': {result.get('error', 'Unknown error')}")
            
            return json.loads(result.get("output", "{}"))
        except json.JSONDecodeError:
            raise KubeAgentError(f"Failed to parse {resource_type} information for '{name}'")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            scope = f"in namespace '{namespace}'" if namespace else "(cluster-scoped)"
            logger.error(f"Error retrieving {resource_type} '{name}' {scope}: {str(e)}")
            raise KubeAgentError(f"Error retrieving resource: {str(e)}")
    
    @staticmethod
    def analyze_resource(resource_type: str,
                              name: str,
                              namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform a comprehensive analysis of a Kubernetes resource.
        
        Args:
            resource_type: Type of resource to analyze
            name: Name of the resource to analyze
            namespace: Namespace where the resource is located (None for cluster-scoped resources)
            
        Returns:
            Dict containing analysis results
            
        Raises:
            ValidationError: If resource type, name, or namespace is invalid
            ResourceNotFoundError: If the resource doesn't exist
            KubeAgentError: If analysis fails
        """
        # Set default namespace for namespaced resources if not provided
        if namespace is None and resource_type.lower() not in ["namespace", "node", "clusterrole", "clusterrolebinding"]:
            namespace = connector.namespace
        
        try:
            # Validate inputs
            ResourceTools._validate_name(name, resource_type)
            if namespace:
                ResourceTools._validate_name(namespace, "namespace")
            
            # Get resource and events
            resource = ResourceTools.get_resource(resource_type, name, namespace)
            
            # Get events related to the resource
            events_result = connector.execute_kubectl_command([
                "get", "events", "--field-selector", f"involvedObject.name={name}", "-o", "json"
            ])
            
            events = []
            if events_result.get("success", False):
                try:
                    events_json = json.loads(events_result.get("output", "{}"))
                    events = events_json.get("items", [])
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse events for {resource_type} '{name}'")
            
            # Extract important resource attributes
            metadata = resource.get("metadata", {})
            labels = metadata.get("labels", {})
            annotations = metadata.get("annotations", {})
            creation_timestamp = metadata.get("creationTimestamp")
            
            age = format_resource_age(creation_timestamp) if creation_timestamp else "Unknown"
            owner_references = metadata.get("ownerReferences", [])
            
            # Analyze status if available
            status = resource.get("status", {})
            spec = resource.get("spec", {})
            
            # Analyze events
            event_count = len(events)
            warning_events = [e for e in events if e.get("type") == "Warning"]
            recent_events = sorted(
                events,
                key=lambda x: x.get("lastTimestamp", ""),
                reverse=True
            )[:5]  # Get 5 most recent events
            
            # Generate insights based on resource type and status
            insights = []
            
            # Insight: Recent warning events
            if warning_events:
                insights.append({
                    "type": "recent_warning_events",
                    "message": f"Resource has {len(warning_events)} warning events",
                    "severity": "medium",
                    "events": [
                        {
                            "reason": e.get("reason", ""),
                            "message": e.get("message", ""),
                            "count": e.get("count", 1),
                            "lastTimestamp": e.get("lastTimestamp", "")
                        }
                        for e in warning_events[:3]  # Show only the top 3 warning events
                    ]
                })
            
            # Add resource-type specific insights
            if resource_type.lower() == "pod":
                phase = status.get("phase", "Unknown")
                if phase != "Running" and phase != "Succeeded":
                    severity = "high" if phase in ["Failed", "Unknown"] else "medium"
                    insights.append({
                        "type": "pod_not_running",
                        "message": f"Pod is in {phase} state",
                        "severity": severity
                    })
            elif resource_type.lower() == "deployment":
                available_condition = next(
                    (c for c in status.get("conditions", []) if c.get("type") == "Available"), 
                    None
                )
                
                if available_condition and available_condition.get("status") != "True":
                    insights.append({
                        "type": "deployment_not_available",
                        "message": f"Deployment is not available: {available_condition.get('message', 'Unknown reason')}",
                        "severity": "high"
                    })
            
            # Check for owner references to understand resource relationships
            if owner_references:
                owner = owner_references[0]
                owner_kind = owner.get("kind", "Unknown")
                owner_name = owner.get("name", "Unknown")
                
                insights.append({
                    "type": "managed_resource",
                    "message": f"This resource is managed by {owner_kind} '{owner_name}'",
                    "severity": "info"
                })
            
            # Compile the analysis results
            analysis_results = {
                "resourceType": resource_type,
                "resourceName": name,
                "namespace": namespace,
                "age": age,
                "labels": labels,
                "annotations": annotations,
                "spec": spec,
                "status": status,
                "events": {
                    "count": event_count,
                    "warningCount": len(warning_events),
                    "recentEvents": recent_events
                },
                "ownerReferences": owner_references,
                "insights": insights,
                "resource": resource,
                "analysisTime": datetime.datetime.now().isoformat()
            }
            
            scope = f"in namespace '{namespace}'" if namespace else "(cluster-scoped)"
            logger.info(f"Analyzed {resource_type} '{name}' {scope}: {len(insights)} insights generated")
            
            return analysis_results
        except ResourceNotFoundError:
            raise
        except Exception as e:
            scope = f"in namespace '{namespace}'" if namespace else "(cluster-scoped)"
            logger.error(f"Error analyzing {resource_type} '{name}' {scope}: {str(e)}")
            raise KubeAgentError(f"Error analyzing resource: {str(e)}")
    
    # Helper methods
    @staticmethod
    def _validate_name(name: str, resource_type: str) -> None:
        """Validate a Kubernetes resource name"""
        if not name or not isinstance(name, str):
            raise ValidationError(f"{resource_type.capitalize()} name must be a non-empty string")
        
        # Less strict validation for real-world names which might not follow ideal patterns
        if not re.match(r'^[a-zA-Z0-9][-a-zA-Z0-9_.]*[a-zA-Z0-9]$', name) and name != "-":
            logger.warning(f"Resource name '{name}' may not conform to Kubernetes naming conventions")