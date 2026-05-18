import json
from typing import List, Tuple
from client import LLM
from schemas import DecisionOutput, Goal, MemoryItem

class DecisionLayer:
    def __init__(self):
        self.llm = LLM()

    def next_step(self, goal: Goal, hits: List[MemoryItem], attached: List[Tuple[str, bytes]], history: List[dict], mcp_tools: List[dict]) -> DecisionOutput:
        
        # Prepare context
        attached_context = ""
        if attached:
            attached_context = "ATTACHED ARTIFACT CONTENT (RAW BYTES):\n"
            for art_id, b in attached:
                # We try to decode as string for the LLM prompt.
                # If it's an image, this would be an issue, but the assignment focuses on text/markdown
                text_content = b.decode("utf-8", errors="replace")
                # Truncate to avoid blowing up context, but keep it large enough
                if len(text_content) > 30000:
                    text_content = text_content[:30000] + "... [TRUNCATED]"
                attached_context += f"--- Artifact {art_id} ---\n{text_content}\n\n"

        import datetime
        now = datetime.datetime.now().isoformat()
        
        hits_context = [{"id": h.id, "kind": h.kind, "descriptor": h.descriptor, "value": h.value, "created_at": h.created_at.isoformat()} for h in hits]
        
        prompt = f"""You are the Decision Layer of an AI agent.
Your current goal is to execute the following task:
GOAL: "{goal.text}"

CURRENT SYSTEM TIME: {now}

You must either:
1. Provide a final ANSWER that satisfies the goal.
2. Select ONE tool to call to gather more information or perform an action to get closer to the goal.

AVAILABLE TOOLS:
{json.dumps(mcp_tools, indent=2)}

MEMORY HITS:
{json.dumps(hits_context, indent=2)}

RUN HISTORY:
{json.dumps(history, indent=2)}

{attached_context}

INSTRUCTIONS:
IMPORTANT: Check the `created_at` timestamp in MEMORY HITS. If the goal requires real-time or time-sensitive information (like weather or live events) and the memory hit is outdated, DO NOT use it to provide an answer. Instead, call a tool to fetch fresh information. For stable facts, old memory hits are fine to reuse.
Output a JSON object matching this schema exactly. Provide either an 'answer' or a 'tool_call', but not both.
{{
    "answer": "string or null",
    "tool_call": {{
        "name": "tool_name",
        "arguments": {{"arg1": "value1"}}
    }} or null
}}
"""
        
        res = self.llm.chat(
            prompt=prompt,
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        data = json.loads(res["text"])
        
        output = DecisionOutput(**data)
        
        # Log decision
        if output.tool_call:
            # truncate args for display
            args_str = json.dumps(output.tool_call.arguments)
            if len(args_str) > 50:
                args_str = args_str[:47] + "..."
            print(f"[decision]      TOOL_CALL: {output.tool_call.name}({args_str})")
        elif output.answer:
            ans_str = output.answer.replace('\n', '\n                ')
            print(f"[decision]      ANSWER: {ans_str}")
            
        return output

decision = DecisionLayer()
