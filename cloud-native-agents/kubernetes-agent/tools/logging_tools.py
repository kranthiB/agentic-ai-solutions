import datetime
import json
import re
from typing import Any, Dict, List, Optional
from utils.exceptions import KubeAgentError, ResourceNotFoundError, ValidationError
from utils.cluster_connector import k8s_cluster_connector
from monitoring.agent_logger import get_logger

connector = k8s_cluster_connector
logger = get_logger(__name__)

class LoggingTools:
    """Tools for accessing and analyzing logs from Kubernetes resources"""
    
    @staticmethod
    def get_pod_logs(pod_name: str,
                          namespace: Optional[str] = None,
                          container: Optional[str] = None,
                          previous: bool = False,
                          since: Optional[str] = None,
                          timestamps: bool = False,
                          tail_lines: Optional[int] = None,
                          limit_bytes: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve logs from a specific pod.
        
        Args:
            pod_name: Name of the pod to retrieve logs from
            namespace: Namespace where the pod is located
            container: Name of the container to retrieve logs from
            previous: Whether to retrieve logs from a previous container instance
            since: Retrieve logs since relative time like 5s, 2m, or 3h
            timestamps: Include timestamps in the log output
            tail_lines: Number of lines to retrieve from the end of the logs
            limit_bytes: Maximum number of bytes to retrieve
            
        Returns:
            Dictionary containing the log content and metadata
            
        Raises:
            ValidationError: If parameters are invalid
            ResourceNotFoundError: If the pod doesn't exist
            KubeAgentError: If log retrieval fails
        """
        # Set default namespace if not provided
        if namespace is None:
            namespace = connector.namespace
        
        try:
            # Validate inputs
            LoggingTools._validate_name(pod_name, "pod")
            LoggingTools._validate_name(namespace, "namespace")
            
            if container:
                if not isinstance(container, str) or not container:
                    raise ValidationError("Container name must be a non-empty string")
            
            if since:
                if not isinstance(since, str) or not re.match(r'^[0-9]+(s|m|h|d)$', since):
                    raise ValidationError("Since time must be in format like 5s, 2m, 3h, or 1d")
            
            if tail_lines is not None:
                if not isinstance(tail_lines, int) or tail_lines <= 0:
                    raise ValidationError("Tail lines must be a positive integer")
            
            if limit_bytes is not None:
                if not isinstance(limit_bytes, int) or limit_bytes <= 0:
                    raise ValidationError("Limit bytes must be a positive integer")
            
            # Build command
            command = ["logs", pod_name, "-n", namespace]
            
            if container:
                command.extend(["-c", container])
            
            if previous:
                command.append("--previous")
            
            if since:
                command.extend(["--since", since])
            
            if timestamps:
                command.append("--timestamps")
            
            if tail_lines is not None:
                command.extend(["--tail", str(tail_lines)])
            
            if limit_bytes is not None:
                command.extend(["--limit-bytes", str(limit_bytes)])
            
            # First get the pod information to retrieve container information
            pod_info_result = connector.execute_kubectl_command(
                ["get", "pod", pod_name, "-n", namespace, "-o", "json"]
            )
            
            if not pod_info_result.get("success", False):
                if "not found" in pod_info_result.get("error", "").lower():
                    raise ResourceNotFoundError(f"Pod '{pod_name}' not found in namespace '{namespace}'")
                raise KubeAgentError(f"Failed to get pod '{pod_name}' information: {pod_info_result.get('error', 'Unknown error')}")
            
            pod_info = json.loads(pod_info_result.get("output", "{}"))
            
            # Get the logs
            log_result = connector.execute_kubectl_command(command)
            
            if not log_result.get("success", False):
                raise KubeAgentError(f"Failed to get logs for pod '{pod_name}': {log_result.get('error', 'Unknown error')}")
            
            # Extract container names
            containers = pod_info.get("spec", {}).get("containers", [])
            init_containers = pod_info.get("spec", {}).get("initContainers", [])
            ephemeral_containers = pod_info.get("spec", {}).get("ephemeralContainers", [])
            
            container_names = [c.get("name") for c in containers]
            init_container_names = [c.get("name") for c in init_containers]
            ephemeral_container_names = [c.get("name") for c in ephemeral_containers]
            
            # Determine which container's logs were retrieved
            container_name = container
            if not container_name and container_names:
                container_name = container_names[0]
            
            # Prepare the response
            log_content = log_result.get("output", "")
            
            logs_data = {
                "podName": pod_name,
                "namespace": namespace,
                "containerName": container_name,
                "isPreviousLogs": previous,
                "logs": log_content,
                "podInfo": {
                    "status": pod_info.get("status", {}).get("phase", "Unknown"),
                    "containers": container_names,
                    "initContainers": init_container_names,
                    "ephemeralContainers": ephemeral_container_names,
                    "creationTimestamp": pod_info.get("metadata", {}).get("creationTimestamp"),
                    "podIP": pod_info.get("status", {}).get("podIP")
                },
                "logSize": len(log_content),
                "lineCount": len(log_content.splitlines()) if log_content else 0
            }
            
            return logs_data
        except json.JSONDecodeError:
            raise KubeAgentError(f"Failed to parse pod information for '{pod_name}'")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving logs for pod '{pod_name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error retrieving pod logs: {str(e)}")
    
    @staticmethod
    def analyze_pod_logs(pod_name: str,
                              namespace: Optional[str] = None,
                              container: Optional[str] = None,
                              since: Optional[str] = None,
                              error_patterns: Optional[List[str]] = None,
                              warning_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze logs from a pod to identify patterns, errors, and trends.
        
        Args:
            pod_name: Name of the pod to analyze logs from
            namespace: Namespace where the pod is located
            container: Name of the container to analyze logs from
            since: Analyze logs since relative time like 5s, 2m, or 3h
            error_patterns: Custom regex patterns to identify as errors
            warning_patterns: Custom regex patterns to identify as warnings
            
        Returns:
            Dictionary containing analysis results
            
        Raises:
            ValidationError: If parameters are invalid
            ResourceNotFoundError: If the pod doesn't exist
            KubeAgentError: If log retrieval or analysis fails
        """
        # Set default namespace if not provided
        if namespace is None:
            namespace = connector.namespace
        
        # Default error and warning patterns
        default_error_patterns = [
            r'error|exception|fail|fatal|critical|panic|crash|unexpected|denied',
            r'exit code [1-9][0-9]*',
            r'ERR[O]?R',
            r'E[0-9]{4}',
            r'SEVERE'
        ]
        
        default_warning_patterns = [
            r'warn|warning|unable to|retry|deprecated|could not',
            r'WARN(ING)?',
            r'W[0-9]{4}'
        ]
        
        # Combine default patterns with custom patterns
        all_error_patterns = default_error_patterns[:]
        if error_patterns:
            all_error_patterns.extend(error_patterns)
        
        all_warning_patterns = default_warning_patterns[:]
        if warning_patterns:
            all_warning_patterns.extend(warning_patterns)
        
        try:
            # Get logs from the pod
            log_data = LoggingTools.get_pod_logs(
                pod_name,
                namespace,
                container,
                False,  # not previous
                since,
                True,  # include timestamps
                None,  # all lines
                None   # no byte limit
            )
        
            log_content = log_data.get("logs", "")
            if not log_content:
                return {
                    "podName": pod_name,
                    "namespace": namespace,
                    "containerName": log_data.get("containerName"),
                    "status": "No logs available",
                    "lineCount": 0,
                    "errorCount": 0,
                    "warningCount": 0,
                    "errors": [],
                    "warnings": [],
                    "patterns": {},
                    "timeDistribution": {}
                }
                
        
            # Prepare regex patterns
            error_regex = re.compile(f"({'|'.join(all_error_patterns)})", re.IGNORECASE)
            warning_regex = re.compile(f"({'|'.join(all_warning_patterns)})", re.IGNORECASE)
        
            # Analyze logs
            lines = log_content.splitlines()
            line_count = len(lines)
        
            # Track errors and warnings
            errors = []
            warnings = []
            
            # Track patterns and frequencies
            patterns = {}
            
            # Track temporal distribution
            time_distribution = {}
            
            # Regular expression to extract timestamp from log line
            timestamp_regex = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})')
        
            # Analyze each line
            for line_number, line in enumerate(lines, 1):
                # Extract timestamp if available
                timestamp_match = timestamp_regex.search(line)
                hour = None
                timestamp_str = None
                
                if timestamp_match:
                    timestamp_str = timestamp_match.group(1)
                    try:
                        # Parse the timestamp and extract the hour
                        timestamp = datetime.datetime.fromisoformat(timestamp_str)
                        hour = timestamp.strftime("%Y-%m-%d %H:00")
                        
                        # Update time distribution
                        if hour not in time_distribution:
                            time_distribution[hour] = 0
                        time_distribution[hour] += 1
                    except ValueError:
                        pass
                
                # Check for errors
                if error_regex.search(line):
                    errors.append({
                        "lineNumber": line_number,
                        "timestamp": timestamp_str,
                        "line": line
                    })
                
                # Check for warnings
                elif warning_regex.search(line):
                    warnings.append({
                        "lineNumber": line_number,
                        "timestamp": timestamp_str,
                        "line": line
                    })
                
                # Extract common patterns (simple approach)
                # Remove timestamps, numbers, UUIDs, etc. to identify message templates
                cleaned_line = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d+Z', '', line)
                cleaned_line = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', 'UUID', cleaned_line)
                cleaned_line = re.sub(r'\b\d+\.\d+\.\d+\.\d+\b', 'IP_ADDR', cleaned_line)
                cleaned_line = re.sub(r'\b\d+\b', 'NUM', cleaned_line)
                
                # Extract the first 50 characters as a pattern signature
                pattern_signature = cleaned_line[:50].strip()
                if pattern_signature:
                    if pattern_signature not in patterns:
                        patterns[pattern_signature] = 0
                    patterns[pattern_signature] += 1
        
                # Sort patterns by frequency
                sorted_patterns = sorted(
                    [{"pattern": k, "count": v} for k, v in patterns.items()],
                    key=lambda x: x["count"],
                    reverse=True
                )
            
                # Get the top patterns
                top_patterns = sorted_patterns[:10] if len(sorted_patterns) > 10 else sorted_patterns
                
                # Generate insights
                insights = []
                
                # Insight: Error frequency
                error_count = len(errors)
                if error_count > 0:
                    error_rate = (error_count / line_count) * 100
                    severity = "high" if error_rate > 10 else ("medium" if error_rate > 1 else "low")
                    insights.append({
                        "type": "error_frequency",
                        "message": f"Found {error_count} errors ({error_rate:.1f}% of log lines)",
                        "severity": severity
                    })
            
                # Insight: Warning frequency
                warning_count = len(warnings)
                if warning_count > 0:
                    warning_rate = (warning_count / line_count) * 100
                    severity = "medium" if warning_rate > 20 else "low"
                    insights.append({
                        "type": "warning_frequency",
                        "message": f"Found {warning_count} warnings ({warning_rate:.1f}% of log lines)",
                        "severity": severity
                    })
            
                # Insight: Common error patterns
                if error_count > 0:
                    # Group errors by pattern
                    error_patterns = {}
                    for error in errors:
                        error_line = error["line"]
                        # Simple normalization to group similar errors
                        normalized = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', 'UUID', error_line)
                        normalized = re.sub(r'\b\d+\.\d+\.\d+\.\d+\b', 'IP_ADDR', normalized)
                        normalized = re.sub(r'\b\d+\b', 'NUM', normalized)
                        
                        pattern_key = normalized[:50].strip()
                        if pattern_key not in error_patterns:
                            error_patterns[pattern_key] = 0
                        error_patterns[pattern_key] += 1
                    
                    # Find the most common error pattern
                    if error_patterns:
                        most_common_error = max(error_patterns.items(), key=lambda x: x[1])
                        insights.append({
                            "type": "common_error",
                            "message": f"Most common error pattern: '{most_common_error[0]}' (occurs {most_common_error[1]} times)",
                            "severity": "medium"
                        })
            
                # Prepare the analysis results
                analysis_results = {
                    "podName": pod_name,
                    "namespace": namespace,
                    "containerName": log_data.get("containerName"),
                    "status": log_data.get("podInfo", {}).get("status", "Unknown"),
                    "logSize": log_data.get("logSize", 0),
                    "lineCount": line_count,
                    "errorCount": error_count,
                    "warningCount": warning_count,
                    "errors": errors[:20] if len(errors) > 20 else errors,  # Limit to first 20 errors
                    "warnings": warnings[:20] if len(warnings) > 20 else warnings,  # Limit to first 20 warnings
                    "patterns": top_patterns,
                    "timeDistribution": time_distribution,
                    "insights": insights,
                    "analysisTime": datetime.datetime.now().isoformat()
                }
            
                return analysis_results
        except Exception as e:
            logger.error(f"Error analyzing logs for pod '{pod_name}' in namespace '{namespace}': {str(e)}")
            raise KubeAgentError(f"Error analyzing pod logs: {str(e)}")
        
        # Helper methods
   
    @staticmethod
    def _validate_name(name: str, resource_type: str) -> None:
        """Validate a Kubernetes resource name"""
        if not name or not isinstance(name, str):
            raise ValidationError(f"{resource_type.capitalize()} name must be a non-empty string")
        
        # Less strict validation for real-world names which might not follow ideal patterns
        if not re.match(r'^[a-zA-Z0-9][-a-zA-Z0-9_.]*[a-zA-Z0-9]$', name) and name != "-":
            logger.warning(f"Resource name '{name}' may not conform to Kubernetes naming conventions")