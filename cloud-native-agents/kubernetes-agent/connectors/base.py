import json

from typing import Optional, List, Dict, Any
from utils.exceptions import ClusterConnectionError
from monitoring.agent_logger import get_logger

class ClusterConnector:
    """
    Handles connections to Kubernetes clusters and executes kubectl commands.
    This is an abstract base class that should be implemented by specific connectors.
    """
    
    def __init__(self, 
                 kubeconfig: Optional[str] = None, 
                 context: Optional[str] = None,
                 namespace: str = "default"):
        """
        Initialize the ClusterConnector.
        
        Args:
            kubeconfig: Path to kubeconfig file (None for in-cluster config)
            context: Kubernetes context to use (None for current context)
            namespace: Default namespace to use
        """
        self.kubeconfig = kubeconfig
        self.context = context
        self.namespace = namespace
        self._connected = False
        self.logger = get_logger(__name__)
        
    def connect(self) -> bool:
        """
        Establish connection to the Kubernetes cluster.
        
        Returns:
            True if connection was successful, False otherwise
        """
        try:
            # Check if we can access the cluster
            result = self.execute_kubectl_command(["version", "--short"])
            self._connected = result.get("success", False)
            if self._connected:
                self.logger.info("Successfully connected to Kubernetes cluster")
            else:
                self.logger.error(f"Failed to connect to Kubernetes cluster: {result.get('error', 'Unknown error')}")
            
            return self._connected
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
        Execute a kubectl command. This method should be implemented by subclasses.
        
        Args:
            command: kubectl command and arguments as a list
            stdin: Input to provide to the command
            background: Whether to run the command in the background
            file_operation: Whether the command involves file operations
            
        Returns:
            Command execution results
            
        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement execute_kubectl_command")
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """
        Get information about the current Kubernetes cluster.
        
        Returns:
            Dictionary containing cluster information
            
        Raises:
            ClusterConnectionError: If getting cluster info fails
        """
        try:
            result = self.execute_kubectl_command(["cluster-info"])
            
            if not result.get("success", False):
                raise ClusterConnectionError(f"Failed to get cluster info: {result.get('error', 'Unknown error')}")
            
            version_result = self.execute_kubectl_command(["version", "-o", "json"])
            
            cluster_info = {
                "clusterInfo": result.get("output", ""),
                "version": json.loads(version_result.get("output", "{}")) if version_result.get("success", False) else {}
            }
            
            return cluster_info
        except Exception as e:
            self.logger.error(f"Error getting cluster info: {str(e)}")
            raise ClusterConnectionError(f"Error getting cluster info: {str(e)}")