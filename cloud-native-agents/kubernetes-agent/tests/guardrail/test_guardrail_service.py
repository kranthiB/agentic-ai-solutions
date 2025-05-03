# tests/guardrail/test_guardrail_service.py
import unittest
import asyncio
from unittest.mock import patch, MagicMock

from services.guardrail.guardrail_service import GuardrailService
from services.guardrail.validators.input_validator import InputValidator
from services.guardrail.validators.action_validator import ActionValidator
from services.guardrail.validators.output_validator import OutputValidator


class TestGuardrailService(unittest.TestCase):
    """Test suite for the GuardrailService"""

    def setUp(self):
        """Set up test environment"""
        # Create mock validators
        self.mock_input_validator = MagicMock(spec=InputValidator)
        self.mock_action_validator = MagicMock(spec=ActionValidator)
        self.mock_output_validator = MagicMock(spec=OutputValidator)
        
        # Create service with mocked configs
        with patch('services.guardrail.guardrail_service.InputValidator', return_value=self.mock_input_validator), \
             patch('services.guardrail.guardrail_service.ActionValidator', return_value=self.mock_action_validator), \
             patch('services.guardrail.guardrail_service.OutputValidator', return_value=self.mock_output_validator), \
             patch('services.guardrail.guardrail_service.get_logger'), \
             patch('services.guardrail.guardrail_service.get_metrics_collector'), \
             patch('services.guardrail.guardrail_service.get_audit_logger'):
            
            # Mock _load_config to return a test configuration
            with patch.object(GuardrailService, '_load_config', return_value={
                "enabled": True,
                "enforcement_level": "warning",
                "input_validation": {"enabled": True},
                "action_validation": {"enabled": True},
                "output_validation": {"enabled": True},
                "role_permissions": {
                    "viewer": ["get", "list"],
                    "editor": ["get", "list", "create", "update"],
                    "admin": ["get", "list", "create", "update", "delete"]
                }
            }):
                self.service = GuardrailService()
                
                # Manually set up the parsing method for tests
                self.service.action_validator._parse_action = MagicMock(return_value=("get", "pod"))

    def test_service_initialization(self):
        """Test if service initializes correctly"""
        self.assertIsNotNone(self.service)
        self.assertTrue(self.service.config.get("enabled"))
        self.assertEqual(self.service.config.get("enforcement_level"), "warning")

    def test_validate_user_input_success(self):
        """Test successful user input validation"""
        # Set up mock to return success
        self.mock_input_validator.validate.return_value = asyncio.Future()
        self.mock_input_validator.validate.return_value.set_result((True, ""))
        
        # Run the test using asyncio
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.service.validate_user_input(
            user_input="Get pods in default namespace",
            user_id="test-user",
            conversation_id="test-conversation"
        ))
        
        # Verify results
        self.assertTrue(result[0])
        self.assertEqual(result[1], "")
        
        # Verify validator was called
        self.mock_input_validator.validate.assert_called_once()

    def test_validate_user_input_failure(self):
        """Test failed user input validation"""
        # Set up mock to return failure
        self.mock_input_validator.validate.return_value = asyncio.Future()
        self.mock_input_validator.validate.return_value.set_result(
            (False, "Prohibited content detected")
        )
        
        # Run the test
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.service.validate_user_input(
            user_input="Execute rm -rf /",
            user_id="test-user",
            conversation_id="test-conversation"
        ))
        
        # Verify results
        self.assertFalse(result[0])
        self.assertEqual(result[1], "Prohibited content detected")

    def test_validate_action_success(self):
        """Test successful action validation"""
        # Set up mock to return success
        self.mock_action_validator.validate.return_value = asyncio.Future()
        self.mock_action_validator.validate.return_value.set_result((True, ""))
        
        # Run the test
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.service.validate_action(
            action="get_pod",
            parameters={"name": "test-pod", "namespace": "default"},
            user_id="test-user",
            user_role="viewer"
        ))
        
        # Verify results
        self.assertTrue(result[0])
        self.assertEqual(result[1], "")
        
        # Verify validator was called
        self.mock_action_validator.validate.assert_called_once()

    def test_validate_action_failure(self):
        """Test failed action validation"""
        # Set up mock to return failure
        self.mock_action_validator.validate.return_value = asyncio.Future()
        self.mock_action_validator.validate.return_value.set_result(
            (False, "User role 'viewer' does not have permission for operation 'delete'")
        )
        
        # Run the test
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.service.validate_action(
            action="delete_pod",
            parameters={"name": "test-pod", "namespace": "default"},
            user_id="test-user",
            user_role="viewer"
        ))
        
        # Verify results
        self.assertFalse(result[0])
        self.assertEqual(result[1], "User role 'viewer' does not have permission for operation 'delete'")

    def test_validate_llm_output_success(self):
        """Test successful LLM output validation"""
        # Set up mock to return success
        self.mock_output_validator.validate.return_value = asyncio.Future()
        self.mock_output_validator.validate.return_value.set_result(
            (True, "", "Safe output content")
        )
        
        # Run the test
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.service.validate_llm_output(
            output="Safe output content"
        ))
        
        # Verify results
        self.assertTrue(result[0])
        self.assertEqual(result[1], "")
        self.assertEqual(result[2], "Safe output content")
        
        # Verify validator was called
        self.mock_output_validator.validate.assert_called_once()

    def test_validate_llm_output_filtered(self):
        """Test LLM output that gets filtered"""
        # Set up mock to return filtered content
        self.mock_output_validator.validate.return_value = asyncio.Future()
        self.mock_output_validator.validate.return_value.set_result(
            (False, "Sensitive information detected", "Filtered content with [credentials removed]")
        )
        
        # Run the test
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.service.validate_llm_output(
            output="Original content with password: secret123"
        ))
        
        # Verify results
        self.assertFalse(result[0])
        self.assertEqual(result[1], "Sensitive information detected")
        self.assertEqual(result[2], "Filtered content with [credentials removed]")

    def test_analyze_operation_risk(self):
        """Test operation risk analysis"""
        # Use asyncio to run the test
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.service.analyze_operation_risk(
            operation="delete",
            resource_type="pod",
            namespace="default"
        ))
        
        # Verify results contain expected fields
        self.assertIn("operation", result)
        self.assertIn("resource_type", result)
        self.assertIn("namespace", result)
        self.assertIn("risk_level", result)
        self.assertIn("requires_approval", result)
        self.assertIn("is_critical_namespace", result)
        self.assertIn("mitigation_steps", result)
        
        # Verify operation details
        self.assertEqual(result["operation"], "delete")
        self.assertEqual(result["resource_type"], "pod")
        self.assertEqual(result["namespace"], "default")

    def test_check_permission(self):
        """Test permission checking"""
        # Test valid permission
        self.assertTrue(self.service.check_permission("admin", "delete", "pod"))
        
        # Test invalid permission
        self.assertFalse(self.service.check_permission("viewer", "delete", "pod"))
        
        # Test edge cases
        self.assertTrue(self.service.check_permission("admin", "get", "pod"))
        self.assertTrue(self.service.check_permission("editor", "update", "pod"))
        self.assertFalse(self.service.check_permission("editor", "delete", "pod"))

    def test_sanitize_fragment(self):
        """Test text sanitization for logging"""
        # Test truncation
        long_text = "This is a very long text that should get truncated for logging purposes"
        sanitized = self.service._sanitize_fragment(long_text, max_length=10)
        self.assertEqual(len(sanitized.rstrip('.')), 10)
        
        # Test email redaction
        email_text = "Contact me at user@example.com for details"
        sanitized = self.service._sanitize_fragment(email_text)
        self.assertIn("[EMAIL]", sanitized)
        self.assertNotIn("user@example.com", sanitized)
        
        # Test phone redaction
        phone_text = "Call me at 123-456-7890"
        sanitized = self.service._sanitize_fragment(phone_text)
        self.assertIn("[PHONE]", sanitized)
        self.assertNotIn("123-456-7890", sanitized)


if __name__ == "__main__":
    unittest.main()