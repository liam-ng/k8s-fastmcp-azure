# Using FastMCP server & MCPO for Azure / M365 oauth in Ollama & Open WebUI 

MCPO is used as a oauth proxy to authenticate user for the functions. This example uses the same Azure credential authenticated during MCPO initialiation for all chats, that means the end user that is using the chat shares the same authorization. Only basic authentication is done when user login to Open WebUI.

To allow end user or chat user to directly authenticate against the Idp, remote oauth would be the best solution. However, major idp like azure / entra, aws or gcp do not support Dynamic Client Registration. It might be somewhat possible to authenticate user on chat using JWT Token Verification, asking user for their bear token might poses serious security risk and the process would not be optimal experience. 

![[Untitled-2026-03-25-0108 (dark).png]]

# Prerequisites
- [Install Kubernetes k8s]
- [Add NVIDIA Device Plugin to k8s cluster]

## Test setup with gpu-pod 
```
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod
spec:
  restartPolicy: Never
  runtimeClassName: nvidia
  containers:
    - name: cuda-container
      image: nvcr.io/nvidia/k8s/cuda-sample:vectoradd-cuda12.5.0
      resources:
        limits:
          nvidia.com/gpu: 1 # requesting 1 GPU
  tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
EOF
```

### Expected result:
```
k logs gpu-pod
```

![[capture-20260325-0215.png]]


###  Troubleshoot `unresolvable CDI devices`
Error message: `CDI device injection failed: unresolvable CDI devices`

- Make sure GPU-Operator is **NOT** used where its container toolkit daemonset pod will conflict with host.
	- The Windows-hosted drivers exposed via `/dev/dxg` must be used.
	- The Operator will try to overwrite host's `nvidia-container-toolkit`.
	- WSL2 uses specific mount points for GPU libraries (like /usr/lib/wsl/drivers) that the automated scripts may not recognize.
- Make sure NVIDIA Container Toolkit is installed and configured. See [deatils](obsidian://open?vault=SWAT-KB&file=06%20Advanced%20Web%20Service%2F01%20Kubernetes%20(K8s)%2FK8s%20Component%2FK8s%20Cluster%2FAdd%20NVIDIA%20Device%20Plugin%20to%20k8s%20cluster##Configure NVIDIA Container Toolkit).
	- `/etc/containerd/conf.d/99.nvidia.toml` config file is being referenced by main config file.
	- `/var/run/cdi/k8s.device-plugin.nvidia.com-gpu.json` exists.
- Make sure Nvidia Device Plugin has populated operator pod, up and running.  

---

# Ollama 
REF https://github.com/ollama/ollama

## Nginx via Helm
```
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
    --namespace ingress-nginx --create-namespace \
    -f yaml/helm-ingress-nginx.yaml
```

## Ollama via Helm
REF https://github.com/otwld/ollama-helm
```bash
helm repo add otwld https://helm.otwld.com/
helm repo update
helm install ollama otwld/ollama \
	--namespace ollama \
	--create-namespace \
	-f yaml/helm-ollama.yaml
```

## Open WebUI via Helm
REF https://docs.openwebui.com/getting-started/quick-start/
```bash
#helm repo add open-webui https://open-webui.github.io/helm-charts
helm repo add open-webui https://helm.openwebui.com/
helm repo update

kubectl apply -f yaml/pv-openwebui-local.yaml

helm upgrade -i open-webui open-webui/open-webui \
	--namespace ollama \
	-f yaml/helm-open-webui.yaml
```

## AI Model used
Make sure you checked the AI model capability if it supports your usage, e.g. reasoning, tooling or image generation.

- Qwen3.5-9B
	 qwen3.5-9b:Q4_K_M
- Jackrong/Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled-v2-GGUF:Q5_K_M
	 hf.co/Jackrong/Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled-v2-GGUF:Q5_K_M
	 hf.co/Jackrong/Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled-v2-GGUF:Q5_K_M
- nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF:Q4_K_M
	 hf.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF:Q4_K_M

---
# FastMCP
[Model Context Protocol](https://modelcontextprotocol.io/) (MCP) connects LLMs to tools and data.
**FastMCP** **[Servers](https://gofastmcp.com/servers/server)** wrap your Python functions into MCP-compliant tools, resources, and prompts. **[Clients](https://gofastmcp.com/clients/client)** connect to any server with full protocol support. And **[Apps](https://gofastmcp.com/apps/overview)** give your tools interactive UIs rendered directly in the conversation.

[How MCP the protocol communicate](https://addozhang.medium.com/understanding-mcp-through-packet-capture-the-communication-mechanism-behind-ai-tool-invocation-83ff0ea8855d)
## Image Used
Python:3.15.0a7-slim

## List of MCP Servers available from Microsoft 
https://github.com/microsoft/mcp

## Azure Auth & On-Behalf-Of (OBO)

FastMCP server handles Azure’s OAuth flow automatically. FastMCP validates Azure JWTs against your application’s client_id.

The On-Behalf-Of (OBO) flow allows your FastMCP server to call downstream Microsoft APIs—like Microsoft Graph—using the authenticated user’s identity.

The client caches tokens locally, so you won’t need to re-authenticate for subsequent runs unless the token expires or you explicitly clear the cache.

1. Create an Azure App Registration
	1. **Name**: Liam-FastMCP
	2. **Supported account types**: **Single tenant**
	3. **Redirect URI**: http://localhost:8000/auth/callback
2. **Expose an API**
	1. Add a scope using default client ID under Application ID URI
	2. Scope name: `vm`
	3. Configure Access Token Version: set ``requestedAccessTokenVersion`` to 2 under manifest
3. Create Client Secret
4. Permissions
	1. graph.microsoft.com/User.Read
	2. management.azure.com/user_impersonation

## Run Azure OBO in FastMCP
REF https://blog.pamelafox.org/2026/01/using-on-behalf-of-flow-for-entra-based.html
Every **MCP client** is actually an **OAuth2 client**, and each **MCP server** is an **OAuth2 resource server**.
On first connection, mcpo will:

1. Perform dynamic client registration (if supported)
2. Open your browser for authorization
3. Capture the OAuth callback automatically
4. Store tokens securely (in `~/.mcpo/tokens/` for file storage)
5. Use tokens for all subsequent requests

- [auth_entra_mcp.py](https://github.com/Azure-Samples/python-mcp-demos/blob/main/servers/auth_entra_mcp.py): The MCP server itself, configured with FastMCP's AzureProvider and tools that use OBO for group membership checks.

## Expose FastMCP as Open API with MCPO
[server.py](https://gofastmcp.com/integrations/azure#step-2-fastmcp-configuration) &  https://github.com/open-webui/mcpo
http://localhost:8000/docs - List of API exposed by MCPO

### MCPO Oauth Config


> [!Error] 
> 1. Change client name `Azure Manager` when encountered no client ID matched in registry. Error msg: `The client ID xxx was not found in the server's client registry`. Also try incognito if problem persists.
> 
> 2. For local development, `url` should be `localhost:<MCP Port>` as restricted by Azure App Registration return URI.
> 
> 3. Try incognito if the oauth page stuck in infinite loading.
> 
> 4. `use_loopback` is set to false to prevent auto opening browser and failed process immediately. 
> 
> 5. From Open WebUI (Ollama), use Open API settings instead of MCP and connect to `http://localhost:<mcp port>/Azure-Manager` to use the "Azure Manager" tools. 

MCPO oauth REF: https://github.com/open-webui/mcpo/blob/main/OAUTH_GUIDE.md
```json
{
    "mcpServers": {
      "Azure-Manager": {
        "type": "streamable-http",
        "url": "http://localhost:8000/mcp",
        "oauth": {
          "server_url": "http://localhost:8000",
          "use_loopback": false,
          "client_metadata": {
            "client_name": "Azure Manager",
            "redirect_uris": ["http://mcp.localwsl/callback"]
          }
        }
      }
    }
}
```

```
az logout
```

```
mcpo --port 9000 --config k8s/fastmcp/mcpo-config.json
```

![[capture-20260325-0215 5.png]]

Paste the callback URL to terminal, looks like:
```
http://localhost:3030/callback?code=beewS05P_5QhoWnkbxCOo5qUtaU7NziHHkmtaswDigw&state=TKhW_ofUiWsaDLaIu3brduPPK6UkSgknGyv77MadQLM
```
## MCP Client

## Testing locally


> [!Important] 
> Azure only allows http://localhost.* in Redirect URI. Use `kubectl port-forward svc/fastmcp-azure-cli-svc 8000:8000`.


```
# Add Deadsnakes PPA for nightly build py3.14
# If missing command add-apt-repository:
# run sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa

sudo apt update
sudo apt install -y python3.14 python3.14-venv python3.14-dev

# alias py=python3.14
# alias python=python3.14
# py --version

python -m venv .venv-fastmcp
source .venv-fastmcp/bin/activate

pip install fastmcp
```

[client.py](https://gofastmcp.com/integrations/azure#testing-with-a-client)
```
py client.py
```