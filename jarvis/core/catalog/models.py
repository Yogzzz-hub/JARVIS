"""Data models for Application Catalog, Package Catalog, and Discovery in JARVIS EDGE."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional, Tuple


class AvailabilityState(str, Enum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    REQUIRES_AUTH = "REQUIRES_AUTH"
    CORRUPTED = "CORRUPTED"


@dataclass(slots=True)
class AppEntry:
    """Canonical launch and discovery metadata for an installed application."""
    app_id: str
    display_name: str
    canonical_name: str
    aliases: Tuple[str, ...]
    executable_path: str
    arguments: Tuple[str, ...] = ()
    source: str = "unknown"  # "registry_uninstall", "app_paths", "start_menu", "uwp", "path", "built_in", "user_alias"
    install_location: Optional[str] = None
    version: Optional[str] = None
    last_verified: float = field(default_factory=time.time)
    availability: str = AvailabilityState.AVAILABLE.value
    process_names: Tuple[str, ...] = ()
    associated: bool = False  # True if launched via shell/protocol/URL
    publisher: Optional[str] = None
    icon_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "display_name": self.display_name,
            "canonical_name": self.canonical_name,
            "aliases": list(self.aliases),
            "executable_path": self.executable_path,
            "arguments": list(self.arguments),
            "source": self.source,
            "install_location": self.install_location,
            "version": self.version,
            "last_verified": self.last_verified,
            "availability": self.availability,
            "process_names": list(self.process_names),
            "associated": self.associated,
            "publisher": self.publisher,
            "icon_path": self.icon_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppEntry:
        return cls(
            app_id=data["app_id"],
            display_name=data["display_name"],
            canonical_name=data["canonical_name"],
            aliases=tuple(data.get("aliases", ())),
            executable_path=data["executable_path"],
            arguments=tuple(data.get("arguments", ())),
            source=data.get("source", "unknown"),
            install_location=data.get("install_location"),
            version=data.get("version"),
            last_verified=data.get("last_verified", time.time()),
            availability=data.get("availability", AvailabilityState.AVAILABLE.value),
            process_names=tuple(data.get("process_names", ())),
            associated=data.get("associated", False),
            publisher=data.get("publisher"),
            icon_path=data.get("icon_path"),
        )


@dataclass(slots=True)
class PackageEntry:
    """Software package definition for package catalog and installation."""
    package_id: str  # e.g. "VideoLAN.VLC", "Microsoft.VisualStudioCode"
    display_name: str
    canonical_name: str
    aliases: Tuple[str, ...] = ()
    installer_type: str = "winget"  # "winget", "msi", "choco"
    default_args: Tuple[str, ...] = ()
    verified: bool = True
    category: str = "utilities"
    expected_process_names: Tuple[str, ...] = ()
    expected_executable_stems: Tuple[str, ...] = ()


@dataclass(slots=True)
class RefreshSummary:
    """Outcome report for an application catalog refresh cycle."""
    total_apps: int
    new_apps: int
    updated_apps: int
    elapsed_ms: float
    sources_scanned: Tuple[str, ...]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_apps": self.total_apps,
            "new_apps": self.new_apps,
            "updated_apps": self.updated_apps,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "sources_scanned": list(self.sources_scanned),
            "timestamp": self.timestamp,
        }
