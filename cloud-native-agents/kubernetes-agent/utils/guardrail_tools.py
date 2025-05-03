from services.guardrail.guardrail_service import get_guardrail_service

guardrail_service = get_guardrail_service()

from monitoring.agent_logger import get_logger
logger = get_logger(__name__)

class GuardrailTools:
    """
    This class provides tools to interact with the Guardrail system.
    It includes methods to check if an operation is permitted by the guardrail system.
    """
    @staticmethod
    def check_operation_permission(operation: str, resource_type: str, user_role: str = "editor"):
        """
        Check if an operation is permitted by the guardrail system
        
        Args:
            operation: The operation to check (e.g., get, list, create, delete)
            resource_type: The resource type (e.g., pod, deployment)
            user_role: The role of the user (viewer, editor, admin)
            
        Returns:
            dict: Permission check result
        """
        try:
            is_permitted = guardrail_service.check_permission(
                user_role=user_role,
                operation=operation,
                resource_type=resource_type
            )
            
            return {
                "operation": operation,
                "resource_type": resource_type,
                "user_role": user_role,
                "is_permitted": is_permitted,
                "message": "Operation permitted" if is_permitted else "Operation not permitted"
            }
        except Exception as e:
            logger.error(f"Error checking operation permission: {str(e)}")
            return {
                "operation": operation,
                "resource_type": resource_type,
                "user_role": user_role,
                "is_permitted": False,
                "error": str(e)
            }
    
    @staticmethod
    def analyze_operation_risk(operation: str, resource_type: str, namespace: str = "default"):
        """
        Analyze the risk level of a Kubernetes operation
        
        Args:
            operation: The operation to analyze (e.g., delete, scale)
            resource_type: The resource type (e.g., node, deployment)
            namespace: The Kubernetes namespace
            
        Returns:
            dict: Risk assessment
        """
        try:
            risk_assessment = guardrail_service.analyze_operation_risk(
                operation=operation,
                resource_type=resource_type,
                namespace=namespace
            )
            
            return risk_assessment
        except Exception as e:
            logger.error(f"Error analyzing operation risk: {str(e)}")
            return {
                "operation": operation,
                "resource_type": resource_type,
                "namespace": namespace,
                "risk_level": "unknown",
                "error": str(e)
            }