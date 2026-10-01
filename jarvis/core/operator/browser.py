"""browser.* primitives over ONE browser model.

Backends, best first:
  1. ``CDPBackend``  - a Chromium browser (Chrome/Edge/Brave) started with ``--remote-debugging-port`` and a
     dedicated persistent profile (Chrome 136+ refuses a debugging port on the default profile, so the owner signs in
     once in that profile and it stays signed in). Tabs come from the DevTools HTTP endpoints; page work runs *named*
     scripts from ``SCRIPTS`` only - never model-written JavaScript.
  2. ``KeyboardBackend`` - the owner's ordinary browser window: tab/navigation chords via the platform layer,
     verified through the window title. No DOM access, so page-level asks fall back to the UI resolver (UIA).
  3. ``FakeBrowser`` - tests.

Page content (titles, result snippets, text) is untrusted data: returned and shown, never executed as instructions.
Logins, passwords, CAPTCHAs and payment confirmations are always the owner's.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Optional

from jarvis.core.operator.platform import Desktop, get_desktop, parse_chord
from jarvis.core.operator.refs import BrowserTabRef, ControlRef, LinkRef, OperatorOutcome
from jarvis.core.operator.resources import OperatorResources, get_resources
from jarvis.core.operator.ui import UIAdapter

logger = logging.getLogger("jarvis.operator.browser")

SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={q}", "bing": "https://www.bing.com/search?q={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}", "youtube": "https://www.youtube.com/results?search_query={q}",
    "github": "https://github.com/search?q={q}", "wikipedia": "https://en.wikipedia.org/w/index.php?search={q}",
    "amazon": "https://www.amazon.in/s?k={q}", "maps": "https://www.google.com/maps/search/{q}",
    "images": "https://www.google.com/search?tbm=isch&q={q}", "news": "https://news.google.com/search?q={q}",
    "stackoverflow": "https://stackoverflow.com/search?q={q}", "reddit": "https://www.reddit.com/search/?q={q}",
    "scholar": "https://scholar.google.com/scholar?q={q}",
}
SITES = {
    "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com", "github": "https://github.com",
    "google": "https://www.google.com", "maps": "https://maps.google.com", "drive": "https://drive.google.com",
    "calendar": "https://calendar.google.com", "whatsapp web": "https://web.whatsapp.com",
    "chatgpt": "https://chatgpt.com", "claude": "https://claude.ai", "linkedin": "https://www.linkedin.com",
    "twitter": "https://x.com", "x": "https://x.com", "reddit": "https://www.reddit.com",
    "stackoverflow": "https://stackoverflow.com", "wikipedia": "https://www.wikipedia.org",
    "amazon": "https://www.amazon.in", "netflix": "https://www.netflix.com", "spotify": "https://open.spotify.com",
    "outlook": "https://outlook.live.com", "docs": "https://docs.google.com", "sheets": "https://sheets.google.com",
}
_URL = re.compile(r"^(https?://|www\.)\S+$|^[\w-]+(\.[\w-]+)+(/\S*)?$", re.I)

# Fixed page scripts. Arguments are passed as JSON, never spliced as code.
SCRIPTS: dict[str, str] = {
    # Interactive elements with accessible names; each gets a stable data-jarvis-id for the action scripts.
    "controls": r"""(() => {
      const sel = 'a[href],button,input,textarea,select,[role=button],[role=link],[role=tab],[role=checkbox],'
        + '[role=menuitem],[role=option],[role=switch],[role=searchbox],[role=textbox],[contenteditable=true]';
      const out = []; let i = 0;
      for (const el of document.querySelectorAll(sel)) {
        const r = el.getBoundingClientRect(); const st = getComputedStyle(el);
        const visible = r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
        if (!visible) continue;
        if (!el.dataset.jarvisId) el.dataset.jarvisId = 'j' + (i++) + '_' + Math.random().toString(36).slice(2, 6);
        const tag = el.tagName.toLowerCase(); const type = (el.getAttribute('type') || '').toLowerCase();
        const role = el.getAttribute('role') || (tag === 'a' ? 'link' : tag === 'textarea' ? 'textbox'
          : tag === 'select' ? 'combobox' : tag === 'input' ? (['checkbox','radio'].includes(type) ? type
          : ['button','submit'].includes(type) ? 'button' : 'textbox') : el.isContentEditable ? 'textbox' : tag);
        const name = (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText
          || el.getAttribute('placeholder') || el.value || el.getAttribute('alt') || '').trim().slice(0, 120);
        out.push({id: el.dataset.jarvisId, role, name, type, href: el.href || '',
          editable: role === 'textbox' || role === 'searchbox' || el.isContentEditable,
          enabled: !el.disabled, checked: el.checked === undefined ? null : el.checked,
          bounds: [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]});
        if (out.length >= 400) break;
      }
      return out; })()""",
    "click": r"""((id) => { const el = document.querySelector(`[data-jarvis-id="${id}"]`);
      if (!el) return false; el.scrollIntoView({block: 'center'}); el.click(); return true; })""",
    "set_value": r"""((id, text) => { const el = document.querySelector(`[data-jarvis-id="${id}"]`);
      if (!el || (el.type || '').toLowerCase() === 'password') return false; el.focus();
      if (el.isContentEditable) { el.textContent = text; }
      else { const proto = Object.getPrototypeOf(el); const d = Object.getOwnPropertyDescriptor(proto, 'value');
        d && d.set ? d.set.call(el, text) : (el.value = text); }
      el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true}));
      return true; })""",
    "read_value": r"""((id) => { const el = document.querySelector(`[data-jarvis-id="${id}"]`);
      return el ? (el.isContentEditable ? el.textContent : (el.value ?? el.innerText)) : null; })""",
    "focus": r"""((id) => { const el = document.querySelector(`[data-jarvis-id="${id}"]`);
      if (!el) return false; el.focus(); return document.activeElement === el; })""",
    # Ranked result links of a search/listing page (Google, Bing, DDG, YouTube, generic main links).
    "results": r"""(() => {
      const pick = [
        ['ytd-video-renderer a#video-title, ytd-rich-item-renderer a#video-title-link', 'youtube'],
        ['#search a h3', 'google'], ['li.b_algo h2 a', 'bing'], ['article h2 a, a[data-testid=result-title-a]', 'ddg'],
      ];
      for (const [sel, kind] of pick) {
        const els = [...document.querySelectorAll(sel)];
        if (els.length) return els.slice(0, 20).map((e, i) => { const a = e.closest('a') || e;
          if (!a.dataset.jarvisId) a.dataset.jarvisId = 'r' + i + '_' + Math.random().toString(36).slice(2, 6);
          return {title: (e.innerText || a.title || '').trim(), url: a.href, id: a.dataset.jarvisId, kind}; });
      }
      const main = document.querySelector('main') || document.body;
      return [...main.querySelectorAll('a[href]')].filter(a => (a.innerText || '').trim().length > 12)
        .slice(0, 20).map((a, i) => { if (!a.dataset.jarvisId) a.dataset.jarvisId = 'r' + i;
          return {title: a.innerText.trim().slice(0, 140), url: a.href, id: a.dataset.jarvisId, kind: 'generic'}; });
    })()""",
    "text": r"""(() => { const m = document.querySelector('article, main, [role=main]') || document.body;
      return {title: document.title, url: location.href, text: (m.innerText || '').slice(0, 20000)}; })()""",
    "scroll": r"""((dir, n) => { const h = window.innerHeight * 0.85 * (n || 1);
      if (dir === 'top') window.scrollTo(0, 0); else if (dir === 'bottom') window.scrollTo(0, document.body.scrollHeight);
      else window.scrollBy(0, dir === 'up' ? -h : h); return window.scrollY; })""",
    "find": r"""((q) => window.find ? window.find(q) : false)""",
    # Media: the page's main <video>/<audio>.
    "media_state": r"""(() => { const v = [...document.querySelectorAll('video,audio')].sort((a, b) =>
        (b.videoWidth || 0) * (b.videoHeight || 0) - (a.videoWidth || 0) * (a.videoHeight || 0))[0];
      if (!v) return null; const ad = !!document.querySelector('.ad-showing, .ytp-ad-player-overlay');
      return {paused: v.paused, t: v.currentTime, d: v.duration || 0, rate: v.playbackRate, muted: v.muted,
              volume: v.volume, ad, title: document.title, url: location.href}; })()""",
    "media": r"""((op, val) => { const v = [...document.querySelectorAll('video,audio')].sort((a, b) =>
        (b.videoWidth || 0) * (b.videoHeight || 0) - (a.videoWidth || 0) * (a.videoHeight || 0))[0];
      if (!v) return null;
      switch (op) {
        case 'play': v.play(); break; case 'pause': v.pause(); break;
        case 'toggle': v.paused ? v.play() : v.pause(); break;
        case 'seek_to': v.currentTime = Math.max(0, Math.min(val, v.duration || val)); break;
        case 'seek_by': v.currentTime = Math.max(0, v.currentTime + val); break;
        case 'rate': v.playbackRate = Math.max(0.25, Math.min(val, 4)); break;
        case 'mute': v.muted = true; break; case 'unmute': v.muted = false; break;
        case 'volume': v.volume = Math.max(0, Math.min(val, 1)); v.muted = false; break;
        case 'restart': v.currentTime = 0; v.play(); break;
        case 'loop': v.loop = !!val; break;
      }
      return {paused: v.paused, t: v.currentTime, d: v.duration || 0, rate: v.playbackRate, muted: v.muted,
              volume: v.volume}; })""",
    "stop": r"""(() => { window.stop(); return document.readyState; })()""",
    "headings": r"""(() => [...document.querySelectorAll('h1,h2,h3,h4,[role=heading]')].slice(0, 200).map((h, i) => {
        if (!h.dataset.jarvisId) h.dataset.jarvisId = 'h' + i + '_' + Math.random().toString(36).slice(2, 6);
        return {id: h.dataset.jarvisId, text: (h.innerText || '').trim().slice(0, 140), level: h.tagName}; }))()""",
    "scroll_to": r"""((id) => { const el = document.querySelector(`[data-jarvis-id="${id}"]`);
      if (!el) return false; el.scrollIntoView({block: 'start'}); return true; })""",
    "section_text": r"""((id) => { const h = document.querySelector(`[data-jarvis-id="${id}"]`); if (!h) return '';
      let out = '', n = h.nextElementSibling; const lvl = /^H(\d)$/.exec(h.tagName);
      while (n && out.length < 12000) { const m = /^H(\d)$/.exec(n.tagName);
        if (m && lvl && Number(m[1]) <= Number(lvl[1])) break; out += (n.innerText || '') + '\n'; n = n.nextElementSibling; }
      return out; })""",
    "login_state": r"""(() => { const pw = document.querySelectorAll('input[type=password]').length;
      const txt = (document.body.innerText || '').slice(0, 20000);
      const signIn = /\b(sign in|log in|login|sign up to continue)\b/i.test(txt);
      const captcha = !!document.querySelector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], .g-recaptcha, #captcha, [class*="captcha" i]');
      return {password_fields: pw, sign_in_text: signIn, captcha, url: location.href, title: document.title}; })()""",
    "links": r"""(() => [...document.querySelectorAll('a[href]')].slice(0, 400).map((a, i) => {
        if (!a.dataset.jarvisId) a.dataset.jarvisId = 'l' + i + '_' + Math.random().toString(36).slice(2, 6);
        return {id: a.dataset.jarvisId, text: (a.innerText || a.title || a.getAttribute('aria-label') || '').trim().slice(0, 140),
                href: a.href, download: a.hasAttribute('download')}; }))()""",
    # Only a *visible* Skip control the player itself shows - nothing is blocked or hidden.
    "skip_ad": r"""(() => { const b = [...document.querySelectorAll(
        '.ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, button[class*="skip" i]')]
        .find(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0
          && /skip/i.test(e.innerText || e.getAttribute('aria-label') || ''); });
      if (!b) return {ad: !!document.querySelector('.ad-showing'), skipped: false};
      b.click(); return {ad: true, skipped: true}; })()""",
}


@dataclass
class FakeTab:
    id: str
    url: str
    title: str
    controls: list[dict] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    text: str = ""
    media: Optional[dict] = None
    history: list[str] = field(default_factory=list)
    values: dict[str, str] = field(default_factory=dict)
    clicked: list[str] = field(default_factory=list)
    skip_visible: bool = False


class BrowserBackend:
    name = "abstract"
    dom = False                            # can run page scripts

    def available(self) -> bool: return True
    def tabs(self) -> list[BrowserTabRef]: raise NotImplementedError
    def active(self) -> Optional[BrowserTabRef]:
        t = self.tabs()
        return t[0] if t else None
    def activate(self, tab: BrowserTabRef) -> bool: raise NotImplementedError
    def new_tab(self, url: str) -> Optional[BrowserTabRef]: raise NotImplementedError
    def close_tab(self, tab: BrowserTabRef) -> bool: raise NotImplementedError
    def navigate(self, tab: BrowserTabRef, url: str) -> bool: raise NotImplementedError
    def history(self, tab: BrowserTabRef, delta: int) -> bool: raise NotImplementedError
    def reload(self, tab: BrowserTabRef) -> bool: raise NotImplementedError
    def run(self, tab: BrowserTabRef, script: str, *args) -> Any: raise NotImplementedError


class FakeBrowser(BrowserBackend):
    name = "fake"
    dom = True

    def __init__(self):
        self._tabs: list[FakeTab] = []
        self._active = -1
        self._n = 0
        self.pages: dict[str, dict] = {}            # url -> {title, controls, results, text, media}

    def add_page(self, url: str, title: str, **kw) -> None:
        self.pages[url] = dict(title=title, **kw)

    def _load(self, tab: FakeTab, url: str) -> None:
        page = self.pages.get(url) or next((p | {"_u": u} for u, p in self.pages.items() if url.startswith(u)), None)
        tab.url = url
        tab.title = (page or {}).get("title") or url
        for k in ("controls", "results", "text", "media", "skip_visible"):
            default = {"controls": [], "results": [], "text": "", "media": None, "skip_visible": False}[k]
            v = (page or {}).get(k, default)
            setattr(tab, k, json.loads(json.dumps(v)) if isinstance(v, (list, dict)) else v)

    def _ref(self, i: int) -> BrowserTabRef:
        t = self._tabs[i]
        return BrowserTabRef(resource_id=f"tab:{t.id}", index=i + 1, title=t.title, url=t.url, browser="fake",
                             metadata={"id": t.id})

    def tab_obj(self, tab: BrowserTabRef) -> FakeTab:
        return next(t for t in self._tabs if t.id == tab.metadata.get("id"))

    def tabs(self) -> list[BrowserTabRef]:
        order = list(range(len(self._tabs)))
        if 0 <= self._active < len(order):
            order.remove(self._active)
            order.insert(0, self._active)
        return [self._ref(i) for i in order]

    def ordered(self) -> list[BrowserTabRef]:
        return [self._ref(i) for i in range(len(self._tabs))]

    def activate(self, tab):
        for i, t in enumerate(self._tabs):
            if t.id == tab.metadata.get("id"):
                self._active = i
                return True
        return False

    def new_tab(self, url):
        self._n += 1
        t = FakeTab(id=f"t{self._n}", url="", title="")
        self._tabs.append(t)
        self._active = len(self._tabs) - 1
        self._load(t, url or "about:blank")
        return self._ref(self._active)

    def close_tab(self, tab):
        for i, t in enumerate(self._tabs):
            if t.id == tab.metadata.get("id"):
                self._tabs.pop(i)
                self._active = min(self._active, len(self._tabs) - 1)
                return True
        return False

    def navigate(self, tab, url):
        t = self.tab_obj(tab)
        t.history.append(t.url)
        self._load(t, url)
        return True

    def history(self, tab, delta):
        t = self.tab_obj(tab)
        if delta < 0 and t.history:
            self._load(t, t.history.pop())
            return True
        return False

    def reload(self, tab):
        return True

    def set_files(self, tab, element_id: str, paths: list[str]) -> bool:
        t = self.tab_obj(tab)
        t.values[element_id] = ";".join(paths)
        return True

    def run(self, tab, script, *args):
        t = self.tab_obj(tab)
        if script == "controls":
            return [dict(c, id=c.get("id") or f"c{i}") for i, c in enumerate(t.controls)]
        if script == "click":
            c = next((c for i, c in enumerate(t.controls) if (c.get("id") or f"c{i}") == args[0]), None)
            r = next((r for i, r in enumerate(t.results) if (r.get("id") or f"r{i}") == args[0]), None)
            if c is None and r is None:
                return False
            t.clicked.append((c or r).get("name") or (c or r).get("title"))
            if c and c.get("type") == "checkbox":
                c["checked"] = not c.get("checked")
            if c and c.get("href"):
                self.navigate(tab, c["href"])
            if r:
                self.navigate(tab, r["url"])
            return True
        if script == "set_value":
            c = next((c for i, c in enumerate(t.controls) if (c.get("id") or f"c{i}") == args[0]), None)
            if not c or c.get("type") == "password":
                return False
            t.values[args[0]] = args[1]
            return True
        if script == "read_value":
            return t.values.get(args[0], "")
        if script == "focus":
            return True
        if script == "results":
            return [dict(r, id=r.get("id") or f"r{i}") for i, r in enumerate(t.results)]
        if script == "text":
            return {"title": t.title, "url": t.url, "text": t.text}
        if script == "scroll":
            return 1
        if script == "find":
            return args[0].lower() in t.text.lower()
        if script == "media_state":
            return dict(t.media, ad=bool(t.media.get("ad"))) if t.media else None
        if script == "media":
            if not t.media:
                return None
            m, op, val = t.media, args[0], (args[1] if len(args) > 1 else None)
            if op == "play": m["paused"] = False
            elif op == "pause": m["paused"] = True
            elif op == "toggle": m["paused"] = not m["paused"]
            elif op == "seek_to": m["t"] = max(0, min(val, m.get("d") or val))
            elif op == "seek_by": m["t"] = max(0, m["t"] + val)
            elif op == "rate": m["rate"] = max(0.25, min(val, 4))
            elif op == "mute": m["muted"] = True
            elif op == "unmute": m["muted"] = False
            elif op == "volume": m["volume"], m["muted"] = max(0, min(val, 1)), False
            elif op == "restart": m["t"], m["paused"] = 0, False
            return dict(m)
        if script == "stop":
            return "complete"
        if script == "headings":
            return [dict(h, id=h.get("id") or f"h{i}") for i, h in enumerate(getattr(t, "headings", []) or self.pages.get(t.url, {}).get("headings", []))]
        if script == "scroll_to":
            t.clicked.append(f"scroll:{args[0]}")
            return True
        if script == "section_text":
            hs = self.pages.get(t.url, {}).get("headings", [])
            h = next((h for i, h in enumerate(hs) if (h.get("id") or f"h{i}") == args[0]), None)
            return (h or {}).get("body", "")
        if script == "login_state":
            pg = self.pages.get(t.url, {})
            return {"password_fields": pg.get("password_fields", 0), "sign_in_text": pg.get("sign_in", False),
                    "captcha": pg.get("captcha", False), "url": t.url, "title": t.title}
        if script == "links":
            return [dict(c, id=c.get("id") or f"c{i}", text=c.get("name", ""), href=c.get("href", ""))
                    for i, c in enumerate(t.controls) if c.get("href")]
        if script == "skip_ad":
            if t.media and t.media.get("ad") and t.skip_visible:
                t.media["ad"], t.skip_visible = False, False
                return {"ad": True, "skipped": True}
            return {"ad": bool(t.media and t.media.get("ad")), "skipped": False}
        raise KeyError(script)


class CDPBackend(BrowserBackend):
    """Chromium DevTools: HTTP endpoints for tabs, a short-lived websocket per page call."""

    name = "cdp"
    dom = True

    def __init__(self, port: int = 9222, host: str = "127.0.0.1"):
        self.base = f"http://{host}:{port}"

    def _http(self, path: str, method: str = "GET"):
        import httpx
        r = httpx.request(method, self.base + path, timeout=1.5)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return r.text

    def available(self) -> bool:
        try:
            return bool(self._http("/json/version"))
        except Exception:
            return False

    def tabs(self) -> list[BrowserTabRef]:
        try:
            items = [t for t in self._http("/json/list") if t.get("type") == "page"]
        except Exception:
            return []
        return [BrowserTabRef(resource_id=f"tab:{t['id']}", index=i + 1, title=t.get("title", ""),
                              url=t.get("url", ""), browser="cdp",
                              metadata={"id": t["id"], "ws": t.get("webSocketDebuggerUrl", "")})
                for i, t in enumerate(items)]                 # /json/list is most-recently-active first

    def activate(self, tab):
        try:
            self._http(f"/json/activate/{tab.metadata['id']}")
            return True
        except Exception:
            return False

    def new_tab(self, url):
        try:
            t = self._http(f"/json/new?{urllib.parse.quote(url or 'about:blank', safe=':/?&=%#')}", method="PUT")
            return BrowserTabRef(resource_id=f"tab:{t['id']}", index=1, title=t.get("title", ""), url=t.get("url", url),
                                 browser="cdp", metadata={"id": t["id"], "ws": t.get("webSocketDebuggerUrl", "")})
        except Exception:
            return None

    def close_tab(self, tab):
        try:
            self._http(f"/json/close/{tab.metadata['id']}")
            return True
        except Exception:
            return False

    def _call(self, tab, method: str, params: dict) -> dict:
        from websockets.sync.client import connect
        ws_url = tab.metadata.get("ws") or next((t.metadata["ws"] for t in self.tabs()
                                                 if t.metadata["id"] == tab.metadata["id"]), "")
        if not ws_url:
            raise RuntimeError("tab has no DevTools socket")
        with connect(ws_url, open_timeout=2, close_timeout=1, max_size=8 * 1024 * 1024) as ws:
            ws.send(json.dumps({"id": 1, "method": method, "params": params}))
            while True:
                msg = json.loads(ws.recv(timeout=8))
                if msg.get("id") == 1:
                    if "error" in msg:
                        raise RuntimeError(msg["error"].get("message", "cdp error"))
                    return msg.get("result", {})

    def navigate(self, tab, url):
        try:
            self._call(tab, "Page.navigate", {"url": url})
            return True
        except Exception:
            return False

    def history(self, tab, delta):
        try:
            self._call(tab, "Runtime.evaluate", {"expression": f"history.go({int(delta)})"})
            return True
        except Exception:
            return False

    def reload(self, tab):
        try:
            self._call(tab, "Page.reload", {})
            return True
        except Exception:
            return False

    def set_files(self, tab, element_id: str, paths: list[str]) -> bool:
        """File inputs can't be filled from page script: DevTools sets the files on the element we resolved."""
        doc = self._call(tab, "DOM.getDocument", {"depth": 0})
        root = (doc.get("root") or {}).get("nodeId")
        node = self._call(tab, "DOM.querySelector", {"nodeId": root, "selector": f'[data-jarvis-id="{element_id}"]'})
        nid = node.get("nodeId")
        if not nid:
            return False
        self._call(tab, "DOM.setFileInputFiles", {"nodeId": nid, "files": paths})
        return True

    def run(self, tab, script, *args):
        body = SCRIPTS[script]
        expr = f"({body})({', '.join(json.dumps(a) for a in args)})" if args or body.lstrip().startswith("((") \
            else body
        res = self._call(tab, "Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True,
                                                   "userGesture": True})
        return (res.get("result") or {}).get("value")


class KeyboardBackend(BrowserBackend):
    """The owner's normal browser window, driven by chords; the window title is the only page signal."""

    name = "keyboard"
    dom = False

    def __init__(self, desktop: Optional[Desktop] = None, tracker=None):
        self._desktop = desktop
        self._tracker = tracker

    @property
    def desktop(self) -> Desktop:
        return self._desktop or get_desktop()

    def _window(self):
        if self._tracker is None:
            from jarvis.core.operator.windows import get_window_tracker
            self._tracker = get_window_tracker()
        found = self._tracker.resolve(family="browser")
        return found.resource if found.ok else None

    def available(self) -> bool:
        return self._window() is not None

    def tabs(self):
        w = self._window()
        if not w:
            return []
        title = re.sub(r"\s+[-–—]\s+(Google Chrome|Microsoft​? Edge|Mozilla Firefox|Brave|Opera)$", "", w.title)
        return [BrowserTabRef(resource_id=f"tab:kb:{w.hwnd}", index=0, title=title, url="", browser=w.process,
                              metadata={"hwnd": w.hwnd})]

    def _focus(self) -> bool:
        w = self._window()
        return bool(w) and self._tracker.focus(w).ok

    def _keys(self, *chords: str) -> bool:
        if not self._focus():
            return False
        for c in chords:
            self.desktop.press(parse_chord(c))
        return True

    def activate(self, tab):
        if tab.index and 1 <= tab.index <= 8:
            return self._keys(f"ctrl+{tab.index}")
        return self._focus()

    def new_tab(self, url):
        if not self._keys("ctrl+t"):
            return None
        if url:
            self.desktop.type_text(url)
            self.desktop.press(parse_chord("enter"))
        return BrowserTabRef(resource_id="tab:kb:new", index=0, title="", url=url, browser="keyboard")

    def close_tab(self, tab):
        return self._keys("ctrl+w")

    def navigate(self, tab, url):
        if not self._keys("ctrl+l"):
            return False
        self.desktop.type_text(url)
        self.desktop.press(parse_chord("enter"))
        return True

    def history(self, tab, delta):
        return self._keys(*(["alt+left"] * -delta if delta < 0 else ["alt+right"] * delta))

    def reload(self, tab):
        return self._keys("f5")

    def run(self, tab, script, *args):
        raise RuntimeError("no page access in keyboard mode")


class WebUIAdapter(UIAdapter):
    """The ui.* resolver over a page's interactive elements (via the fixed 'controls' script)."""

    platform = "web"

    def __init__(self, backend: BrowserBackend, tab: BrowserTabRef):
        self.backend, self.tab = backend, tab
        self._gen = 0

    def snapshot(self) -> list[ControlRef]:
        items = self.backend.run(self.tab, "controls") or []
        self._gen += 1
        return [ControlRef(resource_id=f"web:{c['id']}", platform="web", role=c.get("role", ""), name=c.get("name", ""),
                           selector=c["id"], enabled=c.get("enabled", True), visible=True,
                           editable=bool(c.get("editable")), bounds=tuple(c.get("bounds") or (0, 0, 0, 0)),
                           scope=self.tab.url, generation=self._gen,
                           metadata={"href": c.get("href", ""), "checked": c.get("checked"), "type": c.get("type", "")})
                for c in items]

    def invoke(self, c):
        self._gen += 1
        return bool(self.backend.run(self.tab, "click", c.selector))

    def set_value(self, c, text):
        if (c.metadata or {}).get("type") == "password":
            return False
        return bool(self.backend.run(self.tab, "set_value", c.selector, text))

    def read(self, c):
        v = self.backend.run(self.tab, "read_value", c.selector)
        return v if v is not None else c.name

    def focus(self, c):
        return bool(self.backend.run(self.tab, "focus", c.selector))

    def toggle_state(self, c):
        if (c.metadata or {}).get("type") != "checkbox" and c.role not in ("checkbox", "switch"):
            return None
        for x in self.backend.run(self.tab, "controls") or []:
            if x["id"] == c.selector:
                return x.get("checked")
        return None

    def scroll(self, direction, amount=1):
        return self.backend.run(self.tab, "scroll", direction, amount) is not None

    def generation(self):
        return self._gen


class BrowserOperator:
    def __init__(self, backend: Optional[BrowserBackend] = None, resources: Optional[OperatorResources] = None,
                 cdp_port: int = 9222):
        self._backend = backend
        self._res = resources
        self._port = cdp_port

    @property
    def resources(self) -> OperatorResources:
        return self._res or get_resources()

    @property
    def backend(self) -> BrowserBackend:
        if self._backend is not None:
            return self._backend
        cdp = CDPBackend(self._port)
        return cdp if cdp.available() else KeyboardBackend()

    # -- url building ----------------------------------------------------------------------------------------
    @staticmethod
    def to_url(target: str, engine: str = "") -> str:
        t = (target or "").strip()
        low = t.lower()
        if engine:
            tpl = SEARCH_ENGINES.get(engine.lower(), SEARCH_ENGINES["google"])
            return tpl.format(q=urllib.parse.quote_plus(t))
        if low in SITES:
            return SITES[low]
        if _URL.match(t):
            return t if low.startswith("http") else "https://" + t
        return SEARCH_ENGINES["google"].format(q=urllib.parse.quote_plus(t))

    # -- tabs / navigation -----------------------------------------------------------------------------------
    def current(self) -> Optional[BrowserTabRef]:
        return self.backend.active()

    def open(self, target: str, new_tab: bool = True, engine: str = "") -> OperatorOutcome:
        b = self.backend
        url = self.to_url(target, engine)
        if new_tab or not b.active():
            tab = b.new_tab(url)
            ok = tab is not None
        else:
            tab = b.active()
            ok = b.navigate(tab, url)
        if not ok:
            return OperatorOutcome(False, "The browser didn't respond.")
        tab = b.active() or tab
        self.resources.record(tab)
        return OperatorOutcome(True, f"Opened {tab.title or url}.", resource=tab, evidence={"url": url, "backend": b.name})

    def tab(self, op: str, which: str = "") -> OperatorOutcome:
        """op: new | close | next | previous | switch | reopen | list | duplicate | pin."""
        b = self.backend
        tabs = b.tabs()
        if op == "list":
            names = "; ".join(f"{t.index}. {t.title}" for t in self._ordered(tabs))
            return OperatorOutcome(bool(tabs), names or "No tabs are open.", evidence={"count": len(tabs)})
        if op == "new":
            t = b.new_tab("about:blank")
            return OperatorOutcome(t is not None, "New tab." if t else "I couldn't open a tab.", resource=t)
        if isinstance(b, KeyboardBackend) and op in ("next", "previous", "reopen", "close"):
            chord = {"next": "ctrl+tab", "previous": "ctrl+shift+tab", "reopen": "ctrl+shift+t", "close": "ctrl+w"}[op]
            ok = b._keys(chord)
            return OperatorOutcome(ok, f"{op.title()} tab." if ok else "No browser window is open.")
        if op in ("close", "switch", "next", "previous"):
            target = self._pick_tab(tabs, which, op)
            if isinstance(target, OperatorOutcome):
                return target
            if op == "close":
                ok = b.close_tab(target)
                return OperatorOutcome(ok, f"Closed {target.title}." if ok else "That tab didn't close.", resource=target)
            ok = b.activate(target)
            if ok:
                self.resources.record(target)
            return OperatorOutcome(ok, f"Switched to {target.title}." if ok else "I couldn't switch tabs.",
                                   resource=target)
        return OperatorOutcome(False, f"I can't do '{op}' with tabs here.", needs="clarify")

    def _ordered(self, tabs):
        b = self.backend
        return b.ordered() if hasattr(b, "ordered") else sorted(tabs, key=lambda t: t.index)

    def _pick_tab(self, tabs, which: str, op: str):
        if not tabs:
            return OperatorOutcome(False, "No tabs are open.")
        ordered = self._ordered(tabs)
        active = self.backend.active()
        pos = next((i for i, t in enumerate(ordered) if active and t.resource_id == active.resource_id), 0)
        if op == "next":
            return ordered[(pos + 1) % len(ordered)]
        if op == "previous":
            return ordered[(pos - 1) % len(ordered)]
        w = (which or "").lower().strip()
        if not w or w in ("this", "current", "it", "this one"):
            return active
        m = re.search(r"\b(\d+)\b", w)
        ords = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "last": len(ordered)}
        n = int(m.group(1)) if m else next((v for k, v in ords.items() if re.search(rf"\b{k}\b", w)), 0)
        if n:
            return ordered[n - 1] if 1 <= n <= len(ordered) else OperatorOutcome(
                False, f"There are only {len(ordered)} tabs.", needs="clarify")
        hits = [t for t in ordered if w in t.title.lower() or w in t.url.lower()]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            return OperatorOutcome(False, f"No open tab matches '{which}'.")
        return OperatorOutcome(False, "Which tab? " + "; ".join(f"{t.index}. {t.title}" for t in hits[:5]),
                               needs="clarify", candidates=hits)

    def nav(self, op: str, n: int = 1) -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if not tab:
            return OperatorOutcome(False, "No browser tab is open.")
        before = tab.url
        ok = b.reload(tab) if op == "reload" else b.history(tab, -n if op == "back" else n)
        after = b.active()
        if ok and op != "reload" and b.dom and after and after.url == before:
            ok = False
        return OperatorOutcome(ok, {"back": "Went back.", "forward": "Went forward.", "reload": "Reloaded."}[op]
                               if ok else f"There's no page to go {op} to.", resource=after)

    # -- page ------------------------------------------------------------------------------------------------
    def page_adapter(self) -> Optional[WebUIAdapter]:
        b = self.backend
        tab = b.active()
        return WebUIAdapter(b, tab) if (tab and b.dom) else None

    def results(self) -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if not tab or not b.dom:
            return OperatorOutcome(False, "I can't read this page's results.", needs="vision")
        items = b.run(tab, "results") or []
        links = [LinkRef(resource_id=f"link:{r['id']}", title=r.get("title", ""), url=r.get("url", ""),
                         selector=r["id"], result_rank=i + 1, metadata={"kind": r.get("kind", "")})
                 for i, r in enumerate(items) if r.get("url")]
        try:
            from jarvis.core.context.models import ResultSet
            rs = ResultSet(result_set_id=f"web:{tab.url}", query=tab.title, item_type="LINK", resources=list(links))
            wm = getattr(self.resources, "_wm", None)
            if wm is not None:
                wm.record_result_set(rs)
        except Exception:
            pass
        for link in reversed(links[:10]):
            self.resources.record(link)
        return OperatorOutcome(bool(links), "\n".join(f"{l.result_rank}. {l.title}" for l in links[:10]) or
                               "No results on this page.", candidates=links, evidence={"untrusted": True})

    def open_result(self, ordinal: int = 1, title: str = "", new_tab: bool = False) -> OperatorOutcome:
        found = self.results()
        if not found.ok:
            return found
        links: list[LinkRef] = found.candidates
        pick: Optional[LinkRef] = None
        if title:
            hits = [l for l in links if title.lower() in l.title.lower()]
            if len(hits) > 1 and not ordinal:
                return OperatorOutcome(False, "Which one? " + "; ".join(f"{l.result_rank}. {l.title}" for l in hits[:5]),
                                       needs="clarify", candidates=hits)
            pick = hits[0] if hits else None
        else:
            idx = ordinal - 1 if ordinal > 0 else len(links) - 1
            pick = links[idx] if 0 <= idx < len(links) else None
        if not pick:
            return OperatorOutcome(False, f"There's no result {ordinal or title} on this page.", needs="clarify")
        b = self.backend
        tab = b.active()
        before = tab.url
        if new_tab:
            ok = b.new_tab(pick.url) is not None
        else:
            ok = bool(b.run(tab, "click", pick.selector)) or b.navigate(tab, pick.url)
        after = b.active()
        ok = ok and bool(after) and (new_tab or after.url != before)
        if ok:
            self.resources.record(after)
        return OperatorOutcome(ok, f"Opened {pick.title}." if ok else "The result didn't open.", resource=after or pick)

    def read_page(self) -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if not tab:
            return OperatorOutcome(False, "No page is open.")
        if not b.dom:
            return OperatorOutcome(False, "I can't read this page from here.", needs="vision", resource=tab)
        data = b.run(tab, "text") or {}
        self.resources.record(tab)
        return OperatorOutcome(bool(data.get("text")), data.get("text") or "The page has no readable text.",
                               resource=tab, evidence={"untrusted": True, "title": data.get("title", "")})

    def find_on_page(self, query: str) -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if tab and b.dom:
            found = bool(b.run(tab, "find", query))
            return OperatorOutcome(found, f"Found '{query}'." if found else f"'{query}' isn't on this page.")
        if isinstance(b, KeyboardBackend) and b._keys("ctrl+f"):
            b.desktop.type_text(query)
            return OperatorOutcome(True, f"Searching the page for '{query}'.", evidence={"verified": None})
        return OperatorOutcome(False, "No page is open.")

    def scroll(self, direction: str = "down", amount: int = 1) -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if tab and b.dom:
            b.run(tab, "scroll", direction, amount)
            return OperatorOutcome(True, f"Scrolled {direction}.")
        key = {"down": "pagedown", "up": "pageup", "top": "home", "bottom": "end"}.get(direction, "pagedown")
        ok = isinstance(b, KeyboardBackend) and b._keys(*([key] * max(1, amount)))
        return OperatorOutcome(ok, f"Scrolled {direction}." if ok else "No page is open.")

    # -- more page / tab primitives ----------------------------------------------------------------------------
    def info(self, what: str = "url") -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if not tab:
            return OperatorOutcome(False, "No browser tab is open.")
        if what == "title":
            return OperatorOutcome(bool(tab.title), f"This page is “{tab.title}”." if tab.title else "The page has no title.",
                                   resource=tab, evidence={"untrusted": True})
        if not tab.url:
            return OperatorOutcome(False, f"I can see the tab “{tab.title}”, but not its address without page access.",
                                   resource=tab, needs="vision")
        return OperatorOutcome(True, f"You're on {tab.url}", resource=tab, evidence={"url": tab.url})

    def copy_url(self, desktop=None) -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if not tab:
            return OperatorOutcome(False, "No browser tab is open.")
        if not tab.url and isinstance(b, KeyboardBackend) and b._keys("ctrl+l", "ctrl+c", "escape"):
            return OperatorOutcome(True, "Copied the page link.", resource=tab, evidence={"verified": None})
        from jarvis.core.operator.platform import get_desktop
        d = desktop or get_desktop()
        ok = d.set_clipboard_text(tab.url) and d.clipboard_text() == tab.url
        return OperatorOutcome(ok, f"Copied {tab.url}" if ok else "I couldn't copy the link.", resource=tab)

    def duplicate(self) -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if not tab:
            return OperatorOutcome(False, "No browser tab is open.")
        if isinstance(b, KeyboardBackend):
            ok = b._keys("alt+d", "alt+enter")
            return OperatorOutcome(ok, "Duplicated the tab." if ok else "No browser window is open.", evidence={"verified": None})
        before = len(b.tabs())
        new = b.new_tab(tab.url)
        ok = new is not None and len(b.tabs()) == before + 1
        return OperatorOutcome(ok, f"Duplicated {tab.title}." if ok else "The tab didn't duplicate.", resource=new)

    def stop(self) -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if tab and b.dom:
            b.run(tab, "stop")
            return OperatorOutcome(True, "Stopped loading the page.")
        ok = isinstance(b, KeyboardBackend) and b._keys("escape")
        return OperatorOutcome(ok, "Stopped loading the page." if ok else "No page is loading.", evidence={"verified": None})

    def heading(self, name: str, read: bool = False) -> OperatorOutcome:
        """'take me to installation' / 'summarise only the installation section' (text returned for the model)."""
        b = self.backend
        tab = b.active()
        if not tab or not b.dom:
            if isinstance(b, KeyboardBackend):
                return self.find_on_page(name)
            return OperatorOutcome(False, "No page is open.")
        heads = b.run(tab, "headings") or []
        want = name.lower().strip()
        hits = [h for h in heads if want in (h.get("text") or "").lower()]
        if not hits:
            return OperatorOutcome(False, f"This page has no '{name}' section.", needs="clarify",
                                   candidates=[h.get("text") for h in heads[:8]])
        h = hits[0]
        if read:
            text = b.run(tab, "section_text", h["id"]) or ""
            return OperatorOutcome(bool(text.strip()), text or "That section is empty.", resource=tab,
                                   evidence={"section": h.get("text"), "untrusted": True})
        b.run(tab, "scroll_to", h["id"])
        return OperatorOutcome(True, f"Jumped to “{h.get('text')}”.", resource=tab)

    def site_search(self, query: str) -> OperatorOutcome:
        tab = self.backend.active()
        host = urllib.parse.urlparse(tab.url).hostname if tab and tab.url else ""
        if not host:
            return OperatorOutcome(False, "Which site? I can't read this tab's address.", needs="clarify")
        return self.open(f"site:{host} {query}", new_tab=True, engine="google")

    def official(self, topic: str) -> OperatorOutcome:
        """Search restricted to the project's own documentation: 'official documentation <topic>' with docs/vendor
        domains first. The pages found are data to read, not instructions."""
        q = f"{topic} official documentation"
        return self.open(q, new_tab=True, engine="google")

    def login_state(self) -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if not tab or not b.dom:
            return OperatorOutcome(False, "I need page access to check that.", needs="vision")
        st = b.run(tab, "login_state") or {}
        if st.get("captcha"):
            return OperatorOutcome(True, "There's a CAPTCHA on this page - that one is yours to solve.",
                                   evidence={**st, "needs_user": True})
        needs = bool(st.get("password_fields")) or bool(st.get("sign_in_text"))
        return OperatorOutcome(True, "Yes - this page wants you to sign in (I won't type passwords)." if needs
                               else "No sign-in is needed on this page.", evidence=st)

    def open_link(self, name: str, new_tab: bool = False) -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if not tab or not b.dom:
            return OperatorOutcome(False, "I need page access to find links.", needs="vision")
        links = b.run(tab, "links") or []
        want = name.lower().replace(" link", "").strip()
        hits = [l for l in links if want in (l.get("text") or "").lower()]
        if not hits:
            return OperatorOutcome(False, f"I can't see a '{name}' link here.")
        if len({h["href"] for h in hits}) > 1:
            return OperatorOutcome(False, "Which link? " + "; ".join(h["text"] for h in hits[:5]), needs="clarify",
                                   candidates=hits)
        before = tab.url
        if new_tab:
            ok = b.new_tab(hits[0]["href"]) is not None
        else:
            ok = bool(b.run(tab, "click", hits[0]["id"])) or b.navigate(tab, hits[0]["href"])
        after = b.active()
        ok = ok and (new_tab or (after and after.url != before))
        return OperatorOutcome(ok, f"Opened {hits[0]['text']}." if ok else "The link didn't open.", resource=after)

    def upload(self, paths: list[str], field: str = "") -> OperatorOutcome:
        """Upload via the page's own file input. Never submits the form."""
        b = self.backend
        tab = b.active()
        if not tab or not b.dom or not hasattr(b, "set_files"):
            return OperatorOutcome(False, "I need page access to upload; open the page in the JARVIS Chrome profile.",
                                   needs="user")
        import os as _os
        missing = [p for p in paths if not _os.path.exists(p)]
        if missing:
            return OperatorOutcome(False, f"{_os.path.basename(missing[0])} doesn't exist.")
        controls = b.run(tab, "controls") or []
        inputs = [c for c in controls if c.get("type") == "file" or "upload" in (c.get("name") or "").lower()
                  or "attach" in (c.get("name") or "").lower()]
        if field:
            inputs = [c for c in inputs if field.lower() in (c.get("name") or "").lower()] or inputs
        if not inputs:
            return OperatorOutcome(False, "This page has no file upload field I can see.")
        if len(inputs) > 1 and not field:
            return OperatorOutcome(False, "Which upload field? " + "; ".join(c.get("name") or "file" for c in inputs[:5]),
                                   needs="clarify")
        ok = b.set_files(tab, inputs[0]["id"], paths)
        names = ", ".join(_os.path.basename(p) for p in paths)
        return OperatorOutcome(ok, f"Attached {names} to the page (not submitted)." if ok else "The upload field refused it.",
                               evidence={"verified": ok})

    def download(self, name: str = "") -> OperatorOutcome:
        b = self.backend
        tab = b.active()
        if not tab or not b.dom:
            return OperatorOutcome(False, "I need page access to start a download.", needs="vision")
        links = b.run(tab, "links") or []
        want = (name or "").lower()
        cands = [l for l in links if l.get("download") or re.search(r"\.(pdf|zip|docx?|xlsx?|pptx?|csv|exe|msi|png|jpe?g)(\?|$)",
                                                                    l.get("href", ""), re.I)]
        if want:
            cands = [l for l in cands if any(w in (l.get("text", "") + l.get("href", "")).lower()
                                             for w in re.findall(r"[a-z0-9]+", want) if w not in ("that", "the", "this"))] or cands
        if not cands:
            return OperatorOutcome(False, "I don't see a downloadable file link here.")
        if len(cands) > 1:
            return OperatorOutcome(False, "Which one? " + "; ".join((c.get("text") or c["href"])[:60] for c in cands[:5]),
                                   needs="clarify", candidates=cands)
        b.run(tab, "click", cands[0]["id"])
        return OperatorOutcome(True, f"Started downloading {cands[0].get('text') or cands[0]['href']}. Say 'tell me when "
                                     "the download finishes' to be told.", evidence={"href": cands[0]["href"]})

