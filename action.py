import json
import os
from mcp import ClientSession
from schemas import ToolCall
from artifacts import artifacts

STATS_PATH = "state/tool_stats.json"

def _update_stats(tool_name: str):
    os.makedirs("state", exist_ok=True)
    stats = {}
    if os.path.exists(STATS_PATH):
        try:
            with open(STATS_PATH, "r") as f:
                stats = json.load(f)
        except:
            pass
    
    # Map tool names to friendly categories if needed
    category = "other"
    if "tavily" in tool_name.lower():
        category = "tavily"
    elif "ddg" in tool_name.lower() or "search" in tool_name.lower():
        category = "duckduckgo"
    
    stats[category] = stats.get(category, 0) + 1
    stats["total"] = stats.get("total", 0) + 1
    
    with open(STATS_PATH, "w") as f:
        json.dump(stats, f, indent=2)

class ActionLayer:
    async def execute(self, session: ClientSession, tool_call: ToolCall) -> tuple[str, str | None]:
        print(f"[action]        -> calling {tool_call.name}...")
        
        # Track usage
        _update_stats(tool_call.name)
        
        try:
            # Client-side intercept for fetch_url if it hangs in MCP
            if tool_call.name == "fetch_url" and "wikipedia.org" in tool_call.arguments.get("url", ""):
                print(f"[action]        -> (intercept) using httpx for Wikipedia...")
                import httpx as httpx_client
                async with httpx_client.AsyncClient(timeout=30, follow_redirects=True) as client:
                    resp = await client.get(tool_call.arguments["url"])
                    resp.raise_for_status()
                    content_text = resp.text
            else:
                # Call the tool via MCP session
                result = await session.call_tool(tool_call.name, tool_call.arguments)
                
                # MCP ToolResult Usually has 'content' which is a list of items
                content_text = ""
                if hasattr(result, "content") and result.content:
                    for item in result.content:
                        if hasattr(item, "text"):
                            content_text += item.text
                        elif isinstance(item, dict) and "text" in item:
                            content_text += item["text"]
                else:
                    content_text = str(result)

            # Record descriptor
            descriptor = content_text[:300]
            if len(content_text) > 300:
                descriptor += "..."

            # Store as artifact
            artifact_id = artifacts.put(
                content_text.encode("utf-8"),
                content_type="text/plain",
                source=f"tool:{tool_call.name}",
                descriptor=descriptor
            )
            
            print(f"[action]        -> ok (artifact: {artifact_id})")
            return descriptor, artifact_id
            
        except Exception as e:
            error_msg = f"Error executing tool {tool_call.name}: {str(e)}"
            print(f"[action]        -> {error_msg}")
            return error_msg, None

action = ActionLayer()
