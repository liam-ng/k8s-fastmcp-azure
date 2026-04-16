from fastmcp import Client
import asyncio
import json

async def main():
    # The client will automatically handle Azure OAuth
    async with Client("http://localwsl:8000/mcp", auth="oauth") as client:
        # First-time connection will open Azure login in your browser
        print("✓ Authenticated with Azure!")
        
        # Test the protected tool
        try:
            result = await client.call_tool("get_vm_info")
            print(f"✓ Successfully retrieved VM info")
            data = getattr(result, "structured_content", None)
            print(f"VMs found: {len(data)}")
            
            if isinstance(data, list):
                # concatenate text pieces
                text = "".join(
                    piece.text for piece in data
                    if getattr(piece, "type", None) == "text"
                )
                data = json.loads(text)
            # Pretty print the results
            print("\nVM Details:")
            print(json.dumps(data, indent=2))

        except Exception as e:
            print(f"✗ Error calling get_vm_info: {e}")

if __name__ == "__main__":
    asyncio.run(main())