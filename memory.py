import json
import os
import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from schemas import MemoryItem, ToolCall
from client import LLM

STATE_DIR = "state"
MEMORY_FILE = os.path.join(STATE_DIR, "memory.json")

class MemoryClassifierOutput(BaseModel):
    is_fact_or_preference: bool
    kind: str = Field(description="'fact' or 'preference', or 'none'")
    keywords: list[str] = Field(default_factory=list)
    descriptor: str = Field(description="one short human-readable line summarising the fact/preference")

class MemoryStore:
    def __init__(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.items: list[MemoryItem] = []
        self._load()
        self.llm = LLM()

    def _load(self):
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    self.items = [MemoryItem.model_validate(item) for item in data]
                except Exception:
                    self.items = []

    def _save(self):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump([item.model_dump(mode="json") for item in self.items], f, indent=2)

    def remember(self, query: str, source: str, run_id: str):
        # Classify if the query contains a fact or preference
        prompt = f"""Analyze the following user query:
"{query}"

Does it contain a fact (e.g. "My mom's birthday is 15 May 2026") or a preference (e.g. "I like dark mode") that should be remembered for future runs?
Respond with JSON matching this schema:
{{
  "is_fact_or_preference": bool,
  "kind": "fact" | "preference" | "none",
  "keywords": ["list", "of", "keywords"],
  "descriptor": "Short human readable line"
}}
"""
        try:
            res = self.llm.chat(
                prompt=prompt,
                response_format={"type": "json_object"},
                temperature=0.0
            )
            data = json.loads(res["text"])
            output = MemoryClassifierOutput(**data)
            
            if output.is_fact_or_preference and output.kind in ["fact", "preference"]:
                item = MemoryItem(
                    id=uuid.uuid4().hex,
                    kind=output.kind,
                    keywords=output.keywords,
                    descriptor=output.descriptor,
                    value={"query": query},
                    artifact_id=None,
                    source=source,
                    run_id=run_id,
                    goal_id=None,
                    confidence=1.0,
                    created_at=datetime.utcnow()
                )
                self.items.append(item)
                self._save()
                print(f"[memory.remember]  classified \"{output.descriptor}\" as {output.kind}")
                print(f"                   keywords: {output.keywords}")
        except Exception as e:
            print(f"[memory.remember] error classifying query: {e}")

    def read(self, query: str, history: list[dict]) -> list[MemoryItem]:
        # For simplicity, return all facts and preferences, and tool_outcomes from the current run
        current_run_items = [
            item for item in self.items
            if item.kind in ["fact", "preference"]
        ]
        
        # Add relevant tool outcomes
        # In a real system, we might use embeddings or keyword matching
        # Here we just return recent tool outcomes to give context
        for item in self.items:
            if item.kind == "tool_outcome":
                # Usually tool outcomes are bound to the current run
                current_run_items.append(item)
                
        return current_run_items

    def record_outcome(self, tool_call: ToolCall, result_text: str, artifact_id: str | None, run_id: str, goal_id: str):
        item = MemoryItem(
            id=uuid.uuid4().hex,
            kind="tool_outcome",
            keywords=[tool_call.name],
            descriptor=f"Outcome of {tool_call.name}",
            value={"arguments": tool_call.arguments, "result_text_snippet": result_text[:200]},
            artifact_id=artifact_id,
            source="action",
            run_id=run_id,
            goal_id=goal_id,
            confidence=1.0,
            created_at=datetime.utcnow()
        )
        self.items.append(item)
        # It's debatable whether tool outcomes should be saved to durable storage across runs
        # We will save them so that `read()` can return handles (artifact_id) to Perception.
        self._save()

# Global instance
memory = MemoryStore()
