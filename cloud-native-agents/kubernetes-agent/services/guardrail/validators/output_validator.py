# services/guardrail/validators/output_validator.py
import re
from typing import Dict, Tuple

from monitoring.agent_logger import get_logger

class OutputValidator:
    """
    Validates LLM outputs for safety, harmful content, and policy compliance.
    
    This validator:
    1. Detects and filters harmful content
    2. Redacts sensitive information
    3. Ensures outputs comply with system policies
    """
    
    def __init__(self, config: Dict = None):
        self.logger = get_logger(__name__)
        self.config = config or {}
        
        # Load filter patterns
        self.filter_patterns = self._load_filter_patterns()
        
        # Sensitive information patterns
        self.sensitive_patterns = {
            "token": r'(?:Bearer\s+|token:\s*|--token=|token\s+is\s+)([A-Za-z0-9-._~+/]+=*)',
            "password": r'(?:password:\s*|--password=|password\s+is\s+)([^"\'\s]+)',
            "private_key": r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----.*?-----END\s+(?:RSA\s+)?PRIVATE\s+KEY-----',
            "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        }
        
        self.logger.info("OutputValidator initialized with %d filter patterns", 
                        len(self.filter_patterns))
    
    def _load_filter_patterns(self) -> Dict[str, Dict[str, str]]:
        """Load content filter patterns from configuration"""
        patterns = {
            "harmful_instructions": {
                "pattern": r'(?i)(?:how\s+to|steps\s+for|instructions\s+for)\s+(?:hack|exploit|attack|compromise)',
                "replacement": "[harmful content removed]"
            },
            "offensive_content": {
                "pattern": r'(?i)(?:racial\s+slurs?|offensive\s+language|derogatory\s+terms?)',
                "replacement": "[inappropriate content removed]"
            },
            "credentials": {
                "pattern": r'(?i)(?:password|secret|token|apikey)(?:\s+is|\:)\s*[^\s]+',
                "replacement": "[credentials removed]"
            }
        }
        
        # Add patterns from config
        for category, pattern_data in self.config.get("filter_patterns", {}).items():
            patterns[category] = pattern_data
            
        return patterns
    
    async def validate(self, 
                      output: str, 
                      context: Dict = None) -> Tuple[bool, str, str]:
        """
        Validate and filter LLM output
        
        Args:
            output: Raw LLM output to validate
            context: Additional context about the generation
            
        Returns:
            Tuple of (is_valid, reason_if_invalid, filtered_output)
        """
        # Start with the original output
        filtered_output = output
        modifications = []
        
        # Apply filter patterns
        for category, pattern_data in self.filter_patterns.items():
            pattern = pattern_data["pattern"]
            replacement = pattern_data["replacement"]
            
            # Apply the pattern
            filtered_output, count = re.subn(pattern, replacement, filtered_output)
            if count > 0:
                modifications.append(f"{category} ({count} instances)")
        
        # Redact sensitive information
        for info_type, pattern in self.sensitive_patterns.items():
            # For most patterns, replace with info type
            replacement = f"[{info_type} redacted]"
            
            # Special case for IP addresses in kubectl contexts
            if info_type == "ip_address" and "kubectl" not in output.lower():
                # Only redact IPs when not in kubectl context
                continue
                
            # Apply the pattern
            filtered_output, count = re.subn(pattern, replacement, filtered_output)
            if count > 0:
                modifications.append(f"{info_type} redacted ({count} instances)")
        
        # Check if modifications were made
        if modifications:
            reason = "Output modified: " + ", ".join(modifications)
            return False, reason, filtered_output
        
        return True, "", filtered_output