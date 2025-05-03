class KubeAgentError(Exception):
    """Base exception for all Kubernetes Agent errors"""
    pass

class ResourceNotFoundError(KubeAgentError):
    """Error raised when a Kubernetes resource is not found"""
    pass

class ValidationError(KubeAgentError):
    """Error raised when input validation fails"""
    pass

class ClusterConnectionError(KubeAgentError):
    """Error raised when there are issues connecting to the cluster"""
    pass

class CommandExecutionError(KubeAgentError):
    """Error raised when a kubectl command fails to execute"""
    pass