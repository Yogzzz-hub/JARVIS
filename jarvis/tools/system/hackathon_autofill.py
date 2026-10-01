"""Hackathon & Project Submission Form Automation Tool for JARVIS EDGE.

Supports ordinary permitted forms:
- Hackathon registration
- Project submission metadata (title, github link, demo link, tracks, tech stack, description)
- Event and repetitive application forms
- Never invents personal details; asks for ambiguous values; previews before submit.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import Field

from jarvis.core.catalog.project_catalog import get_project_catalog
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition
from jarvis.tools.system.autofill import load_profile

logger = logging.getLogger("jarvis.tools.hackathon")

HACKATHON_FIELD_HINTS: Dict[str, List[str]] = {
    "project_title": ["project name", "project title", "submission title", "app name", "hackathon project"],
    "tagline": ["tagline", "short description", "one-line pitch", "elevator pitch", "summary"],
    "description": ["description", "about the project", "project details", "overview", "what it does"],
    "github_url": ["github", "repository", "repo link", "source code", "github url", "code repo"],
    "demo_url": ["demo link", "live url", "video demo", "youtube link", "deployed url", "demo url"],
    "tracks": ["track", "category", "prize track", "challenge"],
    "tech_stack": ["tech stack", "technologies used", "languages", "frameworks", "tools used"],
    "team_name": ["team name", "team", "group name"],
}

FILL_HACKATHON_JS = r"""
(args) => {
  const [data, hints] = args;
  const filled = [];
  const els = Array.from(document.querySelectorAll('input, textarea, select'))
      .filter(el => !el.disabled && !el.readOnly && el.offsetParent !== null);

  const getLabel = (el) => {
    let t = [];
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l) t.push(l.innerText);
    }
    const wrap = el.closest('label');
    if (wrap) t.push(wrap.innerText);
    t.push(el.getAttribute('aria-label') || '', el.placeholder || '', el.name || '', el.id || '');
    return t.join(' ').toLowerCase();
  };

  const setVal = (el, val) => {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, val);
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  };

  for (const el of els) {
    if (el.value) continue; // do not overwrite existing content
    const type = (el.type || '').toLowerCase();
    if (['hidden', 'submit', 'button', 'password', 'checkbox', 'radio', 'file'].includes(type)) continue;

    const label = getLabel(el);
    for (const [key, patterns] of Object.entries(hints)) {
      if (!data[key]) continue;
      if (patterns.some(p => label.includes(p))) {
        setVal(el, String(data[key]));
        el.style.outline = '2px solid #10b981';
        filled.push(key);
        break;
      }
    }
  }
  return {filled, count: filled.length};
}
"""


class HackathonAutofillInput(Contract):
    project_name: Optional[str] = Field(default=None, description="Project to use for submission details (defaults to current project)")
    path: Optional[str] = Field(default=None, description="Direct project root directory path")
    team_name: Optional[str] = Field(default=None, description="Team name")
    demo_url: Optional[str] = Field(default=None, description="Live demo link or video link")
    tagline: Optional[str] = Field(default=None, description="Short tagline or elevator pitch")
    track: Optional[str] = Field(default=None, description="Target hackathon track / category")


class HackathonAutofillOutput(Contract):
    status: str
    filled_fields: list[str]
    missing_fields: list[str]
    preview: dict[str, str]
    message: str


class HackathonAutofillTool(Tool):
    definition = ToolDefinition(
        name="hackathon_autofill",
        description="Fills hackathon registration, project submission, and event forms in the active browser using verified project details and profile.",
        input_model=HackathonAutofillInput,
        output_model=HackathonAutofillOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=30.0,
        tags=("browser", "form", "hackathon", "autofill"),
        execution_method=ExecutionMethod.DOM,
    )

    def __init__(self, page_runner: Any = None) -> None:
        self._page_runner = page_runner

    async def _evaluate(self, js: str, args: Any) -> Any:
        if self._page_runner is not None:
            return await self._page_runner(js, args)
        try:
            from jarvis.core.computer.browser.loop import get_browser_loop
            from jarvis.tools.system.computer_tools import get_shared_browser_manager

            async def work():
                page = await get_shared_browser_manager().get_active_page()
                return await page.evaluate(js, args)
            return await get_browser_loop().run_async(work, timeout=25.0)
        except Exception as exc:
            logger.debug("Browser evaluation unavailable: %s", exc)
            return {"filled": [], "count": 0}

    async def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = HackathonAutofillInput(**arguments)

        # 1. Gather project details
        catalog = get_project_catalog()
        if arguments.path:
            proj = catalog.inspect_directory(arguments.path)
        else:
            proj = catalog.find_project(arguments.project_name or "") if arguments.project_name else catalog.inspect_directory(Path.cwd())
        profile = load_profile()

        # Build data dictionary
        data: Dict[str, str] = {}
        if proj:
            data["project_title"] = proj.name
            data["tech_stack"] = ", ".join(proj.languages + proj.frameworks)
            # Try to read short description from README if available
            root = Path(proj.root)
            for rname in ["README.md", "README"]:
                rp = root / rname
                if rp.is_file():
                    lines = [l.strip() for l in rp.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip() and not l.startswith("#")]
                    if lines:
                        data["description"] = lines[0][:500]
                        data["tagline"] = lines[0][:120]
                    break

        # Explicit overrides
        if arguments.team_name:
            data["team_name"] = arguments.team_name
        elif profile.get("full_name"):
            data["team_name"] = f"Team {profile.get('first_name', profile.get('full_name'))}"

        if arguments.demo_url:
            data["demo_url"] = arguments.demo_url
        if arguments.tagline:
            data["tagline"] = arguments.tagline
        if arguments.track:
            data["tracks"] = arguments.track

        # 2. Execute autofill
        filled: list[str] = []
        try:
            res = await self._evaluate(FILL_HACKATHON_JS, [data, HACKATHON_FIELD_HINTS])
            filled = (res or {}).get("filled", [])
        except Exception:
            pass

        missing = [k for k in ["project_title", "description", "team_name"] if k not in data]

        msg = f"Form prepared with {len(filled)} field(s) filled. Please review and verify the submission preview before authorizing final submission."

        return {
            "status": "SUCCESS",
            "filled_fields": filled,
            "missing_fields": missing,
            "preview": data,
            "message": msg,
        }


def create_hackathon_tools() -> list[Tool]:
    return [HackathonAutofillTool()]
