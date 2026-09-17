from dataclasses import dataclass
import logging
import os
from pathlib import Path
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
}
SYNONYMS = {"calc": "calculator", "vs code": "vscode", "file explorer": "explorer"}

def normalize(name):
    return " ".join(name.casefold().split())

class AppResolver:
    def __init__(self, aliases=()):
        self.user_aliases = aliases
        self.cache: dict[str, LaunchTarget] = {}
        self.build_count = 0

    def build(self):
        cache = {}
        app_paths = {}
        if os.name == "nt":
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                    for executable, _ in ALIASES.values():
                        try:
                            with winreg.OpenKey(hive, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable}", 0, winreg.KEY_READ | view) as key:
                                value, _ = winreg.QueryValueEx(key, None)
                                path = Path(os.path.expandvars(value.strip('"')))
                                if path.is_file():
                                    app_paths.setdefault(executable, str(path))
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
        for name, (executable, processes) in ALIASES.items():
            path = app_paths.get(executable) or shutil.which(executable)
            if path:
                cache[name] = LaunchTarget(str(Path(path).resolve()), processes)
            elif name in cache:
                cache[name] = LaunchTarget(cache[name].path, processes, True)
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
        try:
            return self.cache[normalize(name)]
        except KeyError:
            raise ValueError(f"Application is not indexed: {name}") from None
