import hashlib
import json
import os
from pathlib import Path
from schemas import Artifact, ArtifactStore

STATE_DIR = Path("state")
ARTIFACTS_DIR = STATE_DIR / "artifacts"

class LocalArtifactStore(ArtifactStore):
    def __init__(self):
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        self.counter_path = ARTIFACTS_DIR / "counter.txt"

    def _get_next_id(self) -> int:
        if self.counter_path.exists():
            count = int(self.counter_path.read_text(encoding="utf-8"))
        else:
            count = 0
        count += 1
        self.counter_path.write_text(str(count), encoding="utf-8")
        return count

    def put(self, blob: bytes, *, content_type: str, source: str, descriptor: str) -> str:
        art_id = str(self._get_next_id())
        
        art_dir = ARTIFACTS_DIR / art_id
        os.makedirs(art_dir, exist_ok=True)
        
        data_path = art_dir / "data.bin"
        meta_path = art_dir / "meta.json"
        
        data_path.write_bytes(blob)
        
        artifact = Artifact(
            id=art_id,
            content_type=content_type,
            size_bytes=len(blob),
            source=source,
            descriptor=descriptor
        )
        
        meta_path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
        print(f"[artifact]      saved artifact {art_id} (size: {len(blob)} bytes)")
        return art_id

    def get_bytes(self, artifact_id: str) -> bytes:
        art_dir = ARTIFACTS_DIR / artifact_id
        data_path = art_dir / "data.bin"
        if not data_path.exists():
            raise FileNotFoundError(f"Artifact {artifact_id} not found")
        print(f"[artifact]      read artifact {artifact_id}")
        return data_path.read_bytes()

    def get_meta(self, artifact_id: str) -> Artifact:
        art_dir = ARTIFACTS_DIR / artifact_id
        meta_path = art_dir / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Artifact meta {artifact_id} not found")
        return Artifact.model_validate_json(meta_path.read_text(encoding="utf-8"))

    def exists(self, artifact_id: str) -> bool:
        if not artifact_id:
            return False
        art_dir = ARTIFACTS_DIR / artifact_id
        return art_dir.exists()

# Global instance
artifacts = LocalArtifactStore()
