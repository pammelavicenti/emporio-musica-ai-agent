from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emporio_agent.repository import normalize_text


class PolicyStore:
    """Keyword retrieval over a small, reviewed extraction of the policy PDF."""

    def __init__(self, policy_file: Path):
        self.policy_file = Path(policy_file)
        try:
            self.sections = json.loads(self.policy_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Could not load the policy knowledge base.") from exc

    def search(self, query: str, limit: int = 4) -> dict[str, Any]:
        terms = [term for term in normalize_text(query).split() if len(term) > 2]
        scored: list[tuple[int, dict[str, Any]]] = []
        for section in self.sections:
            title = normalize_text(section["title"])
            content = normalize_text(section["content"])
            keywords = [normalize_text(word) for word in section["keywords"]]
            score = 0
            for term in terms:
                if any(term in keyword or keyword in term for keyword in keywords):
                    score += 6
                if term in title:
                    score += 3
                if term in content:
                    score += 1
            if score:
                scored.append((score, section))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["page"], pair[1]["id"]))
        if not scored:
            return {
                "status": "no_results",
                "message": "No relevant policy section was found.",
                "sections": [],
            }
        return {
            "status": "ok",
            "sections": [section for _, section in scored[:limit]],
            "source": "data/políticas_da_loja.pdf",
        }

