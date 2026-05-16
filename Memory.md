/*
Reference Projects:
D:\Projects\EAGv3\

Foundation Project to use Pydantic at MCP client and multiple LLM models to route and handle failovers
D:\Projects\EAGv3\s5_2\llm_gatewayV2

LLM_gateway should be taken latest reference from & MCP server directly frm path
D:\Projects\EAGv3\s6

Constraints\:
Pydantic v2 on every boundary.
uv for Python dependency management and execution. No manual virtualenv activation.
MCP server stdio transport for tool calls. No reimplementing tool dispatch.
No third-party agentic frameworks (LangGraph, LangChain, CrewAI). The architecture and the contracts are the assignment.

Required:
Four code modules with clear separation of concerns: memory.py, perception.py, decision.py, action.py. Plus an agent6.py (or any name) that wires them together in a loop. Plus a schemas.py containing the Pydantic models. Plus the MCP server from earlier sessions.
All four target queries must produce correct final answers. The expected answers and iteration counts are documented above. Queries that exceed twice the expected iteration count are not considered passing; tune the prompts and the contracts until convergence is within bounds.
Memory must persist across runs in a file under state/. Query C requires the durable-memory behaviour: run 1 records the fact, run 2 reads it.
The four cognitive layers must each be backed by typed Pydantic contracts on their inputs and outputs. No free-form dict passing between roles. No regex on LLM output.
The LLM gateway V3 must be the substrate for every LLM call. No direct calls to provider SDKs.
The state/ directory must be cleanable between assignment attempts.

##########

Agentic Orchestratin loop Reference code:

async def run(query: str) -> str:
    ensure_gateway()
    run_id = uuid.uuid4().hex[:8]
    history: list[dict] = []
    prior_goals: list[Goal] = []

    # Durable memory: classify the user's query so facts/preferences
    # in it survive into future runs.
    memory.remember(query, source="user_query", run_id=run_id)

    async with mcp_session() as session:
        mcp_tools = await load_tools(session)
        tools = mcp_tools_for_decision(mcp_tools)

        for it in range(1, MAX_ITERATIONS + 1):
            hits = memory.read(query, history)
            obs = perception.observe(query, hits, history, prior_goals, run_id)
            prior_goals = obs.goals
            if obs.all_done:
                break

            goal = obs.next_unfinished()
            attached = []
            if goal.attach_artifact_id and artifacts.exists(goal.attach_artifact_id):
                attached.append((
                    goal.attach_artifact_id,
                    artifacts.get_bytes(goal.attach_artifact_id),
                ))

            out = decision.next_step(goal, hits, attached, history, tools)

            if out.is_answer:
                history.append({"iter": it, "kind": "answer",
                                "goal_id": goal.id, "text": out.answer})
                continue

            result_text, art_id = await action.execute(session, out.tool_call)
            memory.record_outcome(
                tool_call=out.tool_call,
                result_text=result_text,
                artifact_id=art_id,
                run_id=run_id,
                goal_id=goal.id,
            )
            history.append({"iter": it, "kind": "action",
                            "goal_id": goal.id, "tool": out.tool_call.name,
                            "arguments": out.tool_call.arguments,
                            "result_descriptor": result_text[:300],
                            "artifact_id": art_id})

    return final_answer_from(history)

############
4 roles in MCP client
           ┌──────────────────────────────────────────────────────┐
            │                                                      │
  Memory ◄──┤ holds the handle string ("art:abc...") inside        │
            │ MemoryItem.artifact_id                               │
            │                                                      │
  Perception ◄ sees the handle in MEMORY HITS, never the bytes     │
            │                                                      │
  Decision ◄  sees the bytes only when Perception attaches them    │
            │ to the prompt for the current goal                   │
            │                                                      │
  Action  ◄── produces bytes (writes them via ArtifactStore.put)   │
            │                                                      │
            └──────────────────────────────────────────────────────┘

Agent flow must be refer from 
D:\Projects\AssignmentS6WebProject\flow.webp

Perception role:
1. If the prior goal list is empty, decompose the query into one or more
   bounded goals, each a short imperative statement.

2. For each prior goal, examine the run history. Mark the goal `done: true`
   the moment the history contains an action that satisfies it. Once done,
   the goal remains done in every subsequent iteration.

3. For the first unfinished goal in the list, decide whether it needs raw
   bytes from a previously fetched artifact. If yes, set the goal's
   attach_artifact_id to one of the artifact handles in MEMORY HITS.

4. Preserve goal order. Do not reorder, do not insert in the middle, do
   not drop a goal.

Decision - It returns a DecisionOutput containing either a final answer in plain text or a single typed ToolCall. Decision does not pick more than one tool and does not narrate.
def next_step(
    goal: Goal,
    hits: list[MemoryItem],
    attached: list[tuple[str, bytes]],
    history: list[dict],
    mcp_tools: list[dict],
) -> DecisionOutput: ...

Actin - Pure Dispatch
 It receives a ToolCall and a live MCP session, dispatches the call, and returns a tuple of (descriptor, artifact_id_or_None).
 async def execute(
    session: ClientSession,
    tool_call: ToolCall,
) -> tuple[str, str | None]: ...

#####################

schema.py
class MemoryItem(BaseModel):
    id: str
    kind: Literal["fact", "preference", "tool_outcome", "scratchpad"]
    keywords: list[str]
    descriptor: str            # one short human-readable line
    value: dict                # structured payload
    artifact_id: str | None    # handle into the artifact store
    source: str
    run_id: str
    goal_id: str | None
    confidence: float
    created_at: datetime


class Artifact(BaseModel):
    id: str                    # "art:<sha256-prefix>"
    content_type: str
    size_bytes: int
    source: str
    descriptor: str


class Goal(BaseModel):
    id: str
    text: str                  # short imperative description
    done: bool
    attach_artifact_id: str | None


class Observation(BaseModel):
    goals: list[Goal]


class ToolCall(BaseModel):
    name: str
    arguments: dict


class DecisionOutput(BaseModel):
    answer: str | None         # exactly one of these two is populated
    tool_call: ToolCall | None

class ArtifactStore:
    def put(self, blob: bytes, *,
            content_type: str, source: str, descriptor: str) -> str: ...
    def get_bytes(self, artifact_id: str) -> bytes: ...
    def get_meta(self, artifact_id: str) -> Artifact: ...
    def exists(self, artifact_id: str) -> bool: ...

####################

Query 1 REF logs to be added:
─── iter 1 ───
[perception]    [open] Find 3 family-friendly things to do in Tokyo
                [open] Check Saturday's weather in Tokyo
                [open] Choose the most appropriate activity given the weather
[decision]      TOOL_CALL: web_search({"query": "family-friendly things to do in Tokyo this weekend"})
[action]        → [3 results returned, descriptors recorded]

─── iter 2 ───
[perception]    [done] Find 3 family-friendly things to do in Tokyo
                [open] Check Saturday's weather in Tokyo
                [open] Choose the most appropriate activity given the weather
[decision]      TOOL_CALL: fetch_url({"url": "https://wttr.in/Tokyo?format=...&Saturday"})
[action]        → Saturday forecast: patchy rain, 18C

─── iter 3 ───
[perception]    [done] Find 3 family-friendly things to do in Tokyo
                [done] Check Saturday's weather in Tokyo
                [open] Choose the most appropriate activity given the weather
[decision]      ANSWER: Given Saturday's patchy rain forecast, an indoor
                activity is recommended. From the three options found
                (Ueno Zoo, Tsukiji Outer Market sushi class, Tokyo Skytree),
                the Tsukiji sushi class is most appropriate because it is
                fully indoors and family-oriented.

[done] all 3 goals satisfied


###############
Query 2 REF logs to be added:
─── iter 1 ───
[perception]    [open] Find 3 family-friendly things to do in Tokyo
                [open] Check Saturday's weather in Tokyo
                [open] Choose the most appropriate activity given the weather
[decision]      TOOL_CALL: web_search({"query": "family-friendly things to do in Tokyo this weekend"})
[action]        → [3 results returned, descriptors recorded]

─── iter 2 ───
[perception]    [done] Find 3 family-friendly things to do in Tokyo
                [open] Check Saturday's weather in Tokyo
                [open] Choose the most appropriate activity given the weather
[decision]      TOOL_CALL: fetch_url({"url": "https://wttr.in/Tokyo?format=...&Saturday"})
[action]        → Saturday forecast: patchy rain, 18C

─── iter 3 ───
[perception]    [done] Find 3 family-friendly things to do in Tokyo
                [done] Check Saturday's weather in Tokyo
                [open] Choose the most appropriate activity given the weather
[decision]      ANSWER: Given Saturday's patchy rain forecast, an indoor
                activity is recommended. From the three options found
                (Ueno Zoo, Tsukiji Outer Market sushi class, Tokyo Skytree),
                the Tsukiji sushi class is most appropriate because it is
                fully indoors and family-oriented.

[done] all 3 goals satisfied

####################
Query 3 REF logs to be added:
[memory.remember]  classified "Mom's birthday is 15 May 2026" as fact
                   keywords: ["mom", "birthday", "may", "2026"]

─── iter 1 ───
[perception]    [open] Remember mom's birthday (15 May 2026)
                [open] Create a reminder for 1 May 2026 (two weeks before)
                [open] Create a reminder for 15 May 2026
[decision]      TOOL_CALL: create_file({"path": "reminders/mom_birthday_2026.txt", ...})
[action]        → ok

... two more iterations creating the reminders ...

FINAL: Reminders created. Mom's birthday on 15 May 2026 is recorded.

*/