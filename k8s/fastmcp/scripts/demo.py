from fastmcp import FastMCP, Context

mcp = FastMCP("Demo 🚀")

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

@mcp.tool
def specs(ctx: Context = None):
    """List current hardware specs"""
    return {"Response": "AMD 9600X CPU, 1080Ti GPU, 48GB RAM, 1TB SSD, 10GB Ethernet"} 