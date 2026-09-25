# DESKTOP CAPABILITY CATALOG — JARVIS EDGE v1.x

> Generated: 2026-09-24
> Dependency: DESKTOP_OPERATOR_AUDIT.md
> Purpose: Catalog every reusable capability (existing + new) as typed,
> schema-validated entries. No hardcoded commands.

---

## DESIGN PRINCIPLES

1. **Capabilities, not commands** — Each entry is a reusable, composable unit
2. **Typed contracts** — Every capability has `InputModel → OutputModel`
3. **Single responsibility** — One action per capability
4. **Domain-namespaced** — `domain.verb` naming convention
5. **Policy-annotated** — Risk level, confirmation requirement, reversibility
6. **Tool-backed** — Maps to exactly one Tool in ToolRegistry
7. **Router-discoverable** — YAML intent patterns for Lane-0 matching

---

## CATALOG FORMAT

Each capability entry follows this schema:

```
capability_id: domain.verb
tool: tool_name
input: InputModel fields
output: OutputModel fields
risk: SAFE | REVERSIBLE | DESTRUCTIVE
confirm: never | always | if_destructive
status: EXISTS | EXTEND | NEW
phase: A | B | C | D | E
```

---

## DOMAIN 1: APPLICATION CONTROL (`app.*`)

### app.open ✅ EXISTS
```yaml
capability_id: app.open
tool: open_app
input: { name: str }
output: { name: str, target: str, pid: int?, process_names: list[str], associated: bool }
risk: SAFE
confirm: never
patterns:
  - "open {app}"
  - "launch {app}"
  - "start {app}"
  - "run {app}"
```

### app.close ✅ EXISTS
```yaml
capability_id: app.close
tool: close_app
input: { name: str }
output: { name: str, closed: bool, count: int }
risk: REVERSIBLE
confirm: never
patterns:
  - "close {app}"
  - "quit {app}"
  - "exit {app}"
  - "kill {app}"
```

### app.focus ✅ EXISTS (implicit in open_app)
```yaml
capability_id: app.focus
tool: focus_app
input: { name: str }
output: { name: str, focused: bool, hwnd: int? }
risk: SAFE
confirm: never
status: EXTEND  # Separate from open_app
patterns:
  - "switch to {app}"
  - "go to {app}"
  - "focus {app}"
  - "bring up {app}"
```

### app.list_installed ✅ EXISTS
```yaml
capability_id: app.list_installed
tool: list_installed_apps
input: { query: str?, category: str? }
output: { apps: list[AppInfo], count: int }
risk: SAFE
confirm: never
```

### app.install ✅ EXISTS
```yaml
capability_id: app.install
tool: install_software
input: { name: str, source: str? }
output: { name: str, installed: bool, version: str? }
risk: REVERSIBLE
confirm: always
```

### app.list_running 🆕 NEW
```yaml
capability_id: app.list_running
tool: list_running_apps
input: {}
output: { apps: list[RunningAppInfo], count: int }
risk: SAFE
confirm: never
phase: D
patterns:
  - "what apps are running"
  - "what's open"
  - "show running programs"
```

### app.is_running 🆕 NEW
```yaml
capability_id: app.is_running
tool: is_app_running
input: { name: str }
output: { name: str, running: bool, pid: int?, window_title: str? }
risk: SAFE
confirm: never
phase: D
patterns:
  - "is {app} running"
  - "is {app} open"
```

---

## DOMAIN 2: WINDOW MANAGEMENT (`window.*`)

### window.snap ✅ EXISTS
```yaml
capability_id: window.snap
tool: snap_window
input: { position: str, app_name: str? }  # left, right, top-left, etc.
output: { snapped: bool, position: str, window_title: str }
risk: SAFE
confirm: never
patterns:
  - "snap {app} to the {position}"
  - "put {app} on the {position}"
  - "snap this {position}"
```

### window.arrange ✅ EXISTS
```yaml
capability_id: window.arrange
tool: arrange_windows
input: { layout: str, apps: list[str]? }  # side-by-side, grid
output: { arranged: bool, layout: str, count: int }
risk: SAFE
confirm: never
patterns:
  - "arrange windows side by side"
  - "tile windows"
  - "grid layout"
```

### window.maximize ✅ EXISTS
```yaml
capability_id: window.maximize
tool: maximize_window
input: { app_name: str? }
output: { maximized: bool }
risk: SAFE
confirm: never
patterns:
  - "maximize {app}"
  - "make {app} full screen"
  - "maximize this"
```

### window.minimize ✅ EXISTS
```yaml
capability_id: window.minimize
tool: minimize_window
input: { app_name: str? }
output: { minimized: bool }
risk: SAFE
confirm: never
```

### window.close_active ✅ EXISTS
```yaml
capability_id: window.close_active
tool: close_active_window
input: {}
output: { closed: bool }
risk: REVERSIBLE
confirm: never
```

### window.show_desktop ✅ EXISTS
```yaml
capability_id: window.show_desktop
tool: show_desktop
input: {}
output: { shown: bool }
risk: SAFE
confirm: never
```

### window.switch ✅ EXISTS
```yaml
capability_id: window.switch
tool: switch_window
input: { target: str }
output: { switched: bool, window_title: str }
risk: SAFE
confirm: never
```

### window.list 🆕 NEW
```yaml
capability_id: window.list
tool: list_windows
input: { app_name: str? }
output: { windows: list[WindowInfo], count: int }
risk: SAFE
confirm: never
phase: A
patterns:
  - "list windows"
  - "what windows are open"
  - "show open windows"
```

### window.current 🆕 NEW
```yaml
capability_id: window.current
tool: get_active_window
input: {}
output: { app_name: str, window_title: str, pid: int }
risk: SAFE
confirm: never
phase: A
patterns:
  - "what app am I in"
  - "what window is this"
  - "which app is focused"
```

---

## DOMAIN 3: UI AUTOMATION (`ui.*`)

### ui.snapshot ✅ EXISTS
```yaml
capability_id: ui.snapshot
tool: desktop_ui_snapshot
input: { window_title: str? }
output: { elements: list[UIElement], count: int, app: str }
risk: SAFE
confirm: never
```

### ui.click ✅ EXISTS
```yaml
capability_id: ui.click
tool: desktop_ui_click
input: { window_title: str?, target_name: str?, automation_id: str? }
output: { clicked: bool, target: str, verification: str }
risk: SAFE
confirm: never
```

### ui.find 🆕 NEW
```yaml
capability_id: ui.find
tool: ui_find_element
input: { name: str?, automation_id: str?, control_type: str?, window_title: str? }
output: { found: bool, element: UIElement?, candidates: list[UIElement]?, confidence: str }
risk: SAFE
confirm: never
phase: A
```

### ui.read 🆕 NEW
```yaml
capability_id: ui.read
tool: ui_read_value
input: { target_name: str?, automation_id: str?, window_title: str? }
output: { value: str, name: str, control_type: str, editable: bool, checked: bool? }
risk: SAFE
confirm: never
phase: A
```

### ui.focus 🆕 NEW
```yaml
capability_id: ui.focus
tool: ui_focus_element
input: { target_name: str?, automation_id: str?, window_title: str? }
output: { focused: bool, element: str }
risk: SAFE
confirm: never
phase: A
```

### ui.set_value 🆕 NEW (tool wrapper)
```yaml
capability_id: ui.set_value
tool: ui_set_value
input: { value: str, target_name: str?, automation_id: str?, window_title: str? }
output: { success: bool, verified: bool, actual_value: str? }
risk: SAFE
confirm: never
phase: A
```

### ui.toggle 🆕 NEW (tool wrapper)
```yaml
capability_id: ui.toggle
tool: ui_toggle
input: { target_name: str?, automation_id: str?, expected_state: bool?, window_title: str? }
output: { success: bool, new_state: bool? }
risk: SAFE
confirm: never
phase: A
```

### ui.select 🆕 NEW (tool wrapper)
```yaml
capability_id: ui.select
tool: ui_select
input: { target_name: str?, automation_id: str?, window_title: str? }
output: { success: bool }
risk: SAFE
confirm: never
phase: A
```

### ui.scroll 🆕 NEW
```yaml
capability_id: ui.scroll
tool: ui_scroll
input: { direction: str, amount: int?, target_name: str?, window_title: str? }
output: { scrolled: bool }
risk: SAFE
confirm: never
phase: A
```

### ui.expand 🆕 NEW (tool wrapper)
```yaml
capability_id: ui.expand
tool: ui_expand
input: { target_name: str?, automation_id: str?, window_title: str? }
output: { success: bool }
risk: SAFE
confirm: never
phase: A
```

### ui.collapse 🆕 NEW (tool wrapper)
```yaml
capability_id: ui.collapse
tool: ui_collapse
input: { target_name: str?, automation_id: str?, window_title: str? }
output: { success: bool }
risk: SAFE
confirm: never
phase: A
```

---

## DOMAIN 4: KEYBOARD & INPUT (`input.*`)

### input.shortcut ✅ EXISTS
```yaml
capability_id: input.shortcut
tool: keyboard_shortcut
input: { shortcut: str }
output: { sent: bool, shortcut: str }
risk: SAFE
confirm: never
```

### input.type 🆕 NEW
```yaml
capability_id: input.type
tool: type_text
input: { text: str, method: str? }  # method: unicode | clipboard
output: { typed: bool, characters: int, method: str }
risk: SAFE
confirm: never
phase: A
patterns:
  - "type {text}"
```

---

## DOMAIN 5: CLIPBOARD (`clipboard.*`)

### clipboard.read ✅ EXISTS
### clipboard.copy ✅ EXISTS
### clipboard.paste ✅ EXISTS
### clipboard.act ✅ EXISTS (explain/summarize/rewrite)

### clipboard.set_text 🆕 NEW
```yaml
capability_id: clipboard.set_text
tool: clipboard_set_text
input: { text: str }
output: { success: bool }
risk: SAFE
confirm: never
phase: A
```

---

## DOMAIN 6: SCREEN CAPTURE (`screen.*`)

### screen.capture ✅ EXISTS
```yaml
capability_id: screen.capture
tool: take_screenshot
input: { path: str? }
output: { path: str, bytes: int, resource_id: str }  # NEW: resource_id
risk: SAFE
confirm: never
```

### screen.capture_window 🆕 NEW
```yaml
capability_id: screen.capture_window
tool: capture_window_screenshot
input: { app_name: str?, window_title: str? }
output: { path: str, bytes: int, resource_id: str, window_title: str }
risk: SAFE
confirm: never
phase: C
```

### screen.latest 🆕 NEW
```yaml
capability_id: screen.latest
tool: get_latest_screenshot
input: {}
output: { path: str, resource_id: str, capture_time: float, source_window: str? }
risk: SAFE
confirm: never
phase: C
```

### screen.describe 🆕 NEW
```yaml
capability_id: screen.describe
tool: describe_screenshot
input: { resource_id: str?, query: str? }
output: { description: str, elements: list[str]?, resource_id: str }
risk: SAFE
confirm: never
phase: C
```

---

## DOMAIN 7: DICTATION (`dictation.*`)

### dictation.type ✅ EXISTS
### dictation.voice_edit ✅ EXISTS
### dictation.mode ✅ EXISTS (start/stop/toggle)

### dictation.start 🆕 EXTEND
```yaml
capability_id: dictation.start
tool: dictation_control
input: { target_app: str?, target_window: str?, mode: str? }  # mode: normal | code | spelling | number
output: { active: bool, target: DictationTarget, state: str }
risk: SAFE
confirm: never
phase: B
patterns:
  - "start typing"
  - "start dictation"
  - "type in {app}"
  - "dictate"
```

### dictation.stop 🆕 EXTEND
```yaml
capability_id: dictation.stop
tool: dictation_control
input: { action: "stop" }
output: { active: bool, state: str, total_characters: int }
risk: SAFE
confirm: never
phase: B
patterns:
  - "stop typing"
  - "stop dictation"
  - "done typing"
```

### dictation.code_mode 🆕 NEW
```yaml
capability_id: dictation.code_mode
tool: dictation_code_mode
input: { action: str, language: str? }
output: { active: bool, language: str }
risk: SAFE
confirm: never
phase: B
```

---

## DOMAIN 8: BROWSER (`browser.*`)

### browser.navigate ✅ EXISTS
### browser.click ✅ EXISTS
### browser.type ✅ EXISTS
### browser.snapshot ✅ EXISTS

### browser.back 🆕 NEW
```yaml
capability_id: browser.back
tool: browser_back
input: {}
output: { success: bool, url: str }
risk: SAFE
confirm: never
phase: D
patterns: ["go back", "previous page"]
```

### browser.forward 🆕 NEW
### browser.refresh 🆕 NEW
### browser.new_tab 🆕 NEW
### browser.close_tab 🆕 NEW
### browser.switch_tab 🆕 NEW

### browser.read 🆕 NEW
```yaml
capability_id: browser.read
tool: browser_read_page
input: { selector: str?, max_length: int? }
output: { text: str, title: str, url: str }
risk: SAFE
confirm: never
phase: D
patterns: ["read this page", "what does this page say"]
```

### browser.find 🆕 NEW
```yaml
capability_id: browser.find
tool: browser_find_text
input: { query: str }
output: { found: bool, count: int }
risk: SAFE
confirm: never
phase: D
patterns: ["find {text} on this page"]
```

### browser.download 🆕 NEW
### browser.upload 🆕 NEW

---

## DOMAIN 9: SYSTEM (`system.*`)

### system.info ✅ EXISTS
### system.volume_get ✅ EXISTS
### system.volume_set ✅ EXISTS
### system.brightness_get ✅ EXISTS
### system.brightness_set ✅ EXISTS
### system.time ✅ EXISTS
### system.power ✅ EXISTS
### system.diagnostics ✅ EXISTS

### system.processes 🆕 NEW
```yaml
capability_id: system.processes
tool: list_processes
input: { sort_by: str?, limit: int? }
output: { processes: list[ProcessInfo], count: int }
risk: SAFE
confirm: never
phase: D
```

### system.network 🆕 NEW
```yaml
capability_id: system.network
tool: network_status
input: {}
output: { connected: bool, ssid: str?, ip: str?, download_speed: float? }
risk: SAFE
confirm: never
phase: D
patterns: ["am I connected to wifi", "what's my IP"]
```

---

## DOMAIN 10: FILE (`file.*`)

### file.search ✅ EXISTS
### file.open ✅ EXISTS
### file.create ✅ EXISTS
### file.rename ✅ EXISTS
### file.move ✅ EXISTS
### file.delete ✅ EXISTS
### file.list ✅ EXISTS

### file.copy 🆕 NEW
```yaml
capability_id: file.copy
tool: copy_file
input: { source: str, destination: str }
output: { source: str, destination: str, bytes: int }
risk: REVERSIBLE
confirm: if_destructive
phase: D
```

### file.attach 🆕 NEW
```yaml
capability_id: file.attach
tool: attach_file
input: { resource_id: str?, path: str?, query: str? }
output: { attached: bool, path: str, target_app: str }
risk: SAFE
confirm: never
phase: C
patterns: ["attach that", "attach the {file}", "attach the screenshot"]
```

---

## DOMAIN 11: PHONE / ANDROID (`android.*`)

### android.open_control ✅ EXISTS
### android.type_text ✅ EXISTS
### android.screenshot ✅ EXISTS
### transfer.send ✅ EXISTS

### android.open_app 🆕 NEW
```yaml
capability_id: android.open_app
tool: android_open_app
input: { app_name: str }
output: { opened: bool, app_name: str }
risk: SAFE
confirm: never
phase: D
```

### android.home 🆕 NEW
### android.back 🆕 NEW

---

## DOMAIN 12: WHATSAPP (`whatsapp.*`)

### whatsapp.send ✅ EXISTS
### whatsapp.read ✅ EXISTS
### whatsapp.summarize ✅ EXISTS

---

## DOMAIN 13: IDE (`ide.*`)

### ide.open ✅ EXISTS
### ide.focus ✅ EXISTS
### ide.type_prompt ✅ EXISTS
### ide.submit_prompt ✅ EXISTS
### ide.save_file ✅ EXISTS
### ide.switch_tab ✅ EXISTS
### ide.open_file ✅ EXISTS

---

## DOMAIN 14: MEDIA (`media.*`)

### media.play_youtube ✅ EXISTS
### media.control ✅ EXISTS (play/pause/next/previous/stop)

### media.play 🆕 NEW
```yaml
capability_id: media.play
tool: media_play
input: { query: str?, resource_id: str? }
output: { playing: bool, title: str, source: str, resource_id: str }
risk: SAFE
confirm: never
phase: C
```

---

## SUMMARY

| Domain | Existing | Extended | New | Total |
|---|---|---|---|---|
| app.* | 6 | 1 | 2 | 9 |
| window.* | 7 | 0 | 2 | 9 |
| ui.* | 2 | 0 | 9 | 11 |
| input.* | 1 | 0 | 1 | 2 |
| clipboard.* | 4 | 0 | 1 | 5 |
| screen.* | 1 | 0 | 3 | 4 |
| dictation.* | 3 | 2 | 1 | 6 |
| browser.* | 4 | 0 | 8 | 12 |
| system.* | 8 | 0 | 2 | 10 |
| file.* | 7 | 0 | 2 | 9 |
| android.* | 3 | 0 | 3 | 6 |
| whatsapp.* | 3 | 0 | 0 | 3 |
| ide.* | 7 | 0 | 0 | 7 |
| media.* | 2 | 0 | 1 | 3 |
| **Total** | **58** | **3** | **35** | **96** |
