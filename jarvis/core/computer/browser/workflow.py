"""Bounded observe/act/verify workflows over existing Playwright components.

Experimental. Browser plans are declarative data, not Python/JS. Mutating
controls pause for the existing owner confirmation path; this runner never
accepts a boolean "approved" supplied by a model or page.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4
import weakref

from pydantic import BaseModel, ConfigDict, Field

from jarvis.core.computer.browser.snapshot import BrowserSnapshotBuilder
from jarvis.core.computer.browser.locator import BrowserLocatorResolver
from jarvis.core.computer.models import TargetConfidence
from jarvis.security.supervisor import global_supervisor

_PAGE_LOCKS = weakref.WeakKeyDictionary()


def origin(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password:
        raise ValueError('Only ordinary HTTP(S) origins are allowed')
    return f'{parts.scheme}://{parts.hostname.lower()}:{parts.port or (443 if parts.scheme == "https" else 80)}'


class BrowserAction(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    action_id: str = Field(default_factory=lambda: uuid4().hex)
    action: Literal['READ_PAGE', 'NAVIGATE', 'CLICK', 'TYPE', 'DOWNLOAD', 'REQUEST_OWNER_INPUT']
    observation_id: str
    state_hash: str
    role: str | None = None
    name: str | None = None
    url: str | None = None
    expected_text: str | None = None
    timeout_ms: int = Field(default=5000, ge=100, le=30000)


class BrowserProgram(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    goal: str = Field(min_length=1, max_length=1000)
    allowed_origins: tuple[str, ...] = Field(min_length=1, max_length=10)
    max_steps: int = Field(default=20, ge=1, le=200)
    timeout_s: float = Field(default=120, ge=1, le=1800)
    # Exact owner-provided navigation/completion signals, never arbitrary code.
    next_names: tuple[str, ...] = ('Next', 'Continue', 'Next lesson')
    completion_text: str = Field(min_length=1, max_length=150)


class BrowserTaskState(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_id: str = Field(default_factory=lambda: uuid4().hex)
    status: Literal['OBSERVING', 'RUNNING', 'COMPLETE', 'PAUSED', 'CANCELLED', 'FAILED'] = 'OBSERVING'
    completed_steps: int = 0
    last_verified_hash: str = ''
    current_origin: str = ''
    failure: str | None = None
    # Checkpoints intentionally omit private URLs, titles and page contents.


class BrowserWorkflow:
    def __init__(self, page, program: BrowserProgram, *, checkpoint_dir: Path | None = None):
        self.page = page
        self.program = program
        self.state = BrowserTaskState()
        self.allowed = {origin(u) for u in program.allowed_origins}
        self.checkpoint_dir = checkpoint_dir
        self.stop_event = asyncio.Event()
        self._lock = _PAGE_LOCKS.setdefault(page, asyncio.Lock())
        self._current_observation = None
        self._seen: dict[str, int] = {}
        self.timings = []

    async def resume(self, checkpoint: Path):
        """Resume only against the exact last verified state, supplied by owner.

        No automatic replay, navigation, or persisted private URL is required.
        """
        saved = BrowserTaskState.model_validate_json(checkpoint.read_text(encoding='utf-8'))
        obs = await self.observe()
        if saved.last_verified_hash != obs.state_hash or saved.current_origin != origin(self.page.url):
            raise ValueError('Checkpoint does not match current verified page; re-plan with owner')
        self.state = saved
        self.state.status, self.state.failure = 'OBSERVING', None
        self.stop_event.clear()
        self._seen.clear()
        return await self.run()

    def stop(self):
        self.stop_event.set()

    def _stopped(self):
        return self.stop_event.is_set() or global_supervisor.is_stopped()

    def _checkpoint(self):
        if self.checkpoint_dir is None:
            return
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        target = self.checkpoint_dir / f'{self.state.task_id}.json'
        temp = target.with_suffix('.tmp')
        temp.write_text(self.state.model_dump_json(), encoding='utf-8')
        temp.replace(target)

    async def observe(self):
        if origin(self.page.url) not in self.allowed:
            raise ValueError('UNEXPECTED_ORIGIN')
        obs = await BrowserSnapshotBuilder.capture(self.page)
        self._current_observation = obs
        self.state.current_origin = origin(self.page.url)
        return obs

    async def propose(self, obs):
        # No instructions contained in page text alter the owner-defined goal.
        body = (await self.page.inner_text('body', timeout=5000))[:16000]
        if re.search(r'\b(?:captcha|one.time.password|two.factor|graded (?:exam|assessment)|proctored)\b', body, re.I) or any(e.control_type == 'CredentialControl' for e in obs.elements):
            return BrowserAction(action='REQUEST_OWNER_INPUT', observation_id=obs.observation_id, state_hash=obs.state_hash)
        # Completion is accepted only when the exact signal is visible and no
        # Next/Continue target remains. A page instruction is not a success flag.
        next_elements = [e for e in obs.elements if e.visible and e.enabled and e.name.casefold() in {n.casefold() for n in self.program.next_names}]
        if self.program.completion_text.casefold() in body.casefold() and not next_elements:
            self.state.status = 'COMPLETE'
            self.state.last_verified_hash = obs.state_hash
            return None
        if len(next_elements) != 1:
            self.state.failure = 'ELEMENT_AMBIGUOUS' if next_elements else 'OWNER_INPUT_REQUIRED'
            return BrowserAction(action='REQUEST_OWNER_INPUT', observation_id=obs.observation_id, state_hash=obs.state_hash)
        element = next_elements[0]
        return BrowserAction(action='CLICK', observation_id=obs.observation_id, state_hash=obs.state_hash,
                             role=element.role, name=element.name)

    async def execute(self, action: BrowserAction):
        if self._stopped():
            self.state.status = 'CANCELLED'
            return False
        from jarvis.core.tasks.scope import get_scope_manager
        scopes = get_scope_manager()
        if scopes.current() is None:
            self.state.failure = 'TASK_SCOPE_REQUIRED'
            return False
        scopes.check('browser_workflow')
        before = self._current_observation
        if before is None or action.observation_id != before.observation_id or action.state_hash != before.state_hash:
            self.state.failure = 'STALE_ELEMENT'
            return False
        fresh = await BrowserSnapshotBuilder.capture(self.page)
        if fresh.state_hash != before.state_hash:
            self.state.failure = 'STALE_ELEMENT'
            return False
        if action.action == 'REQUEST_OWNER_INPUT':
            self.state.status = 'PAUSED'
            self.state.failure = self.state.failure or 'OWNER_INPUT_REQUIRED'
            return False
        if action.action == 'READ_PAGE':
            return True
        target = action.url
        if action.action == 'CLICK':
            loc, confidence = await BrowserLocatorResolver.resolve_strict(self.page, role=action.role, name=action.name)
            if confidence == TargetConfidence.AMBIGUOUS or loc is None:
                self.state.failure = 'ELEMENT_AMBIGUOUS'
                return False
            # Only ordinary navigation links can be automated here. Buttons,
            # forms, JS handlers, downloads and commits require registered
            # effect-specific capabilities and exact confirmation tickets.
            attrs = await loc.evaluate('(el) => ({tag:el.tagName, href:el.href || "", onclick:el.hasAttribute("onclick"), download:el.hasAttribute("download")})')
            if attrs['tag'] != 'A' or attrs['onclick'] or attrs['download'] or not attrs['href']:
                self.state.status = 'PAUSED'
                self.state.failure = 'CONFIRMATION_REQUIRED'
                return False
            target = attrs['href']
        if action.action not in {'NAVIGATE', 'CLICK'} or not target:
            self.state.status = 'PAUSED'
            self.state.failure = 'CONFIRMATION_REQUIRED'
            return False
        if origin(target) not in self.allowed:
            self.state.status = 'PAUSED'
            self.state.failure = 'UNEXPECTED_ORIGIN'
            return False
        from jarvis.security.policy.evaluator import PolicyEvaluator
        from jarvis.tools.system.computer_tools import BrowserNavigateTool
        if not PolicyEvaluator().evaluate_node(BrowserNavigateTool.definition, {'url': target}).is_allowed:
            self.state.status, self.state.failure = 'PAUSED', 'POLICY_BLOCK'
            return False
        if self._stopped():
            self.state.status = 'CANCELLED'
            return False
        # A redirect is checked before requesting an out-of-scope destination,
        # not merely after loading its content.
        async def guard(route):
            try:
                allowed = origin(route.request.url) in self.allowed
            except ValueError:
                allowed = False
            if route.request.is_navigation_request() and not allowed:
                await route.abort()
            else:
                await route.continue_()
        await self.page.route('**/*', guard)
        try:
            response = await self.page.goto(target, wait_until='domcontentloaded', timeout=action.timeout_ms)
            if response and response.status >= 400:
                self.state.failure = 'NAVIGATION_ERROR'
                return False
            after = await self.observe()
            if after.state_hash == before.state_hash:
                self.state.failure = 'VERIFICATION_FAILURE'
                return False
            if action.expected_text and action.expected_text not in await self.page.inner_text('body'):
                self.state.failure = 'VERIFICATION_FAILURE'
                return False
            self.state.completed_steps += 1
            self.state.last_verified_hash = after.state_hash
            self._checkpoint()
            return True
        finally:
            await self.page.unroute('**/*', guard)

    async def run(self):
        # One loop owns this instance/page; no parallel actions on the same task.
        async with self._lock:
            self.state.status = 'RUNNING'
            start = time.monotonic()
            try:
                for _ in range(self.program.max_steps):
                    if self._stopped():
                        self.state.status = 'CANCELLED'
                        break
                    if time.monotonic()-start >= self.program.timeout_s:
                        self.state.status, self.state.failure = 'PAUSED', 'TIME_BUDGET'
                        break
                    step = time.perf_counter()
                    obs = await self.observe()
                    self._seen[obs.state_hash] = self._seen.get(obs.state_hash, 0)+1
                    if self._seen[obs.state_hash] > 2:
                        self.state.status, self.state.failure = 'PAUSED', 'INTERACTION_STALLED'
                        break
                    action = await self.propose(obs)
                    if action is None:
                        break
                    if not await self.execute(action):
                        if self.state.status == 'RUNNING':
                            self.state.status = 'PAUSED'
                        break
                    self.timings.append((time.perf_counter()-step)*1000)
                else:
                    self.state.status, self.state.failure = 'PAUSED', 'STEP_BUDGET'
            except Exception as exc:
                self.state.status = 'FAILED'
                self.state.failure = type(exc).__name__  # no private exception text
            self._checkpoint()
            return self.state
