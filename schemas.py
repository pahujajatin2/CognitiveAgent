from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel


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

    def next_unfinished(self) -> Goal | None:
        for g in self.goals:
            if not g.done:
                return g
        return None

    @property
    def all_done(self) -> bool:
        return all(g.done for g in self.goals)


class ToolCall(BaseModel):
    name: str
    arguments: dict


class DecisionOutput(BaseModel):
    answer: str | None = None         # exactly one of these two is populated
    tool_call: ToolCall | None = None


class ArtifactStore:
    def put(self, blob: bytes, *,
            content_type: str, source: str, descriptor: str) -> str:
        raise NotImplementedError

    def get_bytes(self, artifact_id: str) -> bytes:
        raise NotImplementedError

    def get_meta(self, artifact_id: str) -> Artifact:
        raise NotImplementedError

    def exists(self, artifact_id: str) -> bool:
        raise NotImplementedError
