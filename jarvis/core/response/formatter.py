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

        # Filter out purely numeric barcodes/timestamps (>4 digits) so long numbers aren't read out
        words = clean_stem.split()
        readable_words = [w for w in words if not (w.isdigit() and len(w) >= 5)]

        spoken_ext = KNOWN_EXTENSIONS.get(ext, ext.lstrip(".").upper() if ext else "")

        if not readable_words:
            # If the filename was purely numerical (e.g. 10663338_11011301_1787974964233.pdf)
            if ext == ".pdf":
                return "a PDF document"
            if ext in (".jpg", ".jpeg", ".png", ".webp"):
                return "an image file"
            if ext in (".mp4", ".mkv", ".mov"):
                return "a video"
            if ext in (".zip", ".rar", ".7z"):
                return "a zip archive"
            if ext in (".exe", ".msi"):
                return "an installer"
            if spoken_ext:
                return f"a {spoken_ext} file"
            return "a file"

        formatted_words = []
        for w in readable_words:
            if w.isupper() and len(w) > 3:
                formatted_words.append(w.title())
            elif w.islower():
                formatted_words.append(w.capitalize())
            else:
                formatted_words.append(w)
        spoken_stem = " ".join(formatted_words)

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
                norm_app = app_name.lower().strip()
                if norm_app in ("default apps", "defaultapps", "default applications", "default app"):
                    return "Default apps settings is open."
                if norm_app in ("settings", "windows settings"):
                    return "Settings is open."
                if norm_app in ("downloads", "my downloads", "downloads folder"):
                    return "Downloads folder is open."
                if norm_app in ("documents", "my documents", "documents folder"):
                    return "Documents folder is open."
                return f"{app_name.capitalize()} is open."

            case "close_app":
                app_name = data.get("name", "The application")
                return f"{app_name.capitalize()} is closed."

            case "volume_set":
                pct = data.get("percent", 0)
                return f"Volume set to {pct:.0f} percent."

            case "volume_get":
                pct = data.get("percent", 0)
                return f"Volume is {pct:.0f} percent."

            case "brightness_set":
                pct = data.get("percent", 0)
                return f"Brightness set to {pct:.0f} percent."

            case "brightness_get":
                pct = data.get("percent", 0)
                return f"Screen brightness is {pct:.0f} percent."

            case "top_memory_processes":
                procs = data.get("processes", [])
                total_ram = data.get("total_ram_gb", 0)
                used_ram = data.get("used_ram_gb", 0)
                if not procs:
                    return f"Memory usage is {used_ram} GB of {total_ram} GB."
                top_items = [f"{p['name']} using {p['formatted']}" for p in procs[:3]]
                top_str = ", ".join(top_items[:-1]) + f", and {top_items[-1]}" if len(top_items) > 1 else top_items[0]
                return f"The programs using the most memory are {top_str}."

            case "take_screenshot":
                return "Screenshot saved."

            case "set_voice":
                gender = data.get("gender", "male")
                return f"I have switched my voice to {gender}."

            case "show_dashboard" | "wake_greeting":
                return "At your service, sir. What shall I do now?"

            case "system_diagnostics":
                return data.get("summary", "System diagnostics completed.")

            case "microphone_status":
                return data.get("summary", "Microphone is connected and active.")

            case "speech_recognition_status":
                return data.get("summary", "Speech recognition is active using Faster-Whisper.")

            case "wake_word_status":
                return data.get("summary", "Wake word detection is active listening for 'Hey Jarvis'.")

            case "connected_devices":
                return data.get("summary", "Connected devices loaded.")

            case "stop_speaking":
                return "Speech stopped."

            case "whatsapp_action":
                return data.get("message", "WhatsApp action completed.")

            case "get_time":
                date_str = data.get("date", "")
                time_str = data.get("time", "")
                if date_str and time_str:
                    return f"It is {time_str} on {date_str}."
                iso = data.get("iso", "")
                if "T" in iso:
                    time_part = iso.split("T")[1][:5]
                    return cls.format_number(time_part)
                return iso

            case "list_directory":
                entries = data.get("entries", [])
                path_str = data.get("path", "")
                folder_name = cls.format_path(path_str) if path_str else ""
                count = len(entries)
                if count == 0:
                    prefix = f"In {folder_name}, the" if folder_name else "The"
                    return f"{prefix} folder is empty."

                if count <= 3:
                    spoken = cls.format_list(entries, max_items=3)
                    prefix = f"In {folder_name}, there" if folder_name else "There"
                    return f"{prefix} are {count} items: {spoken}."

                # For larger folders, summarize file types and human-readable filenames
                doc_exts = {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".csv", ".md"}
                img_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
                vid_exts = {".mp4", ".mkv", ".avi", ".mov"}
                app_exts = {".exe", ".msi"}
                zip_exts = {".zip", ".rar", ".7z", ".tar", ".gz"}

                docs = sum(1 for e in entries if Path(e).suffix.lower() in doc_exts)
                imgs = sum(1 for e in entries if Path(e).suffix.lower() in img_exts)
                vids = sum(1 for e in entries if Path(e).suffix.lower() in vid_exts)
                apps = sum(1 for e in entries if Path(e).suffix.lower() in app_exts)
                zips = sum(1 for e in entries if Path(e).suffix.lower() in zip_exts)

                type_parts = []
                if docs: type_parts.append(f"{docs} documents" if docs > 1 else "1 document")
                if imgs: type_parts.append(f"{imgs} photos" if imgs > 1 else "1 photo")
                if vids: type_parts.append(f"{vids} videos" if vids > 1 else "1 video")
                if apps: type_parts.append(f"{apps} installers" if apps > 1 else "1 installer")
                if zips: type_parts.append(f"{zips} zip files" if zips > 1 else "1 zip file")

                # Find up to 2 clean, recognizable file names
                clean_names = []
                for e in entries:
                    stem = Path(e).stem
                    letters = sum(1 for c in stem if c.isalpha())
                    digits = sum(1 for c in stem if c.isdigit())
                    if letters >= 5 and digits < letters and not stem.startswith(("IMG", "VID", "PXL", "Screenshot", "202")):
                        readable = cls.format_filename(e)
                        if readable and not readable.startswith("a ") and len(readable) <= 30:
                            clean_names.append(readable)
                            if len(clean_names) == 2:
                                break

                loc = f"in {folder_name}" if folder_name else ""
                loc_phrase = f" {loc}" if loc else ""

                if clean_names and type_parts:
                    names_str = " and ".join(clean_names)
                    types_str = ", ".join(type_parts[:2])
                    return f"I found {count} items{loc_phrase}, including {types_str}, as well as files like {names_str}."
                elif type_parts:
                    types_str = ", ".join(type_parts[:3])
                    return f"I found {count} items{loc_phrase}, including {types_str}."
                else:
                    readable_entries = [cls.format_filename(e) for e in entries if not e.startswith(".")]
                    return f"I found {count} items{loc_phrase}, including {cls.format_list(readable_entries[:3], max_items=3)}."

            case "find_file" | "search_files":
                matches = data.get("matches", []) or data.get("results", [])
                count = len(matches) if isinstance(matches, (list, tuple)) else data.get("count", 0)
                if count == 0:
                    return "I couldn't find any matching files."
                if count == 1 and isinstance(matches, (list, tuple)) and matches:
                    m = matches[0]
                    name = ""
                    path = ""
                    if isinstance(m, dict):
                        name = m.get("name") or m.get("filename") or ""
                        path = m.get("path") or ""
                    elif hasattr(m, "name"):
                        name = getattr(m, "name", "")
                        path = getattr(m, "path", "")
                    else:
                        name = str(m)
                    formatted_name = cls.format_filename(name) if name else "the file"
                    if path:
                        return f"I found {formatted_name} at {path}."
                    return f"I found {formatted_name}."
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

            case "create_folder":
                name = Path(data.get("path", "")).name or "the folder"
                return f"Created folder {name}."

            case "rename_file":
                src_name = Path(data.get("source", "")).name
                dst_name = Path(data.get("new_path", "")).name or "the new name"
                if src_name:
                    return f"Renamed {src_name} to {dst_name}."
                return f"Renamed to {dst_name}."

            case "delete_file":
                name = Path(data.get("path", "")).name or "The file"
                return f"{name} has been deleted."

            case "system_info":
                raw_os = data.get("os", "Windows")
                m_win = re.search(r"Windows-(\d+)", raw_os)
                clean_os = f"Windows {m_win.group(1)}" if m_win else "Windows"
                ram = data.get("ram_total_mb", 0) / 1024
                ram_used = data.get("ram_used_mb", 0) / 1024
                return f"{clean_os} with {ram:.0f} GB of RAM, of which {ram_used:.1f} GB is currently in use."

            case "open_path":
                return "Opened it."

            case "read_whatsapp_messages" | "summarize_whatsapp_messages":
                spoken = data.get("spoken_summary")
                if spoken:
                    return spoken
                count = data.get("count", data.get("total_pending", 0))
                return f"You have {count} WhatsApp messages."

            case "send_whatsapp_message":
                status = data.get("status", "")
                recipient = data.get("recipient", "")
                if status == "SENT":
                    return f"Message delivered to {recipient} on WhatsApp."
                elif status == "CONFIRMATION_REQUIRED":
                    return f"Confirmation required before sending message to {recipient}."
                elif status == "AMBIGUOUS_CONTACT":
                    return data.get("message", f"Multiple contacts match {recipient}.")
                elif status == "FAILED":
                    return data.get("message", f"Failed to deliver WhatsApp message to {recipient}.")
                return data.get("message", "WhatsApp message processed.")

            case "ollama_chat":
                return data.get("response") or "I processed your request."

            case "powershell_command":
                stdout = (data.get("stdout") or "").strip()
                if stdout:
                    first_line = stdout.splitlines()[0]
                    return f"Executed: {first_line[:120]}"
                return data.get("status") or "Command completed."

            case "morning_briefing":
                return data.get("spoken_text") or "Your live briefing is ready."

            case "play_youtube":
                return data.get("message") or "Playing on YouTube."

            case "search_news":
                return data.get("summary") or "Here is the latest news."

            case "close_window":
                return data.get("message") or "Window closed."

            case "maximize_window":
                return data.get("message") or "Window maximized."

            case "minimize_window":
                return data.get("message") or "Window minimized."

            case "show_desktop":
                return data.get("message") or "Desktop shown."

            case "media_control":
                return data.get("message") or "Media action completed."

            case "android_status":
                return data.get("message") or "Phone status check completed."

            case "desktop_ui_snapshot" | "describe_screen":
                return data.get("message") or f"The active window is {data.get('window_title', 'unknown')}."

            case "control":
                return "Task cancelled."

            case _:
                if data.get("message"):
                    return str(data["message"])
                if data.get("summary"):
                    return str(data["summary"])
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
    def sanitize_error(cls, error_msg: str, tool_name: str = "") -> str:
        """Turn raw code/OS/validation errors into clean, concise human-spoken sentences."""
        if not error_msg:
            return "I couldn't complete that action. Please try again."

        msg = error_msg.strip()
        msg_lower = msg.lower()

        # 1. Pydantic / Contract Validation errors (never leak schema details to user)
        if "validation error" in msg_lower or "field required" in msg_lower or "errors.pydantic.dev" in msg_lower:
            if "name" in msg_lower and tool_name in ("open_app", "close_app", "get_app_location", "check_app_installed"):
                return "Please tell me which application you would like me to use."
            if "path" in msg_lower and tool_name in ("list_directory", "open_file", "delete_file"):
                return "Please specify the folder or file you would like to look in."
            if "query" in msg_lower and tool_name in ("find_file", "search_files", "search_web"):
                return "Please tell me what you would like to search for."
            return "Please provide the required details to complete this action."

        # 2. UI Automation / Element resolution errors
        if any(kw in msg_lower for kw in ("object has no attribute", "element_not_found", "target resolution failed", "click failed")):
            return "I couldn't find that button or control on your screen."

        # 3. File and directory errors
        if "not indexed" in msg_lower or "is not installed" in msg_lower:
            target_app = re.sub(r".*not indexed:\s*(?:app\s*)?", "", msg, flags=re.IGNORECASE).strip()
            if target_app:
                return f"Could not find an installed application matching '{target_app}'."
            return "The requested application is not installed on this system."
        if "filenotfounderror" in msg_lower or "no such file" in msg_lower or "cannot find the file" in msg_lower or "not found" in msg_lower:
            return "The requested file or program was not found."
        if "permissionerror" in msg_lower or "access is denied" in msg_lower:
            return "Access was denied by the system."
        if "notadirectoryerror" in msg_lower:
            return "That path is not a valid folder."

        # 4. Network and Service errors
        if "connectionrefused" in msg_lower or "failed to connect" in msg_lower or "service unavailable" in msg_lower:
            return "Could not connect to the required service."
        if "timeouterror" in msg_lower or "timed out" in msg_lower:
            return "The operation took too long and timed out."

        # 5. Security & Policy denials
        if "policydenial" in msg_lower or "denied by policy" in msg_lower:
            return "This action is blocked by security policy."

        # 6. JSON / Parsing errors
        if "jsondecodeerror" in msg_lower or "expecting value" in msg_lower:
            return "I had trouble understanding the response. Please try again."

        # 7. Generic Python exceptions / tracebacks (never leak stack trace to human)
        if "traceback" in msg_lower or "error:" in msg_lower or "exception:" in msg_lower or "nameerror" in msg_lower or "typeerror" in msg_lower:
            return "I ran into a problem completing that task. Please try again."

        # Strip any code punctuation or trailing URLs
        msg = re.sub(r"https?://\S+", "", msg).strip()
        msg = re.sub(r"\[type=[^\]]+\]", "", msg).strip()

        # Keep it concise and natural
        if len(msg) > 85:
            msg = msg[:82] + "..."
        return msg
