# kubernetes_agent/agent_config.py

from typing import Literal

# Which connector to use: "local", "remote", "api"
CONNECTOR_TYPE: Literal["local", "remote", "api"] = "local"

# Local/remote connector options
KUBECONFIG_PATH = None   # Path to kubeconfig if needed
KUBE_CONTEXT = None      # Optional context

# For remote SSH connector
SSH_HOST = "your.remote.server" 
SSH_PORT = 22
SSH_USERNAME = "your_username"
SSH_PASSWORD = None          # OR use SSH key
SSH_KEY_FILENAME = None
SSH_KEY_DATA = None          # If you have private key string
REMOTE_KUBECTL_PATH = "kubectl"  # Path to kubectl on remote server
