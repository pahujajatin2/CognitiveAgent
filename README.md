# Cognitive Architecture Agent (Assignment S6)

A multi-agent cognitive orchestrator built with a modular layered architecture, leveraging the Model Context Protocol (MCP) and a dedicated LLM Gateway (V3) to securely and autonomously execute complex user tasks.

## 🧠 Architecture Overview

The system breaks down reasoning and execution into distinct, specialized layers to prevent LLM hallucination and ensure deterministic tool usage:

1. **Perception Layer (`perception.py`)**: Analyzes the user's query against historical memory hits and the current run history to break the query down into manageable, short, imperative goals. It manages the lifecycle of these goals, tracking what is `[open]` and what is `[done]`.
2. **Decision Layer (`decision.py`)**: Takes the first unfinished goal and determines the best next step. It outputs either a **Final Answer** or selects a specific **Tool Call** (along with arguments) from the available MCP server tools.
3. **Action Layer (`action.py`)**: The execution engine. It interfaces with the local MCP Server to run the requested tools (e.g., `web_search`, `fetch_url`). It stores raw execution outputs in the Artifact Store and handles fallback execution (e.g., using `httpx` for stubborn endpoints).
4. **Memory Layer (`memory.py`)**: A durable state manager that classifies and remembers user preferences and facts. It intelligently recalls past `tool_outcomes` across different runs to prevent redundant MCP tool calls, while using timestamp-awareness to ensure volatile data (like weather) is always fetched fresh.
5. **Artifacts Store (`artifacts.py`)**: A file-based blob storage system utilizing sequential integer IDs to save large blocks of text, web page content, or tool outputs, ensuring the orchestrator's context window isn't blown out.

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- `uv` package manager installed.

### Installation
1. Clone the repository.
2. The project uses `uv` for dependency management. Install dependencies from the `pyproject.toml`:
   ```bash
   uv sync
   ```
3. Set up your `.env` file with necessary API keys (e.g., `GEMINI_API_KEY`).

### Running the Agent
You can run the agent locally by invoking `agent6.py` and passing your query as arguments. The agent will automatically spin up the LLM Gateway if it isn't running.

```bash
uv run python agent6.py "Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date."
```

Alternatively, you can run the provided bash scripts for predefined testing queries:
```bash
bash query1.sh
bash query2.sh
```

## 🛠 Features

- **Model Context Protocol (MCP) Integration**: The action layer dynamically reads available tools from the `mcp_server.py` using the `stdio` client, allowing easy extendability. 
- **LLM Gateway Routing**: All LLM calls pass through `llm_gatewayV3`, which abstracts provider logic and can dynamically route cognitive tasks to different model tiers (Tiny, Large, Huge) based on complexity and tokens.
- **Smart Memory Recall**: The memory layer calculates word-overlap relevance between past tool arguments and the current query. If relevant, it pulls the cached artifact.
- **Time-Awareness**: Both Perception and Decision layers are injected with the `CURRENT SYSTEM TIME` and evaluate memory hit timestamps (`created_at`). This ensures the agent avoids caching time-sensitive data like weather or stock prices.
- **Terminal Execution Logging**: Rich terminal output tracking the agent's internal monologue and communication between layers:
  ```text
  [orchestrator] requesting memory.read()
  [memory]        recalling past tool outcome 'Outcome of web_search' from run b8975dc3
  [orchestrator] passing hits to perception.observe()
  [perception]    [open] Fetch the content...
  [orchestrator] passing goal to decision.next_step()
  [decision]      TOOL_CALL: web_search(...)
  [action]        -> calling MCP server for 'web_search'...
  ```
  
## 🌐 LLM Gateway Architecture

The orchestrator relies on the `llm_gatewayV3` backend for reliable and optimized access to AI models. Key features of the gateway include:

- **Supported Providers**: Natively integrates adapters for 7 providers, allowing seamless swapping and fallback across:
  - `gemini` (Google Generative AI)
  - `nvidia` (Nvidia NIMs)
  - `groq` (High-speed LPU inference)
  - `cerebras` (Wafer-scale high-speed inference)
  - `openrouter` (Model aggregator)
  - `github` (GitHub Models Inference)
  - `ollama` (Local execution for privacy/offline support)

- **Simultaneous Calls & Failover Strategy**: Built on asynchronous Python (FastAPI, `httpx`, `asyncio`), the gateway supports concurrent requests. It implements an automatic failover strategy: if a primary provider hits rate limits (429) or goes offline (503), the gateway instantly triggers a cooldown for that provider and routes the exact same request to the next provider in the fallback tier list, ensuring near-100% uptime for the cognitive agent.

- **Dual-Pool Execution (Worker vs. Router)**:
  - **Router Pool**: Fast, cheap models (e.g., `groq`, `cerebras`) tasked strictly with classifying prompt sizes (TINY, LARGE, HUGE). They output a single word and preserve the rate limits of your more powerful models.
  - **Worker Pool**: Heavy-lifting models (e.g., `gemini`, `openrouter`) tasked with deep reasoning, strictly formatted JSON outputs, and handling massive artifact contexts passed by the memory/action layers.

## 📁 Repository Structure

- `agent6.py` - The core orchestrator orchestrating the loops and iteration limits.
- `action.py`, `artifacts.py`, `decision.py`, `memory.py`, `perception.py` - Cognitive layers.
- `schemas.py` - Pydantic V2 definitions enforcing strict inputs/outputs across layers.
- `client.py` - Custom Python HTTP client to connect to the LLM Gateway.
- `llm_gatewayV3/` - The dedicated FastAPI routing backend.
- `state/` - The auto-generated directory where `gateway.log`, `memory.json`, and `artifacts/` are securely stored.

---
*Built for advanced AI autonomy and stable environment execution.*
