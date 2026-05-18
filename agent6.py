import asyncio
import os
import socket
import subprocess
import uuid
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from action import action
from artifacts import artifacts
from decision import decision
from memory import memory
from perception import perception
from schemas import Goal

MAX_ITERATIONS = 10
GATEWAY_URL = "http://localhost:8101"
GATEWAY_PATH = os.path.join(os.getcwd(), "llm_gatewayV3", "main.py")
MCP_SERVER_PATH = r"D:\Projects\EAGv3\s6\mcp_server.py"

def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

import time

def ensure_gateway():
    if is_port_open("localhost", 8101):
        print("[setup] LLM Gateway V3 is already running.")
        return

    os.makedirs("state", exist_ok=True)
    log_file = open("state/gateway.log", "a", encoding="utf-8")
    subprocess.Popen(
        [sys.executable, GATEWAY_PATH],
        cwd=os.path.dirname(GATEWAY_PATH),
        stdout=log_file,
        stderr=log_file,
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
    )
    # Wait for it to start
    for _ in range(10):
        if is_port_open("localhost", 8101):
            print("[setup] LLM Gateway V3 started.")
            return
        time.sleep(2)
    print("[setup] WARNING: Could not confirm LLM Gateway V3 is running.")

@asynccontextmanager
async def mcp_session():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    env["PYTHONIOENCODING"] = "utf-8"
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[MCP_SERVER_PATH],
        env=env
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

async def load_tools(session: ClientSession):
    result = await session.list_tools()
    # Handle both tool objects and raw dicts depending on MCP version
    tools = []
    for t in result.tools:
        # Pydantic model vs dict
        if hasattr(t, "model_dump"):
            tools.append(t.model_dump())
        else:
            tools.append(dict(t))
    return tools

def mcp_tools_for_decision(mcp_tools: list[dict]):
    # Decision layer only needs name, description, and input_schema
    out = []
    for t in mcp_tools:
        out.append({
            "name": t.get("name"),
            "description": t.get("description"),
            "input_schema": t.get("inputSchema") or t.get("input_schema")
        })
    return out

def final_answer_from(history: list[dict]) -> str:
    # Find the last answer kind in history
    for item in reversed(history):
        if item.get("kind") == "answer":
            return item.get("text", "No answer found.")
    return "No final answer was reached."

async def run(query: str) -> str:
    ensure_gateway()
    run_id = uuid.uuid4().hex[:8]
    history: list[dict] = []
    prior_goals: list[Goal] = []

    print(f"\n--- Starting run: {run_id} ---")
    print(f"Query: {query}")
    print(f"Python: {sys.executable}")

    # Durable memory
    memory.remember(query, source="user_query", run_id=run_id)

    async with mcp_session() as session:
        mcp_tools_raw = await load_tools(session)
        tools = mcp_tools_for_decision(mcp_tools_raw)

        for it in range(1, MAX_ITERATIONS + 1):
            print(f"\n--- iter {it} ---")
            print("[orchestrator] requesting memory.read()")
            hits = memory.read(query, history, run_id)
            
            print("[orchestrator] passing hits to perception.observe()")
            obs = perception.observe(query, hits, history, prior_goals, run_id)
            prior_goals = obs.goals
            
            if obs.all_done:
                print("\n[done] all goals satisfied")
                break

            goal = obs.next_unfinished()
            attached = []
            if goal.attach_artifact_id and artifacts.exists(goal.attach_artifact_id):
                print(f"[orchestrator] fetching attached artifact {goal.attach_artifact_id}")
                attached.append((
                    goal.attach_artifact_id,
                    artifacts.get_bytes(goal.attach_artifact_id),
                ))

            print("[orchestrator] passing goal to decision.next_step()")
            out = decision.next_step(goal, hits, attached, history, tools)

            if out.answer:
                print("[orchestrator] received answer from decision")
                history.append({
                    "iter": it, "kind": "answer",
                    "goal_id": goal.id, "text": out.answer
                })
                # Check if this answer satisfies the current goal by re-running perception or just continuing?
                # The reference code says 'continue', which means perception will mark it done in next iter.
                continue

            if out.tool_call:
                print(f"[orchestrator] received tool_call '{out.tool_call.name}' from decision, passing to action.execute()")
                result_text, art_id = await action.execute(session, out.tool_call)
                
                print(f"[orchestrator] recording tool outcome to memory")
                memory.record_outcome(
                    tool_call=out.tool_call,
                    result_text=result_text,
                    artifact_id=art_id,
                    run_id=run_id,
                    goal_id=goal.id,
                )
                history.append({
                    "iter": it, "kind": "action",
                    "goal_id": goal.id, "tool": out.tool_call.name,
                    "arguments": out.tool_call.arguments,
                    "result_descriptor": result_text[:300],
                    "artifact_id": art_id
                })

    return final_answer_from(history)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        ans = asyncio.run(run(q))
        print(f"\nFINAL ANSWER:\n{ans}")
    else:
        print("Usage: python agent6.py <query>")
