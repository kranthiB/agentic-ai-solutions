import subprocess
from typing import Any, Dict, List, Optional
from connectors.base import ClusterConnector

class LocalKubectlConnector(ClusterConnector):
    """
    Connector that uses the local kubectl command-line tool.
    """
    
    def execute_kubectl_command(self, 
                                     command: List[str], 
                                     stdin: Optional[str] = None,
                                     background: bool = False,
                                     file_operation: bool = False) -> Dict[str, Any]:
        """
        Execute a kubectl command using the local kubectl binary.
        
        Args:
            command: kubectl command and arguments as a list
            stdin: Input to provide to the command
            background: Whether to run the command in the background
            file_operation: Whether the command involves file operations
            
        Returns:
            Command execution results
            
        Raises:
            CommandExecutionError: If the command execution fails
        """
        base_command = ["kubectl"]
        
        # Add kubeconfig and context if specified
        if self.kubeconfig:
            base_command.extend(["--kubeconfig", self.kubeconfig])
        
        if self.context:
            base_command.extend(["--context", self.context])
        
        # Combine base command with the specific command
        full_command = base_command + command
        try:
            if background:
                process = subprocess.Popen(
                    full_command,
                    stdin=subprocess.PIPE if stdin else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                if stdin:
                    process.stdin.write(stdin.encode())
                    process.stdin.close()
                
                return {
                    "success": True,
                    "processId": process.pid,
                    "command": " ".join(full_command)
                }
            else:
                # For regular commands
                process = subprocess.Popen(
                    full_command,
                    stdin=subprocess.PIPE if stdin else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                if stdin:
                    stdout, stderr = process.communicate(stdin.encode())
                else:
                    stdout, stderr = process.communicate()
                
                stdout = stdout.decode("utf-8", errors="replace")
                stderr = stderr.decode("utf-8", errors="replace")
                
                success = process.returncode == 0
                
                if file_operation and success:
                    # If this is a file operation and it succeeded, we might need to
                    # return the file content
                    return {
                        "success": success,
                        "output": stdout,
                        "error": stderr,
                        "returncode": process.returncode,
                        "file_content": stdout
                    }
                else:
                    return {
                        "success": success,
                        "output": stdout,
                        "error": stderr,
                        "returncode": process.returncode
                    }
        except Exception as e:
            error_msg = f"Error executing kubectl command {' '.join(full_command)}: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "output": "",
                "returncode": -1
            }