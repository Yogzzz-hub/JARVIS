"""Browser form auto-fill from the owner's profile (config/profile.toml) - deterministic, no AI model needed.

Each field is matched by its autocomplete hint, name, id, label, placeholder and aria-label. Empty fields only;
passwords, OTPs, CVV and card numbers are never touched; nothing is submitted.
"""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

PROFILE_PATH = Path(__file__).resolve().parents[3] / "config" / "profile.toml"

# profile key -> words that identify the field (checked against autocomplete/name/id/label/placeholder)
FIELD_HINTS: dict[str, list[str]] = {
    "email": ["email", "e-mail", "mail id"],
    "phone": ["phone", "mobile", "tel", "contact number", "whatsapp", "cell"],
    "first_name": ["first name", "firstname", "first_name", "given-name", "fname"],
    "last_name": ["last name", "lastname", "last_name", "surname", "family-name", "lname"],
    "full_name": ["full name", "fullname", "your name", "name", "candidate name", "student name", "applicant name"],
    "date_of_birth": ["date of birth", "dob", "birth date", "bday", "birthday"],
    "gender": ["gender", "sex"],
    "pincode": ["pincode", "pin code", "postal", "zip", "postcode"],
    "city": ["city", "town", "address-level2"],
    "state": ["state", "province", "address-level1"],
    "country": ["country"],
    "address": ["address", "street", "address-line1"],
    "college": ["college", "university", "institution", "school"],
    "degree": ["degree", "qualification", "course"],
    "department": ["department", "branch", "stream"],
    "register_number": ["register number", "registration number", "reg no", "roll number", "roll no", "usn"],
    "graduation_year": ["graduation year", "year of passing", "passing year", "batch"],
    "company": ["company", "organization", "organisation", "employer"],
    "job_title": ["job title", "designation", "position", "role"],
    "linkedin": ["linkedin"],
    "github": ["github"],
    "website": ["website", "portfolio", "url"],
}

FILL_JS = r"""
(args) => {
  const [values, hints] = args;
  const NEVER = /pass(word)?|otp|one.time|cvv|cvc|card.?num|security.?code|pin$|captcha/i;
  const labelOf = (el) => {
    let t = [];
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) t.push(l.innerText); }
    const wrap = el.closest('label'); if (wrap) t.push(wrap.innerText);
    t.push(el.getAttribute('aria-label') || '', el.placeholder || '', el.name || '', el.id || '', el.getAttribute('autocomplete') || '');
    const prev = el.closest('div,li,td,p'); if (prev && prev.innerText && prev.innerText.length < 80) t.push(prev.innerText);
    return t.join(' ').toLowerCase();
  };
  const setVal = (el, v) => {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, v);  // works with React/Vue controlled inputs
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  };
  const filled = [], skipped = [];
  const els = Array.from(document.querySelectorAll('input, textarea, select'))
      .filter(el => !el.disabled && !el.readOnly && el.offsetParent !== null);
  for (const el of els) {
    const type = (el.type || '').toLowerCase();
    if (['hidden','submit','button','checkbox','radio','file','image','reset','password'].includes(type)) continue;
    const text = labelOf(el);
    if (NEVER.test(text)) { skipped.push(text.slice(0, 30)); continue; }
    if (el.tagName !== 'SELECT' && el.value) continue;  // never overwrite what is already there
    let key = null;
    const order = ['email','phone','first_name','last_name','date_of_birth','pincode','register_number','graduation_year',
                   'linkedin','github','city','state','country','college','degree','department','company','job_title','gender',
                   'address','website','full_name'];
    for (const k of order) {
      if (!values[k]) continue;
      if (type === 'email' && k !== 'email') continue;
      // whole-word match: "fullname" must not look like "lname", "state" must not match "statement"
      if (hints[k].some(h => new RegExp('(^|[^a-z0-9])' + h.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '([^a-z0-9]|$)').test(text))) { key = k; break; }
    }
    if (!key && type === 'email' && values.email) key = 'email';
    if (!key && type === 'tel' && values.phone) key = 'phone';
    if (!key) continue;
    const v = String(values[key]);
    if (el.tagName === 'SELECT') {
      const opt = Array.from(el.options).find(o => o.text.toLowerCase().trim() === v.toLowerCase()
                                                  || o.value.toLowerCase() === v.toLowerCase());
      if (!opt) continue;
      el.value = opt.value; el.dispatchEvent(new Event('change', {bubbles: true}));
    } else if (type === 'date' && /\d{4}-\d{2}-\d{2}/.test(v)) { setVal(el, v); }
    else { setVal(el, v); }
    el.style.outline = '2px solid #00d4ff';
    filled.push(key);
  }
  return {filled, skipped: skipped.length, url: location.href};
}
"""


def load_profile() -> dict[str, str]:
    try:
        with PROFILE_PATH.open("rb") as f:
            data = tomllib.load(f).get("profile", {})
    except Exception:
        return {}
    values = {k: str(v).strip() for k, v in data.items() if str(v or "").strip()}
    if values.get("full_name") and not values.get("first_name"):
        parts = values["full_name"].split()
        values.setdefault("first_name", parts[0])
        if len(parts) > 1:
            values.setdefault("last_name", " ".join(parts[1:]))
    return values


class AutofillInput(Contract):
    only: list[str] = Field(default_factory=list, description="Fill only these profile fields (optional)")


class AutofillOutput(Contract):
    status: str
    message: str
    filled: list[str] = Field(default_factory=list)


class BrowserAutofillTool(Tool):
    definition = ToolDefinition(
        name="browser_autofill",
        description="Fills the form on the current page of the JARVIS browser with the owner's saved details (name, email, "
                    "phone, address, college, ...). Never fills passwords/OTPs/card numbers and never submits.",
        input_model=AutofillInput,
        output_model=AutofillOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=30.0,
        tags=("browser", "form", "autofill", "dom"),
        execution_method=ExecutionMethod.DOM,
    )

    def __init__(self, page_runner: Any = None) -> None:
        self._page_runner = page_runner  # tests: async fn(js, args) -> result

    async def _evaluate(self, js: str, args: Any) -> Any:
        if self._page_runner is not None:
            return await self._page_runner(js, args)
        from jarvis.core.computer.browser.loop import get_browser_loop
        from jarvis.tools.system.computer_tools import get_shared_browser_manager

        async def work():
            page = await get_shared_browser_manager().get_active_page()
            return await page.evaluate(js, args)
        return await get_browser_loop().run_async(work, timeout=25.0)

    async def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = AutofillInput(**arguments)
        values = load_profile()
        if arguments.only:
            values = {k: v for k, v in values.items() if k in arguments.only}
        if not values:
            return {"status": "NEEDS_SETUP", "filled": [],
                    "message": "I don't have your details yet. Copy config/profile.example.toml to config/profile.toml, "
                               "fill in your name, email, phone and so on, then say 'fill this form' again."}
        try:
            res = await self._evaluate(FILL_JS, [values, FIELD_HINTS])
        except Exception as exc:
            return {"status": "FAILED", "filled": [], "message": f"I couldn't reach a form in the JARVIS browser ({exc})."}
        filled = list(dict.fromkeys((res or {}).get("filled", [])))
        if not filled:
            return {"status": "NOTHING", "filled": [],
                    "message": "I didn't find empty fields I have details for on this page."}
        pretty = ", ".join(k.replace("_", " ") for k in filled)
        extra = f" I left {res['skipped']} sensitive field(s) for you." if res.get("skipped") else ""
        return {"status": "SUCCESS", "filled": filled,
                "message": f"Filled {len(filled)} field(s): {pretty}. Please check them and press Submit yourself.{extra}"}
