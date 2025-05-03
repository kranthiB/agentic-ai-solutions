# services/guardrail/validators/input_validator.py
import re
import asyncio
from typing import Dict, List, Tuple

from monitoring.agent_logger import get_logger

class InputValidator:
    """
    Validates user input for safety, policy compliance, and appropriateness.
    
    This validator checks for:
    1. Prohibited content (sensitive commands, harmful inputs)
    2. Content policy violations (offensive language, inappropriate content)
    3. Input security risks (injection attempts, command executions)
    """
    
    def __init__(self, config: Dict = None):
        self.logger = get_logger(__name__)
        self.config = config or {}
        
        # Load prohibited patterns
        self.prohibited_patterns = self._load_prohibited_patterns()
        
        # Flags for validation types
        self.check_prohibited = self.config.get("check_prohibited", True)
        self.check_content_policy = self.config.get("check_content_policy", True)
        self.check_security = self.config.get("check_security", True)
        
        self.logger.info("InputValidator initialized with %d prohibited patterns", 
                        len(self.prohibited_patterns))
    
    def _load_prohibited_patterns(self) -> Dict[str, List[str]]:
        """Load prohibited patterns from configuration"""
        patterns = {
            "security": [
                r'(?i)(?:sudo|su)\s+.*',  # sudo commands
                r'(?:rm|chmod|chown|dd|mkfs)\s+.*-[rf].*',  # dangerous system commands
                r'(?:\|\s*(?:bash|sh|zsh|csh)|`.*`)',  # shell execution attempts
            ],
            "content_policy": [
                # Highly offensive content patterns
                r'(?i)(?:fuck|shit|dick|asshole|bitch)',
            ],
            "kubernetes_sensitive": [
                r'(?i)(?:kubeconfig|\.kube/config)',  # kubeconfig references
                r'(?i)(?:--token\s+\S+|bearer\s+token)',  # direct token references
                r'(?i)secret(?:\s+create|\s+edit|\s+expose)',  # secret operations
            ]
        }
        
        # Add patterns from config
        for category, pattern_list in self.config.get("prohibited_patterns", {}).items():
            if category not in patterns:
                patterns[category] = []
            patterns[category].extend(pattern_list)
            
        return patterns
    
    async def validate(self, 
                      user_input: str, 
                      user_id: str = "anonymous",
                      conversation_id: str = None, 
                      metadata: Dict = None) -> Tuple[bool, str]:
        """
        Validate the user input
        
        Args:
            user_input: The raw user input to validate
            user_id: User identifier
            conversation_id: Optional conversation context
            metadata: Additional context metadata
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        if not user_input or not user_input.strip():
            return False, "Empty input"
            
        # Run all validation checks asynchronously
        validation_tasks = []
        
        if self.check_prohibited:
            validation_tasks.append(self._check_prohibited_patterns(user_input))
            
        if self.check_content_policy:
            validation_tasks.append(self._check_content_policy(user_input))
            
        if self.check_security:
            validation_tasks.append(self._check_security_risks(user_input))
        
        # Run all validation checks
        results = await asyncio.gather(*validation_tasks)
        
        # Check if any validation failed
        for is_valid, reason in results:
            if not is_valid:
                return False, reason
                
        return True, ""
    
    async def _check_prohibited_patterns(self, user_input: str) -> Tuple[bool, str]:
        """Check for prohibited patterns"""
        for category, patterns in self.prohibited_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, user_input)
                if match:
                    return False, f"Prohibited content detected: {category}"
        
        return True, ""
    
    async def _check_content_policy(self, user_input: str) -> Tuple[bool, str]:
        """Check for content policy violations"""
        # Simple check for offensive language
        offensive_terms_count = sum(1 for pattern in self.prohibited_patterns.get("content_policy", []) 
                                  if re.search(pattern, user_input))
        
        if offensive_terms_count > 0:
            return False, "Content policy violation: offensive language detected"
            
        return True, ""
    
    async def _check_security_risks(self, user_input: str) -> Tuple[bool, str]:
        """Check for security risks like injection attempts"""
        # Check for command injection patterns
        injection_patterns = [
            r'(?:;|\|\||\||&&)\s*(?:bash|sh|zsh|csh|curl|wget)',  # Command chaining
            r'(?:\$\(\)|`[^`]*`)',  # Command substitution
            r'(?i)(?:eval|exec)\s*\(',  # Code execution functions
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, user_input):
                return False, "Security risk: potential command injection"
                
        return True, ""