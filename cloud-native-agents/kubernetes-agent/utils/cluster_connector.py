from configs.agent_config import CONNECTOR_TYPE, KUBECONFIG_PATH, KUBE_CONTEXT, SSH_HOST, SSH_PORT, SSH_USERNAME, SSH_PASSWORD, SSH_KEY_FILENAME, SSH_KEY_DATA, REMOTE_KUBECTL_PATH
from connectors.local import LocalKubectlConnector
from connectors.remote import RemoteKubectlConnector
from connectors.k8s_api import KubernetesAPIConnector


k8s_cluster_connector = LocalKubectlConnector(kubeconfig=KUBECONFIG_PATH, context=KUBE_CONTEXT)

if CONNECTOR_TYPE == "remote":
    k8s_cluster_connector = RemoteKubectlConnector(
        host=SSH_HOST,
        port=SSH_PORT,
        username=SSH_USERNAME,
        password=SSH_PASSWORD,
        key_filename=SSH_KEY_FILENAME,
        key_data=SSH_KEY_DATA,
        kubeconfig=KUBECONFIG_PATH,
        context=KUBE_CONTEXT,
        kubectl_path=REMOTE_KUBECTL_PATH
    )
elif CONNECTOR_TYPE == "api":
    k8s_cluster_connector = KubernetesAPIConnector(kubeconfig=KUBECONFIG_PATH, context=KUBE_CONTEXT)