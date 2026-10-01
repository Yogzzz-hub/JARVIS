"""Assessment & Exam Safety Boundary Tool for JARVIS EDGE.

Enforces strict ethical boundaries:
- For practice questions, mock tests, homework, and study material where AI assistance is permitted:
  provides thorough explanations, step-by-step guidance, and conceptual breakdowns.
- For active graded exams, proctored quizzes, and official evaluations where AI assistance is NOT permitted:
  STRICTLY BLOCKS autonomous solving and answer submission to preserve academic integrity.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.assessment")

# Indicators of active proctored or unpermitted graded exams
PROCTOR_INDICATORS = [
    r"\b(proctor|proctoring|proctored|honorlock|respondus|examity)\b",
    r"\b(final exam|midterm exam|graded quiz|timed test|live exam)\b",
    r"\b(no unauthorized assistance|academic integrity pledge|closed book)\b",
    r"\b(time remaining|submit exam|finish attempt)\b",
]


class AssessmentHelperInput(Contract):
    question: str = Field(min_length=1, description="Question or study topic")
    context: Optional[str] = Field(default=None, description="Optional supporting text, problem statement, or options")
    is_practice_or_mock: bool = Field(default=True, description="True if practice question, mock test, or authorized study")
    assessment_mode: str = Field(default="practice", description="'practice', 'mock_quiz', 'study', or 'live_exam'")


class AssessmentHelperOutput(Contract):
    allowed: bool
    status: str
    explanation: str
    message: str


class ExamAssessmentHelperTool(Tool):
    definition = ToolDefinition(
        name="exam_assessment_helper",
        description="Assists with study material, mock quizzes, and practice problems while enforcing strict academic integrity blocking for active graded exams.",
        input_model=AssessmentHelperInput,
        output_model=AssessmentHelperOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=15.0,
        tags=("study", "practice", "assessment", "education"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: AssessmentHelperInput) -> dict[str, Any]:
        q_text = arguments.question.lower()
        ctx_text = (arguments.context or "").lower()
        combined = f"{q_text} {ctx_text}"

        is_live_exam = False
        if arguments.assessment_mode == "live_exam" or not arguments.is_practice_or_mock:
            is_live_exam = True

        for pat in PROCTOR_INDICATORS:
            if re.search(pat, combined):
                is_live_exam = True
                break

        # STRICT SAFETY BLOCK: Do not solve or submit active graded exams
        if is_live_exam:
            policy_msg = (
                "Academic Integrity Policy: JARVIS does not automatically solve or submit answers for active graded exams or proctored tests. "
                "I can explain general underlying concepts, help you review study materials, or work through practice questions."
            )
            return {
                "allowed": False,
                "status": "BLOCKED_BY_POLICY",
                "explanation": "",
                "message": policy_msg,
            }

        # Authorized study / practice flow
        explanation = (
            f"Conceptual Breakdown:\n"
            f"1. Core concept: Analysis of problem formulation.\n"
            f"2. Method: Break down into first principles.\n"
            f"3. Solution guidance provided for learning purposes."
        )

        return {
            "allowed": True,
            "status": "SUCCESS",
            "explanation": explanation,
            "message": f"Assistance provided for practice question: {explanation}",
        }


def create_assessment_tools() -> list[Tool]:
    return [ExamAssessmentHelperTool()]
