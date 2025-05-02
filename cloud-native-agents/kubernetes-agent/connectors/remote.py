import json
import tempfile
import paramiko
import io
import base64
from typing import Any, Dict, List, Optional
from connectors.base import ClusterConnector

class RemoteKubectlConnector(ClusterConnector):
    """
    Connector that executes kubectl commands on a remote server via SSH.
    This is useful for scenarios where direct access to the cluster is not possible,
    but can be achieved through an SSH bastion or jump host.
    """
    
    def __init__(self,
                host: str,
                port: int = 22,
                username: str = None,
                password: str = None,
                key_filename: str = None,
                key_data: str = None,
                kubeconfig: Optional[str] = None,
                context: Optional[str] = None,
                namespace: str = "default",
                kubectl_path: str = "kubectl"):
        """
        Initialize the remote kubectl connector.
        
        Args:
            host: SSH host to connect to
            port: SSH port (default: 22)
            username: SSH username
            password: SSH password (optional if key_filename or key_data is provided)
            key_filename: Path to SSH private key file (optional if password or key_data is provided)
            key_data: SSH private key data as string (optional if password or key_filename is provided)
            kubeconfig: Path to kubeconfig file on the remote server or kubeconfig content
            context: Kubernetes context to use (None for current context)
            namespace: Default namespace to use
            kubectl_path: Path to kubectl binary on the remote server
        """
        super().__init__(kubeconfig, context, namespace)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.key_data = key_data
        self.kubectl_path = kubectl_path
        self._ssh_client = None
        
    def connect(self) -> bool:
        """
        Establish SSH connection to the remote server and verify kubectl access.
        
        Returns:
            True if connection was successful, False otherwise
        """
        try:
            # Create SSH client
            self._ssh_client = paramiko.SSHClient()
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect to the remote server
            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
                'timeout': 10
            }
            
            if self.password:
                connect_kwargs['password'] = self.password
            
            if self.key_filename:
                connect_kwargs['key_filename'] = self.key_filename
            
            if self.key_data:
                key_file = io.StringIO(self.key_data)
                private_key = paramiko.RSAKey.from_private_key(key_file)
                connect_kwargs['pkey'] = private_key
            
            self._ssh_client.connect(**connect_kwargs)
            
            # Check if kubectl is available
            stdin, stdout, stderr = self._ssh_client.exec_command(f"{self.kubectl_path} version --client")
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code != 0:
                self.logger.error(f"kubectl not available on remote server: {stderr.read().decode('utf-8')}")
                self._ssh_client.close()
                self._ssh_client = None
                self._connected = False
                return False
            
            # Upload kubeconfig if provided as content
            if self.kubeconfig and isinstance(self.kubeconfig, dict):
                # Create a temporary file for the kubeconfig
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                    json.dump(self.kubeconfig, temp_file)
                    temp_file_path = temp_file.name
                
                # Upload to remote server
                remote_path = f"/tmp/kube_agent_config_{hash(json.dumps(self.kubeconfig))}"
                sftp = self._ssh_client.open_sftp()
                sftp.put(temp_file_path, remote_path)
                sftp.close()
                
                # Update kubeconfig path
                self.kubeconfig = remote_path
            
            # Test connection to the Kubernetes cluster
            result = self.execute_kubectl_command(["version", "--short"])
            self._connected = result.get("success", False)
            
            if self._connected:
                self.logger.info(f"Successfully connected to Kubernetes cluster via {self.host}")
            else:
                self.logger.error(f"Failed to connect to Kubernetes cluster via {self.host}: {result.get('error', 'Unknown error')}")
                if self._ssh_client:
                    self._ssh_client.close()
                    self._ssh_client = None
            
            return self._connected
        except Exception as e:
            self.logger.error(f"Error connecting to remote server: {str(e)}")
            if self._ssh_client:
                self._ssh_client.close()
                self._ssh_client = None
            self._connected = False
            return False
    
    def execute_kubectl_command(self, 
                                     command: List[str], 
                                     stdin: Optional[str] = None,
                                     background: bool = False,
                                     file_operation: bool = False) -> Dict[str, Any]:
        """
        Execute a kubectl command on the remote server.
        
        Args:
            command: kubectl command and arguments as a list
            stdin: Input to provide to the command
            background: Whether to run the command in the background
            file_operation: Whether the command involves file operations
            
        Returns:
            Command execution results
            
        Raises:
            ConnectionError: If the SSH connection is not established
        """
        if not self._ssh_client or not self._connected:
            try:
                success = self.connect()
                if not success:
                    return {
                        "success": False,
                        "error": "Failed to connect to remote server",
                        "output": "",
                        "returncode": -1
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error connecting to remote server: {str(e)}",
                    "output": "",
                    "returncode": -1
                }
        
        try:
            # Build the kubectl command
            base_command = [self.kubectl_path]
            
            if self.kubeconfig:
                base_command.extend(["--kubeconfig", self.kubeconfig])
            
            if self.context:
                base_command.extend(["--context", self.context])
            
            # Combine base command with the specific command
            full_command = " ".join(base_command + command)
            
            # If a background process is requested, we need to use nohup
            if background:
                if stdin:
                    # For background processes with stdin, we need to create a file
                    stdin_file = f"/tmp/kube_agent_stdin_{hash(stdin)}"
                    sftp = self._ssh_client.open_sftp()
                    with sftp.open(stdin_file, 'w') as f:
                        f.write(stdin)
                    sftp.close()
                    
                    # Execute the command, redirecting stdin from the file
                    full_command = f"nohup {full_command} < {stdin_file} > /dev/null 2>&1 & echo $!"
                else:
                    # Execute the command in the background
                    full_command = f"nohup {full_command} > /dev/null 2>&1 & echo $!"
                
                # Execute the command
                self.logger.debug(f"Executing command: {full_command}")
                stdin_stream, stdout_stream, stderr_stream = self._ssh_client.exec_command(full_command)
                
                # Get the process ID
                pid = stdout_stream.read().decode('utf-8').strip()
                exit_code = stdout_stream.channel.recv_exit_status()
                
                return {
                    "success": exit_code == 0,
                    "processId": pid,
                    "command": full_command,
                    "error": stderr_stream.read().decode('utf-8'),
                    "returncode": exit_code
                }
            else:
                # For regular commands
                if stdin:
                    # If stdin is provided, we'll use a here-document approach
                    # Encode stdin to base64 to avoid issues with special characters
                    stdin_encoded = base64.b64encode(stdin.encode('utf-8')).decode('utf-8')
                    decode_command = f"echo '{stdin_encoded}' | base64 --decode"
                    full_command = f"{decode_command} | {full_command}"
                
                # Execute the command
                self.logger.debug(f"Executing command: {full_command}")
                stdin_stream, stdout_stream, stderr_stream = self._ssh_client.exec_command(full_command)
                
                # Get the command output
                stdout = stdout_stream.read().decode('utf-8')
                stderr = stderr_stream.read().decode('utf-8')
                exit_code = stdout_stream.channel.recv_exit_status()
                
                success = exit_code == 0
                
                if file_operation and success:
                    # If this is a file operation and it succeeded, we might need to
                    # return the file content
                    return {
                        "success": success,
                        "output": stdout,
                        "error": stderr,
                        "returncode": exit_code,
                        "file_content": stdout
                    }
                else:
                    return {
                        "success": success,
                        "output": stdout,
                        "error": stderr,
                        "returncode": exit_code
                    }
        except Exception as e:
            error_msg = f"Error executing kubectl command {' '.join(command)}: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "output": "",
                "returncode": -1
            }
    
    def __del__(self):
        """Ensure SSH connection is closed when the object is destroyed."""
        if hasattr(self, '_ssh_client') and self._ssh_client:
            try:
                self._ssh_client.close()
                self.logger.debug("SSH connection closed")
            except Exception as e:
                self.logger.warning(f"Error closing SSH connection: {str(e)}")
    
    def close(self):
        """
        Close the SSH connection explicitly.
        """
        if self._ssh_client:
            try:
                self._ssh_client.close()
                self._ssh_client = None
                self._connected = False
                self.logger.debug("SSH connection closed")
                return True
            except Exception as e:
                self.logger.warning(f"Error closing SSH connection: {str(e)}")
                return False
        return True
    
    def execute_script(self, script_content: str, script_args: List[str] = None) -> Dict[str, Any]:
        """
        Execute a shell script on the remote server.
        
        Args:
            script_content: Content of the script to execute
            script_args: Arguments to pass to the script
            
        Returns:
            Script execution results
        """
        if not self._ssh_client or not self._connected:
            try:
                success = self.connect()
                if not success:
                    return {
                        "success": False,
                        "error": "Failed to connect to remote server",
                        "output": "",
                        "returncode": -1
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error connecting to remote server: {str(e)}",
                    "output": "",
                    "returncode": -1
                }
        
        try:
            # Create a temporary script file
            script_hash = hash(script_content)
            remote_script_path = f"/tmp/kube_agent_script_{script_hash}.sh"
            
            # Upload the script
            sftp = self._ssh_client.open_sftp()
            with sftp.open(remote_script_path, 'w') as f:
                f.write(script_content)
            
            # Make the script executable
            sftp.chmod(remote_script_path, 0o755)
            sftp.close()
            
            # Build the command to execute the script
            command = remote_script_path
            if script_args:
                command += " " + " ".join(script_args)
            
            # Execute the script
            self.logger.debug(f"Executing script: {command}")
            stdin, stdout, stderr = self._ssh_client.exec_command(command)
            
            # Get the script output
            stdout_content = stdout.read().decode('utf-8')
            stderr_content = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            # Clean up the script file
            try:
                sftp = self._ssh_client.open_sftp()
                sftp.remove(remote_script_path)
                sftp.close()
            except Exception as e:
                self.logger.warning(f"Failed to remove temporary script file: {str(e)}")
            
            return {
                "success": exit_code == 0,
                "output": stdout_content,
                "error": stderr_content,
                "returncode": exit_code
            }
        except Exception as e:
            error_msg = f"Error executing script: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "output": "",
                "returncode": -1
            }
    
    def upload_file(self, local_path: str, remote_path: str) -> Dict[str, Any]:
        """
        Upload a file to the remote server.
        
        Args:
            local_path: Path to the local file
            remote_path: Path where the file should be uploaded on the remote server
            
        Returns:
            Upload results
        """
        if not self._ssh_client or not self._connected:
            try:
                success = self.connect()
                if not success:
                    return {
                        "success": False,
                        "error": "Failed to connect to remote server",
                        "output": "",
                        "returncode": -1
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error connecting to remote server: {str(e)}",
                    "output": "",
                    "returncode": -1
                }
        
        try:
            # Upload the file
            sftp = self._ssh_client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            
            return {
                "success": True,
                "output": f"File uploaded to {remote_path}",
                "error": "",
                "returncode": 0
            }
        except Exception as e:
            error_msg = f"Error uploading file: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "output": "",
                "returncode": -1
            }
    
    def download_file(self, remote_path: str, local_path: str) -> Dict[str, Any]:
        """
        Download a file from the remote server.
        
        Args:
            remote_path: Path to the file on the remote server
            local_path: Path where the file should be saved locally
            
        Returns:
            Download results
        """
        if not self._ssh_client or not self._connected:
            try:
                success = self.connect()
                if not success:
                    return {
                        "success": False,
                        "error": "Failed to connect to remote server",
                        "output": "",
                        "returncode": -1
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error connecting to remote server: {str(e)}",
                    "output": "",
                    "returncode": -1
                }
        
        try:
            # Download the file
            sftp = self._ssh_client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            
            return {
                "success": True,
                "output": f"File downloaded to {local_path}",
                "error": "",
                "returncode": 0
            }
        except Exception as e:
            error_msg = f"Error downloading file: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "output": "",
                "returncode": -1
            }
    
    def check_kubectx_available(self) -> bool:
        """
        Check if kubectx tool is available on the remote server.
        
        Returns:
            True if kubectx is available, False otherwise
        """
        if not self._ssh_client or not self._connected:
            try:
                success = self.connect()
                if not success:
                    return False
            except Exception:
                return False
        
        try:
            # Check if kubectx is available
            stdin, stdout, stderr = self._ssh_client.exec_command("which kubectx")
            exit_code = stdout.channel.recv_exit_status()
            
            return exit_code == 0
        except Exception:
            return False
    
    def get_available_contexts(self) -> Dict[str, Any]:
        """
        Get a list of available Kubernetes contexts on the remote server.
        
        Returns:
            Dict containing available contexts
        """
        if not self._ssh_client or not self._connected:
            try:
                success = self.connect()
                if not success:
                    return {
                        "success": False,
                        "error": "Failed to connect to remote server",
                        "contexts": []
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error connecting to remote server: {str(e)}",
                    "contexts": []
                }
        
        try:
            # Build the command to get contexts
            command = f"{self.kubectl_path} config get-contexts"
            if self.kubeconfig:
                command += f" --kubeconfig {self.kubeconfig}"
            
            # Execute the command
            stdin, stdout, stderr = self._ssh_client.exec_command(command)
            stdout_content = stdout.read().decode('utf-8')
            stderr_content = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code != 0:
                return {
                    "success": False,
                    "error": stderr_content,
                    "contexts": []
                }
            
            # Parse the output to extract contexts
            lines = stdout_content.strip().split('\n')
            if len(lines) < 2:
                return {
                    "success": True,
                    "contexts": []
                }
            
            # Skip the header line
            contexts = []
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    current = '*' in line
                    name = parts[0] if not current else parts[1]
                    contexts.append({
                        "name": name,
                        "current": current
                    })
            
            return {
                "success": True,
                "contexts": contexts
            }
        except Exception as e:
            error_msg = f"Error getting available contexts: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "contexts": []
            }
    
    def switch_context(self, context_name: str) -> Dict[str, Any]:
        """
        Switch to a different Kubernetes context.
        
        Args:
            context_name: Name of the context to switch to
            
        Returns:
            Dict containing the result of the operation
        """
        # Check if kubectx is available
        kubectx_available = self.check_kubectx_available()
        
        if kubectx_available:
            # Use kubectx for switching contexts
            command = f"kubectx {context_name}"
            if self.kubeconfig:
                command += f" --kubeconfig {self.kubeconfig}"
            
            stdin, stdout, stderr = self._ssh_client.exec_command(command)
            stdout_content = stdout.read().decode('utf-8')
            stderr_content = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code == 0:
                self.context = context_name
                return {
                    "success": True,
                    "output": stdout_content,
                    "error": "",
                    "context": context_name
                }
            else:
                return {
                    "success": False,
                    "output": "",
                    "error": stderr_content,
                    "context": self.context
                }
        else:
            # Use kubectl config use-context
            result = self.execute_kubectl_command(["config", "use-context", context_name])
            
            if result.get("success", False):
                self.context = context_name
            
            return {
                "success": result.get("success", False),
                "output": result.get("output", ""),
                "error": result.get("error", ""),
                "context": self.context
            }