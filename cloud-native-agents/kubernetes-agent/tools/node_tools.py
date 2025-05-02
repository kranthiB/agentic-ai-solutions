"""
Node Tools Module for Kubernetes Agent

This module provides tools for working with Kubernetes nodes, including
getting node information, metrics, managing node cordoning and draining,
and performing analysis on node resources and health.
"""

import datetime
import json
import re
from typing import Any, Dict, List, Optional

from utils.formatting import format_resource_age
from utils.exceptions import KubeAgentError, ResourceNotFoundError, ValidationError
from utils.cluster_connector import k8s_cluster_connector
from monitoring.agent_logger import get_logger

connector = k8s_cluster_connector
logger = get_logger(__name__)

class NodeTools:
    """
    Tools for working with Kubernetes nodes.
    
    This class provides methods for retrieving node information, managing node
    scheduling (cordon, uncordon, drain), and analyzing node health and capacity.
    """

    @staticmethod
    def _validate_name(name: str, resource_type: str) -> None:
        """Validate a Kubernetes resource name"""
        if not name or not isinstance(name, str):
            raise ValidationError(f"{resource_type.capitalize()} name must be a non-empty string")
        
        # Check if name matches Kubernetes naming conventions
        if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$', name):
            logger.warning(f"Resource name '{name}' may not conform to Kubernetes naming conventions")

    @staticmethod  
    def _validate_label_selector(label_selector: str) -> None:
        """Validate a label selector"""
        if not re.match(r'^[a-zA-Z0-9-_./]+(=[a-zA-Z0-9-_./]+)?$', label_selector):
            raise ValidationError(f"Invalid label selector format: '{label_selector}'")
        
    @staticmethod
    def _is_valid_label_key(key: str) -> bool:
        """Validate a label key"""
        if not isinstance(key, str) or not key:
            return False
        
        # Check if the key is a valid DNS subdomain name
        # Optional prefix with a DNS subdomain name
        key_parts = key.split('/')
        if len(key_parts) > 2:
            return False
        
        if len(key_parts) == 2:
            prefix = key_parts[0]
            name = key_parts[1]
            
            # Validate prefix (optional DNS subdomain name)
            if not re.match(r'^([a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*)?$', prefix):
                return False
        else:
            name = key_parts[0]
        
        # Validate name (63 character limit)
        return re.match(r'^([a-z0-9]([-a-z0-9]*[a-z0-9])?)?$', name) and len(name) <= 63
    
    @staticmethod
    def _is_valid_label_value(value: str) -> bool:
        """Validate a label value"""
        if not isinstance(value, str):
            return False
        
        # Empty values are allowed
        if not value:
            return True
        
        # Check if the value is a valid DNS label (63 character limit)
        return re.match(r'^(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])?$', value) and len(value) <= 63
    
    @staticmethod
    def get_node(name: str) -> Dict[str, Any]:
        """
        Retrieve detailed information about a specific node.
        
        Args:
            name: Name of the node to retrieve information about
            
        Returns:
            Dict containing the node information
            
        Raises:
            ResourceNotFoundError: If the node doesn't exist
            KubeAgentError: If an error occurs during retrieval
        """
        try:
            # Validate inputs
            NodeTools._validate_name(name, "node")
            
            result = connector.execute_kubectl_command(
                ["get", "node", name, "-o", "json"]
            )
            
            if not result.get("success", False):
                if "not found" in result.get("error", "").lower():
                    raise ResourceNotFoundError(f"Node '{name}' not found")
                raise KubeAgentError(f"Failed to get node '{name}': {result.get('error', 'Unknown error')}")
            
            node_json = json.loads(result.get("output", "{}"))
            logger.debug(f"Retrieved node '{name}'")
            return node_json
        except json.JSONDecodeError:
            raise KubeAgentError(f"Failed to parse node information for '{name}'")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving node '{name}': {str(e)}")
            raise KubeAgentError(f"Error retrieving node: {str(e)}")

    @staticmethod
    def list_nodes(
        label_selector: Optional[str] = None,
        field_selector: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all nodes in the cluster, optionally filtered by labels or fields.
        
        Args:
            label_selector: Label selector to filter nodes (e.g. "node-role.kubernetes.io/control-plane")
            field_selector: Field selector to filter nodes (e.g. "metadata.name=node1")
            
        Returns:
            List of dictionaries containing node information
            
        Raises:
            ValidationError: If the selectors are invalid
            KubeAgentError: If an error occurs during the operation
        """
        try:
            # Validate label selector if provided
            if label_selector:
                NodeTools._validate_label_selector(label_selector)
            
            # Build command
            command = ["get", "nodes", "-o", "json"]
            if label_selector:
                command.extend(["-l", label_selector])
            if field_selector:
                command.extend(["--field-selector", field_selector])
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to list nodes: {result.get('error', 'Unknown error')}")
            
            nodes_json = json.loads(result.get("output", "{}"))
            nodes = nodes_json.get("items", [])
            
            logger.debug(f"Listed {len(nodes)} nodes")
            return nodes
        except json.JSONDecodeError:
            raise KubeAgentError("Failed to parse node list")
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error listing nodes: {str(e)}")
            raise KubeAgentError(f"Error listing nodes: {str(e)}")

    @staticmethod
    def describe_node(name: str) -> str:
        """
        Get a detailed description of a node using kubectl describe.
        
        Args:
            name: Name of the node to describe
            
        Returns:
            String containing the detailed description
            
        Raises:
            ValidationError: If the node name is invalid
            ResourceNotFoundError: If the node doesn't exist
            KubeAgentError: If description retrieval fails
        """
        try:
            # Validate inputs
            NodeTools._validate_name(name, "node")
            
            result = connector.execute_kubectl_command(
                ["describe", "node", name]
            )
            
            if not result.get("success", False):
                if "not found" in result.get("error", "").lower():
                    raise ResourceNotFoundError(f"Node '{name}' not found")
                raise KubeAgentError(f"Failed to describe node '{name}': {result.get('error', 'Unknown error')}")
            
            logger.debug(f"Retrieved description for node '{name}'")
            return result.get("output", "")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error describing node '{name}': {str(e)}")
            raise KubeAgentError(f"Error describing node: {str(e)}")
        
    @staticmethod
    def get_node_metrics(node_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve resource usage metrics for nodes in the cluster.
        
        Args:
            node_name: Optional name of a specific node to get metrics for
            
        Returns:
            Dict containing node metrics
            
        Raises:
            ValidationError: If the node name is invalid
            ResourceNotFoundError: If the node doesn't exist
            KubeAgentError: If metrics retrieval fails
        """
        try:
            # Validate inputs if a specific node is requested
            if node_name:
                NodeTools._validate_name(node_name, "node")
            
            # Build command
            command = ["top", "node"]
            if node_name:
                command.append(node_name)
            
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                if node_name and "not found" in result.get("error", "").lower():
                    raise ResourceNotFoundError(f"Node '{node_name}' not found")
                # Handle the case where metrics-server is not available
                if "metrics not available" in result.get("error", "").lower():
                    return {
                        "error": "Metrics not available - metrics-server may not be deployed in the cluster",
                        "nodes": [],
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                raise KubeAgentError(f"Failed to get node metrics: {result.get('error', 'Unknown error')}")
            
            # Parse the output (top command returns text, not JSON)
            output = result.get("output", "")
            lines = output.strip().split("\n")
            
            if len(lines) < 2:
                return {"nodes": [], "timestamp": datetime.datetime.now().isoformat()}
            
            # Parse header to get column names
            header = lines[0]
            headers = [h.strip() for h in re.split(r'\s+', header)]
            
            # Parse metrics for each node
            metrics = []
            for i in range(1, len(lines)):
                line = lines[i]
                values = [v.strip() for v in re.split(r'\s+', line)]
                
                if len(values) >= len(headers):
                    node_metrics = {headers[j]: values[j] for j in range(len(headers))}
                    metrics.append(node_metrics)
            
            result_data = {
                "nodes": metrics,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            if node_name:
                logger.debug(f"Retrieved metrics for node '{node_name}'")
            else:
                logger.debug(f"Retrieved metrics for {len(metrics)} nodes")
            
            return result_data
        except ResourceNotFoundError:
            raise
        except Exception as e:
            scope = f"node '{node_name}'" if node_name else "nodes"
            logger.error(f"Error retrieving metrics for {scope}: {str(e)}")
            raise KubeAgentError(f"Error retrieving node metrics: {str(e)}")

    @staticmethod
    def cordon_node(
        node_name: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cordon a node to prevent new pods from being scheduled on it.
        
        Args:
            node_name: Name of the node to cordon
            reason: Optional reason for cordoning the node
            
        Returns:
            Dict containing the result of the operation
            
        Raises:
            ValidationError: If the node name is invalid
            ResourceNotFoundError: If the node doesn't exist
            KubeAgentError: If node cordoning fails
        """
        try:
            # Validate inputs
            NodeTools._validate_name(node_name, "node")
            
            # Check if the node exists
            try:
                NodeTools.get_node(node_name)
            except ResourceNotFoundError:
                raise
            
            # Cordon the node
            command = ["cordon", node_name]
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to cordon node '{node_name}': {result.get('error', 'Unknown error')}")
            
            # If reason is provided, annotate the node with the reason
            if reason:
                annotation_command = [
                    "annotate", "node", node_name, 
                    f"maintenance.kubernetes.io/reason={reason}", 
                    "--overwrite"
                ]
                
                annotation_result = connector.execute_kubectl_command(annotation_command)
                if not annotation_result.get("success", False):
                    logger.warning(f"Failed to annotate node with reason: {annotation_result.get('error', 'Unknown error')}")
            
            # Get the updated node info
            updated_node = NodeTools.get_node(node_name)
            
            logger.info(f"Cordoned node '{node_name}'" + (f" with reason: {reason}" if reason else ""))
            
            return {
                "nodeName": node_name,
                "operation": "cordon",
                "success": True,
                "reason": reason,
                "timestamp": datetime.datetime.now().isoformat(),
                "node": updated_node
            }
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error cordoning node '{node_name}': {str(e)}")
            raise KubeAgentError(f"Error cordoning node: {str(e)}")

    @staticmethod    
    def uncordon_node(node_name: str) -> Dict[str, Any]:
        """
        Uncordon a node to allow scheduling of new pods.
        
        Args:
            node_name: Name of the node to uncordon
            
        Returns:
            Dict containing the result of the operation
            
        Raises:
            ValidationError: If the node name is invalid
            ResourceNotFoundError: If the node doesn't exist
            KubeAgentError: If node uncordoning fails
        """
        try:
            # Validate inputs
            NodeTools._validate_name(node_name, "node")
            
            # Check if the node exists
            try:
                NodeTools.get_node(node_name)
            except ResourceNotFoundError:
                raise
            
            # Uncordon the node
            command = ["uncordon", node_name]
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to uncordon node '{node_name}': {result.get('error', 'Unknown error')}")
            
            # Remove any maintenance annotation if it exists
            annotation_command = [
                "annotate", "node", node_name, 
                "maintenance.kubernetes.io/reason-", 
                "--ignore-not-found"
            ]
            
            annotation_result = connector.execute_kubectl_command(annotation_command)
            if not annotation_result.get("success", False):
                logger.warning(f"Failed to remove maintenance annotation: {annotation_result.get('error', 'Unknown error')}")
            
            # Get the updated node info
            updated_node = NodeTools.get_node(node_name)
            
            logger.info(f"Uncordoned node '{node_name}'")
            
            return {
                "nodeName": node_name,
                "operation": "uncordon",
                "success": True,
                "timestamp": datetime.datetime.now().isoformat(),
                "node": updated_node
            }
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error uncordoning node '{node_name}': {str(e)}")
            raise KubeAgentError(f"Error uncordoning node: {str(e)}")

    @staticmethod    
    def drain_node(
        node_name: str,
        ignore_daemonsets: bool = True,
        delete_local_data: bool = False,
        force: bool = False,
        grace_period: Optional[int] = None,
        timeout: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Drain a node, evicting all pods to prepare for maintenance.
        
        Args:
            node_name: Name of the node to drain
            ignore_daemonsets: Whether to ignore DaemonSet-managed pods (default: True)
            delete_local_data: Whether to delete pods with local storage (default: False)
            force: Whether to force drain even if there are pods not managed by ReplicationController, etc. (default: False)
            grace_period: Override the default grace period for pod eviction (seconds)
            timeout: The length of time to wait before giving up (e.g., "5m")
            
        Returns:
            Dict containing the result of the operation
            
        Raises:
            ValidationError: If parameters are invalid
            ResourceNotFoundError: If the node doesn't exist
            KubeAgentError: If node draining fails
        """
        try:
            # Validate inputs
            NodeTools._validate_name(node_name, "node")
            
            if grace_period is not None and (not isinstance(grace_period, int) or grace_period < 0):
                raise ValidationError("Grace period must be a non-negative integer")
            
            if timeout is not None and not re.match(r'^[0-9]+(s|m|h)$', timeout):
                raise ValidationError("Timeout must be in format like 5s, 2m, or 3h")
            
            # Check if the node exists
            try:
                NodeTools.get_node(node_name)
            except ResourceNotFoundError:
                raise
            
            # Build the drain command
            command = ["drain", node_name]
            
            if ignore_daemonsets:
                command.append("--ignore-daemonsets")
            
            if delete_local_data:
                command.append("--delete-local-data")
            
            if force:
                command.append("--force")
            
            if grace_period is not None:
                command.extend(["--grace-period", str(grace_period)])
            
            if timeout is not None:
                command.extend(["--timeout", timeout])
            
            # Drain the node
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to drain node '{node_name}': {result.get('error', 'Unknown error')}")
            
            # Get the updated node info
            updated_node = NodeTools.get_node(node_name)
            
            logger.info(f"Drained node '{node_name}'")
            
            return {
                "nodeName": node_name,
                "operation": "drain",
                "success": True,
                "timestamp": datetime.datetime.now().isoformat(),
                "options": {
                    "ignoreDaemonsets": ignore_daemonsets,
                    "deleteLocalData": delete_local_data,
                    "force": force,
                    "gracePeriod": grace_period,
                    "timeout": timeout
                },
                "output": result.get("output", ""),
                "node": updated_node
            }
        except ResourceNotFoundError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error draining node '{node_name}': {str(e)}")
            raise KubeAgentError(f"Error draining node: {str(e)}")
        
    @staticmethod
    def get_pods_on_node(
        node_name: str,
        namespace: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all pods running on a specific node.
        
        Args:
            node_name: Name of the node to get pods from
            namespace: Optional namespace to filter pods by
            
        Returns:
            List of dictionaries containing pod information
            
        Raises:
            ValidationError: If parameters are invalid
            ResourceNotFoundError: If the node doesn't exist
            KubeAgentError: If pod retrieval fails
        """
        try:
            # Validate inputs
            NodeTools._validate_name(node_name, "node")
            if namespace:
                NodeTools._validate_name(namespace, "namespace")
            
            # Verify the node exists
            try:
                NodeTools.get_node(node_name)
            except ResourceNotFoundError:
                raise
            
            # Build the command
            command = ["get", "pods"]
            
            if namespace:
                command.extend(["-n", namespace])
            else:
                command.append("--all-namespaces")
            
            command.extend(["--field-selector", f"spec.nodeName={node_name}", "-o", "json"])
            
            # Get pods on the node
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to get pods on node '{node_name}': {result.get('error', 'Unknown error')}")
            
            pods_json = json.loads(result.get("output", "{}"))
            pods = pods_json.get("items", [])
            
            scope = f"in namespace '{namespace}'" if namespace else "across all namespaces"
            logger.debug(f"Retrieved {len(pods)} pods on node '{node_name}' {scope}")
            return pods
        except json.JSONDecodeError:
            raise KubeAgentError(f"Failed to parse pod information for node '{node_name}'")
        except ResourceNotFoundError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            scope = f"in namespace '{namespace}'" if namespace else "across all namespaces"
            logger.error(f"Error retrieving pods on node '{node_name}' {scope}: {str(e)}")
            raise KubeAgentError(f"Error retrieving pods on node: {str(e)}")

    @staticmethod    
    def label_node(
        node_name: str,
        labels: Dict[str, str],
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Apply labels to a node.
        
        Args:
            node_name: Name of the node to label
            labels: Dictionary of key-value pairs to apply as labels
            overwrite: Whether to overwrite existing labels with the same keys (default: False)
            
        Returns:
            Dict containing the updated node information
            
        Raises:
            ValidationError: If parameters are invalid
            ResourceNotFoundError: If the node doesn't exist
            KubeAgentError: If labeling fails
        """
        try:
            # Validate inputs
            NodeTools._validate_name(node_name, "node")
            
            if not isinstance(labels, dict) or not labels:
                raise ValidationError("Labels must be a non-empty dictionary")
            
            # Validate label keys and values
            for key, value in labels.items():
                if not NodeTools._is_valid_label_key(key):
                    raise ValidationError(f"Invalid label key: {key}")
                
                if not NodeTools._is_valid_label_value(value):
                    raise ValidationError(f"Invalid label value: {value}")
            
            # Check if the node exists
            try:
                NodeTools.get_node(node_name)
            except ResourceNotFoundError:
                raise
            
            # Build labels string
            labels_list = [f"{key}={value}" for key, value in labels.items()]
            
            # Build the command
            command = ["label", "node", node_name] + labels_list
            
            if overwrite:
                command.append("--overwrite")
            
            # Apply the labels
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to label node '{node_name}': {result.get('error', 'Unknown error')}")
            
            # Get the updated node info
            updated_node = NodeTools.get_node(node_name)
            
            logger.info(f"Applied labels to node '{node_name}': {labels}")
            
            return {
                "nodeName": node_name,
                "operation": "label",
                "labels": labels,
                "overwrite": overwrite,
                "success": True,
                "node": updated_node
            }
        except ResourceNotFoundError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error labeling node '{node_name}': {str(e)}")
            raise KubeAgentError(f"Error labeling node: {str(e)}")
        
    @staticmethod
    def taint_node(
        node_name: str,
        taints: List[Dict[str, str]],
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Apply taints to a node.
        
        Args:
            node_name: Name of the node to taint
            taints: List of taint dictionaries, each containing 'key', 'value', and 'effect'
            overwrite: Whether to overwrite existing taints with the same keys (default: False)
            
        Returns:
            Dict containing the updated node information
            
        Raises:
            ValidationError: If parameters are invalid
            ResourceNotFoundError: If the node doesn't exist
            KubeAgentError: If tainting fails
        """
        try:
            # Validate inputs
            NodeTools._validate_name(node_name, "node")
            
            if not isinstance(taints, list) or not taints:
                raise ValidationError("Taints must be a non-empty list")
            
            # Validate taint structure and values
            valid_effects = ["NoSchedule", "PreferNoSchedule", "NoExecute"]
            
            for taint in taints:
                if not isinstance(taint, dict):
                    raise ValidationError("Each taint must be a dictionary")
                
                if not all(k in taint for k in ("key", "effect")):
                    raise ValidationError("Taints must have 'key' and 'effect' fields")
                
                if taint["effect"] not in valid_effects:
                    raise ValidationError(f"Taint effect must be one of: {', '.join(valid_effects)}")
                
                if not NodeTools._is_valid_label_key(taint["key"]):
                    raise ValidationError(f"Invalid taint key: {taint['key']}")
                
                if "value" in taint and taint["value"] and not NodeTools._is_valid_label_value(taint["value"]):
                    raise ValidationError(f"Invalid taint value: {taint['value']}")
            
            # Check if the node exists
            try:
                NodeTools.get_node(node_name)
            except ResourceNotFoundError:
                raise
            
            # Build taints string
            taint_strings = []
            for taint in taints:
                taint_str = f"{taint['key']}"
                if "value" in taint and taint["value"]:
                    taint_str += f"={taint['value']}"
                taint_str += f":{taint['effect']}"
                taint_strings.append(taint_str)
            
            # Build the command
            command = ["taint", "node", node_name] + taint_strings
            
            if overwrite:
                command.append("--overwrite")
            
            # Apply the taints
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to taint node '{node_name}': {result.get('error', 'Unknown error')}")
            
            # Get the updated node info
            updated_node = NodeTools.get_node(node_name)
            
            logger.info(f"Applied taints to node '{node_name}': {taint_strings}")
            
            return {
                "nodeName": node_name,
                "operation": "taint",
                "taints": taints,
                "overwrite": overwrite,
                "success": True,
                "node": updated_node
            }
        except ResourceNotFoundError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error tainting node '{node_name}': {str(e)}")
            raise KubeAgentError(f"Error tainting node: {str(e)}")
        
    @staticmethod
    def remove_node_taint(
        node_name: str,
        taint_key: str,
        effect: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Remove a taint from a node.
        
        Args:
            node_name: Name of the node to remove taint from
            taint_key: Key of the taint to remove
            effect: Optional effect of the taint to remove (if None, removes all effects for this key)
            
        Returns:
            Dict containing the updated node information
            
        Raises:
            ValidationError: If parameters are invalid
            ResourceNotFoundError: If the node doesn't exist
            KubeAgentError: If taint removal fails
        """
        try:
            # Validate inputs
            NodeTools._validate_name(node_name, "node")
            
            if not taint_key or not isinstance(taint_key, str):
                raise ValidationError("Taint key must be a non-empty string")
            
            if effect and effect not in ["NoSchedule", "PreferNoSchedule", "NoExecute"]:
                raise ValidationError("Taint effect must be one of: NoSchedule, PreferNoSchedule, NoExecute")
            
            # Check if the node exists
            try:
                NodeTools.get_node(node_name)
            except ResourceNotFoundError:
                raise
            
            # Build the taint removal string
            taint_str = taint_key
            if effect:
                taint_str += f":{effect}"
            taint_str += "-"  # The '-' suffix indicates removal
            
            # Build the command
            command = ["taint", "node", node_name, taint_str]
            
            # Remove the taint
            result = connector.execute_kubectl_command(command)
            
            if not result.get("success", False):
                raise KubeAgentError(f"Failed to remove taint from node '{node_name}': {result.get('error', 'Unknown error')}")
            
            # Get the updated node info
            updated_node = NodeTools.get_node(node_name)
            
            taint_desc = f"{taint_key}" + (f":{effect}" if effect else "")
            logger.info(f"Removed taint '{taint_desc}' from node '{node_name}'")
            
            return {
                "nodeName": node_name,
                "operation": "removeTaint",
                "taintKey": taint_key,
                "effect": effect,
                "success": True,
                "node": updated_node
            }
        except ResourceNotFoundError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error removing taint from node '{node_name}': {str(e)}")
            raise KubeAgentError(f"Error removing node taint: {str(e)}")

    @staticmethod    
    def analyze_node(node_name: str) -> Dict[str, Any]:
        """
        Perform a comprehensive analysis of a node, including resource usage, conditions, and potential issues.
        
        Args:
            node_name: Name of the node to analyze
            
        Returns:
            Dict containing analysis results
            
        Raises:
            ValidationError: If the node name is invalid
            ResourceNotFoundError: If the node doesn't exist
            KubeAgentError: If analysis fails
        """
        try:
            # Validate inputs
            NodeTools._validate_name(node_name, "node")
            
            # Get node information
            node = NodeTools.get_node(node_name)
            
            # Try to get node metrics (non-critical, might not be available)
            try:
                metrics = NodeTools.get_node_metrics(node_name)
            except Exception as e:
                logger.warning(f"Unable to get metrics for node '{node_name}': {str(e)}")
                metrics = {"nodes": []}
            
            # Get pods on the node
            try:
                pods = NodeTools.get_pods_on_node(node_name)
            except Exception as e:
                logger.warning(f"Unable to get pods for node '{node_name}': {str(e)}")
                pods = []
            
            # Get node events
            events_result = connector.execute_kubectl_command([
                "get", "events", "--field-selector", f"involvedObject.name={node_name}", "-o", "json"
            ])
            
            events = []
            if events_result.get("success", False):
                try:
                    events_json = json.loads(events_result.get("output", "{}"))
                    events = events_json.get("items", [])
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse events for node '{node_name}'")
            
            # Extract node status and conditions
            status = node.get("status", {})
            conditions = status.get("conditions", [])
            
            # Check node readiness
            ready_condition = next((c for c in conditions if c.get("type") == "Ready"), None)
            is_ready = ready_condition and ready_condition.get("status") == "True"
            
            # Extract capacity and allocatable resources
            capacity = status.get("capacity", {})
            allocatable = status.get("allocatable", {})
            
            # Extract node labels and taints
            labels = node.get("metadata", {}).get("labels", {})
            spec = node.get("spec", {})
            taints = spec.get("taints", [])
            
            # Check for pending pods
            pending_pods = [p for p in pods if p.get("status", {}).get("phase") == "Pending"]
            
            # Extract CPU and memory metrics if available
            node_metrics_items = metrics.get("nodes", [])
            cpu_usage = "Unknown"
            memory_usage = "Unknown"
            
            if node_metrics_items:
                node_metric = node_metrics_items[0]
                cpu_usage = node_metric.get("CPU", node_metric.get("CPU%", "Unknown"))
                memory_usage = node_metric.get("MEMORY", node_metric.get("MEMORY%", "Unknown"))
            
            # Analyze node conditions
            condition_issues = []
            for condition in conditions:
                condition_type = condition.get("type", "")
                condition_status = condition.get("status", "")
                
                # Check for problematic conditions
                is_problem = (
                    (condition_type == "Ready" and condition_status != "True") or
                    (condition_type != "Ready" and condition_status == "True")
                )
                
                if is_problem:
                    condition_issues.append({
                        "type": condition_type,
                        "status": condition_status,
                        "message": condition.get("message", ""),
                        "lastTransitionTime": condition.get("lastTransitionTime", "")
                    })
            
            # Analyze events for potential issues
            event_issues = []
            for event in events:
                if event.get("type") == "Warning":
                    event_issues.append({
                        "reason": event.get("reason", ""),
                        "message": event.get("message", ""),
                        "count": event.get("count", 1),
                        "lastTimestamp": event.get("lastTimestamp", "")
                    })
            
            # Check for cordoned state
            is_cordoned = "unschedulable" in spec and spec["unschedulable"] is True
            
            # Calculate resource usage and pressure
            resource_pressure = {
                "cpu": False,
                "memory": False,
                "disk": False,
                "pid": False
            }
            
            # Check pressure conditions
            for condition in conditions:
                if condition.get("type") == "DiskPressure" and condition.get("status") == "True":
                    resource_pressure["disk"] = True
                elif condition.get("type") == "MemoryPressure" and condition.get("status") == "True":
                    resource_pressure["memory"] = True
                elif condition.get("type") == "PIDPressure" and condition.get("status") == "True":
                    resource_pressure["pid"] = True
            
            # Try to parse CPU usage percentage to detect CPU pressure
            if isinstance(cpu_usage, str) and "%" in cpu_usage:
                try:
                    cpu_percent = float(cpu_usage.replace("%", ""))
                    if cpu_percent > 90:
                        resource_pressure["cpu"] = True
                except (ValueError, TypeError):
                    pass
            
            # Generate insights
            insights = []
            
            # Insight: Node readiness
            if not is_ready:
                insights.append({
                    "type": "node_not_ready",
                    "message": f"Node is not in Ready state: {ready_condition.get('message') if ready_condition else 'Unknown reason'}",
                    "severity": "high"
                })
            
            # Insight: Resource pressure
            pressure_types = [k for k, v in resource_pressure.items() if v]
            if pressure_types:
                insights.append({
                    "type": "resource_pressure",
                    "message": f"Node is experiencing resource pressure: {', '.join(pressure_types)}",
                    "severity": "high"
                })
            
            # Insight: Cordoned state
            if is_cordoned:
                insights.append({
                    "type": "node_cordoned",
                    "message": "Node is cordoned (unschedulable)",
                    "severity": "medium"
                })
            
            # Insight: Taints
            if taints:
                insights.append({
                    "type": "node_taints",
                    "message": f"Node has {len(taints)} taints that may affect pod scheduling",
                    "severity": "low",
                    "taints": taints
                })
            
            # Insight: Pod distribution
            pod_count = len(pods)
            if pod_count > 100:
                insights.append({
                    "type": "high_pod_count",
                    "message": f"Node is running a high number of pods ({pod_count})",
                    "severity": "medium"
                })
            
            # Insight: Pending pods
            if pending_pods:
                insights.append({
                    "type": "pending_pods",
                    "message": f"Node has {len(pending_pods)} pods in Pending state",
                    "severity": "medium"
                })
            
            # Insight: Node age
            creation_timestamp = node.get("metadata", {}).get("creationTimestamp")
            if creation_timestamp:
                try:
                    node_age = format_resource_age(creation_timestamp)
                    if node_age.endswith("d") and int(node_age[:-1]) > 365:
                        insights.append({
                            "type": "old_node",
                            "message": f"Node is quite old ({node_age}), consider reviewing for updates",
                            "severity": "low"
                        })
                except Exception:
                    pass
            
            # Compile the analysis results
            analysis_results = {
                "nodeName": node_name,
                "status": "Ready" if is_ready else "NotReady",
                "isCordoned": is_cordoned,
                "podCount": len(pods),
                "pendingPodCount": len(pending_pods),
                "labels": labels,
                "taints": taints,
                "metrics": {
                    "cpu": cpu_usage,
                    "memory": memory_usage
                },
                "capacity": capacity,
                "allocatable": allocatable,
                "conditions": conditions,
                "resourcePressure": resource_pressure,
                "issues": {
                    "conditions": condition_issues,
                    "events": event_issues
                },
                "insights": insights,
                "analysisTime": datetime.datetime.now().isoformat()
            }
            
            logger.info(f"Analyzed node '{node_name}': {len(insights)} insights generated")
            return analysis_results
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error analyzing node '{node_name}': {str(e)}")
            raise KubeAgentError(f"Error analyzing node: {str(e)}")
        
    @staticmethod
    def analyze_cluster_nodes() -> Dict[str, Any]:
        """
        Perform an analysis of all nodes in the cluster, identifying potential issues and imbalances.
        
        Returns:
            Dict containing cluster-wide node analysis
            
        Raises:
            KubeAgentError: If analysis fails
        """
        try:
            # Get all nodes
            nodes = NodeTools.list_nodes()
            
            # Get metrics for all nodes
            try:
                metrics = NodeTools.get_node_metrics()
                metrics_by_node = {
                    item.get("NAME", ""): item 
                    for item in metrics.get("nodes", [])
                }
            except Exception as e:
                logger.warning(f"Unable to get metrics for cluster nodes: {str(e)}")
                metrics_by_node = {}
            
            # Basic node statistics
            node_count = len(nodes)
            ready_nodes = 0
            cordoned_nodes = 0
            master_nodes = 0
            worker_nodes = 0
            
            # Resource statistics
            total_cpu_capacity = 0
            total_memory_capacity = 0
            
            # Node condition summary
            condition_summary = {}
            
            # Node version distribution
            kubernetes_versions = {}
            
            # Nodes by zone/region
            nodes_by_zone = {}
            nodes_by_region = {}
            
            # Collect data on each node
            node_details = []
            for node in nodes:
                node_name = node.get("metadata", {}).get("name", "")
                status = node.get("status", {})
                spec = node.get("spec", {})
                
                # Check if node is ready
                conditions = status.get("conditions", [])
                ready_condition = next((c for c in conditions if c.get("type") == "Ready"), None)
                is_ready = ready_condition and ready_condition.get("status") == "True"
                if is_ready:
                    ready_nodes += 1
                
                # Check if node is cordoned
                is_cordoned = spec.get("unschedulable", False)
                if is_cordoned:
                    cordoned_nodes += 1
                
                # Check node role
                labels = node.get("metadata", {}).get("labels", {})
                is_master = False
                for label in labels:
                    if "master" in label or "control-plane" in label:
                        is_master = True
                        master_nodes += 1
                        break
                
                if not is_master:
                    worker_nodes += 1
                
                # Get node capacity
                capacity = status.get("capacity", {})
                cpu_capacity = capacity.get("cpu", "0")
                memory_capacity = capacity.get("memory", "0Ki")
                
                # Try to convert CPU capacity to a number
                try:
                    if isinstance(cpu_capacity, str):
                        cpu_capacity = float(cpu_capacity)
                    total_cpu_capacity += cpu_capacity
                except (ValueError, TypeError):
                    pass
                
                # Try to convert memory capacity to a number (in GB)
                try:
                    if isinstance(memory_capacity, str):
                        if memory_capacity.endswith("Ki"):
                            memory_gb = float(memory_capacity[:-2]) / (1024 * 1024)
                        elif memory_capacity.endswith("Mi"):
                            memory_gb = float(memory_capacity[:-2]) / 1024
                        elif memory_capacity.endswith("Gi"):
                            memory_gb = float(memory_capacity[:-2])
                        elif memory_capacity.endswith("Ti"):
                            memory_gb = float(memory_capacity[:-2]) * 1024
                        else:
                            # Assume bytes
                            memory_gb = float(memory_capacity) / (1024 * 1024 * 1024)
                        
                        total_memory_capacity += memory_gb
                    else:
                        # Convert to GB assuming bytes
                        memory_gb = float(memory_capacity) / (1024 * 1024 * 1024)
                        total_memory_capacity += memory_gb
                except (ValueError, TypeError):
                    pass
                
                # Get Kubernetes version
                node_version = status.get("nodeInfo", {}).get("kubeletVersion", "Unknown")
                kubernetes_versions[node_version] = kubernetes_versions.get(node_version, 0) + 1
                
                # Get zone and region
                zone = labels.get("topology.kubernetes.io/zone", 
                                  labels.get("failure-domain.beta.kubernetes.io/zone", "Unknown"))
                region = labels.get("topology.kubernetes.io/region", 
                                    labels.get("failure-domain.beta.kubernetes.io/region", "Unknown"))
                
                nodes_by_zone[zone] = nodes_by_zone.get(zone, 0) + 1
                nodes_by_region[region] = nodes_by_region.get(region, 0) + 1
                
                # Process node conditions
                for condition in conditions:
                    condition_type = condition.get("type", "Unknown")
                    condition_status = condition.get("status", "Unknown")
                    
                    if condition_type not in condition_summary:
                        condition_summary[condition_type] = {"True": 0, "False": 0, "Unknown": 0}
                    
                    condition_summary[condition_type][condition_status] = condition_summary[condition_type].get(condition_status, 0) + 1
                
                # Get metrics if available
                node_metrics = metrics_by_node.get(node_name, {})
                cpu_usage = node_metrics.get("CPU", node_metrics.get("CPU%", "Unknown"))
                memory_usage = node_metrics.get("MEMORY", node_metrics.get("MEMORY%", "Unknown"))
                
                # Collect node details
                node_details.append({
                    "name": node_name,
                    "status": "Ready" if is_ready else "NotReady",
                    "role": "Master" if is_master else "Worker",
                    "cordoned": is_cordoned,
                    "capacity": {
                        "cpu": cpu_capacity,
                        "memory": memory_capacity
                    },
                    "usage": {
                        "cpu": cpu_usage,
                        "memory": memory_usage
                    },
                    "version": node_version,
                    "zone": zone,
                    "region": region,
                    "age": format_resource_age(node.get("metadata", {}).get("creationTimestamp", ""))
                })
            
            # Generate insights
            insights = []
            
            # Insight: Readiness
            if ready_nodes < node_count:
                insights.append({
                    "type": "node_readiness",
                    "message": f"{node_count - ready_nodes} out of {node_count} nodes are not in Ready state",
                    "severity": "high"
                })
            
            # Insight: Cordoned nodes
            if cordoned_nodes > 0:
                insights.append({
                    "type": "cordoned_nodes",
                    "message": f"{cordoned_nodes} nodes are cordoned (unschedulable)",
                    "severity": "medium"
                })
            
            # Insight: Version diversity
            if len(kubernetes_versions) > 1:
                insights.append({
                    "type": "version_diversity",
                    "message": f"Cluster has {len(kubernetes_versions)} different Kubernetes versions",
                    "severity": "medium",
                    "versions": kubernetes_versions
                })
            
            # Insight: Master node count
            if master_nodes == 1:
                insights.append({
                    "type": "single_master",
                    "message": "Cluster has only one master/control-plane node, consider adding more for high availability",
                    "severity": "medium"
                })
            
            # Insight: Zone distribution
            if len(nodes_by_zone) == 1 and node_count > 3:
                insights.append({
                    "type": "single_zone",
                    "message": "All nodes are in a single zone, consider distributing across multiple zones for high availability",
                    "severity": "low"
                })
            
            # Insight: Region distribution
            if len(nodes_by_region) == 1 and node_count > 3:
                insights.append({
                    "type": "single_region",
                    "message": "All nodes are in a single region, consider multi-region deployment for disaster recovery",
                    "severity": "low"
                })
            
            # Check for problematic conditions across the cluster
            for condition_type, statuses in condition_summary.items():
                if condition_type != "Ready" and statuses.get("True", 0) > 0:
                    insights.append({
                        "type": f"{condition_type.lower()}_condition",
                        "message": f"{statuses.get('True', 0)} nodes have {condition_type} condition",
                        "severity": "high"
                    })
            
            # Prepare the analysis results
            analysis_results = {
                "clusterOverview": {
                    "totalNodes": node_count,
                    "readyNodes": ready_nodes,
                    "notReadyNodes": node_count - ready_nodes,
                    "masterNodes": master_nodes,
                    "workerNodes": worker_nodes,
                    "cordonedNodes": cordoned_nodes
                },
                "resourceSummary": {
                    "totalCPU": total_cpu_capacity,
                    "totalMemoryGB": round(total_memory_capacity, 2)
                },
                "distribution": {
                    "versions": kubernetes_versions,
                    "zones": nodes_by_zone,
                    "regions": nodes_by_region
                },
                "conditionSummary": condition_summary,
                "insights": insights,
                "nodes": node_details,
                "analysisTime": datetime.datetime.now().isoformat()
            }
            
            logger.info(f"Analyzed cluster nodes: {len(insights)} insights generated")
            return analysis_results
        except Exception as e:
            logger.error(f"Error analyzing cluster nodes: {str(e)}")
            raise KubeAgentError(f"Error analyzing cluster nodes: {str(e)}")