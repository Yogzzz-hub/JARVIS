"""Deterministic Response Formatter for JARVIS EDGE Phase 7.

Translates verified outcomes, filenames, paths, numbers, acronyms, and lists
into natural, concise speakable sentences without requiring an LLM.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, List, Optional, Sequence


KNOWN_EXTENSIONS = {
    ".pdf": "PDF",
    ".xlsx": "Excel file",
    ".xls": "Excel file",
    ".docx": "Word document",
    ".doc": "Word document",
    ".pptx": "PowerPoint file",
    ".ppt": "PowerPoint file",
    ".txt": "text file",
    ".csv": "CSV file",
    ".zip": "ZIP archive",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".mp3": "audio file",
    ".wav": "audio file",
    ".mp4": "video file",
    ".py": "Python script",
    ".json": "JSON file",
}

KNOWN_FOLDERS = {
    "downloads": "your Downloads folder",
    "desktop": "your Desktop",
    "documents": "your Documents",
    "pictures": "your Pictures",
    "music": "your Music folder",
    "videos": "your Videos folder",
}


class ResponseFormatter:
    """Formats system facts into concise, natural spoken responses."""

    @classmethod
    def format_filename(cls, filename: str) -> str:
        """Convert ugly filenames like UNIT_4_DL_FINAL_2.pdf into natural speech."""
        if not filename:
            return ""

        path_obj = Path(filename)
        stem = path_obj.stem
        ext = path_obj.suffix.lower()

        # Replace underscores and hyphens with spaces
        clean_stem = re.sub(r"[_\-]+", " ", stem)

        # Normalize casing
        words = clean_stem.split()
        formatted_words = []
        for w in words:
            if w.isupper() and len(w) > 3:
                formatted_words.append(w.title())
            elif w.islower():
                formatted_words.append(w.capitalize())
            else:
                formatted_words.append(w)
        spoken_stem = " ".join(formatted_words)

        spoken_ext = KNOWN_EXTENSIONS.get(ext, ext.lstrip(".").upper() if ext else "")
        if spoken_ext:
            return f"{spoken_stem} {spoken_ext}".strip()
        return spoken_stem.strip()

    @classmethod
    def format_path(cls, path_str: str) -> str:
        """Convert absolute paths into friendly spoken descriptions."""
        if not path_str:
            return ""

        path = Path(path_str)
        name_lower = path.name.lower()
        if name_lower in KNOWN_FOLDERS:
            return KNOWN_FOLDERS[name_lower]

        # Look at last folder name
        parts = [p for p in path.parts if p not in (path.anchor, "\\", "/")]
        if not parts:
            return "the root folder"

        last = parts[-1]
        last_lower = last.lower()
        if last_lower in KNOWN_FOLDERS:
            return KNOWN_FOLDERS[last_lower]

        clean_last = re.sub(r"[_\-]+", " ", last)
        return clean_last

    @classmethod
    def format_number(cls, text: str) -> str:
        """Normalize numbers, percentages, and times for natural speech."""
        # 30% -> 30 percent
        text = re.sub(r"(\d+(?:\.\d+)?)%", r"\1 percent", text)

        # Time formatting: 20:35 -> 8:35 PM, 08:35 -> 8:35 AM
        def _replace_time(match: re.Match) -> str:
            hour = int(match.group(1))
            minute = int(match.group(2))
            suffix = "AM" if hour < 12 else "PM"
            display_hour = hour % 12
            if display_hour == 0:
                display_hour = 12
            if minute == 0:
                return f"{display_hour} {suffix}"
            return f"{display_hour}:{minute:02d} {suffix}"

        text = re.sub(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", _replace_time, text)
        return text

    @classmethod
    def format_list(cls, items: Sequence[str], max_items: int = 3) -> str:
        """Format a list of items bounded to at most max_items spoken."""
        if not items:
            return "none"

        formatted_items = [cls.format_filename(it) if "." in it else it for it in items]
        total = len(formatted_items)

        if total == 1:
            return formatted_items[0]
        if total == 2:
            return f"{formatted_items[0]} and {formatted_items[1]}"
        if total <= max_items:
            return ", ".join(formatted_items[:-1]) + f", and {formatted_items[-1]}"

        # Truncated list
        spoken_slice = formatted_items[:max_items]
        remaining = total - max_items
        return ", ".join(spoken_slice) + f", plus {remaining} more"

    @classmethod
    def format_verified_tool(cls, tool_name: str, data: Any) -> str:
        """Deterministic templating for standard tool execution."""
        match tool_name:
            case "open_app":
                app_name = data.get("name", "The application")
                return f"{app_name.capitalize()} is open."

            case "volume_set":
                pct = data.get("percent", 0)
                return f"Volume set to {pct:.0f} percent."

            case "volume_get":
                pct = data.get("percent", 0)
                return f"Volume is {pct:.0f} percent."

            case "take_screenshot":
                return "Screenshot saved."

            case "get_time":
                # E.g. "2026-09-17T20:35:00" -> "8:35 PM"
                iso = data.get("iso", "")
                if "T" in iso:
                    time_part = iso.split("T")[1][:5]
                    return cls.format_number(time_part)
                return iso

            case "list_directory":
                entries = data.get("entries", [])
                count = len(entries)
                if count == 0:
                    return "The folder is empty."
                if count <= 3:
                    spoken = cls.format_list(entries, max_items=3)
                    return f"Found {count} items: {spoken}."
                return f"Found {count} items, including {cls.format_list(entries[:3], max_items=3)}."

            case "find_file" | "search_files":
                matches = data.get("matches", []) or data.get("results", [])
                count = len(matches) if isinstance(matches, list) else data.get("count", 0)
                if count == 0:
                    return "I couldn't find any matching files."
                if count == 1 and isinstance(matches, list) and matches:
                    m = matches[0]
                    name = m.get("filename", "") if isinstance(m, dict) else str(m)
                    return f"I found {cls.format_filename(name)}."
                return f"I found {count} matching files."

            case "copy_file":
                dest = data.get("destination", "")
                dest_name = cls.format_path(dest)
                if dest_name:
                    return f"The file has been copied to {dest_name}."
                return "The file has been copied."

            case "move_file":
                dest = data.get("destination", "")
                dest_name = cls.format_path(dest)
                if dest_name:
                    return f"The file has been moved to {dest_name}."
                return "The file has been moved."

            case "delete_file":
                return "The file has been deleted."

            case "system_info":
                os_name = data.get("os", "Windows")
                ram = data.get("ram_total_mb", 0) / 1024
                return f"{os_name} system with {ram:.1f} gigabytes of RAM."

            case "control":
                return "Task cancelled."

            case _:
                return "Task completed and verified."

    @classmethod
    def format_graph_result(cls, graph_result: Any) -> str:
        """Format DAG planner outcome truthfully."""
        if isinstance(graph_result, dict):
            status = graph_result.get("status", "")
            user_msg = graph_result.get("user_message_data", "")
            node_results = graph_result.get("node_results", {})
            error = graph_result.get("error", "")
        else:
            status = getattr(graph_result, "status", "")
            user_msg = getattr(graph_result, "user_message_data", "")
            node_results = getattr(graph_result, "node_results", {})
            error = getattr(graph_result, "error", "")

        status_str = status.value if hasattr(status, "value") else str(status)
        total_nodes = len(node_results)

        if status_str == "success":
            if user_msg:
                return user_msg
            return f"Done. I completed all {total_nodes} steps."

        if status_str == "partial":
            if isinstance(node_results, dict):
                succeeded = sum(
                    1 for nr in node_results.values()
                    if (isinstance(nr, dict) and nr.get("success", False)) or getattr(nr, "success", False) or nr is True
                )
            else:
                succeeded = sum(1 for nr in node_results if getattr(nr, "success", False))
            return f"I completed {succeeded} of {total_nodes} steps. Some actions could not be finished."

        if status_str == "uncertain":
            return "I performed the action, but I couldn't verify whether it completed."

        if status_str == "cancelled":
            return "Task cancelled."

        # Failed
        if error:
            return f"I couldn't complete the task: {cls.sanitize_error(error)}"
        return "I couldn't complete the task."

    @classmethod
    def sanitize_error(cls, error_msg: str) -> str:
        """Turn raw code/OS errors into clean, concise spoken sentences."""
        if not error_msg:
            return "An unknown error occurred."

        msg = error_msg.strip()
        msg_lower = msg.lower()

        # Common Windows OS errors checked directly
        if "filenotfounderror" in msg_lower or "no such file" in msg_lower or "not found" in msg_lower:
            return "The requested file or program was not found."
        if "permissionerror" in msg_lower or "access is denied" in msg_lower:
            return "Access was denied by the system."
        if "timeouterror" in msg_lower or "timed out" in msg_lower:
            return "The operation timed out."
        if "policydenial" in msg_lower or "denied by policy" in msg_lower:
            return "This action is blocked by security policy."

        # Strip traceback indicators
        if "Traceback" in msg or "Error:" in msg:
            lines = msg.splitlines()
            last_line = lines[-1].strip()
            if ":" in last_line:
                msg = last_line.split(":", 1)[1].strip()
            else:
                msg = last_line

        # Re-check after stripping
        msg_lower = msg.lower()
        if "no such file" in msg_lower or "not found" in msg_lower:
            return "The requested file or program was not found."

        # Keep it concise
        if len(msg) > 100:
            msg = msg[:97] + "..."
        return msg
