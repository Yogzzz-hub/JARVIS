"""Answers about JARVIS itself, built only from runtime state (task manager, the last results, psutil, the health
checks). No model, no planner, no web: if a fact is not known here, the answer says so instead of guessing."""
from __future__ import annotations

import re
import shutil
import subprocess
import time
from typing import Any, Optional

# Human names for tools in step lists ("pc_quick_action" is never read out).
_TOOL_WORDS = {"dag_scheduler": "plan", "pc_quick_action": "media / PC quick action", "system_diagnostics": "health check",
               "control": "cancel", "open_app": "open app", "close_app": "close app", "find_file": "file search",
               "search_web": "web search", "send_whatsapp_message": "WhatsApp message", "install_software": "software install"}
INTROSPECTION_INTENTS = frozenset({"jarvis_availability", "resource_usage", "task_status", "previous_outcome", "cancel_task",
                                   "stop_task"})


def tool_words(name: str) -> str:
    return _TOOL_WORDS.get(name or "", (name or "step").replace("_", " "))


def _elapsed(task) -> str:
    s = max(0.0, time.monotonic() - getattr(task, "started_monotonic", time.monotonic()))
    return f"{s:.0f} s" if s < 90 else f"{s / 60:.0f} min"


# ---------------------------------------------------------------------------------------------- resources
def _gpu() -> Optional[dict]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=2.5).stdout.strip().splitlines()
    except Exception:
        return None
    if not out:
        return None
    name, util, used, total = [x.strip() for x in out[0].split(",")[:4]]
    return {"name": name, "percent": float(util), "vram_used_mb": float(used), "vram_total_mb": float(total)}


def resource_usage() -> tuple[str, dict]:
    import psutil
    cpu = psutil.cpu_percent(interval=0.3)
    vm = psutil.virtual_memory()
    data: dict[str, Any] = {"cpu_percent": cpu, "ram_percent": vm.percent, "ram_used_gb": round(vm.used / 2**30, 1),
                            "ram_total_gb": round(vm.total / 2**30, 1), "gpu": _gpu()}
    parts = [f"CPU {cpu:.0f}%", f"RAM {data['ram_used_gb']:.1f} of {data['ram_total_gb']:.0f} GB ({vm.percent:.0f}%)"]
    g = data["gpu"]
    if g:
        parts.append(f"GPU {g['percent']:.0f}% ({g['name']}, {g['vram_used_mb'] / 1024:.1f} of {g['vram_total_mb'] / 1024:.0f} GB video memory)")
    else:
        parts.append("GPU usage isn't available (no NVIDIA driver tools found)")
    return ", ".join(parts) + ".", data


# ---------------------------------------------------------------------------------------------- health / availability
_GROUPS = [
    ("Core", re.compile(r"^(?:Python|Configuration|Database|Gateway|fastapi|uvicorn|httpx|pydantic|psutil|yaml|rapidfuzz|numpy|watchdog)$")),
    ("Voice", re.compile(r"sounddevice|faster_whisper|openwakeword|silero|piper|scipy|Speech model|Wake word|Voice model|Audio devices|"
                         r"Feature: (?:voice|tts)", re.I)),
    ("Local AI", re.compile(r"^(?:Ollama|AI role)", re.I)),
    ("Screen & vision", re.compile(r"vision|PIL|uiautomation|win32gui", re.I)),
    ("Browser automation", re.compile(r"playwright|Feature: browser", re.I)),
    ("Hotkeys & keyboard", re.compile(r"^keyboard$", re.I)),
    ("Media tools", re.compile(r"^(?:ffmpeg|nvidia-smi|winget|git)$", re.I)),
    ("Google", re.compile(r"^(?:Google|Feature: google)", re.I)),
    ("Phone", re.compile(r"^Feature: phone", re.I)),
    ("Planning & routing", re.compile(r"^Feature: (?:planner|router_ai)", re.I)),
]


def _group(name: str) -> str:
    for label, rx in _GROUPS:
        if rx.search(name):
            return label
    return "Features" if name.startswith("Feature:") else "Other"


def availability(checks: list[dict]) -> tuple[str, dict]:
    groups: dict[str, dict] = {}
    for c in checks:
        g = groups.setdefault(_group(str(c.get("name", ""))), {"ok": 0, "problems": []})
        if c.get("status") in ("PASS", "OK"):
            g["ok"] += 1
        else:
            g["problems"].append({"name": c.get("name"), "status": c.get("status"), "detail": str(c.get("detail", ""))[:140]})
    available = [k for k, v in groups.items() if not any(p["status"] == "FAIL" for p in v["problems"]) and v["ok"]]
    unavailable = [k for k, v in groups.items() if any(p["status"] == "FAIL" for p in v["problems"]) or not v["ok"]]
    limited = [k for k in available if groups[k]["problems"]]
    msg = "Available: " + (", ".join(available) or "nothing") + "."
    if unavailable:
        why = []
        for k in unavailable:
            p = next((x for x in groups[k]["problems"] if x["status"] == "FAIL"), groups[k]["problems"][0] if groups[k]["problems"] else None)
            why.append(f"{k} ({p['name']}: {p['detail'][:60]})" if p else k)
        msg += " Unavailable: " + "; ".join(why) + "."
    else:
        msg += " Nothing is unavailable."
    if limited:
        msg += " Working with limits: " + ", ".join(f"{k} ({len(groups[k]['problems'])} warning{'s' if len(groups[k]['problems']) != 1 else ''})"
                                                   for k in limited) + "."
    return msg, {"available": available, "unavailable": unavailable, "limited": limited, "groups": groups}


# ---------------------------------------------------------------------------------------------- tasks
def _step_line(task) -> str:
    steps = getattr(task, "steps", {}) or {}
    total = getattr(task, "steps_total", 0)
    if not total:
        return ""
    done = sum(1 for s in steps.values() if s["state"] == "SUCCESS")
    failed = [s for s in steps.values() if s["state"] in ("FAILED", "TIMEOUT")]
    line = f"{len(steps)} of {total} steps finished ({done} succeeded" + (f", {len(failed)} failed" if failed else "") + ")"
    running = total - len(steps)
    if running > 0:
        line += f"; {running} still to go"
    return line


def task_status(tasks, current, stuck_only: bool = False, stuck_after_s: float = 60.0) -> tuple[str, dict]:
    active = tasks.active_tasks(exclude=current)
    fg = [t for t in active if not t.background]
    bg = [t for t in active if t.background]
    data = {"foreground": [], "background": []}
    lines = []
    for label, group in (("foreground", fg), ("background", bg)):
        for t in group:
            age = time.monotonic() - t.started_monotonic
            stuck = age > stuck_after_s and str(t.state) not in ("WAITING_CONFIRMATION",)
            info = {"request_id": t.request_id, "command": t.raw_text, "state": str(t.state), "elapsed_s": round(age, 1),
                    "steps_total": t.steps_total, "steps_finished": len(t.steps), "possibly_stuck": stuck}
            data[label].append(info)
            step = _step_line(t)
            waiting = " - waiting for your confirmation" if str(t.state) == "WAITING_CONFIRMATION" else ""
            if t.cancellation.is_set():
                waiting += " - cancel requested, finishing the step in progress"
            lines.append(f"{'Background job' if label == 'background' else 'Running'}: “{t.raw_text[:80]}”, "
                         f"{str(t.state).lower().replace('_', ' ')} for {_elapsed(t)}{waiting}" + (f", {step}" if step else "")
                         + (" - it may be stuck" if stuck else "") + ".")
    if not fg and not bg:
        msg = "No foreground task is currently running, and there are no background jobs."
        if stuck_only:
            msg = "Nothing is stuck: no task is running right now."
        return msg, data
    if stuck_only:
        stuck = [x for g in data.values() for x in g if x["possibly_stuck"]]
        if not stuck:
            return ("Nothing looks stuck. " + " ".join(lines)).strip(), data
    if not fg:
        lines.insert(0, "No foreground task is currently running.")
    return " ".join(lines), data


def previous_outcome(tasks, current, skip_intents: frozenset = INTROSPECTION_INTENTS) -> tuple[str, dict]:
    """The last finished command before this one, step by step, exactly as it was recorded."""
    prev = None
    for t in tasks.recent(60):
        if t is current or t.result is None:
            continue
        if getattr(t, "intent", "") in skip_intents:
            continue  # "what failed?" asks about the last real command, not about an earlier status question
        prev = t
        break
    if prev is None:
        return "There is no previous command in this session yet.", {"found": False}
    res = prev.result
    tr = getattr(res, "tool_result", None)
    data: dict[str, Any] = {"found": True, "command": prev.raw_text, "state": res.state, "message": res.message,
                            "succeeded": [], "failed": [], "skipped": [], "uncertain": []}
    out = tr.data if tr is not None and isinstance(tr.data, dict) else {}
    nodes = out.get("node_results") if isinstance(out.get("node_results"), dict) else None
    if nodes:
        for nid, nr in nodes.items():
            label = tool_words(nr.get("tool", ""))
            st = str(nr.get("state", "")).upper()
            if st == "SUCCESS":
                data["succeeded"].append(label)
            elif st in ("FAILED", "TIMEOUT"):
                data["failed"].append(f"{label} ({(nr.get('error') or 'no reason recorded')[:80]})")
            elif st.startswith("SKIPPED") or st.startswith("BLOCKED"):
                data["skipped"].append(f"{label} ({'an earlier step failed' if 'DEPENDENCY' in st else st.lower().replace('_', ' ')})")
            else:
                data["uncertain"].append(f"{label} ({st.lower() or 'unknown'})")
    else:
        label = tool_words(tr.tool_name if tr is not None else "")
        if res.state == "SUCCESS":
            data["succeeded"].append(label)
        elif res.state == "WAITING_CONFIRMATION":
            data["uncertain"].append(f"{label} (was waiting for your confirmation)")
        elif res.state == "CANCELLED":
            data["skipped"].append(f"{label} (cancelled)")
        else:
            data["failed"].append(f"{label} ({(tr.error if tr is not None and tr.error else res.message)[:100]})")
    head = {"SUCCESS": "succeeded", "FAILED": "failed", "CANCELLED": "was cancelled",
            "WAITING_CONFIRMATION": "stopped to wait for your confirmation"}.get(res.state, res.state.lower())
    parts = [f"The previous command, “{prev.raw_text[:80]}”, {head}."]
    for key, word in (("succeeded", "Completed"), ("failed", "Failed"), ("skipped", "Skipped"), ("uncertain", "Uncertain")):
        if data[key]:
            parts.append(f"{word}: {', '.join(dict.fromkeys(data[key]))}.")
    if not any(data[k] for k in ("failed", "skipped", "uncertain")):
        parts.append("Nothing failed.")
    return " ".join(parts), data


def cancel(tasks, current, scope: str = "foreground") -> tuple[str, dict]:
    """Cancel only the requested kind of task. The voice listener and JARVIS itself are never stopped here."""
    want_bg = scope == "background"
    targets = [t for t in tasks.active_tasks(exclude=current, background=want_bg) if not t.cancellation.is_set()]
    cancelled = [t.raw_text for t in targets if tasks.cancel(t.request_id)]
    untouched = tasks.active_tasks(exclude=current, background=not want_bg)
    data = {"scope": scope, "cancelled": cancelled, "left_running": [t.raw_text for t in untouched], "listening": True}
    if want_bg:
        if not cancelled:
            msg = "No background job is running, so nothing was cancelled."
        else:
            msg = f"Cancelled {len(cancelled)} background job{'s' if len(cancelled) != 1 else ''}: " + \
                  "; ".join(f"“{c[:60]}”" for c in cancelled) + "."
        if untouched:
            msg += f" Your foreground task “{untouched[0].raw_text[:60]}” keeps running."
    else:
        if not cancelled:
            msg = "No foreground task is currently running, so nothing was cancelled."
        else:
            msg = f"Cancelled “{cancelled[0][:60]}”" + (f" and {len(cancelled) - 1} more" if len(cancelled) > 1 else "") + \
                  ". Steps that had already started may finish."
        if untouched:
            msg += f" {len(untouched)} background job{'s' if len(untouched) != 1 else ''} left running."
    return msg + " I'm still listening.", data
