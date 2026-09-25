"""Capability Models and Semantic Data Contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.tools.base import RiskLevel


class CapabilityCategory(StrEnum):
    SYSTEM = "SYSTEM"
    APP = "APP"
    WINDOWS = "WINDOWS"
    BROWSER = "BROWSER"
    FILE = "FILE"
    RAG = "RAG"
    PHONE = "PHONE"
    WHATSAPP = "WHATSAPP"
    GOOGLE = "GOOGLE"
    WORKFLOW = "WORKFLOW"
    TERMINAL = "TERMINAL"
    HARDWARE = "HARDWARE"


class CostTier(StrEnum):
    FREE = "FREE"            # Local Win32 / OS API / Fast in-memory (< 2 ms)
    LOW = "LOW"              # Local SQLite FTS5 / file metadata / quick shell (< 50 ms)
    MEDIUM = "MEDIUM"        # Local Faster-Whisper / Piper TTS / Playwright action (< 500 ms)
    EXPENSIVE = "EXPENSIVE"  # Local LLM generation / heavy OCR / video processing (> 500 ms)


class CapabilityDefinition(BaseModel):
    """Semantic specification of an atomic capability in JARVIS."""

    id: str = Field(..., description="Unique slug for the capability, e.g. 'app.open'")
    category: CapabilityCategory = Field(..., description="High-level capability domain")
    description: str = Field(..., description="Clear human and LLM-facing explanation of what this does")
    keywords: List[str] = Field(default_factory=list, description="Semantic anchors for retrieval")
    examples: List[str] = Field(default_factory=list, description="Natural language phrases triggering this capability")
    counterexamples: List[str] = Field(default_factory=list, description="Phrases that sound similar but must NOT trigger this")
    preconditions: List[str] = Field(default_factory=list, description="Required state before execution")
    required_slots: List[str] = Field(default_factory=list, description="Mandatory slot keys required to execute")
    optional_slots: List[str] = Field(default_factory=list, description="Optional modifier parameters")
    risk_level: RiskLevel = Field(default=RiskLevel.READ_ONLY, description="Phase 5 risk classification")
    target_tool: str = Field(..., description="Corresponding tool name in ToolRegistry")
    verifier: str = Field(default="", description="Key of the verifier strategy in VerifierMap")
    recovery_methods: List[str] = Field(default_factory=list, description="Fallback methods: NATIVE, POWERSHELL, UIA, VISION")
    availability_check: Optional[str] = Field(default=None, description="Identifier of runtime check or boolean state")
    dependencies: List[str] = Field(default_factory=list, description="System or software dependencies (e.g. adb, playwright)")
    cost_tier: CostTier = Field(default=CostTier.FREE, description="Resource cost tier")
    family: str = Field(default="", description="Logical capability family, e.g. 'FILE', 'APP', 'BROWSER', 'PHONE', 'SYSTEM', 'WHATSAPP', 'RAG'")
    input_resource_types: List[str] = Field(default_factory=list, description="Accepted resource types, e.g. ['FileResource']")
    output_resource_types: List[str] = Field(default_factory=list, description="Produced resource types, e.g. ['FileResource']")

    def get_family(self) -> str:
        if self.family:
            return self.family.upper()
        parts = self.id.split(".")
        if len(parts) >= 2:
            prefix = parts[0].upper()
            if prefix == "WINDOWS":
                return "SYSTEM"
            return prefix
        return self.category.value

    model_config = {"arbitrary_types_allowed": True}
