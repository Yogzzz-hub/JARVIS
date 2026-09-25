from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from pydantic import Field
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition


class DocumentQAInput(Contract):
    document_path: str = Field(min_length=1, max_length=4096)
    question: str = Field(min_length=1, max_length=1024)


class Citation(Contract):
    source_path: str
    section: str
    line_number: int
    excerpt: str


class DocumentQAOutput(Contract):
    answer: str
    citations: tuple[Citation, ...]
    abstained: bool
    confidence: float


class DocumentQATool(Tool):
    definition = ToolDefinition(
        name="document_qa",
        description="Answers questions across local documents with explicit line/section citations. Abstains when evidence is insufficient.",
        input_model=DocumentQAInput,
        output_model=DocumentQAOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=15.0,
        tags=("document", "qa", "f09"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: DocumentQAInput) -> dict[str, Any]:
        p = Path(arguments.document_path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"Document '{arguments.document_path}' not found.")

        # Read content safely
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as exc:
            raise RuntimeError(f"Failed to read document {p}: {exc}")

        # Extract keywords from question
        q_words = {w.lower() for w in re.findall(r"\w+", arguments.question) if len(w) > 2}
        citations: list[Citation] = []
        best_matches: list[tuple[int, str, float]] = []

        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            line_words = {w.lower() for w in re.findall(r"\w+", line_str)}
            overlap = len(q_words & line_words)
            if overlap > 0:
                score = overlap / max(len(q_words), 1)
                best_matches.append((idx, line_str, score))

        best_matches.sort(key=lambda x: x[2], reverse=True)

        # Abstain if evidence is below threshold
        if not best_matches or best_matches[0][2] < 0.2:
            return {
                "answer": "I cannot answer based on the provided document because the source text does not contain sufficient relevant evidence.",
                "citations": (),
                "abstained": True,
                "confidence": 0.0,
            }

        top_matches = best_matches[:3]
        for line_no, content, score in top_matches:
            citations.append(
                Citation(
                    source_path=str(p),
                    section=f"Line {line_no}",
                    line_number=line_no,
                    excerpt=content[:200],
                )
            )

        grounded_answer = f"According to {p.name}: " + " ".join(c.excerpt for c in citations[:2])
        return {
            "answer": grounded_answer,
            "citations": tuple(citations),
            "abstained": False,
            "confidence": min(top_matches[0][2], 1.0),
        }
