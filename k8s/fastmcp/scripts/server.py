
import os
import logging
from rich.console import Console
from rich.logging import RichHandler
import httpx

import time
from datetime import timedelta

from fastmcp import FastMCP, Context, Client
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.auth.providers.azure import AzureProvider, EntraOBOToken
from fastmcp.server.dependencies import get_access_token

from key_value.aio.stores.memory import MemoryStore
from starlette.responses import JSONResponse
#from msal import ConfidentialClientApplication, TokenCache

logging.basicConfig(
    level=logging.WARNING,
    format="%(name)s: %(message)s",
    handlers=[
        RichHandler(
            console=Console(stderr=True),
            show_path=False,
            show_level=False,
            rich_tracebacks=True,
        )
    ],
)

logger = logging.getLogger("fastmcp")
logger.setLevel(logging.INFO)

# Get uptime of the server for def health_check / endpoint
_start_time = time.time()
def get_uptime() -> str:
    return str(timedelta(seconds=time.time() - _start_time))

# Configure Azure Provider for Entra OAuth Proxy authentication
auth_provider = AzureProvider(
    client_id=os.environ["AZURE_CLIENT_ID"],
    client_secret=os.environ["AZURE_CLIENT_SECRET"],
    tenant_id=os.environ["AZURE_TENANT_ID"],
    base_url="http://localhost:8000",
    required_scopes=["mcp-access"],
    client_storage=MemoryStore(),
    additional_authorize_scopes=[
        "https://graph.microsoft.com/User.Read",
        "https://management.azure.com/user_impersonation",
    ],
)

async def check_user_in_group(graph_token: str, group_id: str) -> bool:
    """Check if the authenticated user is a member of the specified group (including transitive membership)."""
    async with httpx.AsyncClient() as client:
        url = (
            "https://graph.microsoft.com/v1.0/me/transitiveMemberOf/microsoft.graph.group"
            f"?$filter=id eq '{group_id}'&$count=true"
        )
        logger.info(f"Checking group membership for group ID: {group_id}")
        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {graph_token}",
                "ConsistencyLevel": "eventual",
            },
        )
        response.raise_for_status()
        data = response.json()
        membership_count = data.get("@odata.count", 0)
        logger.info(f"User membership count in group {group_id}: {membership_count}")
        return membership_count > 0

# Middleware to populate user_id in per-request context state
class UserAuthMiddleware(Middleware):
    def _get_user_id(self):
        token = get_access_token()
        if not (token and hasattr(token, "claims")):
            return None
        return token.claims.get("oid")

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        user_id = self._get_user_id()
        if context.fastmcp_context is not None:
            context.fastmcp_context.set_state("user_id", user_id)
        return await call_next(context)

    async def on_read_resource(self, context: MiddlewareContext, call_next):
        user_id = self._get_user_id()
        if context.fastmcp_context is not None:
            context.fastmcp_context.set_state("user_id", user_id)
        return await call_next(context)

# Create the MCP server
mcp = FastMCP(name="Azure Manager", auth=auth_provider, middleware=[ UserAuthMiddleware()])

@mcp.tool
async def get_user_info(ctx: Context) -> dict:
    """Returns information about the authenticated Azure user."""
    
    user_id = ctx.get_state("user_id")
    if not user_id:
        return "Error: Authentication required (no user_id present)"
    
    token = get_access_token()
    if not (token and hasattr(token, "claims")):
        return "Error: Authentication required (no token present)"
    
    # The AzureProvider stores user data in token claims
    return {
        "azure_id": token.claims.get("sub"),
        "email": token.claims.get("email"),
        "name": token.claims.get("name"),
        "job_title": token.claims.get("job_title"),
        "office_location": token.claims.get("office_location")
    }

# Resource Graph URL for Azure Management API
RESOURCE_GRAPH_URL = (
    "https://management.azure.com/providers/Microsoft.ResourceGraph/resources"
    "?api-version=2021-03-01"
)

VM_QUERY = """
Resources
| where type =~ 'microsoft.compute/virtualmachines'
| extend nicId = tostring(properties.networkProfile.networkInterfaces[0].id)
| join kind=leftouter (
    Resources
    | where type =~ 'microsoft.network/networkinterfaces'
    | project nicId = id,
        internalIp = tostring(properties.ipConfigurations[0].properties.privateIPAddress),
        publicIpId = tostring(properties.ipConfigurations[0].properties.publicIPAddress.id),
        vnetId = tostring(properties.ipConfigurations[0].properties.subnet.id)
) on nicId
| join kind=leftouter (
    Resources
    | where type =~ 'microsoft.network/publicipaddresses'
    | project publicIpId = id,
        externalIp = tostring(properties.ipAddress)
) on publicIpId
| extend vnetName = iif(
    isempty(vnetId),
    '',
    tostring(split(vnetId, '/')[8])
)
| project
    name,
    resourceGroup,
    subscriptionID = subscriptionId,
    location,
    status = tostring(properties.extended.instanceView.powerState.displayStatus),
    vmSize = tostring(properties.hardwareProfile.vmSize),
    diskSize = toint(properties.storageProfile.osDisk.diskSizeGB),
    osType = tostring(properties.storageProfile.osDisk.osType),
    internalIP = internalIp,
    externalIP = externalIp,
    vnetName
""".strip()

@mcp.tool
async def get_vm_info(
    ctx: Context,
    graph_token: str = EntraOBOToken(["https://management.azure.com/user_impersonation"])
) -> dict:
    """
    Returns information about the virtual machines in the Azure subscription
    on behalf of the authenticated user.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            RESOURCE_GRAPH_URL,
            headers={
                "Authorization": f"Bearer {graph_token}",
                "Content-Type": "application/json",
            },
            json={"query": VM_QUERY},
        )
        response.raise_for_status()
        data = response.json()
    # Resource Graph returns { "data": [ {vm1}, {vm2}, ... ], ... }
    vms = data.get("data", [])
    return {"vms": vms}


    
@mcp.custom_route("/", methods=["GET"])
async def health_check(_request):
    """Health check endpoint for service availability."""
    return JSONResponse({"status": "healthy", "service": "mcp-server","uptime": get_uptime()})