# JARVIS EDGE: Master Capability Catalog

This catalog provides the complete, authoritative machine- and human-readable map of every executable capability supported by the JARVIS EDGE brain. It is automatically generated from `CapabilityRegistry` and synchronized with `ToolRegistry`.

**Total Registered Capabilities**: 80

---

## SYSTEM Capabilities (10)

### `system.time`

- **DESCRIPTION**: Retrieves the current local date, time, and timezone.
- **TARGET TOOL**: `get_time`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `time_format_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "iso": {
    "title": "Iso",
    "type": "string"
  },
  "date": {
    "default": "",
    "title": "Date",
    "type": "string"
  },
  "time": {
    "default": "",
    "title": "Time",
    "type": "string"
  },
  "formatted": {
    "default": "",
    "title": "Formatted",
    "type": "string"
  }
}
```

#### EXAMPLES
- "What time is it?"
- "Tell me the current time"
- "What's today's date?"
- "Current time please"

#### COUNTEREXAMPLES
- "Set a timer for 10 minutes"
- "Remind me at 5pm"
- "How long did that take?"

---

### `system.info`

- **DESCRIPTION**: Retrieves CPU, RAM, OS version, disk usage, and host specifications.
- **TARGET TOOL**: `system_info`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `system_info_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "os": {
    "title": "Os",
    "type": "string"
  },
  "python": {
    "title": "Python",
    "type": "string"
  },
  "cpu": {
    "title": "Cpu",
    "type": "string"
  },
  "ram_total_mb": {
    "title": "Ram Total Mb",
    "type": "number"
  },
  "ram_used_mb": {
    "title": "Ram Used Mb",
    "type": "number"
  },
  "gpu_name": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "title": "Gpu Name"
  },
  "gpu_vram_mb": {
    "anyOf": [
      {
        "type": "number"
      },
      {
        "type": "null"
      }
    ],
    "title": "Gpu Vram Mb"
  }
}
```

#### EXAMPLES
- "Show system specs"
- "How much RAM is free?"
- "What CPU do I have?"
- "System info"

#### COUNTEREXAMPLES
- "Check internet speed"
- "Is VLC installed?"
- "Run diagnostics"

---

### `system.diagnostics`

- **DESCRIPTION**: Runs diagnostic audit across system health, Ollama status, event loop, and processes.
- **TARGET TOOL**: `system_diagnostics`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `diagnostic_report_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "scope": {
    "default": "all",
    "description": "Scope of diagnostics to collect",
    "title": "Scope",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "total_checks": {
    "title": "Total Checks",
    "type": "integer"
  },
  "passed_checks": {
    "title": "Passed Checks",
    "type": "integer"
  },
  "failed_checks": {
    "title": "Failed Checks",
    "type": "integer"
  },
  "summary": {
    "title": "Summary",
    "type": "string"
  },
  "checks": {
    "items": {
      "additionalProperties": true,
      "type": "object"
    },
    "title": "Checks",
    "type": "array"
  }
}
```

#### EXAMPLES
- "Run system diagnostics"
- "Check system health"
- "Audit subsystems"
- "Diagnostics"

#### COUNTEREXAMPLES
- "System specs"
- "Fix my internet"
- "Open task manager"

---

### `system.devices`

- **DESCRIPTION**: Lists connected audio input microphones, output speakers/headphones, and monitors.
- **TARGET TOOL**: `connected_devices`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `devices_list_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "input_device": {
    "title": "Input Device",
    "type": "string"
  },
  "output_device": {
    "title": "Output Device",
    "type": "string"
  },
  "display": {
    "title": "Display",
    "type": "string"
  },
  "summary": {
    "title": "Summary",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Show connected devices"
- "What audio devices are plugged in?"
- "List screens and speakers"

#### COUNTEREXAMPLES
- "Is my phone connected?"
- "Bluetooth settings"
- "Volume 50"

---

### `system.microphone_status`

- **DESCRIPTION**: Checks default audio input microphone availability, recording status, and sound levels.
- **TARGET TOOL**: `microphone_status`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `mic_active_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "device": {
    "title": "Device",
    "type": "string"
  },
  "is_active": {
    "title": "Is Active",
    "type": "boolean"
  },
  "summary": {
    "title": "Summary",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Is my microphone working?"
- "Check microphone status"
- "Mic test"

#### COUNTEREXAMPLES
- "Mute system volume"
- "Start dictation"
- "Listen to me"

---

### `system.stt_status`

- **DESCRIPTION**: Checks speech-to-text (STT) Faster-Whisper model loading and latency status.
- **TARGET TOOL**: `speech_recognition_status`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `stt_ready_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "engine": {
    "title": "Engine",
    "type": "string"
  },
  "model": {
    "title": "Model",
    "type": "string"
  },
  "ready": {
    "title": "Ready",
    "type": "boolean"
  },
  "summary": {
    "title": "Summary",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Check speech recognition status"
- "Is whisper loaded?"
- "STT health"

#### COUNTEREXAMPLES
- "Start dictation"
- "Record audio"
- "Check microphone"

---

### `system.wake_word_status`

- **DESCRIPTION**: Checks status and sensitivity of the openWakeWord local engine.
- **TARGET TOOL**: `wake_word_status`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `wake_word_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "engine": {
    "title": "Engine",
    "type": "string"
  },
  "wake_word": {
    "title": "Wake Word",
    "type": "string"
  },
  "active": {
    "title": "Active",
    "type": "boolean"
  },
  "summary": {
    "title": "Summary",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Check wake word status"
- "Is wake word detection enabled?"
- "Wake word health"

#### COUNTEREXAMPLES
- "Change wake word"
- "Mute mic"
- "Hey Jarvis"

---

### `system.voice_set`

- **DESCRIPTION**: Changes the active Piper TTS synthesis voice between male and female models.
- **TARGET TOOL**: `set_voice`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `tts_voice_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "gender": {
    "maxLength": 64,
    "minLength": 1,
    "title": "Gender",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "gender": {
    "title": "Gender",
    "type": "string"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Switch to female voice"
- "Change voice to male"
- "Set voice female"
- "Use male voice"

#### COUNTEREXAMPLES
- "Speak louder"
- "Mute volume"
- "Stop talking"

---

### `system.dashboard`

- **DESCRIPTION**: Displays the interactive JARVIS desktop UI monitoring dashboard.
- **TARGET TOOL**: `show_dashboard`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `window_visible_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Open dashboard"
- "Show dashboard"
- "Display status dashboard"

#### COUNTEREXAMPLES
- "Show desktop"
- "Open settings"
- "Run diagnostics"

---

### `system.wake_greeting`

- **DESCRIPTION**: Generates a contextual natural audio greeting upon user wake or presence.
- **TARGET TOOL**: `wake_greeting`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `greeting_spoken_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Good morning Jarvis"
- "Wake up Jarvis"
- "Greet me"

#### COUNTEREXAMPLES
- "What time is it?"
- "Tell me a joke"
- "Morning briefing"

---

## APP Capabilities (7)

### `app.open`

- **DESCRIPTION**: Resolves and launches an application, local software, or registered web app by name.
- **TARGET TOOL**: `open_app`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `process_running_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "name": {
    "maxLength": 256,
    "minLength": 1,
    "title": "Name",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "name": {
    "title": "Name",
    "type": "string"
  },
  "target": {
    "title": "Target",
    "type": "string"
  },
  "pid": {
    "anyOf": [
      {
        "type": "integer"
      },
      {
        "type": "null"
      }
    ],
    "title": "Pid"
  },
  "process_names": {
    "items": {
      "type": "string"
    },
    "title": "Process Names",
    "type": "array"
  },
  "associated": {
    "default": false,
    "title": "Associated",
    "type": "boolean"
  }
}
```

#### EXAMPLES
- "Open Chrome"
- "Launch VS Code"
- "Start Calculator"
- "Open Notepad"
- "Run Spotify"

#### COUNTEREXAMPLES
- "Close Chrome"
- "Is Chrome installed?"
- "Open index.html"
- "Install Chrome"

---

### `app.close`

- **DESCRIPTION**: Terminates or gracefully closes a running application by process name or title.
- **TARGET TOOL**: `close_app`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `process_terminated_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "name": {
    "maxLength": 256,
    "minLength": 1,
    "title": "Name",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "name": {
    "title": "Name",
    "type": "string"
  },
  "closed": {
    "title": "Closed",
    "type": "boolean"
  },
  "count": {
    "default": 0,
    "title": "Count",
    "type": "integer"
  }
}
```

#### EXAMPLES
- "Close Chrome"
- "Quit Notepad"
- "Close Spotify"
- "Exit VS Code"

#### COUNTEREXAMPLES
- "Close window"
- "Minimize Chrome"
- "Uninstall Chrome"
- "Open Chrome"

---

### `app.check_installed`

- **DESCRIPTION**: Queries the AppCatalog to verify whether a specific application is installed on this PC.
- **TARGET TOOL**: `check_app_installed`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `catalog_query_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "name": {
    "description": "Name or alias of the software to check",
    "maxLength": 128,
    "minLength": 1,
    "title": "Name",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "installed": {
    "title": "Installed",
    "type": "boolean"
  },
  "app_name": {
    "title": "App Name",
    "type": "string"
  },
  "canonical_id": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Canonical Id"
  },
  "version": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Version"
  },
  "location": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Location"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Is VLC installed?"
- "Do I have Chrome?"
- "Check if Spotify is installed"
- "Is VS Code on this PC?"

#### COUNTEREXAMPLES
- "Where is VLC installed?"
- "Install VLC"
- "Open VLC"
- "Uninstall VLC"

---

### `app.get_location`

- **DESCRIPTION**: Retrieves the verified executable path and installation folder of an installed software.
- **TARGET TOOL**: `get_app_location`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `path_exists_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "name": {
    "description": "Name or alias of the software to find",
    "maxLength": 128,
    "minLength": 1,
    "title": "Name",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "found": {
    "title": "Found",
    "type": "boolean"
  },
  "app_name": {
    "title": "App Name",
    "type": "string"
  },
  "executable_path": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Executable Path"
  },
  "install_location": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Install Location"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Where is VLC installed?"
- "Find executable for Chrome"
- "Where is VS Code located?"

#### COUNTEREXAMPLES
- "Is VLC installed?"
- "Open VLC"
- "Where are my downloads?"

---

### `app.list_installed`

- **DESCRIPTION**: Lists all verified installed applications and Start Menu software tracked in the AppCatalog.
- **TARGET TOOL**: `list_installed_applications`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `catalog_list_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "filter": {
    "default": "",
    "description": "Optional search term to filter applications",
    "title": "Filter",
    "type": "string"
  },
  "limit": {
    "default": 20,
    "description": "Max applications to return",
    "maximum": 200,
    "minimum": 1,
    "title": "Limit",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "count": {
    "title": "Count",
    "type": "integer"
  },
  "total_installed": {
    "title": "Total Installed",
    "type": "integer"
  },
  "applications": {
    "items": {
      "additionalProperties": true,
      "type": "object"
    },
    "title": "Applications",
    "type": "array"
  },
  "spoken_summary": {
    "title": "Spoken Summary",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Show installed applications"
- "List all my software"
- "What apps are installed?"

#### COUNTEREXAMPLES
- "List files in directory"
- "Refresh applications"
- "What devices are connected?"

---

### `app.refresh_catalog`

- **DESCRIPTION**: Triggers a fresh scan across Windows registry, Start Menu, UWP, and PATH without modifying system PATH.
- **TARGET TOOL**: `refresh_applications`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `catalog_refresh_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "force": {
    "default": true,
    "description": "Force a full rescan of all registration sources",
    "title": "Force",
    "type": "boolean"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "total_apps": {
    "title": "Total Apps",
    "type": "integer"
  },
  "new_apps": {
    "title": "New Apps",
    "type": "integer"
  },
  "elapsed_ms": {
    "title": "Elapsed Ms",
    "type": "number"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Refresh applications"
- "Rescan installed programs"
- "Update application catalog"

#### COUNTEREXAMPLES
- "Show installed applications"
- "Refresh browser page"
- "Clean desktop"

---

### `app.install_software`

- **DESCRIPTION**: Installs a verified software package via trusted package manager (winget), verifies install, and updates AppCatalog.
- **TARGET TOOL**: `install_software`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `EXPENSIVE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `app_catalog_resolved_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "name": {
    "description": "Name of the software or application to install",
    "maxLength": 128,
    "minLength": 1,
    "title": "Name",
    "type": "string"
  },
  "package_id": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "description": "Optional explicit package ID",
    "title": "Package Id"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "app_name": {
    "title": "App Name",
    "type": "string"
  },
  "package_id": {
    "title": "Package Id",
    "type": "string"
  },
  "executable_path": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Executable Path"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Install VLC"
- "Install VS Code"
- "Install Google Chrome"
- "Download and install 7-Zip"

#### COUNTEREXAMPLES
- "Is VLC installed?"
- "Open VLC"
- "Uninstall VLC"
- "Update Windows"

---

## WINDOWS Capabilities (10)

### `windows.close_window`

- **DESCRIPTION**: Closes the currently active foreground window via Win32 API in under 200 microseconds.
- **TARGET TOOL**: `close_window`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `active_window_changed_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Close window"
- "Close this window"
- "Close the current window"

#### COUNTEREXAMPLES
- "Close Chrome"
- "Minimize window"
- "Show desktop"

---

### `windows.minimize_window`

- **DESCRIPTION**: Minimizes the currently active foreground window to the taskbar.
- **TARGET TOOL**: `minimize_window`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `window_state_minimized_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Minimize window"
- "Minimize this window"
- "Minimize active window"

#### COUNTEREXAMPLES
- "Maximize window"
- "Show desktop"
- "Close window"

---

### `windows.maximize_window`

- **DESCRIPTION**: Maximizes the currently active foreground window to fill the monitor display.
- **TARGET TOOL**: `maximize_window`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `window_state_maximized_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Maximize window"
- "Maximize this"
- "Full screen this window"

#### COUNTEREXAMPLES
- "Minimize window"
- "Close window"
- "Snap left"

---

### `windows.show_desktop`

- **DESCRIPTION**: Minimizes all open windows and toggles display to the Windows desktop (Win+D).
- **TARGET TOOL**: `show_desktop`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `desktop_foreground_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Show desktop"
- "Minimize all windows"
- "Go to desktop"

#### COUNTEREXAMPLES
- "Show dashboard"
- "Open desktop folder"
- "Close all windows"

---

### `windows.volume_get`

- **DESCRIPTION**: Retrieves the current master audio output volume percentage and mute status.
- **TARGET TOOL**: `volume_get`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `volume_read_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "percent": {
    "maximum": 100,
    "minimum": 0,
    "title": "Percent",
    "type": "number"
  }
}
```

#### EXAMPLES
- "What's the volume?"
- "Check volume level"
- "Tell me the volume"

#### COUNTEREXAMPLES
- "Set volume to 50"
- "Mute volume"
- "Volume up"

---

### `windows.volume_set`

- **DESCRIPTION**: Sets the master audio output volume to a specific percentage (0 to 100).
- **TARGET TOOL**: `volume_set`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `pycaw_volume_match_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "percent": {
    "maximum": 100,
    "minimum": 0,
    "title": "Percent",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "percent": {
    "maximum": 100,
    "minimum": 0,
    "title": "Percent",
    "type": "number"
  }
}
```

#### EXAMPLES
- "Volume 50"
- "Set volume to 30"
- "Volume 80 percent"
- "Turn sound down to 20"

#### COUNTEREXAMPLES
- "What is the volume?"
- "Mute audio"
- "Volume up"

---

### `windows.screenshot`

- **DESCRIPTION**: Captures a full screenshot of the primary monitor and saves it to a verified PNG file.
- **TARGET TOOL**: `take_screenshot`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `png_file_valid_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "path": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Path"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "path": {
    "title": "Path",
    "type": "string"
  },
  "bytes": {
    "exclusiveMinimum": 0,
    "title": "Bytes",
    "type": "integer"
  }
}
```

#### EXAMPLES
- "Take a screenshot"
- "Capture my screen"
- "Take snapshot"
- "Screen capture"

#### COUNTEREXAMPLES
- "Take a photo with phone"
- "Record video"
- "Desktop UI snapshot"

---

### `windows.media_control`

- **DESCRIPTION**: Dispatches multimedia hardware keys: play, pause, next track, previous track, or mute.
- **TARGET TOOL**: `media_control`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `media_key_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "action": {
    "default": "play_pause",
    "description": "Media action: play, pause, play_pause, next, previous, mute, volume_up, volume_down",
    "title": "Action",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "action": {
    "title": "Action",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Pause playback"
- "Resume music"
- "Next track"
- "Previous song"
- "Mute audio"

#### COUNTEREXAMPLES
- "Play lo-fi on YouTube"
- "Volume 50"
- "Open Spotify"

---

### `windows.desktop_ui_click`

- **DESCRIPTION**: Clicks an interactive button, menu item, or tab inside an active desktop window via UI Automation.
- **TARGET TOOL**: `desktop_ui_click`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `uia_action_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "name": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Name"
  },
  "automation_id": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Automation Id"
  },
  "control_type": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Control Type"
  },
  "window_id": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Window Id"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "action": {
    "title": "Action",
    "type": "string"
  },
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "verification_status": {
    "title": "Verification Status",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Click Save button"
- "Click File menu"
- "Click Submit in application"

#### COUNTEREXAMPLES
- "Click link on website"
- "Right click file"
- "Close window"

---

### `windows.desktop_ui_snapshot`

- **DESCRIPTION**: Captures accessibility hierarchy and interactive elements of the active desktop window via UI Automation.
- **TARGET TOOL**: `desktop_ui_snapshot`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `uia_tree_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "window_id": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "description": "Window title or handle, or None for foreground window",
    "title": "Window Id"
  },
  "max_elements": {
    "default": 150,
    "maximum": 500,
    "minimum": 1,
    "title": "Max Elements",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "application": {
    "title": "Application",
    "type": "string"
  },
  "window_title": {
    "title": "Window Title",
    "type": "string"
  },
  "element_count": {
    "title": "Element Count",
    "type": "integer"
  },
  "elements_summary": {
    "items": {
      "type": "string"
    },
    "title": "Elements Summary",
    "type": "array"
  }
}
```

#### EXAMPLES
- "Inspect active window controls"
- "What buttons are on screen?"
- "Snapshot desktop UI"

#### COUNTEREXAMPLES
- "Take screenshot"
- "Browser snapshot"
- "List directory"

---

## BROWSER Capabilities (6)

### `browser.open_url`

- **DESCRIPTION**: Opens a web URL in the managed Playwright browser session.
- **TARGET TOOL**: `browser_open_url`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `browser_url_match_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "url": {
    "description": "URL to open in the browser",
    "title": "Url",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "title": {
    "default": "",
    "title": "Title",
    "type": "string"
  },
  "url": {
    "default": "",
    "title": "Url",
    "type": "string"
  },
  "content": {
    "default": "",
    "title": "Content",
    "type": "string"
  },
  "success": {
    "default": true,
    "title": "Success",
    "type": "boolean"
  }
}
```

#### EXAMPLES
- "Open example.com"
- "Go to https://github.com"
- "Open reddit.com in browser"

#### COUNTEREXAMPLES
- "Open Chrome"
- "Search the web for python"
- "Play youtube"

---

### `browser.navigate`

- **DESCRIPTION**: Navigates the currently active browser tab to a new URL.
- **TARGET TOOL**: `browser_navigate`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `browser_url_match_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "url": {
    "description": "Web URL to navigate to",
    "maxLength": 2048,
    "minLength": 1,
    "title": "Url",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "url": {
    "title": "Url",
    "type": "string"
  },
  "title": {
    "title": "Title",
    "type": "string"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Navigate to https://wikipedia.org"
- "Go to docs.python.org in active tab"

#### COUNTEREXAMPLES
- "Open Chrome"
- "Browser back"
- "Click link"

---

### `browser.click`

- **DESCRIPTION**: Clicks an interactive DOM element, link, or button on the active web page.
- **TARGET TOOL**: `browser_click`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `browser_dom_mutation_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "role": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Role"
  },
  "name": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Name"
  },
  "text": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Text"
  },
  "label": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Label"
  },
  "test_id": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Test Id"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "action": {
    "title": "Action",
    "type": "string"
  },
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "verification_status": {
    "title": "Verification Status",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Click the login button"
- "Click the first search result"
- "Click Download link"

#### COUNTEREXAMPLES
- "Desktop UI click"
- "Click Save in Notepad"
- "Browser navigate"

---

### `browser.type`

- **DESCRIPTION**: Enters text into an input field or search box on the active web page.
- **TARGET TOOL**: `browser_type`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `browser_dom_value_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "text": {
    "description": "Text to enter into the input element",
    "maxLength": 2048,
    "minLength": 1,
    "title": "Text",
    "type": "string"
  },
  "role": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Role"
  },
  "name": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Name"
  },
  "label": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Label"
  },
  "placeholder": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Placeholder"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "action": {
    "title": "Action",
    "type": "string"
  },
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "verification_status": {
    "title": "Verification Status",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Type 'artificial intelligence' in search box"
- "Fill email input with test@example.com"

#### COUNTEREXAMPLES
- "Dictate text into Notepad"
- "Send WhatsApp message"
- "Create note"

---

### `browser.snapshot`

- **DESCRIPTION**: Extracts the accessibility tree and interactive elements of the active browser page.
- **TARGET TOOL**: `browser_snapshot`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `browser_tree_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "max_elements": {
    "default": 200,
    "maximum": 1000,
    "minimum": 1,
    "title": "Max Elements",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "url": {
    "title": "Url",
    "type": "string"
  },
  "title": {
    "title": "Title",
    "type": "string"
  },
  "element_count": {
    "title": "Element Count",
    "type": "integer"
  },
  "elements_summary": {
    "items": {
      "type": "string"
    },
    "title": "Elements Summary",
    "type": "array"
  }
}
```

#### EXAMPLES
- "Snapshot active web page"
- "What links are on this page?"
- "Read browser content"

#### COUNTEREXAMPLES
- "Take screenshot"
- "Desktop UI snapshot"
- "Search web"

---

### `browser.play_youtube`

- **DESCRIPTION**: Opens YouTube and searches for or plays a specified video, artist, or song query.
- **TARGET TOOL**: `play_youtube`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `browser_url_match_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "query": {
    "description": "Video, song, or search query to play on YouTube",
    "maxLength": 512,
    "minLength": 1,
    "title": "Query",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "url": {
    "title": "Url",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Play lo-fi music on YouTube"
- "Open YouTube and search for quantum computing"
- "Watch Python tutorial on YouTube"

#### COUNTEREXAMPLES
- "Play local mp3"
- "Resume music"
- "Open Spotify"

---

## FILE Capabilities (12)

### `file.list_directory`

- **DESCRIPTION**: Lists the files and subdirectories inside a specific local directory path.
- **TARGET TOOL**: `list_directory`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `directory_read_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "path": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Path",
    "type": "string"
  },
  "limit": {
    "default": 100,
    "maximum": 1000,
    "minimum": 1,
    "title": "Limit",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "path": {
    "title": "Path",
    "type": "string"
  },
  "entries": {
    "items": {
      "type": "string"
    },
    "title": "Entries",
    "type": "array"
  },
  "truncated": {
    "title": "Truncated",
    "type": "boolean"
  }
}
```

#### EXAMPLES
- "List files in Downloads"
- "What's inside C:/Projects?"
- "List directory C:/Users/Documents"

#### COUNTEREXAMPLES
- "Find file budget.xlsx"
- "Open folder"
- "Create folder"

---

### `file.find`

- **DESCRIPTION**: Searches indexed local files using cascaded FTS5 full-text search and semantic scoring.
- **TARGET TOOL**: `find_file`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `search_results_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "query": {
    "maxLength": 1024,
    "minLength": 1,
    "title": "Query",
    "type": "string"
  },
  "type_hint": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Type Hint"
  },
  "time_hint": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Time Hint"
  },
  "directory_hint": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Directory Hint"
  },
  "limit": {
    "default": 5,
    "maximum": 50,
    "minimum": 1,
    "title": "Limit",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "query": {
    "title": "Query",
    "type": "string"
  },
  "results": {
    "items": {
      "$ref": "#/$defs/FileSearchResultItem"
    },
    "title": "Results",
    "type": "array"
  },
  "search_mode": {
    "title": "Search Mode",
    "type": "string"
  },
  "semantic_used": {
    "title": "Semantic Used",
    "type": "boolean"
  },
  "latency_ms": {
    "title": "Latency Ms",
    "type": "number"
  },
  "is_ambiguous": {
    "title": "Is Ambiguous",
    "type": "boolean"
  },
  "clarification": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Clarification"
  }
}
```

#### EXAMPLES
- "Find my project report PDF"
- "Search for budget.xlsx"
- "Where is resume.docx?"

#### COUNTEREXAMPLES
- "Search the web for python"
- "Search notes"
- "Find text in document"

---

### `file.open`

- **DESCRIPTION**: Opens an existing local file using its registered Windows default application.
- **TARGET TOOL**: `open_file`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `file_open_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "path": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Path"
  },
  "file_id": {
    "anyOf": [
      {
        "type": "integer"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "File Id"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "path": {
    "title": "Path",
    "type": "string"
  },
  "file_id": {
    "anyOf": [
      {
        "type": "integer"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "File Id"
  },
  "opened": {
    "title": "Opened",
    "type": "boolean"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Open my resume.pdf"
- "Open C:/Projects/data.csv"
- "Open the report we just found"

#### COUNTEREXAMPLES
- "Open Chrome"
- "Find file"
- "Read file metadata"

---

### `file.create_folder`

- **DESCRIPTION**: Creates a new directory or folder at the specified path if it does not already exist.
- **TARGET TOOL**: `create_folder`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `path_is_dir_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "path": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Path",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "path": {
    "title": "Path",
    "type": "string"
  },
  "created": {
    "title": "Created",
    "type": "boolean"
  }
}
```

#### EXAMPLES
- "Create a folder named Projects on Desktop"
- "Make new folder C:/Data/Backup"
- "Create directory test"

#### COUNTEREXAMPLES
- "Delete folder"
- "Move folder"
- "List directory"

---

### `file.rename`

- **DESCRIPTION**: Renames an existing file or directory with conflict checking and collision prevention.
- **TARGET TOOL**: `rename_file`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `new_name_exists_old_absent_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "source": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Source",
    "type": "string"
  },
  "new_name": {
    "maxLength": 256,
    "minLength": 1,
    "title": "New Name",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "source": {
    "title": "Source",
    "type": "string"
  },
  "new_path": {
    "title": "New Path",
    "type": "string"
  },
  "renamed": {
    "title": "Renamed",
    "type": "boolean"
  }
}
```

#### EXAMPLES
- "Rename old.txt to new.txt"
- "Rename document draft to final_report.pdf"

#### COUNTEREXAMPLES
- "Move file"
- "Copy file"
- "Batch rename"

---

### `file.move`

- **DESCRIPTION**: Relocates a file or directory from source to destination path with TOCTOU checks.
- **TARGET TOOL**: `move_file`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `dest_exists_source_absent_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "source": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Source",
    "type": "string"
  },
  "destination": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Destination",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "source": {
    "title": "Source",
    "type": "string"
  },
  "destination": {
    "title": "Destination",
    "type": "string"
  },
  "moved": {
    "title": "Moved",
    "type": "boolean"
  }
}
```

#### EXAMPLES
- "Move report.pdf to Desktop"
- "Move downloaded file to C:/Archives"

#### COUNTEREXAMPLES
- "Copy file"
- "Rename file"
- "Delete file"

---

### `file.copy`

- **DESCRIPTION**: Creates a duplicate copy of a file at the specified destination path.
- **TARGET TOOL**: `copy_file`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `destination_file_exists_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "source": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Source",
    "type": "string"
  },
  "destination": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Destination",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "source": {
    "title": "Source",
    "type": "string"
  },
  "destination": {
    "title": "Destination",
    "type": "string"
  },
  "copied": {
    "title": "Copied",
    "type": "boolean"
  }
}
```

#### EXAMPLES
- "Copy notes.txt to C:/Backup"
- "Duplicate budget.xlsx as budget_copy.xlsx"

#### COUNTEREXAMPLES
- "Move file"
- "Send file to phone"
- "Find duplicates"

---

### `file.delete`

- **DESCRIPTION**: Safely moves a local file or folder to the Windows Recycle Bin using send2trash.
- **TARGET TOOL**: `delete_file`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `source_absent_in_recycle_bin_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "path": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Path",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "path": {
    "title": "Path",
    "type": "string"
  },
  "deleted": {
    "title": "Deleted",
    "type": "boolean"
  },
  "method": {
    "title": "Method",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Delete test.tmp from Desktop"
- "Remove outdated_draft.docx"
- "Trash temporary folder"

#### COUNTEREXAMPLES
- "Don't delete that"
- "Move file"
- "Clear cache"

---

### `file.read_metadata`

- **DESCRIPTION**: Reads size in bytes, modification timestamp, and MIME type of a local file path.
- **TARGET TOOL**: `read_file_metadata`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `metadata_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "path": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Path",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "path": {
    "title": "Path",
    "type": "string"
  },
  "name": {
    "title": "Name",
    "type": "string"
  },
  "extension": {
    "title": "Extension",
    "type": "string"
  },
  "size_bytes": {
    "title": "Size Bytes",
    "type": "integer"
  },
  "created_iso": {
    "title": "Created Iso",
    "type": "string"
  },
  "modified_iso": {
    "title": "Modified Iso",
    "type": "string"
  },
  "is_directory": {
    "title": "Is Directory",
    "type": "boolean"
  },
  "mime_type": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Mime Type"
  }
}
```

#### EXAMPLES
- "Check size of video.mp4"
- "When was report.pdf last modified?"
- "Get metadata for data.csv"

#### COUNTEREXAMPLES
- "Read file content"
- "Document QA"
- "Find duplicates"

---

### `file.batch_rename`

- **DESCRIPTION**: Applies systematic pattern or regex renaming across multiple files in a directory with dry-run preview.
- **TARGET TOOL**: `batch_rename`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `batch_rename_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "directory": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Directory",
    "type": "string"
  },
  "pattern": {
    "maxLength": 256,
    "minLength": 1,
    "title": "Pattern",
    "type": "string"
  },
  "replacement": {
    "maxLength": 256,
    "title": "Replacement",
    "type": "string"
  },
  "dry_run": {
    "default": true,
    "title": "Dry Run",
    "type": "boolean"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "items": {
    "items": {
      "$ref": "#/$defs/BatchRenameItem"
    },
    "title": "Items",
    "type": "array"
  },
  "dry_run": {
    "title": "Dry Run",
    "type": "boolean"
  },
  "total_processed": {
    "title": "Total Processed",
    "type": "integer"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Batch rename all images in Photos to vacation_001.jpg"
- "Add prefix 2026_ to all files in Documents"

#### COUNTEREXAMPLES
- "Rename single file"
- "Organize downloads"

---

### `file.organize_downloads`

- **DESCRIPTION**: Automatically sorts loose files in the Downloads folder into subdirectories by file type.
- **TARGET TOOL**: `organize_downloads`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `downloads_organized_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "downloads_path": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Downloads Path",
    "type": "string"
  },
  "dry_run": {
    "default": true,
    "title": "Dry Run",
    "type": "boolean"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "moves": {
    "items": {
      "$ref": "#/$defs/OrganizedFileItem"
    },
    "title": "Moves",
    "type": "array"
  },
  "dry_run": {
    "title": "Dry Run",
    "type": "boolean"
  },
  "total_moved": {
    "title": "Total Moved",
    "type": "integer"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Organize my Downloads folder"
- "Clean up Downloads by sorting documents and images"

#### COUNTEREXAMPLES
- "List files in downloads"
- "Delete downloads"

---

### `file.find_duplicates`

- **DESCRIPTION**: Identifies identical duplicate files across a directory tree based on exact size and SHA-256 content hashes.
- **TARGET TOOL**: `find_duplicates`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `duplicates_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "directory": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Directory",
    "type": "string"
  },
  "min_size_bytes": {
    "default": 1,
    "minimum": 0,
    "title": "Min Size Bytes",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "directory": {
    "title": "Directory",
    "type": "string"
  },
  "duplicate_groups": {
    "items": {
      "$ref": "#/$defs/DuplicateGroup"
    },
    "title": "Duplicate Groups",
    "type": "array"
  },
  "total_duplicates": {
    "title": "Total Duplicates",
    "type": "integer"
  },
  "wasted_bytes": {
    "title": "Wasted Bytes",
    "type": "integer"
  }
}
```

#### EXAMPLES
- "Find duplicate files in Documents"
- "Scan C:/Media for duplicate images"

#### COUNTEREXAMPLES
- "Copy file"
- "Find file"
- "Find notes"

---

## RAG Capabilities (12)

### `rag.document_qa`

- **DESCRIPTION**: Answers questions based on local document contents with verifiable section citations.
- **TARGET TOOL**: `document_qa`
- **RISK**: `READ_ONLY`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `qa_citation_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "document_path": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Document Path",
    "type": "string"
  },
  "question": {
    "maxLength": 1024,
    "minLength": 1,
    "title": "Question",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "answer": {
    "title": "Answer",
    "type": "string"
  },
  "citations": {
    "items": {
      "$ref": "#/$defs/Citation"
    },
    "title": "Citations",
    "type": "array"
  },
  "abstained": {
    "title": "Abstained",
    "type": "boolean"
  },
  "confidence": {
    "title": "Confidence",
    "type": "number"
  }
}
```

#### EXAMPLES
- "What are the revenue figures in the financial report?"
- "Summarize Section 3 of project_plan.pdf"

#### COUNTEREXAMPLES
- "Search the web"
- "Find file"
- "Read file metadata"

---

### `rag.search_web`

- **DESCRIPTION**: Performs a real-time web search for recent news, technical documentation, or factual queries.
- **TARGET TOOL**: `search_web`
- **RISK**: `READ_ONLY`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `web_results_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "query": {
    "description": "Search query or question (e.g., 'AI news today', 'weather in Tokyo')",
    "maxLength": 512,
    "minLength": 1,
    "title": "Query",
    "type": "string"
  },
  "max_results": {
    "default": 5,
    "description": "Maximum number of search results to return",
    "maximum": 10,
    "minimum": 1,
    "title": "Max Results",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "query": {
    "title": "Query",
    "type": "string"
  },
  "summary": {
    "title": "Summary",
    "type": "string"
  },
  "results": {
    "items": {
      "$ref": "#/$defs/SearchResultItem"
    },
    "title": "Results",
    "type": "array"
  },
  "count": {
    "title": "Count",
    "type": "integer"
  }
}
```

#### EXAMPLES
- "Search the web for artificial intelligence news"
- "Look up latest Python 3.12 release notes online"

#### COUNTEREXAMPLES
- "Find file"
- "Search local notes"
- "Browse to url"

---

### `rag.search_news`

- **DESCRIPTION**: Searches for verified real-time Indian and global news headlines.
- **TARGET TOOL**: `search_news`
- **RISK**: `READ_ONLY`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `news_results_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "query": {
    "default": "India today news",
    "description": "News topic or region to search",
    "maxLength": 512,
    "title": "Query",
    "type": "string"
  },
  "open_browser": {
    "default": true,
    "description": "Whether to open the news page in browser",
    "title": "Open Browser",
    "type": "boolean"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "query": {
    "title": "Query",
    "type": "string"
  },
  "headlines": {
    "items": {
      "type": "string"
    },
    "title": "Headlines",
    "type": "array"
  },
  "summary": {
    "title": "Summary",
    "type": "string"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Search for latest news in India"
- "What are today's top tech headlines?"

#### COUNTEREXAMPLES
- "Search notes"
- "RSS latest"
- "Search web for python"

---

### `rag.rss_latest`

- **DESCRIPTION**: Fetches recent unread articles and news headlines from configured RSS/Atom feeds.
- **TARGET TOOL**: `rss_latest`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `rss_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "query": {
    "default": "",
    "description": "Query or topic to filter, e.g. 'AI', 'tech'",
    "title": "Query",
    "type": "string"
  },
  "limit": {
    "default": 5,
    "description": "Max number of items to return",
    "maximum": 20,
    "minimum": 1,
    "title": "Limit",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "items": {
    "items": {
      "additionalProperties": true,
      "type": "object"
    },
    "title": "Items",
    "type": "array"
  },
  "count": {
    "default": 0,
    "title": "Count",
    "type": "integer"
  },
  "source": {
    "default": "rss",
    "title": "Source",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Fetch latest RSS headlines"
- "What's new on my RSS feeds?"

#### COUNTEREXAMPLES
- "Search web"
- "Morning briefing"

---

### `rag.capture_note`

- **DESCRIPTION**: Quickly saves a short thought, snippet, or reminder into the local markdown notes system.
- **TARGET TOOL**: `capture_note`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `note_file_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "content": {
    "maxLength": 10000,
    "minLength": 1,
    "title": "Content",
    "type": "string"
  },
  "tag": {
    "default": "general",
    "maxLength": 64,
    "title": "Tag",
    "type": "string"
  },
  "source": {
    "default": "user_capture",
    "maxLength": 256,
    "title": "Source",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "note_id": {
    "title": "Note Id",
    "type": "string"
  },
  "file_path": {
    "title": "File Path",
    "type": "string"
  },
  "timestamp": {
    "title": "Timestamp",
    "type": "string"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Note down that meeting is at 4 PM"
- "Capture note: buy groceries tomorrow"
- "Write down api key idea"

#### COUNTEREXAMPLES
- "Search notes"
- "Memos create"
- "Dictate text"

---

### `rag.search_notes`

- **DESCRIPTION**: Searches previously captured local markdown notes using full-text keywords.
- **TARGET TOOL**: `search_notes`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `notes_results_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "query": {
    "maxLength": 512,
    "minLength": 1,
    "title": "Query",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "matches": {
    "items": {
      "$ref": "#/$defs/NoteItem"
    },
    "title": "Matches",
    "type": "array"
  },
  "total_found": {
    "title": "Total Found",
    "type": "integer"
  }
}
```

#### EXAMPLES
- "Search notes for grocery list"
- "Find my notes about project architecture"
- "Look up note meeting"

#### COUNTEREXAMPLES
- "Search the web"
- "Find file"
- "Document QA"

---

### `rag.memos_create`

- **DESCRIPTION**: Posts a note or reminder into the local Memos inbox instance.
- **TARGET TOOL**: `memos_create`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `memos_api_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "content": {
    "description": "Note text to save to Memos",
    "title": "Content",
    "type": "string"
  },
  "tags": {
    "description": "Optional tags for the note",
    "items": {
      "type": "string"
    },
    "title": "Tags",
    "type": "array"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "notes": {
    "items": {
      "additionalProperties": true,
      "type": "object"
    },
    "title": "Notes",
    "type": "array"
  },
  "count": {
    "default": 0,
    "title": "Count",
    "type": "integer"
  },
  "message": {
    "default": "",
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Add a memo about server restart"
- "Save to Memos: test deployment"

#### COUNTEREXAMPLES
- "Capture note"
- "Memos recent"
- "Send whatsapp"

---

### `rag.memos_recent`

- **DESCRIPTION**: Retrieves the most recent human-readable memos and reminders from Memos inbox.
- **TARGET TOOL**: `memos_recent`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `memos_list_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "query": {
    "default": "",
    "description": "Search query",
    "title": "Query",
    "type": "string"
  },
  "limit": {
    "default": 5,
    "description": "Max number of notes",
    "maximum": 20,
    "minimum": 1,
    "title": "Limit",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "notes": {
    "items": {
      "additionalProperties": true,
      "type": "object"
    },
    "title": "Notes",
    "type": "array"
  },
  "count": {
    "default": 0,
    "title": "Count",
    "type": "integer"
  },
  "message": {
    "default": "",
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Show recent memos"
- "What's in my Memos inbox?"
- "List my latest memos"

#### COUNTEREXAMPLES
- "Memos create"
- "Search notes"
- "Morning briefing"

---

### `rag.morning_briefing`

- **DESCRIPTION**: Compiles and speaks an integrated morning briefing covering system health, RSS, weather, and tasks.
- **TARGET TOOL**: `morning_briefing`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `briefing_compiled_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "spoken_text": {
    "title": "Spoken Text",
    "type": "string"
  },
  "duration_ms": {
    "default": 0.0,
    "title": "Duration Ms",
    "type": "number"
  },
  "sections": {
    "additionalProperties": true,
    "title": "Sections",
    "type": "object"
  }
}
```

#### EXAMPLES
- "Give me my morning briefing"
- "What's my briefing for today?"
- "Good morning, brief me"

#### COUNTEREXAMPLES
- "Personal briefing"
- "System diagnostics"
- "RSS latest"

---

### `rag.personal_briefing`

- **DESCRIPTION**: Generates an actionable daily briefing focused on active projects, tasks, and recent notes.
- **TARGET TOOL**: `personal_briefing`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `briefing_compiled_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "include_calendar": {
    "default": true,
    "title": "Include Calendar",
    "type": "boolean"
  },
  "include_notes": {
    "default": true,
    "title": "Include Notes",
    "type": "boolean"
  },
  "project_path": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Project Path"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "briefing_text": {
    "title": "Briefing Text",
    "type": "string"
  },
  "items_count": {
    "title": "Items Count",
    "type": "integer"
  },
  "generated_at": {
    "title": "Generated At",
    "type": "string"
  }
}
```

#### EXAMPLES
- "What are my priorities today?"
- "Give me my personal briefing"
- "Summarize active tasks"

#### COUNTEREXAMPLES
- "Morning briefing"
- "System info"

---

### `rag.meeting_notes`

- **DESCRIPTION**: Extracts structured summary, key decisions, and action items from a meeting transcript.
- **TARGET TOOL**: `generate_meeting_notes`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `action_items_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "title": {
    "maxLength": 256,
    "minLength": 1,
    "title": "Title",
    "type": "string"
  },
  "transcript": {
    "maxLength": 50000,
    "minLength": 1,
    "title": "Transcript",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "title": {
    "title": "Title",
    "type": "string"
  },
  "summary_path": {
    "title": "Summary Path",
    "type": "string"
  },
  "action_items": {
    "items": {
      "type": "string"
    },
    "title": "Action Items",
    "type": "array"
  },
  "summary_points": {
    "items": {
      "type": "string"
    },
    "title": "Summary Points",
    "type": "array"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Generate meeting notes from transcript.txt"
- "Extract action items from the meeting log"

#### COUNTEREXAMPLES
- "Document QA"
- "Dictate text"
- "Capture note"

---

### `rag.ollama_chat`

- **DESCRIPTION**: Queries the local Ollama LLM for general knowledge, coding assistance, or reasoning.
- **TARGET TOOL**: `ollama_chat`
- **RISK**: `READ_ONLY`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `llm_response_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "query": {
    "description": "User question, text, or instruction for Ollama",
    "title": "Query",
    "type": "string"
  },
  "system_prompt": {
    "default": "You are JARVIS, an intelligent, concise AI assistant for Windows. Answer the user's question directly, clearly, and concisely in 1-3 sentences. If the user asks for code or terminal commands, provide them directly.",
    "description": "System prompt guiding Ollama's behavior",
    "title": "System Prompt",
    "type": "string"
  },
  "timeout_s": {
    "default": 30.0,
    "description": "Query timeout in seconds",
    "title": "Timeout S",
    "type": "number"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "response": {
    "title": "Response",
    "type": "string"
  },
  "model": {
    "default": "llama3.2:latest",
    "title": "Model",
    "type": "string"
  },
  "status": {
    "default": "completed",
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Explain how quantum entanglement works"
- "Why is the sky blue?"
- "Write a quick Python sort function"

#### COUNTEREXAMPLES
- "Run powershell command"
- "Open app"
- "Search web"

---

## PHONE Capabilities (9)

### `phone.status`

- **DESCRIPTION**: Queries connected Android device status, battery percentage, and scrcpy readiness via ADB.
- **TARGET TOOL**: `android_status`
- **RISK**: `READ_ONLY`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `adb_device_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "message": {
    "title": "Message",
    "type": "string"
  },
  "data": {
    "additionalProperties": true,
    "title": "Data",
    "type": "object"
  }
}
```

#### EXAMPLES
- "Is my phone connected?"
- "Check phone status"
- "What is my phone's battery level?"

#### COUNTEREXAMPLES
- "Mirror phone screen"
- "Send file to phone"
- "Send notification"

---

### `phone.mirror_open`

- **DESCRIPTION**: Spawns low-latency desktop phone screen mirroring via scrcpy over USB or Wi-Fi.
- **TARGET TOOL**: `android_open_control`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `scrcpy_process_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "message": {
    "title": "Message",
    "type": "string"
  },
  "data": {
    "additionalProperties": true,
    "title": "Data",
    "type": "object"
  }
}
```

#### EXAMPLES
- "Show my phone screen on PC"
- "Mirror phone"
- "Open phone control"

#### COUNTEREXAMPLES
- "Close phone mirror"
- "Phone status"
- "Send text to phone"

---

### `phone.mirror_close`

- **DESCRIPTION**: Closes the active scrcpy screen mirroring window.
- **TARGET TOOL**: `android_close_control`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `scrcpy_closed_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "message": {
    "title": "Message",
    "type": "string"
  },
  "data": {
    "additionalProperties": true,
    "title": "Data",
    "type": "object"
  }
}
```

#### EXAMPLES
- "Close phone control"
- "Stop mirroring phone screen"
- "Close scrcpy"

#### COUNTEREXAMPLES
- "Open phone control"
- "Close app Chrome"
- "Close window"

---

### `phone.home`

- **DESCRIPTION**: Presses the Home navigation button on the connected Android phone via ADB.
- **TARGET TOOL**: `android_home`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `adb_keyevent_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "message": {
    "title": "Message",
    "type": "string"
  },
  "data": {
    "additionalProperties": true,
    "title": "Data",
    "type": "object"
  }
}
```

#### EXAMPLES
- "Press home on my phone"
- "Go to phone home screen"

#### COUNTEREXAMPLES
- "Show desktop"
- "Phone back"
- "Mirror phone"

---

### `phone.back`

- **DESCRIPTION**: Presses the Back navigation button on the connected Android phone via ADB.
- **TARGET TOOL**: `android_back`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `adb_keyevent_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{}
```

#### OUTPUT SCHEMA
```json
{
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "message": {
    "title": "Message",
    "type": "string"
  },
  "data": {
    "additionalProperties": true,
    "title": "Data",
    "type": "object"
  }
}
```

#### EXAMPLES
- "Press back on my phone"
- "Go back on Android"

#### COUNTEREXAMPLES
- "Phone home"
- "Browser back"
- "Close app"

---

### `phone.open_app`

- **DESCRIPTION**: Launches an Android application or package on the connected phone via ADB intent.
- **TARGET TOOL**: `android_open_app`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `adb_focused_window_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "app_name": {
    "description": "Name or package name of the app to open, e.g. 'Spotify', 'camera', 'settings'",
    "title": "App Name",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "message": {
    "title": "Message",
    "type": "string"
  },
  "data": {
    "additionalProperties": true,
    "title": "Data",
    "type": "object"
  }
}
```

#### EXAMPLES
- "Open WhatsApp on my phone"
- "Launch Camera on Android"
- "Open Spotify on phone"

#### COUNTEREXAMPLES
- "Open Spotify on PC"
- "Mirror phone"
- "Phone status"

---

### `phone.send_file`

- **DESCRIPTION**: Transfers a local file from PC to connected phone over local Wi-Fi via LocalSend protocol.
- **TARGET TOOL**: `localsend_file`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `localsend_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "path": {
    "default": "",
    "description": "Path to the file to send. If empty, resolves from active file or recent files.",
    "title": "Path",
    "type": "string"
  },
  "target_alias": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "description": "Optional target device alias",
    "title": "Target Alias"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "message": {
    "title": "Message",
    "type": "string"
  },
  "bytes_transferred": {
    "default": 0,
    "title": "Bytes Transferred",
    "type": "integer"
  }
}
```

#### EXAMPLES
- "Send report.pdf to my phone"
- "Transfer image.png to phone via LocalSend"

#### COUNTEREXAMPLES
- "Send text to phone"
- "Copy file"
- "Send notification"

---

### `phone.send_text`

- **DESCRIPTION**: Transfers clipboard text or URL to phone via LocalSend protocol.
- **TARGET TOOL**: `localsend_text`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `localsend_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "text": {
    "description": "Text or URL to send to phone",
    "title": "Text",
    "type": "string"
  },
  "target_alias": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "description": "Optional target device alias",
    "title": "Target Alias"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "message": {
    "title": "Message",
    "type": "string"
  },
  "bytes_transferred": {
    "default": 0,
    "title": "Bytes Transferred",
    "type": "integer"
  }
}
```

#### EXAMPLES
- "Send clipboard text to my phone"
- "Push link https://github.com to phone"

#### COUNTEREXAMPLES
- "Send file to phone"
- "Send WhatsApp message"
- "Notification send"

---

### `phone.send_notification`

- **DESCRIPTION**: Dispatches an encrypted push notification to user phone via ntfy or Gotify service.
- **TARGET TOOL**: `notification_send`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `notification_ack_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "title": {
    "default": "JARVIS Alert",
    "description": "Notification title",
    "title": "Title",
    "type": "string"
  },
  "message": {
    "description": "Message body to send",
    "title": "Message",
    "type": "string"
  },
  "priority": {
    "default": 3,
    "description": "Priority 1-5",
    "maximum": 5,
    "minimum": 1,
    "title": "Priority",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "success": {
    "title": "Success",
    "type": "boolean"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Send a test notification to my phone"
- "Alert my phone when task finishes"

#### COUNTEREXAMPLES
- "Send text to phone"
- "Send WhatsApp message"
- "Wake greeting"

---

## WHATSAPP Capabilities (4)

### `whatsapp.send`

- **DESCRIPTION**: Sends a WhatsApp message to a recipient contact or phone number. Requires confirmation ticket in production.
- **TARGET TOOL**: `send_whatsapp_message`
- **RISK**: `EXTERNAL_EFFECT`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `whatsapp_transport_ack_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "recipient": {
    "description": "Contact name, phone number, or WhatsApp JID",
    "maxLength": 256,
    "minLength": 1,
    "title": "Recipient",
    "type": "string"
  },
  "message": {
    "description": "Message text to send",
    "maxLength": 4096,
    "minLength": 1,
    "title": "Message",
    "type": "string"
  },
  "confirmation_ticket": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "description": "Confirmation ticket ID if action required approval",
    "title": "Confirmation Ticket"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "recipient": {
    "title": "Recipient",
    "type": "string"
  },
  "recipient_jid": {
    "title": "Recipient Jid",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  },
  "message_id": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Message Id"
  },
  "ticket_id": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Ticket Id"
  },
  "action_ledger_status": {
    "default": "COMMITTED",
    "title": "Action Ledger Status",
    "type": "string"
  },
  "evidence": {
    "additionalProperties": true,
    "title": "Evidence",
    "type": "object"
  }
}
```

#### EXAMPLES
- "Send a WhatsApp message to Mom saying I will be home soon"
- "Message Rahul on WhatsApp"

#### COUNTEREXAMPLES
- "Read whatsapp messages"
- "Summarize whatsapp"
- "Send text to phone"

---

### `whatsapp.read`

- **DESCRIPTION**: Reads incoming unread or recent WhatsApp messages from the local Baileys bridge.
- **TARGET TOOL**: `read_whatsapp_messages`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `whatsapp_read_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "filter": {
    "default": "needs_reply",
    "description": "Filter: 'needs_reply', 'urgent', 'unread', or 'all'",
    "title": "Filter",
    "type": "string"
  },
  "limit": {
    "default": 5,
    "description": "Max messages to retrieve",
    "maximum": 50,
    "minimum": 1,
    "title": "Limit",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "count": {
    "title": "Count",
    "type": "integer"
  },
  "filter": {
    "title": "Filter",
    "type": "string"
  },
  "messages": {
    "items": {
      "additionalProperties": true,
      "type": "object"
    },
    "title": "Messages",
    "type": "array"
  },
  "spoken_summary": {
    "title": "Spoken Summary",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Read my unread WhatsApp messages"
- "Check recent WhatsApp messages"

#### COUNTEREXAMPLES
- "Send whatsapp"
- "Summarize whatsapp"
- "Read file"

---

### `whatsapp.summarize`

- **DESCRIPTION**: Summarizes pending WhatsApp messages requiring attention, highlighting urgent items.
- **TARGET TOOL**: `summarize_whatsapp_messages`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `whatsapp_summary_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "include_all": {
    "default": false,
    "description": "Whether to include already read messages",
    "title": "Include All",
    "type": "boolean"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "total_pending": {
    "title": "Total Pending",
    "type": "integer"
  },
  "urgent_count": {
    "title": "Urgent Count",
    "type": "integer"
  },
  "normal_count": {
    "title": "Normal Count",
    "type": "integer"
  },
  "spoken_summary": {
    "title": "Spoken Summary",
    "type": "string"
  },
  "urgent_messages": {
    "items": {
      "additionalProperties": true,
      "type": "object"
    },
    "title": "Urgent Messages",
    "type": "array"
  },
  "normal_messages": {
    "items": {
      "additionalProperties": true,
      "type": "object"
    },
    "title": "Normal Messages",
    "type": "array"
  }
}
```

#### EXAMPLES
- "Summarize my WhatsApp messages"
- "What urgent WhatsApp messages need my attention?"

#### COUNTEREXAMPLES
- "Read whatsapp"
- "Morning briefing"
- "Meeting notes"

---

### `whatsapp.action`

- **DESCRIPTION**: Manages WhatsApp transport bridge connectivity: pair QR, connect, or disconnect.
- **TARGET TOOL**: `whatsapp_action`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `whatsapp_bridge_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "action": {
    "default": "status",
    "description": "Action: connect, disconnect, pair, status",
    "title": "Action",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "status": {
    "title": "Status",
    "type": "string"
  },
  "action": {
    "title": "Action",
    "type": "string"
  },
  "message": {
    "title": "Message",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Re-pair WhatsApp"
- "Show WhatsApp pairing QR code"
- "Reconnect WhatsApp bridge"

#### COUNTEREXAMPLES
- "Send whatsapp message"
- "Read whatsapp"

---

## WORKFLOW Capabilities (9)

### `workflow.save_workspace`

- **DESCRIPTION**: Saves a workspace manifest of open applications, directories, and browser tabs for later resumption.
- **TARGET TOOL**: `save_workspace`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `manifest_exists_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "name": {
    "maxLength": 128,
    "minLength": 1,
    "title": "Name",
    "type": "string"
  },
  "folders": {
    "default": [],
    "items": {
      "type": "string"
    },
    "title": "Folders",
    "type": "array"
  },
  "urls": {
    "default": [],
    "items": {
      "type": "string"
    },
    "title": "Urls",
    "type": "array"
  },
  "notes_path": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Notes Path"
  },
  "editor_command": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Editor Command"
  },
  "timer_minutes": {
    "anyOf": [
      {
        "type": "integer"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Timer Minutes"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "name": {
    "title": "Name",
    "type": "string"
  },
  "manifest_path": {
    "title": "Manifest Path",
    "type": "string"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Save my workspace as 'CodingSession'"
- "Save workspace PythonProject"

#### COUNTEREXAMPLES
- "Launch workspace"
- "Save file"
- "Take screenshot"

---

### `workflow.launch_workspace`

- **DESCRIPTION**: Restores and opens apps, folders, and browser tabs saved in a workspace manifest.
- **TARGET TOOL**: `launch_workspace`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `workspace_restored_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "name": {
    "maxLength": 128,
    "minLength": 1,
    "title": "Name",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "name": {
    "title": "Name",
    "type": "string"
  },
  "opened_folders": {
    "items": {
      "type": "string"
    },
    "title": "Opened Folders",
    "type": "array"
  },
  "opened_urls": {
    "items": {
      "type": "string"
    },
    "title": "Opened Urls",
    "type": "array"
  },
  "notes_path": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "title": "Notes Path"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Launch workspace 'CodingSession'"
- "Restore PythonProject workspace"

#### COUNTEREXAMPLES
- "Save workspace"
- "Open app"
- "Open folder"

---

### `workflow.study_focus`

- **DESCRIPTION**: Starts a distraction-free focus or study session with a countdown timer.
- **TARGET TOOL**: `start_study_focus`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `FREE`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `focus_active_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "subject": {
    "maxLength": 128,
    "minLength": 1,
    "title": "Subject",
    "type": "string"
  },
  "duration_minutes": {
    "default": 25,
    "maximum": 180,
    "minimum": 1,
    "title": "Duration Minutes",
    "type": "integer"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "subject": {
    "title": "Subject",
    "type": "string"
  },
  "timer_minutes": {
    "title": "Timer Minutes",
    "type": "integer"
  },
  "started_at": {
    "title": "Started At",
    "type": "string"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Start study focus for 25 minutes"
- "Begin focus mode"
- "Focus session 45 mins"

#### COUNTEREXAMPLES
- "Set alarm"
- "What time is it?"
- "Sleep PC"

---

### `workflow.run_tests`

- **DESCRIPTION**: Executes automated unit tests (pytest) for an approved developer repository and returns metrics.
- **TARGET TOOL**: `run_project_tests`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `test_results_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "repo_path": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Repo Path",
    "type": "string"
  },
  "test_target": {
    "default": ".",
    "maxLength": 512,
    "title": "Test Target",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "passed": {
    "title": "Passed",
    "type": "boolean"
  },
  "summary": {
    "title": "Summary",
    "type": "string"
  },
  "exit_code": {
    "title": "Exit Code",
    "type": "integer"
  }
}
```

#### EXAMPLES
- "Run project tests"
- "Execute unit tests for current repository"
- "Run pytest"

#### COUNTEREXAMPLES
- "Diagnose error"
- "Git status"
- "Run powershell"

---

### `workflow.git_status`

- **DESCRIPTION**: Checks Git branch, staged/unstaged changes, and untracked files in an approved project directory.
- **TARGET TOOL**: `git_status`
- **RISK**: `READ_ONLY`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `git_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "repo_path": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Repo Path",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "branch": {
    "title": "Branch",
    "type": "string"
  },
  "modified_files": {
    "items": {
      "type": "string"
    },
    "title": "Modified Files",
    "type": "array"
  },
  "untracked_files": {
    "items": {
      "type": "string"
    },
    "title": "Untracked Files",
    "type": "array"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Check git status"
- "What files are modified in git?"
- "Show git diff status"

#### COUNTEREXAMPLES
- "Run tests"
- "Find file"
- "Diagnose error"

---

### `workflow.diagnose_error`

- **DESCRIPTION**: Analyzes stack traces, redaction of sensitive credentials, and produces actionable fixes.
- **TARGET TOOL**: `diagnose_error`
- **RISK**: `READ_ONLY`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `diagnostic_fix_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "error_log": {
    "maxLength": 20000,
    "minLength": 1,
    "title": "Error Log",
    "type": "string"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "diagnosis": {
    "title": "Diagnosis",
    "type": "string"
  },
  "suggested_fix": {
    "title": "Suggested Fix",
    "type": "string"
  },
  "redacted_log": {
    "title": "Redacted Log",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Diagnose this error traceback"
- "Debug error from log file"

#### COUNTEREXAMPLES
- "System diagnostics"
- "Run tests"
- "Ollama chat"

---

### `workflow.dictate_text`

- **DESCRIPTION**: Transcribes spoken dictation, normalizes grammar, and inserts text into the active application.
- **TARGET TOOL**: `dictate_text`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `dictate_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "text": {
    "maxLength": 10000,
    "minLength": 1,
    "title": "Text",
    "type": "string"
  },
  "target_app": {
    "anyOf": [
      {
        "maxLength": 256,
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Target App"
  },
  "auto_punctuate": {
    "default": true,
    "title": "Auto Punctuate",
    "type": "boolean"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "formatted_text": {
    "title": "Formatted Text",
    "type": "string"
  },
  "target_app": {
    "title": "Target App",
    "type": "string"
  },
  "characters": {
    "title": "Characters",
    "type": "integer"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Dictate text into Notepad"
- "Start dictation mode"
- "Type: Meeting confirmed for Monday"

#### COUNTEREXAMPLES
- "Capture note"
- "Send whatsapp"
- "TTS voice"

---

### `workflow.extract_audio`

- **DESCRIPTION**: Extracts the audio track from a video file into an MP3 or WAV audio file using FFmpeg.
- **TARGET TOOL**: `extract_audio`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `audio_file_exists_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "video_path": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Video Path",
    "type": "string"
  },
  "output_audio_path": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Output Audio Path"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "output_path": {
    "title": "Output Path",
    "type": "string"
  },
  "format": {
    "title": "Format",
    "type": "string"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Extract audio from video.mp4"
- "Convert presentation.mp4 to audio.mp3"

#### COUNTEREXAMPLES
- "Trim media clip"
- "Play youtube"
- "Media control"

---

### `workflow.trim_clip`

- **DESCRIPTION**: Trims a section of a video or audio file given start timestamp and duration using FFmpeg.
- **TARGET TOOL**: `trim_media_clip`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `MEDIUM`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `clip_trimmed_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "media_path": {
    "maxLength": 4096,
    "minLength": 1,
    "title": "Media Path",
    "type": "string"
  },
  "start_time": {
    "maxLength": 16,
    "minLength": 1,
    "title": "Start Time",
    "type": "string"
  },
  "duration": {
    "maxLength": 16,
    "minLength": 1,
    "title": "Duration",
    "type": "string"
  },
  "output_path": {
    "anyOf": [
      {
        "type": "string"
      },
      {
        "type": "null"
      }
    ],
    "default": null,
    "title": "Output Path"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "output_path": {
    "title": "Output Path",
    "type": "string"
  },
  "duration": {
    "title": "Duration",
    "type": "string"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Trim the first 30 seconds of recording.mp4"
- "Cut audio from 01:00 for 45 seconds"

#### COUNTEREXAMPLES
- "Extract audio"
- "Take screenshot"
- "Play video"

---

## TERMINAL Capabilities (1)

### `terminal.powershell`

- **DESCRIPTION**: Executes a validated, policy-checked PowerShell command or script with administrative elevation if permitted.
- **TARGET TOOL**: `powershell_command`
- **RISK**: `REVERSIBLE`
- **COST TIER**: `LOW`
- **DEPENDENCIES**: Standard Windows Environment
- **VERIFIER**: `process_exit_code_zero_probe`
- **AVAILABILITY**: Always Available (Local Host)

#### INPUT SCHEMA
```json
{
  "command": {
    "description": "PowerShell command or script to execute",
    "maxLength": 8192,
    "minLength": 1,
    "title": "Command",
    "type": "string"
  },
  "as_admin": {
    "default": true,
    "description": "Run in administrator context by default",
    "title": "As Admin",
    "type": "boolean"
  },
  "timeout_s": {
    "default": 120.0,
    "description": "Execution timeout in seconds",
    "maximum": 600.0,
    "minimum": 1.0,
    "title": "Timeout S",
    "type": "number"
  }
}
```

#### OUTPUT SCHEMA
```json
{
  "stdout": {
    "title": "Stdout",
    "type": "string"
  },
  "stderr": {
    "title": "Stderr",
    "type": "string"
  },
  "exit_code": {
    "title": "Exit Code",
    "type": "integer"
  },
  "as_admin": {
    "title": "As Admin",
    "type": "boolean"
  },
  "status": {
    "title": "Status",
    "type": "string"
  }
}
```

#### EXAMPLES
- "Run powershell Get-Process"
- "Execute powershell script to check disk"
- "cmd dir"

#### COUNTEREXAMPLES
- "Install software"
- "System diagnostics"
- "List directory"

---
