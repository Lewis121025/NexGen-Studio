"""Artifact storage abstraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import settings


class ArtifactStorage:
    """Basic local storage layer that mimics S3 semantics."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("artifacts")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, *parts: str) -> Path:
        path = self.root.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def save_text(self, relative_path: str, content: str) -> str:
        path = self._path(relative_path)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def save_json(self, relative_path: str, data: Any) -> str:
        content = json.dumps(data, indent=2, ensure_ascii=False)
        return self.save_text(relative_path, content)

    def save_bytes(self, relative_path: str, payload: bytes) -> str:
        path = self._path(relative_path)
        path.write_bytes(payload)
        return str(path)


default_storage = ArtifactStorage(settings.sandbox.working_directory / "artifacts")

