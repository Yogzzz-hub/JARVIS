from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import shutil

@dataclass(frozen=True, slots=True)
class LaunchTarget:
    path: str
    process_names: tuple[str, ...]
    associated: bool = False

ALIASES = {
    "chrome": ("chrome.exe", ("chrome.exe",)),
    "edge": ("msedge.exe", ("msedge.exe",)),
    "notepad": ("notepad.exe", ("notepad.exe",)),
    "calculator": ("calc.exe", ("calculatorapp.exe", "calculator.exe", "calc.exe")),
    "vscode": ("code.exe", ("code.exe",)),
    "explorer": ("explorer.exe", ("explorer.exe",)),
    "terminal": ("wt.exe", ("windowsterminal.exe",)),
    "cmd": ("cmd.exe", ("cmd.exe",)),
    "powershell": ("powershell.exe", ("powershell.exe",)),
    "brave": ("brave.exe", ("brave.exe",)),
    "firefox": ("firefox.exe", ("firefox.exe",)),
    "outlook": ("outlook.exe", ("outlook.exe", "olk.exe")),
    "onenote": ("onenote.exe", ("onenote.exe",)),
    "vlc": ("vlc.exe", ("vlc.exe",)),
    "discord": ("discord.exe", ("discord.exe",)),
    "zoom": ("zoom.exe", ("zoom.exe",)),
    "telegram": ("telegram.exe", ("telegram.exe",)),
    "opera": ("opera.exe", ("opera.exe",)),
    "winrar": ("winrar.exe", ("winrar.exe",)),
    "mspaint": ("mspaint.exe", ("mspaint.exe", "paint.exe")),
    "paint": ("mspaint.exe", ("mspaint.exe", "paint.exe")),
    "snippingtool": ("snippingtool.exe", ("snippingtool.exe", "screensketch.exe")),
    "word": ("winword.exe", ("winword.exe",)),
    "excel": ("excel.exe", ("excel.exe",)),
    "powerpoint": ("powerpnt.exe", ("powerpnt.exe",)),
    "defaultapps": ("ms-settings:defaultapps", ("systemsettings.exe",)),
    "downloads": ("shell:Downloads", ("explorer.exe",)),
    "documents": ("shell:Personal", ("explorer.exe",)),
    "pictures": ("shell:My Pictures", ("explorer.exe",)),
    "videos": ("shell:My Video", ("explorer.exe",)),
    "music": ("shell:My Music", ("explorer.exe",)),
}
SYNONYMS = {
    "calc": "calculator", "vs code": "vscode", "visual studio code": "vscode",
    "google chrome": "chrome", "microsoft edge": "edge", "msedge": "edge",
    "browser": "chrome", "web browser": "chrome", "internet": "chrome",
    "my browser": "chrome", "the browser": "chrome",
    "default apps": "defaultapps", "default application": "defaultapps",
    "default applications": "defaultapps", "default app": "defaultapps",
    "downloads": "downloads", "my downloads": "downloads", "downloads folder": "downloads",
    "documents": "documents", "my documents": "documents", "documents folder": "documents",
    "pictures": "pictures", "my pictures": "pictures", "pictures folder": "pictures",
    "videos": "videos", "my videos": "videos", "videos folder": "videos",
    "music": "music", "my music": "music", "music folder": "music",
    "file explorer": "explorer", "windows terminal": "terminal",
    "command": "cmd", "command prompt": "cmd",
    # Paint & drawing
    "paint": "mspaint", "ms paint": "mspaint", "microsoft paint": "mspaint",
    # Snipping / screenshot
    "snipping tool": "snippingtool", "snip": "snippingtool", "screen snip": "snippingtool",
    "screenshot tool": "snippingtool",
    # Office
    "microsoft word": "word", "ms word": "word",
    "microsoft excel": "excel", "ms excel": "excel",
    "microsoft powerpoint": "powerpoint", "ms powerpoint": "powerpoint", "ppt": "powerpoint",
    "microsoft outlook": "outlook", "ms outlook": "outlook", "mail": "outlook",
    "microsoft onenote": "onenote", "ms onenote": "onenote",
    # Teams
    "teams": "ms-teams", "microsoft teams": "ms-teams",
    # Store
    "microsoft store": "store", "windows store": "store", "ms store": "store",
    # Task manager
    "taskmgr": "task manager", "taskmanager": "task manager",
    # Media
    "photos": "microsoft photos", "windows photos": "microsoft photos",
    "camera": "microsoft camera", "webcam": "microsoft camera",
    # Browsers
    "browser": "chrome", "web browser": "chrome", "my browser": "chrome", "the browser": "chrome",
    "internet": "chrome", "internet browser": "chrome",
    "brave browser": "brave", "mozilla firefox": "firefox", "mozilla": "firefox",
    "opera browser": "opera",
    # Communication
    "telegram desktop": "telegram",
    # Others
    "clock": "windows clock", "alarms": "windows clock", "timer": "windows clock",
    "weather": "msn weather",
    "maps": "windows maps",
    "this pc": "explorer", "my computer": "explorer",
    "control panel": "control",
    "recycle bin": "explorer",
}

def normalize(name):
    return " ".join(name.casefold().split())


def trusted_executable(raw_path):
    """Only automatically discover executables in standard installed-app roots.

    Other locations require an explicit user-configured alias.
    """
    path = Path(os.path.expandvars(str(raw_path).strip('"')))
    if not path.is_absolute() or path.suffix.casefold() != ".exe" or not path.is_file():
        return None
    path = path.resolve()
    # Reject raw binaries inside Program Files\WindowsApps because they fail when directly invoked without package activation
    parts_lower = [p.casefold() for p in path.parts]
    if "windowsapps" in parts_lower and "program files" in parts_lower:
        return None
    roots = [Path(os.environ[key]).resolve() for key in ('SystemRoot', 'ProgramFiles', 'ProgramFiles(x86)') if os.environ.get(key)]
    local = os.environ.get('LOCALAPPDATA')
    if local:
        roots.extend((Path(local) / suffix).resolve() for suffix in ('Programs', 'Microsoft/WindowsApps', 'Google/Chrome', 'Microsoft/Edge'))
    return str(path) if any(path.is_relative_to(root) for root in roots) else None

WEB_SERVICES = {
    "youtube": "https://www.youtube.com",
    "whatsapp": "https://web.whatsapp.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
    "gmail": "https://mail.google.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "spotify": "https://open.spotify.com",
    "netflix": "https://www.netflix.com",
    "chatgpt": "https://chatgpt.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "linkedin": "https://www.linkedin.com",
}

class AppResolver:
    def __init__(self, aliases=(), auto_build: bool = True):
        self.user_aliases = aliases
        self.cache: dict[str, LaunchTarget] = {}
        self.build_count = 0
        if auto_build and not aliases and type(self) is AppResolver:
            try:
                self.build()
            except Exception as exc:
                logging.getLogger("jarvis.resolver").warning("Initial app cache build warning: %s", exc)

    def list_apps(self) -> list[str]:
        return sorted(self.cache.keys())

    def build(self):
        cache = {}
        app_paths = {}
        if os.name == "nt":
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                    names = set(executable for executable, _ in ALIASES.values())
                    try:
                        with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\App Paths", 0, winreg.KEY_READ | view) as parent:
                            for index in range(winreg.QueryInfoKey(parent)[0]):
                                names.add(winreg.EnumKey(parent, index))
                    except OSError:
                        pass
                    for executable in sorted(names):
                        try:
                            with winreg.OpenKey(hive, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable}", 0, winreg.KEY_READ | view) as key:
                                value, _ = winreg.QueryValueEx(key, None)
                                path = trusted_executable(value)
                                if path:
                                    app_paths.setdefault(executable.casefold(), path)
                                    cache.setdefault(normalize(Path(executable).stem), LaunchTarget(path, (Path(path).name.casefold(),)))
                        except FileNotFoundError:
                            continue
                        except OSError as exc:
                            logging.getLogger("jarvis.resolver").warning("App Paths read failed: %s", exc)
            for env in ("APPDATA", "PROGRAMDATA"):
                if os.environ.get(env):
                    root = Path(os.environ[env]) / "Microsoft/Windows/Start Menu/Programs"
                    for path in sorted(root.rglob("*.lnk")):
                        # Unknown shortcut process names cannot be confidently verified.
                        cache.setdefault(normalize(path.stem), LaunchTarget(str(path), (), True))
            cache["settings"] = LaunchTarget("ms-settings:", ("systemsettings.exe",), True)
            cache["default apps"] = LaunchTarget("ms-settings:defaultapps", ("systemsettings.exe",), True)
            cache["defaultapps"] = LaunchTarget("ms-settings:defaultapps", ("systemsettings.exe",), True)
            cache["default applications"] = LaunchTarget("ms-settings:defaultapps", ("systemsettings.exe",), True)
            # UWP apps with protocol URIs (fallback for apps not found via App Paths/Start Menu)
            uwp_protocols = {
                "photos": ("ms-photos:", ("microsoft.photos.exe",)),
                "microsoft photos": ("ms-photos:", ("microsoft.photos.exe",)),
                "camera": ("microsoft.windows.camera:", ("windowscamera.exe",)),
                "microsoft camera": ("microsoft.windows.camera:", ("windowscamera.exe",)),
                "clock": ("ms-clock:", ("time.exe",)),
                "windows clock": ("ms-clock:", ("time.exe",)),
                "alarms": ("ms-clock:", ("time.exe",)),
                "weather": ("bingweather:", ("microsoft.bingweather.exe",)),
                "msn weather": ("bingweather:", ("microsoft.bingweather.exe",)),
                "maps": ("bingmaps:", ("microsoft.windowsmaps.exe",)),
                "windows maps": ("bingmaps:", ("microsoft.windowsmaps.exe",)),
                "mail": ("outlookmail:", ("hxoutlook.exe",)),
                "outlook": ("outlookmail:", ("hxoutlook.exe",)),
                "calendar": ("outlookcal:", ("hxcalendarappimm.exe",)),
            }
            for uwp_name, (protocol, procs) in uwp_protocols.items():
                cache.setdefault(uwp_name, LaunchTarget(protocol, procs, True))
        for name, (executable, processes) in ALIASES.items():
            candidate = shutil.which(executable)
            cand_path = trusted_executable(candidate) if candidate and os.name == 'nt' else candidate
            app_path = app_paths.get(executable)
            # Prefer system/alias executable over registry App Paths if available
            path = cand_path or app_path
            if path:
                cache[name] = LaunchTarget(str(Path(path).resolve()), processes)
            elif name in cache:
                cache[name] = LaunchTarget(cache[name].path, processes, True)
        for svc_name, svc_url in WEB_SERVICES.items():
            if svc_name not in cache:
                cache[svc_name] = LaunchTarget(svc_url, ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"), True)
        for alias, name in SYNONYMS.items():
            if name in cache:
                cache[alias] = cache[name]
        for name, raw_path in self.user_aliases:
            path = Path(raw_path)
            if not path.is_absolute() or not path.is_file() or path.suffix.casefold() != ".exe":
                raise ValueError(f"alias {name!r} must reference an existing absolute .exe")
            cache[normalize(name)] = LaunchTarget(str(path), (path.name.casefold(),))
        self.cache = cache  # atomically replace, including during background rebuild
        self.build_count += 1

    def resolve(self, name):
        norm = normalize(name)
        if norm in self.cache:
            return self.cache[norm]

        # Conversational / politeness cleanup
        cleaned = norm
        cleaned = re.sub(r"^(?:the\s+|an\s+|a\s+)", "", cleaned)
        for _ in range(3):
            prev_len = len(cleaned)
            cleaned = re.sub(
                r"\s+(?:for me please|for us please|for me|for us|please|kindly|plz|if you can|right now|quickly|immediately|now|bro|dude|yaar|da|app|application|browser)$",
                "",
                cleaned,
            ).strip()
            if len(cleaned) == prev_len:
                break

        if cleaned in self.cache:
            return self.cache[cleaned]

        if cleaned in SYNONYMS and SYNONYMS[cleaned] in self.cache:
            return self.cache[SYNONYMS[cleaned]]

        # Check known web services
        if cleaned in WEB_SERVICES:
            return LaunchTarget(WEB_SERVICES[cleaned], ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"), True)
        if norm in WEB_SERVICES:
            return LaunchTarget(WEB_SERVICES[norm], ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"), True)

        # Fallback: check individual tokens against known aliases / web services
        for token in cleaned.split():
            if token in ALIASES and token in self.cache:
                return self.cache[token]
            if token in SYNONYMS and SYNONYMS[token] in self.cache:
                return self.cache[SYNONYMS[token]]
            if token in WEB_SERVICES:
                return LaunchTarget(WEB_SERVICES[token], ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"), True)

        # Check if direct URL or domain
        if norm.startswith(("http://", "https://", "www.")) or (len(norm.split()) == 1 and any(norm.endswith(tld) for tld in (".com", ".org", ".net", ".io", ".ai", ".dev", ".edu", ".in"))):
            url = norm if norm.startswith(("http://", "https://")) else f"https://{norm}"
            return LaunchTarget(url, ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"), True)

        # Check YouTube search / music query, e.g. "music in youtube"
        if "youtube" in norm:
            import urllib.parse
            clean_q = norm.replace("in youtube", "").replace("on youtube", "").replace("youtube", "").strip()
            if clean_q:
                query = urllib.parse.quote_plus(clean_q)
                return LaunchTarget(f"https://www.youtube.com/results?search_query={query}", ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"), True)
            return LaunchTarget("https://www.youtube.com", ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"), True)

        # Check Google search query, e.g. "google python" or "search google for python"
        if norm.startswith("google ") or norm.startswith("search google for ") or " on google" in norm:
            import urllib.parse
            clean_q = norm.replace("search google for ", "").replace("google ", "").replace("on google", "").strip()
            if clean_q:
                query = urllib.parse.quote_plus(clean_q)
                return LaunchTarget(f"https://www.google.com/search?q={query}", ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"), True)
            return LaunchTarget("https://www.google.com", ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"), True)

        # Fuzzy / substring match against cache keys (e.g. "paint" matches "mspaint")
        search_terms = [cleaned, norm]
        # Also check synonym target even if not in cache directly
        if cleaned in SYNONYMS:
            search_terms.append(SYNONYMS[cleaned])
        for term in search_terms:
            if not term:
                continue
            for key, target in self.cache.items():
                if len(term) >= 3 and term in key:
                    return target
                if len(key) >= 3 and re.search(rf"\b{re.escape(key)}\b", term):
                    return target

        raise ValueError(f"Application is not indexed: {name}") from None
