# tests/guardrail/test_validators.py
import unittest
import asyncio
from unittest.mock import patch

from services.guardrail.validators.input_validator import InputValidator
from services.guardrail.validators.action_validator import ActionValidator
from services.guardrail.validators.output_validator import OutputValidator


class TestInputValidator(unittest.TestCase):
    """Test suite for the InputValidator"""

    def setUp(self):
        """Set up test environment"""
        # Mock logger
        with patch('services.guardrail.validators.input_validator.get_logger'):
            self.validator = InputValidator({
                "check_prohibited": True,
                "check_content_policy": True,
                "check_security": True,
                "prohibited_patterns": {
                    "security": [
                        r'(?:sudo|su)\s+.*',
                        r'(?:rm|chmod|chown|dd|mkfs)\s+.*-[rf].*'
                    ],
                    "content_policy": [
                        r'(?i)(?:offensive|inappropriate)'
                    ]
                }
            })

    def test_load_prohibited_patterns(self):
        """Test loading prohibited patterns"""
        patterns = self.validator._load_prohibited_patterns()
        
        # Check that patterns were loaded
        self.assertIn("security", patterns)
        self.assertIn("content_policy", patterns)
        
        # Check specific patterns
        self.assertTrue(any('sudo' in pattern for pattern in patterns["security"]))
        self.assertTrue(any('offensive' in pattern for pattern in patterns["content_policy"]))

    def test_check_prohibited_patterns_clean(self):
        """Test checking clean input against prohibited patterns"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator._check_prohibited_patterns("Get pods in default namespace")
        )
        
        self.assertTrue(result[0])
        self.assertEqual(result[1], "")

    def test_check_prohibited_patterns_malicious(self):
        """Test checking malicious input against prohibited patterns"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator._check_prohibited_patterns("sudo rm -rf /")
        )
        
        self.assertFalse(result[0])
        self.assertIn("Prohibited content detected", result[1])

    def test_check_content_policy_clean(self):
        """Test checking clean input against content policy"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator._check_content_policy("Professional and appropriate content")
        )
        
        self.assertTrue(result[0])
        self.assertEqual(result[1], "")

    def test_check_content_policy_offensive(self):
        """Test checking offensive input against content policy"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator._check_content_policy("This is offensive content")
        )
        
        self.assertFalse(result[0])
        self.assertIn("Content policy violation", result[1])

    def test_check_security_risks_clean(self):
        """Test checking clean input for security risks"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator._check_security_risks("Get pods in default namespace")
        )
        
        self.assertTrue(result[0])
        self.assertEqual(result[1], "")

    def test_check_security_risks_injection(self):
        """Test checking input with injection attempts for security risks"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator._check_security_risks("get pods; curl | bash")
        )
        
        self.assertFalse(result[0])
        self.assertIn("Security risk", result[1])

    def test_validate_clean_input(self):
        """Test validation of clean input"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate("Get pods in default namespace")
        )
        
        self.assertTrue(result[0])
    
    def test_validate_malicious_input(self):
        """Test validation of malicious input"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate("sudo rm -rf /")
        )
        
        self.assertFalse(result[0])
        self.assertIn("Prohibited content detected", result[1])

    def test_validate_offensive_input(self):
        """Test validation of offensive input"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate("This is offensive content")
        )
        
        self.assertFalse(result[0])
        self.assertIn("Content policy violation", result[1])

    def test_validate_empty_input(self):
        """Test validation of empty input"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate("")
        )
        
        self.assertFalse(result[0])
        self.assertEqual(result[1], "Empty input")


class TestActionValidator(unittest.TestCase):
    """Test suite for the ActionValidator"""

    def setUp(self):
        """Set up test environment"""
        # Mock logger
        with patch('services.guardrail.validators.action_validator.get_logger'):
            self.validator = ActionValidator({
                "role_permissions": {
                    "viewer": ["get", "list", "describe", "watch"],
                    "editor": ["get", "list", "describe", "watch", "create", "update", "patch"],
                    "admin": ["get", "list", "describe", "watch", "create", "update", "patch", "delete", "exec"]
                },
                "protected_resources": {
                    "namespaces": ["kube-system", "kube-public"],
                    "resource_types": ["nodes", "secrets"]
                },
                "critical_resource_patterns": [
                    r'(?i)^kube-',
                    r'(?i).*-system$'
                ],
                "high_risk_operations": {
                    "delete": ["nodes", "namespaces"],
                    "exec": ["pods"]
                }
            })

    def test_parse_action(self):
        """Test parsing action strings into operation and resource type"""
        # Test standard format
        operation, resource = self.validator._parse_action("get_pod")
        self.assertEqual(operation, "get")
        self.assertEqual(resource, "pod")
        
        # Test list with plural
        operation, resource = self.validator._parse_action("list_pods")
        self.assertEqual(operation, "list")
        self.assertEqual(resource, "pod")
        
        # Test special case
        operation, resource = self.validator._parse_action("exec_command_in_pod")
        self.assertEqual(operation, "exec")
        self.assertEqual(resource, "pod")
        
        # Test kubectl wrapper
        operation, resource = self.validator._parse_action("kubectl_delete")
        self.assertEqual(operation, "delete")
        self.assertEqual(resource, "resource")

    def test_check_role_permission_allowed(self):
        """Test permission checking for allowed operations"""
        # Viewer can get
        self.assertTrue(self.validator._check_role_permission("viewer", "get"))
        
        # Editor can update
        self.assertTrue(self.validator._check_role_permission("editor", "update"))
        
        # Admin can delete
        self.assertTrue(self.validator._check_role_permission("admin", "delete"))

    def test_check_role_permission_denied(self):
        """Test permission checking for denied operations"""
        # Viewer cannot delete
        self.assertFalse(self.validator._check_role_permission("viewer", "delete"))
        
        # Editor cannot delete
        self.assertFalse(self.validator._check_role_permission("editor", "delete"))
        
        # Viewer cannot exec
        self.assertFalse(self.validator._check_role_permission("viewer", "exec"))

    def test_is_critical_resource(self):
        """Test checking critical resource patterns"""
        # Test critical resources
        self.assertTrue(self.validator._is_critical_resource("kube-dns"))
        self.assertTrue(self.validator._is_critical_resource("ingress-system"))
        
        # Test non-critical resources
        self.assertFalse(self.validator._is_critical_resource("user-app"))
        self.assertFalse(self.validator._is_critical_resource("frontend"))

    def test_validate_allowed_action(self):
        """Test validation of allowed actions"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate(
                action="get_pod",
                parameters={"name": "my-pod", "namespace": "default"},
                user_role="viewer"
            )
        )
        
        self.assertTrue(result[0])
        self.assertEqual(result[1], "")

    def test_validate_denied_by_role(self):
        """Test validation of actions denied by role"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate(
                action="delete_pod",
                parameters={"name": "my-pod", "namespace": "default"},
                user_role="viewer"
            )
        )
        
        self.assertFalse(result[0])
        self.assertIn("does not have permission", result[1])

    def test_validate_protected_namespace(self):
        """Test validation with protected namespaces"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate(
                action="get_pod",
                parameters={"name": "my-pod", "namespace": "kube-system"},
                user_role="viewer"
            )
        )
        
        self.assertFalse(result[0])
        self.assertIn("is protected and requires admin privileges", result[1])

    def test_validate_protected_resource(self):
        """Test validation with protected resource types"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate(
                action="get_secret",
                parameters={"name": "my-secret", "namespace": "default"},
                user_role="viewer"
            )
        )
        
        self.assertFalse(result[0])
        self.assertIn("is protected and requires admin privileges", result[1])

    def test_validate_critical_resource_name(self):
        """Test validation with critical resource names"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate(
                action="get_pod",
                parameters={"name": "kube-proxy", "namespace": "default"},
                user_role="viewer"
            )
        )
        
        self.assertFalse(result[0])
        self.assertIn("appears to be critical and requires admin privileges", result[1])

    def test_validate_high_risk_operation(self):
        """Test validation of high-risk operations"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate(
                action="delete_node",
                parameters={"name": "node-1", "namespace": "default"},
                user_role="admin"
            )
        )
        
        self.assertFalse(result[0])
        self.assertIn("requires explicit confirmation", result[1])

    def test_validate_high_risk_operation_confirmed(self):
        """Test validation of high-risk operations with confirmation"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate(
                action="delete_node",
                parameters={"name": "node-1", "namespace": "default", "confirmed": True},
                user_role="admin"
            )
        )
        
        self.assertTrue(result[0])
        self.assertEqual(result[1], "")


class TestOutputValidator(unittest.TestCase):
    """Test suite for the OutputValidator"""

    def setUp(self):
        """Set up test environment"""
        # Mock logger
        with patch('services.guardrail.validators.output_validator.get_logger'):
            self.validator = OutputValidator({
                "filter_patterns": {
                    "harmful_instructions": {
                        "pattern": r'(?i)(?:how\s+to|steps\s+for|instructions\s+for)\s+(?:hack|exploit|attack|compromise)',
                        "replacement": "[harmful content removed]"
                    },
                    "credentials": {
                        "pattern": r'(?i)(?:password|secret|token|apikey)(?:\s+is|\:)\s*[^\s]+',
                        "replacement": "[credentials removed]"
                    }
                }
            })

    def test_load_filter_patterns(self):
        """Test loading filter patterns"""
        patterns = self.validator._load_filter_patterns()
        
        # Check that patterns were loaded
        self.assertIn("harmful_instructions", patterns)
        self.assertIn("credentials", patterns)
        
        # Check specific patterns
        self.assertIn("hack", patterns["harmful_instructions"]["pattern"])
        self.assertIn("password", patterns["credentials"]["pattern"])

    def test_validate_clean_output(self):
        """Test validation of clean output"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate("Here are the pods in the default namespace: pod-1, pod-2, pod-3.")
        )
        
        self.assertTrue(result[0])
        self.assertEqual(result[1], "")
        self.assertEqual(result[2], "Here are the pods in the default namespace: pod-1, pod-2, pod-3.")

    def test_validate_harmful_instructions(self):
        """Test validation of output with harmful instructions"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate("Here are steps for how to hack the cluster...")
        )
        
        self.assertFalse(result[0])
        self.assertIn("harmful_instructions", result[1])
        self.assertIn("[harmful content removed]", result[2])

    def test_validate_credentials(self):
        """Test validation of output with credentials"""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate("Your password is: secr3t!")
        )
        
        self.assertFalse(result[0])
        self.assertIn("credentials", result[1])
        self.assertIn("[credentials removed]", result[2])

    def test_validate_sensitive_info(self):
        """Test redaction of sensitive information"""
        # Set up test with token pattern
        test_output = "Your token is: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate(test_output)
        )
        
        self.assertFalse(result[0])
        self.assertIn("[token redacted]", result[2])
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", result[2])

    def test_validate_multiple_issues(self):
        """Test validation of output with multiple issues"""
        test_output = "Your password is: secr3t! Here are steps for how to hack the cluster..."
        
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.validator.validate(test_output)
        )
        
        self.assertFalse(result[0])
        self.assertIn("[credentials removed]", result[2])
        self.assertIn("[harmful content removed]", result[2])
        self.assertNotIn("secr3t", result[2])


if __name__ == "__main__":
    unittest.main()