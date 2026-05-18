import json
import uuid
from typing import List

from client import LLM
from schemas import Goal, MemoryItem, Observation

class PerceptionLayer:
    def __init__(self):
        self.llm = LLM()

    def observe(self, query: str, hits: List[MemoryItem], history: List[dict], prior_goals: List[Goal], run_id: str) -> Observation:
        
        import datetime
        now = datetime.datetime.now().isoformat()
        
        # Prepare context for LLM
        hits_context = [{"id": h.id, "kind": h.kind, "descriptor": h.descriptor, "artifact_id": h.artifact_id, "value": h.value, "created_at": h.created_at.isoformat()} for h in hits]
        prior_goals_context = [{"id": g.id, "text": g.text, "done": g.done} for g in prior_goals]
        
        prompt = f"""You are the Perception Layer of an AI agent.
Your task is to manage the goals required to answer the user query.

CURRENT SYSTEM TIME: {now}
USER QUERY: "{query}"

PRIOR GOALS:
{json.dumps(prior_goals_context, indent=2)}

MEMORY HITS (Facts, Preferences, Tool Outcomes):
{json.dumps(hits_context, indent=2)}

RUN HISTORY (Actions and Answers so far):
{json.dumps(history, indent=2)}

INSTRUCTIONS:
1. If PRIOR GOALS is empty, decompose the USER QUERY into one or more bounded goals. Each goal must be a short imperative statement.
2. If PRIOR GOALS is not empty, preserve the exact same goals in the exact same order. Do not drop or reorder them.
3. For each goal, examine the RUN HISTORY. If the history contains an action or answer that satisfies the goal, mark it as `done: true`. Once done, it must remain done.
4. For the FIRST unfinished goal ONLY, look at MEMORY HITS. If answering the goal requires reading the raw bytes of a previously fetched artifact, set `attach_artifact_id` to the `artifact_id` from the relevant Memory Hit.
   IMPORTANT: Check `created_at`. If the goal involves highly volatile or time-sensitive data (e.g. weather, live scores) and the memory hit is outdated, DO NOT attach its artifact. For stable facts, old memory hits are fine to reuse.

Output a JSON object matching this schema exactly:
{{
    "goals": [
        {{
            "id": "string (generate short uuid if new, else keep existing)",
            "text": "short imperative description",
            "done": boolean,
            "attach_artifact_id": "string or null"
        }}
    ]
}}
"""
        
        res = self.llm.chat(
            prompt=prompt,
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        data = json.loads(res["text"])
        
        # Print perception logs
        print("[perception]", end="")
        first = True
        for g in data.get("goals", []):
            status = "[done]" if g.get("done") else "[open]"
            pad = "    " if first else "                "
            print(f"{pad}{status} {g.get('text')}")
            first = False
            
        return Observation(**data)

perception = PerceptionLayer()
