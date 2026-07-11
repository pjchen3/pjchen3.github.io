from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import CacheEntry, PaperAnalysis


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class AnalysisCache:
    def __init__(self, directory: Path, fingerprint: str):
        self.directory = directory
        self.fingerprint = fingerprint
        directory.mkdir(parents=True, exist_ok=True)

    def _path(self, digest: str) -> Path:
        return self.directory / f"{digest}.json"

    def load(self, path: Path) -> PaperAnalysis | None:
        digest = file_hash(path)
        cache_path = self._path(digest)
        if not cache_path.exists():
            return None
        try:
            entry = CacheEntry.model_validate_json(cache_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if entry.file_hash != digest or entry.fingerprint != self.fingerprint:
            return None
        return entry.paper

    def store(self, path: Path, paper: PaperAnalysis) -> None:
        digest = file_hash(path)
        entry = CacheEntry(file_hash=digest, fingerprint=self.fingerprint, paper=paper)
        self._path(digest).write_text(entry.model_dump_json(indent=2), encoding="utf-8")

