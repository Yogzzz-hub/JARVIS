# JARVIS EDGE: the complete guide

JARVIS EDGE is a personal AI assistant for Windows that runs on your own PC. You can talk to it ("Hey Jarvis"), type
to it, or message it on WhatsApp.

It can:
- control the PC, apps, windows, files and settings;
- control an Android phone over ADB;
- send and answer WhatsApp messages;
- drive a browser and operate any desktop app by looking at the screen;
- answer questions from your own documents (RAG) and the web;
- remember things for you, run reminders, timers, to-dos and voice shortcuts.

Everything runs locally: deterministic fast paths (well under a millisecond to a few milliseconds), a local decision
engine (about 1 ms), and local LLMs through [Ollama](https://ollama.com). Anything risky is read back to you before it
happens.

This file is the single source of documentation for the project. It covers how to install and use JARVIS, every
command and feature, the architecture and workflow, every configuration file, the tools, the development workflow and
the project history.

---

## Contents

1. [Quick start](#1-quick-start)
2. [How to talk to JARVIS](#2-how-to-talk-to-jarvis)
3. [Everyday command cheat sheet](#3-everyday-command-cheat-sheet)
4. [Complete feature and command reference (144 capabilities)](#4-complete-feature-and-command-reference)
5. [Architecture and workflow](#5-architecture-and-workflow)
6. [The decision engine (JDE)](#6-the-decision-engine-jde)
7. [AI models, knowledge (RAG), memory and the database](#7-ai-models-knowledge-rag-memory-and-the-database)
8. [Integrations: WhatsApp, phone, Google, browser, screen](#8-integrations)
9. [Safety and security model](#9-safety-and-security-model)
10. [Performance](#10-performance)
11. [Configuration reference](#11-configuration-reference)
12. [Command-line tools and scripts](#12-command-line-tools-and-scripts)
13. [Development: tests, benchmarks, training](#13-development)
14. [Project phases and feature history](#14-project-phases-and-feature-history)
15. [Troubleshooting](#15-troubleshooting)
16. [Licences](#16-licences)

---

## 1. Quick start

### Requirements

- Windows 10/11 and Python 3.12. Setup can create `.venv` and a workspace-local Python for you.
- [Ollama](https://ollama.com/download) for the AI features. Deterministic commands work without it.
- Optional:
  - an NVIDIA GPU (faster speech recognition and larger models);
  - an Android phone with USB debugging (phone control);
  - Node.js (the WhatsApp bridge);
  - a Google OAuth client (Gmail/Calendar/Drive).

### Install (one time)

```powershell
powershell -NoProfile -File .\setup_jarvis.ps1           # core + voice + Windows automation + models
powershell -NoProfile -File .\setup_jarvis.ps1 -Browser  # also install the automated browser (Playwright)
python scripts\setup_models.py --jde                     # optional: GloVe vectors for the decision engine
```

Setup installs:
- the voice extras: wake word, speech recognition, VAD, TTS, push-to-talk hotkey;
- the Whisper speech model and the Piper voice, which are too large for git;
- the Ollama models named in `jarvis/config/jarvis.toml`.

Check everything at any time:

```powershell
powershell -NoProfile -File .\diagnose_jarvis.ps1
python scripts\setup_models.py --check
python -m jarvis.diagnostics
```

### Start

Double-click **`start.bat`**, or run `start.ps1`. It:
1. starts Ollama;
2. starts the WhatsApp bridge;
3. starts the backend (`python -m jarvis`, on `http://127.0.0.1:8765`);
4. opens the desktop UI.

Then say **"Hey Jarvis"**, or press **Ctrl+Shift+J** (push-to-talk). Typed commands work too:

```powershell
python -m jarvis.cli "open notepad"
python -m jarvis.cli "what is 15% of 240"
python -m jarvis.cli "ask rahul if he is free tonight on whatsapp"
python -m jarvis.cli --plan-only "find the latest invoice and send it to my phone"   # show the plan, run nothing
```

Stop the backend with Ctrl+C in its window. Restart it after changing configuration.

---

## 2. How to talk to JARVIS

| Way | How |
|---|---|
| Voice | Say **"Hey Jarvis"**, then the command. After a reply there is a short follow-up window, so you don't need the wake word again. Say "Hey Jarvis" while it is talking to interrupt (barge-in). |
| Push-to-talk | **Ctrl+Shift+J** anywhere in Windows. |
| Desktop UI | **Ctrl+Space** talk/finish, **Ctrl+K** type, **Esc** stop talking, **Up/Down** command history. Click the 3D reactor to talk. **Ctrl+Shift+D** opens the full dashboard. |
| Typed | `python -m jarvis.cli "<command>"`, or the UI command bar. |
| WhatsApp (owner) | Message your own number (the owner number in `config/whatsapp.toml`) with any command, such as "take a screenshot and send it to me". JARVIS runs it on the PC and replies in the chat. Nothing is spoken on the PC. |
| HTTP / WebSocket | `POST http://127.0.0.1:8765/...` and `ws://127.0.0.1:8765/ws` (used by the UI). `GET /voice/status` shows the voice pipeline state. |

**Confirmations.** JARVIS reads the action back and waits for **"yes"** / **"no"** (or `YES` / `NO` on WhatsApp)
before anything that:
- sends data outside the PC (messages, e-mail, uploads);
- deletes, uninstalls or powers off;
- was planned by the AI.

Tickets expire after 30 seconds.

**Control words.** These work at any time:
- "stop" / "cancel" stop the current task;
- "stop talking" / "be quiet" stop speech;
- "yes" / "no" answer a pending confirmation;
- "do that again" / "repeat that" re-runs the last command.

**Follow-ups work.** Examples:
- "find my resume" → "open the second one";
- "what's the weather in Chennai" → "and tomorrow?";
- "install VLC" → "open it".

---

## 3. Everyday command cheat sheet

| Area | Say |
|---|---|
| **Instant answers (offline, <1 ms)** | `what is 25 times 4`, `15% of 240`, `18% tip on 450`, `convert 100 km to miles`, `30 celsius in fahrenheit`, `5 kg in pounds`, `2 gb in mb`, `how many days until christmas`, `what day is it in 10 days`, `what time is it in tokyo`, `is 2028 a leap year`, `flip a coin`, `roll 2 dice`, `pick a random number between 1 and 50` |
| **PC** | `open chrome`, `close spotify`, `volume 40`, `turn it up`, `mute`, `brightness 70`, `take a screenshot`, `lock the pc`, `what's my battery`, `what's my ip address`, `am I online`, `system info`, `what's using my RAM`, `empty the recycle bin` |
| **Windows** | `snap window left`, `maximize this`, `minimize all`, `switch to chrome`, `restore window`, `show desktop` |
| **Files** | `find my resume`, `open the second one`, `organize my downloads`, `find duplicate files in downloads`, `rename these to report 1, 2, 3`, `move my downloads folder to desktop`, `open documents` |
| **To-do, timers, reminders** | `add buy milk to my to-do list`, `show my to-do list`, `mark buy milk as done`, `set a timer for 10 minutes`, `start the stopwatch` / `lap` / `stop the stopwatch`, `remind me to call mom at 6 pm`, `remind me to drink water in 20 minutes`, `show my reminders` |
| **Memory** | `remember that my car is parked on level 2`, `where did I park`, `what do you remember about my car`, `forget that my car is parked on level 2`, `what did I ask you earlier` |
| **Voice shortcuts** | `when I say goodnight, lock the pc and mute the volume`, then just say `goodnight`. Also `create a shortcut called study time that opens notion and plays lofi music`, `list my shortcuts`, `delete the goodnight shortcut` |
| **Notes & briefings** | `take a note: review PR 42`, `read my recent notes`, `good morning jarvis`, `start study focus for 45 minutes`, `launch my work workspace` |
| **Knowledge (RAG)** | `learn my documents folder`, `what do my documents say about the refund policy`, `search my notes for the wifi setup`, `what did rahul say about the trip` |
| **Ask anything** | `explain recursion`, `what's the weather in Chennai today`, `latest news about AI`, `write a birthday wish for my sister`, `tell me a joke` |
| **Browser (instant)** | `open a new tab`, `close this tab`, `reopen the closed tab`, `next tab`, `go to tab 3`, `go back`, `refresh the page`, `zoom in`, `reset zoom`, `bookmark this page`, `open incognito window`, `find on page`, `scroll down`, `go to the top of the page`, `show browser history` |
| **Windows (instant)** | `open task manager`, `show clipboard history`, `open the emoji panel`, `take a snip`, `open task view`, `new virtual desktop`, `switch to the next desktop`, `open windows settings`, `open the run box`, `project my screen` |
| **Web & browser** | `search amazon for headphones`, `go to wikipedia.org`, `play lofi music on youtube`, `use the browser to find the price of a Pixel 9 on Flipkart`, `continue` after signing in to a site |
| **Any desktop app (vision)** | `click the Save button`, `right click the desktop`, `what is this error on my screen`, `use my computer to turn on dark mode in Settings`, `in Excel make the first row bold` |
| **Software** | `install vlc`, `uninstall zoom`, `update all my apps`, `is python installed` |
| **Phone (Android)** | `lock my phone`, `turn up the volume on my phone`, `open spotify on my phone`, `take a screenshot of my phone`, `read my phone notifications`, `tap Allow on my phone`, `turn off bluetooth on my phone`, `call 98765 43210 on my phone`, `mirror my phone` |
| **Phone (instant)** | `set my phone brightness to 40`, `set phone volume to 8`, `open quick settings on my phone`, `open wifi settings on my phone`, `open the notification panel on my phone`, `what app is open on my phone`, `send sms to 98765 43210 saying I'm late` (you tap send) |
| **Phone ⇄ PC files** | `get the latest photo from my phone`, `copy my last 3 screenshots from my phone`, `copy report.pdf to my phone`, `send this file to my phone` (LocalSend) |
| **WhatsApp** | `tell mom I'll be late`, `ask rahul if he is free tonight`, `reply to rahul saying yes at 10`, `summarize my whatsapp`, `tell everyone who messaged me that I'm in a meeting` (personal chats only; groups are skipped), `reply to Yoga automatically for the next hour`, `stop WhatsApp auto reply` |
| **Google** | `check my emails`, `draft an email to priya about the report`, `what's on my calendar tomorrow`, `schedule a meeting with arun at 11 tomorrow` |
| **Developer** | `git status`, `run the project tests`, `what's causing this stack trace` |
| **Multi-step** | `find the latest invoice and send it to my phone`, `look up train timings to madurai and email them to dad`, or anything else in plain words. The planner or agent works it out and asks before any risky step. |

---

## 4. Complete feature and command reference

Every capability JARVIS can route to, generated from the live capability registry (`jarvis/core/capabilities/registry.py`).
The table covers 144 capabilities across 138 registered tools.

"Risk" drives the safety policy:
- **Read only** and **Reversible** run directly;
- **External effect** asks first;
- **Destructive** always asks.

Examples are phrasings the router is tested on. You can say them in your own words.

#### App (2)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 1 | Terminates or gracefully closes a running application by process name or title | `close_app` | Reversible | `Close Chrome` · `Quit Notepad` · `Close Spotify` |
| 2 | Resolves and launches an application, local software, or registered web app by name | `open_app` | Reversible | `Open Chrome` · `Launch VS Code` · `Start Calculator` |

#### System (28)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 3 | Tells you what you asked JARVIS recently | `command_history` | Read Only | `What did I ask you earlier?` · `Show my command history` |
| 4 | Sends push alert notifications to mobile phone via ntfy or Gotify | `notification_send` | Reversible | `Send notification to phone: task complete` · `Push alert to mobile` |
| 5 | Dispatches an encrypted push notification to user phone via ntfy or Gotify service | `notification_send` | Reversible | `Send a test notification to my phone` · `Alert my phone when task finishes` |
| 6 | Generates a strong random password and copies it to the clipboard | `generate_password` | Read Only | `Generate a strong password` · `Create a password of 20 characters` |
| 7 | Reports the laptop battery level, charging state and time left | `battery_status` | Read Only | `What's my battery?` · `Is my laptop charging?` |
| 8 | Reads clipboard, pastes text with clipboard preservation, or acts on selected text (explain, summarize, rewrite, copy) | `clipboard_intelligence` | Reversible | `Read clipboard text` · `Explain selected text` · `Summarize selected text` |
| 9 | Displays the interactive JARVIS desktop UI monitoring dashboard | `show_dashboard` | Reversible | `Open dashboard` · `Show dashboard` · `Display status dashboard` |
| 10 | Lists connected audio input microphones, output speakers/headphones, and monitors | `connected_devices` | Read Only | `Show connected devices` · `What audio devices are plugged in?` · `List screens and speakers` |
| 11 | Runs diagnostic audit across system health, Ollama status, event loop, and processes | `system_diagnostics` | Read Only | `Run system diagnostics` · `Check system health` · `Audit subsystems` |
| 12 | Retrieves CPU, RAM, OS version, disk usage, and host specifications | `system_info` | Read Only | `Show system specs` · `How much RAM is free?` · `What CPU do I have?` |
| 13 | Checks default audio input microphone availability, recording status, and sound levels | `microphone_status` | Read Only | `Is my microphone working?` · `Check microphone status` · `Mic test` |
| 14 | Shows the PC's IP address, Wi-Fi network and whether the internet works | `network_info` | Read Only | `What's my IP address?` · `Am I connected to the internet?` · `Check my wifi` |
| 15 | Empties the Windows Recycle Bin (asks for confirmation) | `empty_recycle_bin` | Destructive | `Empty the recycle bin` |
| 16 | Checks speech-to-text (STT) Faster-Whisper model loading and latency status | `speech_recognition_status` | Read Only | `Check speech recognition status` · `Is whisper loaded?` · `STT health` |
| 17 | Retrieves the current local date, time, and timezone | `get_time` | Read Only | `What time is it?` · `Tell me the current time` · `What's today's date?` |
| 18 | Changes the active Piper TTS synthesis voice between male and female models | `set_voice` | Reversible | `Switch to female voice` · `Change voice to male` · `Set voice female` |
| 19 | Checks status and sensitivity of the openWakeWord local engine | `wake_word_status` | Read Only | `Check wake word status` · `Is wake word detection enabled?` · `Wake word health` |
| 20 | Gets the current display screen brightness percentage | `brightness_get` | Read Only | `What is the screen brightness?` · `Check brightness level` · `Current brightness` |
| 21 | Sets the display screen brightness to a specific percentage (0 to 100) | `brightness_set` | Reversible | `Turn the brightness down to 30 percent` · `Set brightness to 50` · `Make screen brighter` |
| 22 | Controls system power state: Lock PC, Sleep PC, or confirmed Restart/Shutdown | `system_power_control` | Destructive | `Lock the PC` · `Sleep PC` · `Restart PC` |
| 23 | Captures a full screenshot of the primary monitor and saves it to a verified PNG file | `take_screenshot` | Reversible | `Take a screenshot` · `Capture my screen` · `Take snapshot` |
| 24 | Opens Windows Settings pages: sound, display, network, Wi-Fi, apps, Task Manager, system info | `open_system_settings` | Read Only | `Open sound settings` · `Open display settings` · `Open network settings` |
| 25 | Lists the running applications and programs consuming the most RAM/memory | `top_memory_processes` | Read Only | `Which programs are using the most memory?` · `What apps are using the most RAM?` · `Show memory hogs` |
| 26 | Retrieves the current master audio output volume percentage and mute status | `volume_get` | Read Only | `What's the volume?` · `Check volume level` · `Tell me the volume` |
| 27 | Mutes system audio output for total silence | `volume_set` | Reversible | `Mute volume` · `Total silence please` · `Mute sound` |
| 28 | Sets the master audio output volume to a specific percentage (0 to 100) | `volume_set` | Reversible | `Volume 50` · `Set volume to 30` · `Volume 80 percent` |
| 29 | Unmutes system audio output restoring previous volume level | `volume_set` | Reversible | `Unmute volume` · `Sound back on` · `Turn sound back on` |
| 30 | Instant Windows actions: Task Manager, Settings, File Explorer, Run, clipboard history, emoji panel, screen snip, task view, virtual desktops, project display, notification centre, quick settings, Windows search | `pc_quick_action` | Reversible | `Open task manager` · `Show clipboard history` · `New virtual desktop` · `Take a snip` |

#### File (15)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 31 | Applies systematic pattern or regex renaming across multiple files in a directory with dry-run preview | `batch_rename` | Reversible | `Batch rename all images in Photos to vacation_001.jpg` · `Add prefix 2026_ to all files in Documents` |
| 32 | Creates a duplicate copy of a file at the specified destination path | `copy_file` | Reversible | `Copy notes.txt to C:/Backup` · `Duplicate budget.xlsx as budget_copy.xlsx` |
| 33 | Creates a new directory or folder at the specified path if it does not already exist | `create_folder` | Reversible | `Create a folder named Projects on Desktop` · `Make new folder C:/Data/Backup` · `Create directory test` |
| 34 | Safely moves a local file or folder to the Windows Recycle Bin using send2trash | `delete_file` | Reversible | `Delete test.tmp from Desktop` · `Remove outdated_draft.docx` · `Trash temporary folder` |
| 35 | Searches indexed local files using cascaded FTS5 full-text search and semantic scoring | `find_file` | Read Only | `Find my project report PDF` · `Search for budget.xlsx` · `Where is resume.docx?` |
| 36 | Identifies identical duplicate files across a directory tree based on exact size and SHA-256 content hashes | `find_duplicates` | Read Only | `Find duplicate files in Documents` · `Scan C:/Media for duplicate images` |
| 37 | Lists the files and subdirectories inside a specific local directory path | `list_directory` | Read Only | `List files in Downloads` · `What's inside C:/Projects?` · `List directory C:/Users/Documents` |
| 38 | Relocates a file or directory from source to destination path with TOCTOU checks | `move_file` | Reversible | `Move report.pdf to Desktop` · `Move downloaded file to C:/Archives` |
| 39 | Opens an existing local file using its registered Windows default application | `open_file` | Reversible | `Open my resume.pdf` · `Open C:/Projects/data.csv` · `Open the report we just found` |
| 40 | Automatically sorts loose files in the Downloads folder into subdirectories by file type | `organize_downloads` | Reversible | `Organize my Downloads folder` · `Clean up Downloads by sorting documents and images` |
| 41 | Reads size in bytes, modification timestamp, and MIME type of a local file path | `read_file_metadata` | Read Only | `Check size of video.mp4` · `When was report.pdf last modified?` · `Get metadata for data.csv` |
| 42 | Renames an existing file or directory with conflict checking and collision prevention | `rename_file` | Reversible | `Rename old.txt to new.txt` · `Rename document draft to final_report.pdf` |
| 43 | Opens Windows Known Folders (Downloads, Documents, Desktop, Pictures, Music, Videos) resolving exact paths dynamically | `open_known_folder` | Read Only | `Open Downloads folder` · `Open Documents` · `Open Desktop folder` |
| 44 | Extracts the audio track from a video file into an MP3 or WAV audio file using FFmpeg | `extract_audio` | Reversible | `Extract audio from video.mp4` · `Convert presentation.mp4 to audio.mp3` |
| 45 | Trims a section of a video or audio file given start timestamp and duration using FFmpeg | `trim_media_clip` | Reversible | `Trim the first 30 seconds of recording.mp4` · `Cut audio from 01:00 for 45 seconds` |

#### Desktop (16)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 46 | Clicks any button or element on the PC screen by describing it (accessibility first, then vision) | `screen_click` | Reversible | `Click the Save button` · `Click the blue download icon` |
| 47 | Operates any desktop app with mouse and keyboard by looking at the screen until a goal is done | `computer_task` | Reversible | `Use my computer to turn on dark mode in Settings` · `In Excel make the first row bold` |
| 48 | Dispatches standard keyboard shortcuts: Enter, Escape, Tab, Shift+Tab, Arrow keys, Ctrl+A/C/V/X/Z/Y/F/S | `keyboard_shortcut` | Reversible | `Press Enter` · `Press Escape` · `Press Tab` |
| 49 | Looks at the PC or phone screen with the local vision model and answers questions about it | `describe_screen` | Read Only | `What is this error on my screen?` · `Look at my phone screen and tell me what it says` |
| 50 | Arranges two applications side-by-side or lays out multiple open windows in a grid | `arrange_windows` | Reversible | `Arrange windows side by side` · `Arrange Chrome and VS Code side by side` · `Tile windows` |
| 51 | Closes the currently active foreground window via Win32 API in under 200 microseconds | `close_window` | Reversible | `Close window` · `Close this window` · `Close the current window` |
| 52 | Clicks an interactive button, menu item, or tab inside an active desktop window via UI Automation | `desktop_ui_click` | Reversible | `Click Save button` · `Click File menu` · `Click Submit in application` |
| 53 | Captures accessibility hierarchy and interactive elements of the active desktop window via UI Automation | `desktop_ui_snapshot` | Read Only | `Inspect active window controls` · `What buttons are on screen?` · `Snapshot desktop UI` |
| 54 | Inspects active window for modal/confirmation dialogs, checks if app is not responding, or responds to dialogs | `dialog_interaction` | Reversible | `Check if app is responding` · `Confirm dialog` · `Dismiss dialog` |
| 55 | Maximizes the currently active foreground window to fill the monitor display | `maximize_window` | Reversible | `Maximize window` · `Maximize this` · `Full screen this window` |
| 56 | Minimizes the currently active foreground window to the taskbar | `minimize_window` | Reversible | `Minimize window` · `Minimize this window` · `Minimize active window` |
| 57 | Moves, resizes, or restores the currently active window | `move_resize_window` | Reversible | `Restore window` · `Resize window to 800 by 600` · `Move window` |
| 58 | Minimizes all open windows and toggles display to the Windows desktop (Win+D) | `show_desktop` | Reversible | `Show desktop` · `Minimize all windows` · `Go to desktop` |
| 59 | Snaps the active window to screen boundaries (left, right, top, bottom, or corners) | `snap_window` | Reversible | `Snap window left` · `Snap window right` · `Snap this to the left` |
| 60 | Switches to the previous application (Alt+Tab) or brings a named window to the foreground | `switch_window` | Reversible | `Switch to previous window` · `Switch window` · `Switch to Chrome` |
| 61 | Transcribes spoken dictation, normalizes grammar, and inserts text into the active application | `dictate_text` | Reversible | `Dictate text into Notepad` · `Start dictation mode` · `Type: Meeting confirmed for Monday` |

#### Media (1)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 62 | Dispatches multimedia hardware keys: play, pause, next track, previous track, or mute | `media_control` | Reversible | `Pause playback` · `Resume music` · `Next track` |

#### Browser (9)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 63 | Clicks an interactive DOM element, link, or button on the active web page | `browser_click` | Reversible | `Click the login button` · `Click the first search result` · `Click Download link` |
| 64 | Navigates the currently active browser tab to a new URL | `browser_navigate` | Reversible | `Navigate to https://wikipedia.org` · `Go to docs.python.org in active tab` |
| 65 | Opens a web URL in the managed Playwright browser session | `browser_open_url` | Reversible | `Open example.com` · `Go to https://github.com` · `Open reddit.com in browser` |
| 66 | Opens YouTube and searches for or plays a specified video, artist, or song query | `play_youtube` | Reversible | `Play lo-fi music on YouTube` · `Open YouTube and search for quantum computing` · `Watch Python tutorial on YouTube` |
| 67 | Extracts the accessibility tree and interactive elements of the active browser page | `browser_snapshot` | Read Only | `Snapshot active web page` · `What links are on this page?` · `Read browser content` |
| 68 | Enters text into an input field or search box on the active web page | `browser_type` | Reversible | `Type 'artificial intelligence' in search box` · `Fill email input with test@example.com` |
| 69 | Opens a website or a site's search results page in the default browser | `open_website` | Reversible | `Go to wikipedia.org` · `Search Amazon for wireless earbuds` · `Open github.com` |
| 70 | Uses the browser with AI to complete a multi-step web goal and report the result | `web_task` | Reversible | `Use the browser to find the price of a Pixel 9 on Flipkart` · `Check the website for today's opening hours` |
| 71 | Instant browser controls in the browser you are using: new/close/reopen tab, next/previous tab, go to tab N, back, forward, reload, zoom, bookmark, history, downloads, incognito, find on page, scroll | `browser_quick_action` | Reversible | `Open a new tab` · `Reopen the closed tab` · `Go to tab 3` · `Bookmark this page` · `Scroll down` |

#### Web (3)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 72 | Fetches recent unread articles and news headlines from configured RSS/Atom feeds | `rss_latest` | Read Only | `Fetch latest RSS headlines` · `What's new on my RSS feeds?` |
| 73 | Searches for verified real-time Indian and global news headlines | `search_news` | Read Only | `Search for latest news in India` · `What are today's top tech headlines?` |
| 74 | Performs a real-time web search for recent news, technical documentation, or factual queries | `search_web` | Read Only | `Search the web for artificial intelligence news` · `Look up latest Python 3.12 release notes online` |

#### Knowledge (2)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 75 | Queries the local Ollama LLM for general knowledge, coding assistance, or reasoning | `ollama_chat` | Read Only | `Explain how quantum entanglement works` · `Why is the sky blue?` · `Write a quick Python sort function` |
| 76 | Instantly answers calculations, percentages, unit and temperature conversions, date maths, world time, coin flips and dice | `quick_answer` | Read Only | `What is 25 times 4` · `Convert 100 km to miles` · `How many days until Christmas` |

#### Rag (9)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 77 | Forgets a remembered personal fact | `forget_fact` | Reversible | `Forget that my car is on level 2` |
| 78 | Recalls personal facts you asked JARVIS to remember | `recall_facts` | Read Only | `What do you remember about my car?` · `Where did I park?` |
| 79 | Remembers a personal fact (stored locally and added to the knowledge base) | `remember_fact` | Reversible | `Remember that my car is parked on level 2` · `Note that the wifi guest network is Home5G` |
| 80 | Answers questions based on local document contents with verifiable section citations | `document_qa` | Read Only | `What are the revenue figures in the financial report?` · `Summarize Section 3 of project_plan.pdf` |
| 81 | Adds a folder or document to JARVIS's knowledge base so questions can be answered from it | `knowledge_ingest` | Read Only | `Learn my Documents folder` · `Add D:\Notes to your knowledge base` |
| 82 | Answers a question from the knowledge base (indexed documents and notes) with citations | `knowledge_search` | Read Only | `What do my documents say about the refund policy?` · `Search my knowledge base for the project deadline` |
| 83 | Extracts structured summary, key decisions, and action items from a meeting transcript | `generate_meeting_notes` | Reversible | `Generate meeting notes from transcript.txt` · `Extract action items from the meeting log` |
| 84 | Retrieves the most recent human-readable memos and reminders from Memos inbox | `memos_recent` | Read Only | `Show recent memos` · `What's in my Memos inbox?` · `List my latest memos` |
| 85 | Searches previously captured local markdown notes using full-text keywords | `search_notes` | Read Only | `Search notes for grocery list` · `Find my notes about project architecture` · `Look up note meeting` |

#### Reminder (6)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 86 | Manages a local to-do list: add, list, mark done, remove tasks | `todo` | Reversible | `Add buy milk to my to-do list` · `Show my to-do list` · `Mark buy milk as done` |
| 87 | Quickly saves a short thought, snippet, or reminder into the local markdown notes system | `capture_note` | Reversible | `Note down that meeting is at 4 PM` · `Capture note: buy groceries tomorrow` · `Write down api key idea` |
| 88 | Posts a note or reminder into the local Memos inbox instance | `memos_create` | Reversible | `Add a memo about server restart` · `Save to Memos: test deployment` |
| 89 | Lists pending reminders | `list_reminders` | Read Only | `What are my reminders?` · `Show my reminders` |
| 90 | Sets a spoken reminder for a time, e.g. in 10 minutes or at 6 pm | `set_reminder` | Reversible | `Remind me to drink water in 20 minutes` · `Set a reminder to call mom at 6 pm` |
| 91 | Starts, laps, stops or resets a stopwatch | `stopwatch` | Reversible | `Start the stopwatch` · `Stop the stopwatch` |

#### Workflow (11)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 92 | Creates a voice shortcut (macro): saying one trigger word runs several saved commands | `create_shortcut` | Reversible | `When I say goodnight, lock the PC and mute the volume` · `Create a shortcut called study time that opens Notion and plays lofi music` |
| 93 | Deletes a voice shortcut | `delete_shortcut` | Reversible | `Delete the goodnight shortcut` |
| 94 | Lists your voice shortcuts | `list_shortcuts` | Read Only | `List my shortcuts` |
| 95 | Compiles and speaks an integrated morning briefing covering system health, RSS, weather, and tasks | `morning_briefing` | Read Only | `Give me my morning briefing` · `What's my briefing for today?` · `Good morning, brief me` |
| 96 | Generates an actionable daily briefing focused on active projects, tasks, and recent notes | `personal_briefing` | Read Only | `What are my priorities today?` · `Give me my personal briefing` · `Summarize active tasks` |
| 97 | Generates a contextual natural audio greeting upon user wake or presence | `wake_greeting` | Reversible | `Good morning Jarvis` · `Wake up Jarvis` · `Greet me` |
| 98 | Explicitly activates or stops continuous voice typing dictation mode into any editable field | `dictation_mode_control` | Reversible | `Start typing dictation mode` · `Start typing` · `Stop typing mode` |
| 99 | Restores and opens apps, folders, and browser tabs saved in a workspace manifest | `launch_workspace` | Reversible | `Launch workspace 'CodingSession'` · `Restore PythonProject workspace` |
| 100 | Saves a workspace manifest of open applications, directories, and browser tabs for later resumption | `save_workspace` | Reversible | `Save my workspace as 'CodingSession'` · `Save workspace PythonProject` |
| 101 | Starts a distraction-free focus or study session with a countdown timer | `start_study_focus` | Reversible | `Start study focus for 25 minutes` · `Begin focus mode` · `Focus session 45 mins` |
| 102 | Performs voice-driven editing on active text: backspace, delete word, delete sentence, undo, redo, select, replace X with Y, capitalize, lowercase, copy, cut, paste | `voice_edit` | Reversible | `Delete last word` · `Voice backspace` · `Delete last sentence` |

#### Package (7)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 103 | Queries the AppCatalog to verify whether a specific application is installed on this PC | `check_app_installed` | Read Only | `Is VLC installed?` · `Do I have Chrome?` · `Check if Spotify is installed` |
| 104 | Retrieves the verified executable path and installation folder of an installed software | `get_app_location` | Read Only | `Where is VLC installed?` · `Find executable for Chrome` · `Where is VS Code located?` |
| 105 | Installs a verified software package via trusted package manager (winget), verifies install, and updates AppCatalog | `install_software` | Reversible | `Install VLC` · `Install VS Code` · `Install Google Chrome` |
| 106 | Lists all verified installed applications and Start Menu software tracked in the AppCatalog | `list_installed_applications` | Read Only | `Show installed applications` · `List all my software` · `What apps are installed?` |
| 107 | Triggers a fresh scan across Windows registry, Start Menu, UWP, and PATH without modifying system PATH | `refresh_applications` | Read Only | `Refresh applications` · `Rescan installed programs` · `Update application catalog` |
| 108 | Uninstalls an installed application after confirmation (winget) | `uninstall_software` | Destructive | `Uninstall VLC` · `Remove the Zoom app from my laptop` |
| 109 | Updates one application or all applications that have updates (winget upgrade) | `update_software` | Reversible | `Update all my apps` · `Update the Chrome app` |

#### Development (5)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 110 | Executes a validated, policy-checked PowerShell command or script with administrative elevation if permitted | `powershell_command` | Reversible | `Run powershell Get-Process` · `Execute powershell script to check disk` · `cmd dir` |
| 111 | Analyzes stack traces, redaction of sensitive credentials, and produces actionable fixes | `diagnose_error` | Read Only | `Diagnose this error traceback` · `Debug error from log file` |
| 112 | Checks Git branch, staged/unstaged changes, and untracked files in an approved project directory | `git_status` | Read Only | `Check git status` · `What files are modified in git?` · `Show git diff status` |
| 113 | Automates Antigravity / VS Code IDE actions: live dictate/type prompts, open files, switch tabs, save files, open terminal/problems panels, explain visible errors, and submit prompts | `antigravity_ide_control` | Reversible | `Open Antigravity` · `Focus coding prompt` · `Open problems panel` |
| 114 | Executes automated unit tests (pytest) for an approved developer repository and returns metrics | `run_project_tests` | Reversible | `Run project tests` · `Execute unit tests for current repository` · `Run pytest` |

#### Phone (15)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 115 | Presses the Back navigation button on the connected Android phone via ADB | `android_back` | Reversible | `Press back on my phone` · `Go back on Android` |
| 116 | Opens the phone dialer with a number or contact ready to call | `android_dial` | Reversible | `Call 9876543210 on my phone` · `Dial mom on my phone` |
| 117 | Presses the Home navigation button on the connected Android phone via ADB | `android_home` | Reversible | `Press home on my phone` · `Go to phone home screen` |
| 118 | Types text, taps or swipes on the connected phone | `android_input` | Reversible | `Type hello on my phone` · `Swipe up on my phone` |
| 119 | Presses phone keys: volume, lock or wake the screen, play or pause media, home, back | `android_key` | Reversible | `Turn up the volume on my phone` · `Lock my phone` · `Pause the music on my phone` |
| 120 | Closes the active Android phone screen mirror or scrcpy window | `android_close_control` | Reversible | `Close phone screen` · `Stop phone mirroring` · `Exit scrcpy` |
| 121 | Mirrors Android phone screen directly onto PC desktop with interactive control via scrcpy | `android_open_control` | Reversible | `Show my phone screen` · `Mirror my phone` · `Open phone control` |
| 122 | Reads the notifications showing on the phone | `android_notifications` | Read Only | `Read my phone notifications` · `Any notifications on my phone?` |
| 123 | Launches an application directly on the connected Android mobile phone | `android_open_app` | Reversible | `Open Spotify on my phone` · `Launch camera on mobile` · `Open WhatsApp on phone` |
| 124 | Opens a web page on the phone's browser | `android_open_url` | Reversible | `Open youtube.com on my phone` |
| 125 | Takes a screenshot of the phone screen and saves it on the PC | `android_screenshot` | Reversible | `Take a screenshot of my phone` |
| 126 | Checks Android phone connection status via ADB, scrcpy availability, and battery status | `android_status` | Read Only | `Is my phone connected?` · `Check phone status` · `Show phone battery level` |
| 127 | Taps a button or item by its label on the phone screen | `android_tap_text` | Reversible | `Tap Settings on my phone` · `Press Allow on my phone` |
| 128 | Turns phone Wi-Fi, Bluetooth, mobile data, airplane mode or do-not-disturb on or off | `android_toggle` | Reversible | `Turn off Bluetooth on my phone` · `Turn on Wi-Fi on my phone` |
| 129 | Fast phone controls: quick settings, notification shade, settings pages, brightness %, media volume, which app is open, screen on/off, SMS prepared for you to send | `android_quick_action` | Reversible | `Set my phone brightness to 40` · `Open wifi settings on my phone` · `What app is open on my phone` · `Send SMS to 98765 43210 saying I'm late` |

#### Transfer (4)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 130 | Copies photos, screenshots, videos, downloads, documents or a named file from the phone to the PC | `android_pull_file` | Reversible | `Get the latest photo from my phone` · `Copy my last 3 screenshots from my phone` |
| 131 | Copies a PC file to the phone's Download folder over USB (ADB) | `android_push_file` | Reversible | `Copy report.pdf to my phone` |
| 132 | Transfers files, photos, or documents to connected Android phone over Wi-Fi via LocalSend | `localsend_file` | Reversible | `Send this file to my phone` · `Transfer report to mobile via LocalSend` · `Send photo to phone` |
| 133 | Sends text snippets, clipboard content, or web URLs to Android phone via LocalSend | `localsend_text` | Reversible | `Send this link to my phone` · `Send text to phone via LocalSend` · `Share clipboard with mobile` |

#### Whatsapp (7)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 134 | Manages WhatsApp transport bridge connectivity: pair QR, connect, or disconnect | `whatsapp_action` | Reversible | `Re-pair WhatsApp` · `Show WhatsApp pairing QR code` · `Reconnect WhatsApp bridge` |
| 135 | Reads incoming unread or recent WhatsApp messages from the local Baileys bridge | `read_whatsapp_messages` | Read Only | `Read my unread WhatsApp messages` · `Check recent WhatsApp messages` |
| 136 | Drafts a reply to the latest WhatsApp message from someone and asks before sending | `reply_whatsapp_message` | Read Only | `Reply to Rahul saying I'll be there at 6` · `Reply to the last WhatsApp message` |
| 137 | Replies to everyone who messaged recently (personal chats only, groups skipped) with one message, personalised per person, after confirmation | `reply_whatsapp_all` | Read Only | `Tell everyone who messaged me that I'm in a meeting` · `Reply to all the people texting me that I'll call back in an hour` |
| 138 | Sends a WhatsApp message to a recipient contact or phone number. Requires confirmation ticket in production | `send_whatsapp_message` | External Effect | `Send a WhatsApp message to Mom saying I will be home soon` · `Message Rahul on WhatsApp` · `Say hi to yoga in whatsapp` |
| 139 | Summarizes pending WhatsApp messages requiring attention, highlighting urgent items | `summarize_whatsapp_messages` | Read Only | `Summarize my WhatsApp messages` · `What urgent WhatsApp messages need my attention?` |
| 140 | Turns WhatsApp auto-reply on for one contact, several, or all direct contacts for a limited time (never groups), turns it off, or reports its status. Replies follow the owner's own style with each person | `whatsapp_auto_reply` | Reversible | `Reply to Yoga automatically for the next hour` · `Handle Arun's messages until 6 PM` · `Stop WhatsApp auto reply` |

#### Google (4)

| # | Feature | Tool | Risk | Say, for example |
|---|---|---|---|---|
| 141 | Schedules a new meeting or event on Google Calendar | `calendar_create_event` | External Effect | `Schedule meeting with team tomorrow at 10am` · `Add calendar event Doctor Appointment on Friday` · `New calendar event Review at 3pm` |
| 142 | Lists upcoming events and appointments from Google Calendar | `calendar_list_events` | Read Only | `What meetings do I have today?` · `Show my upcoming calendar events` · `Check my schedule for tomorrow` |
| 143 | Composes and sends an email draft via connected Gmail account | `gmail_create_draft` | External Effect | `Send an email to boss@company.com` · `Draft email to client about project` · `Compose new email to Sarah` |
| 144 | Reads recent or unread emails from connected Gmail inbox | `gmail_list_recent` | Read Only | `Check my emails` · `Read recent emails from inbox` · `Show my unread emails` |

**Beyond the table:**
- **Control words**: stop, cancel, pause, resume, yes / no, stop talking.
- **Repeat**: "do that again" re-runs the last command.
- **Voice shortcuts**: each saved phrase expands into its steps, and every step is routed and policy-checked like a
  normal command.
- **Chat**: open questions go to grounded chat.
- **Agent**: anything unrecognised goes to the tool-using agent.

---

## 5. Architecture and workflow

```
voice (wake word / push-to-talk) ─┐
desktop UI (WebSocket) ───────────┤
CLI / HTTP ───────────────────────┼─► CommandService
WhatsApp (Baileys bridge) ────────┘        │  shortcut expansion · "do that again" · owner check
                                           ▼
                                   SmartRouter (deterministic, ~1 ms)
     control → normalise → unsupported guard → direct system actions → negation → context/pronouns
     → extended domains (instant answers, utilities, phone, WhatsApp, knowledge, web, reminders, questions)
     → hot cache → compound split → grammar/regex → fuzzy → complexity gate → BM25 capability retrieval
                                           │
         ┌────────────── matched ──────────┼────────── not matched ──────────────┐
         ▼                                 ▼                                      ▼
   Lane 0: tool call           Lane 1: fast LLM classifier              Lane 2: planner / chat / agent
                               (schema-constrained to real tools)       (DAG planner, grounded chat, ReAct agent)
         │                                 │                                      │
         └──────────────┬──────────────────┴──────────────────────────────────────┘
                        ▼                       JDE (read_only): logs + sends plain questions to chat
             ExecutionEngine: PolicyEvaluator → confirmation ticket → ActionLedger → tool → Verifier
                        ▼
             Response: PULSE feedback → streaming TTS (Piper) / UI / WhatsApp reply
```

### Request workflow step by step

1. **Input.** Voice goes through the wake word (openWakeWord), VAD (Silero), adaptive endpointing and Whisper (STT).
   Speech recognition is local, free and unlimited. `stt_model = "auto"` picks Whisper large-v3-turbo on an NVIDIA
   GPU (near large-v3 accuracy) and small.en on the CPU. The final pass filters rumble, cuts non-speech with Whisper's
   own voice detection, drops pieces Whisper isn't confident about, and rejects noise hallucinations (repeated phrases,
   "Also, we...", "Thanks for watching", more words than the audio could hold, or under 0.22 s of real speech).
   Text arrives from the UI, CLI, HTTP or WhatsApp.
2. **CommandService.**
   - Creates the task.
   - Expands voice shortcuts and "do that again".
   - Tags the channel.
   - Enforces owner-only control for WhatsApp.
3. **SmartRouter**, cheapest and safest first:
   - **Lane 0**, deterministic, about 1 ms median: control words, normalisation, guards, direct system actions,
     extended domains, cache, grammar/regex, fuzzy matching, and BM25 retrieval over the capability registry.
   - **Lane 1**: the fast local LLM classifies only what Lane 0 could not. It chooses from an enum of the retrieved
     real tools, and its arguments are validated against each tool's pydantic schema.
   - **Lane 2**: questions go to grounded chat (RAG + conversation + live web). Multi-step goals go to the DAG
     planner. Anything else goes to the ReAct tool agent.
4. **Decision engine (JDE)** runs in read_only mode: it records its decision next to the router's, and an unmatched plain
   question goes straight to chat instead of the slower agent. It never picks a consequential tool
   ([section 6](#6-the-decision-engine-jde)).
5. **ExecutionEngine**, the only way any tool runs, including planner and agent calls:
   - the policy decides by risk class;
   - a confirmation ticket is issued when needed;
   - the ActionLedger records PREPARED → COMMITTED;
   - the tool runs with a timeout;
   - the Verifier checks the real effect (process started, volume read back, file exists, message acknowledged).
6. **Response.**
   - PULSE gives instant feedback.
   - Answers stream sentence by sentence into Piper TTS, so speech starts after the first sentence.
   - The UI shows the answer as it types.
   - WhatsApp replies go back to the chat.
7. **Memory.**
   - Working memory records results, resources and topics, so follow-ups work.
   - The conversation transcript is kept per channel.
   - Everything is persisted to SQLite.

### Main packages

| Package | Responsibility |
|---|---|
| `jarvis/core/commands` | CommandService: the request lifecycle, confirmations, shortcuts, repeat, dispatch |
| `jarvis/core/router` | SmartRouter, guards, extended domains, Lane-1 classifier, caches |
| `jarvis/core/capabilities` | Capability registry (descriptions, examples, risk) and BM25 retrieval |
| `jarvis/decision` | JDE: local decision engine, training, evaluation, shadow runtime |
| `jarvis/core/executor`, `jarvis/security` | Policy, confirmation tickets, ledger, audit, paths guard |
| `jarvis/core/planner`, `jarvis/core/scheduler`, `jarvis/core/agent` | DAG planner, scheduler, ReAct tool agent |
| `jarvis/core/llm` | The single Ollama client, model roles, assistant (grounded chat), streaming, tool catalog |
| `jarvis/core/knowledge`, `jarvis/memory` | Knowledge base (RAG), file search index, working memory |
| `jarvis/core/audio`, `stt`, `tts`, `pulse`, `response` | Voice input, speech recognition, speech synthesis, feedback |
| `jarvis/core/computer`, `desktop`, `vision` | Browser (Playwright), Windows UI Automation, screen vision |
| `jarvis/tools` | All tools: system, files, apps, windows, phone, WhatsApp, web, everyday utilities, productivity |
| `jarvis/connectors`, `jarvis/integrations` | Android/ADB/scrcpy, LocalSend, notifications, RSS, Node-RED, Google, WhatsApp |
| `jarvis/ui` | PySide6/QML desktop UI with the 3D reactor |
| `jarvis/db/migrations` | SQLite schema (applied automatically at start-up) |

---

### Accuracy features

- **Typo-tolerant commands.** Misspelt command words and app names are repaired before routing ("launsh chrom",
  "mut volum", "wher is chrom installed"). Only the command part is repaired, never message text or real words.
- **Exclusions and corrections.** "Open Calculator but not Notepad" opens only Calculator. "Open the second file - sorry,
  the third" uses the correction. "Open the second one" with nothing listed yet asks which list you mean.
- **Precise RAG.** Retrieved passages are reranked against your question (term coverage, phrase and heading matches,
  vector similarity). Unrelated or near-duplicate passages are dropped, so chat only sees evidence that answers the
  question (`python -m tests.rag.benchmark`: 100% recall@3, 100% precision, 92% abstention on unanswerable questions).
- **No invented personal facts.** "What is my blood group?" is answered only from your documents or what you asked
  JARVIS to remember; if nothing mentions it, JARVIS says so instead of guessing. Grounded answers use a low temperature.
- **Personalisation.** Facts you save ("remember that my car is on level 2") are added to chat answers when relevant.

## 6. The decision engine (JDE)

JDE is a local, offline, CPU-only "System-One" decision layer. It sits between the deterministic router and the
LLMs.

In one pass over one text encoding (hashing n-grams, plus GloVe word vectors when installed), it answers typed
questions:
- **Choice**: route family (20 families) and model class (none / tiny / small / planner / vision).
- **Score**: complexity, 0 to 3.
- **Probability**: needs an LLM, the planner, context or the web; external effect; destructive; ambiguous;
  supported; is an action.

Each answer is calibrated:
- temperature scaling for the route;
- Platt scaling for the binary heads;
- risk-class gates. Each gate is the lowest confidence at which precision on validation data reaches the risk
  target (95% for read-only, 97% reversible, 99% external, 99.5% destructive), judged by a 95% Wilson lower bound
  rather than the raw estimate.

The gate returns one of EXECUTE, FALLBACK, CLARIFY, ABSTAIN or UNSUPPORTED.

**Rules JDE never breaks:**
- JDE never executes anything and never authorizes anything. Its confidence is never used as authorization.
- It picks a family, never a tool, so it cannot invent a tool.
- The existing router stays first and remains the fallback.
- The policy stays the final authority.
- It never trains on webpages, WhatsApp messages, documents or other external text, and never on its own logs
  automatically.
- `JDE_LOCAL_ONLY=true` (the default) refuses any hosted decision engine.

**Rollout stages** (`[decision] stage` in `jarvis/config/jarvis.toml`, or the `JARVIS_JDE_STAGE` environment
variable):

| Stage | Effect |
|---|---|
| `off` | Not loaded. |
| `shadow` | The router acts; JDE decides on a background thread and the pair is stored in the SQLite table `jde_decisions`. The model is loaded at start-up, off the event loop. |
| `read_only` (default) | Stage B: an unmatched plain question that JDE calibrates as KNOWLEDGE goes to read-only chat instead of the agent. |
| C / D | Not implemented. They need zero wrong consequential executions on every evaluation split first. |

**Latest measurements** (500 hand-labelled cases never used for training: 350 dev / 100 holdout / 50 adversarial;
no LLM involved):

| Metric | Dev (350) | Holdout (100) | Adversarial (50) | Target |
|---|---|---|---|---|
| Route family accuracy | 87.1% | 89.0% | 86.0% | ≥ 98% |
| Route top-3 recall | 97.7% | 98.0% | 96.0% |  |
| Actionability accuracy | 94.3% | 95.0% | 88.0% | ≥ 99% |
| Needs-LLM accuracy | 92.0% | 90.0% | 90.0% | ≥ 98% |
| Unknown / clarify detection | 100.0% | 100.0% | 100.0% | ≥ 98% |
| Route calibration ECE | 0.047 | 0.068 | 0.122 |  |
| Auto-execute rate | 51.1% | 55.0% | 56.0% |  |
| Precision of auto-executed routes | 97.2% | 98.2% | 92.9% |  |
| **Wrong consequential executions** | **0** | **0** | **0** | 0 |
| Current router accuracy → router + JDE | 59.1% → 69.1% | 48.0% → 59.0% | 62.0% → 68.0% |  |

Model `jde-20260925-231642-d13eb5` (hash encoder, catalog `cat-f2b89475f2`). Latency over 10,000 requests: cache miss p50 1.07 ms, p95 1.55 ms, p99 2.01 ms; cache hit 0.023 ms; 884 decisions/s; about 107 MB RAM; cold load 186 ms. JDE is not yet at the 98% route target, so it runs in `read_only` mode (it may only send plain questions to chat), with zero wrong consequential executions on every split.

Train and evaluate:

```powershell
python -m jarvis.decision.train --encoder hash            # or glove+hash, minilm+hash, bge-small+hash
python -m jarvis.decision.evaluation.evaluate --latency 10000   # writes reports/JDE_BENCHMARK.md (+ .json)
python scripts\bench_jde_backbones.py                     # compare encoders (MiniLM/BGE need fastembed + huggingface.co)
python -m jarvis.decision.train --encoder glove+hash --promote   # make it CURRENT (after checking the report)
```

The route families and their tools:

| Family | Risk class | What it covers |
|---|---|---|
| APP | Reversible | open / close apps |
| SYSTEM | Destructive (power) | volume, brightness, time, screenshot, power, battery, network, diagnostics, password, recycle bin |
| FILE | Reversible | find / open / copy / move / rename / delete (to recycle bin), organise, duplicates, media clips |
| RAG | Reversible | knowledge base, document Q&A, notes search, personal memory |
| KNOWLEDGE | Read only | chat, explanations, writing, instant answers |
| WEB | Read only | web search, news, RSS |
| BROWSER | Reversible | websites, YouTube, browser agent |
| DESKTOP | Reversible | windows, UI automation, screen click, computer-use agent, screen description |
| MEDIA | Reversible | play / pause / next / previous |
| PHONE | Reversible | Android control over ADB / scrcpy |
| TRANSFER | Reversible | phone ⇄ PC files, LocalSend |
| WHATSAPP | External effect | read, summarise, send, reply, bulk reply |
| GOOGLE | External effect | Gmail, Calendar |
| REMINDER | Reversible | reminders, timers, stopwatch, to-do list, notes |
| PACKAGE | Destructive | install / uninstall / update software |
| DEVELOPMENT | Reversible | git status, tests, error diagnosis, IDE, PowerShell |
| WORKFLOW | Reversible | briefings, workspaces, focus mode, voice shortcuts |
| PLANNER / CLARIFY / UNKNOWN | — | multi-step goals / ask the user / unsupported |

---

## 7. AI models, knowledge (RAG), memory and the database

### One model client, several roles

`jarvis/core/llm/client.py` (`OllamaClient`) is the only code that talks to Ollama. Features use it through roles
set in `[models]`:

| Role | Used by | Default |
|---|---|---|
| `fast` | Lane-1 intent classifier | `qwen3:1.7b` |
| `planner` | DAG planner, tool agent, web agent | `llama3.2:latest` |
| `chat` | answers, document Q&A, WhatsApp composing / replies / summaries | `llama3.2:latest` |
| `vision` | screen description, visual clicking, computer-use agent | `qwen2.5vl:3b` |
| `embed` | knowledge-base embeddings (optional) | `nomic-embed-text` |

How the client behaves:
- **Model fallback.** A role whose model isn't pulled falls back to the best installed model.
- **Server start and warm-up.** Ollama is started automatically if it isn't running. The fast and chat models are
  warmed at start-up and kept resident (`keep_alive = "30m"`).
- **Circuit breaker.** "Ollama is down" becomes an immediate fallback instead of a timeout.
- **Thinking models.** Their `<think>` output is stripped.
- **Structured output.** Structured calls use JSON-schema output restricted to real tool names.

### Knowledge base (RAG): `jarvis/db/knowledge.db`

- **Indexing.** "learn my documents folder" indexes text, markdown, code, PDF and DOCX into section-aware chunks.
  Embeddings are added in the background when an embedding model is installed.
- **Search.** BM25 over SQLite FTS5 is fused with embedding cosine similarity through Reciprocal Rank Fusion.
  Privacy scopes are applied **before** ranking, so one WhatsApp contact's chat never leaks into another's.
- **Answers.** `knowledge_search` and `document_qa` answer only from retrieved passages, with citations, and abstain
  when the passages don't contain the answer.
- **Chat grounding.** Grounded chat uses the knowledge base, the conversation so far and live web results for
  time-sensitive questions. Retrieved text is always treated as untrusted data.
- **WhatsApp chats** are indexed too (`scope:whatsapp_history`), so "what did Rahul say about the trip" works. Only
  your own assistant can search them. Turn this off with `remember_chats = false`.
- **Personal memory.** "Remember that…" facts are stored in SQLite (`memory_facts`) and also indexed into the
  knowledge base as the *Personal Memory* collection, so grounded answers can use them. Passwords, PINs and keys are
  refused.

### Working memory and context

`WorkingMemory` keeps the recent search results, the active resource (file, app, contact, URL), the topic, the last
failure and any pending confirmation. That is what makes "open the second one", "send it to my phone", "install it"
and "and tomorrow?" work.

Layered long-term memory (preferences, aliases, verified outcomes) has an inspect/forget CLI:
`python -m jarvis.memory list|inspect|forget|conflicts`.

### The database: `jarvis/db/jarvis.db` (SQLite, WAL)

Migrations in `jarvis/db/migrations` are applied automatically:

| Migration | Tables |
|---|---|
| 001 | `requests`, `task_events`, `tool_runs`, `metrics`, `kv_settings` |
| 002 | `route_cache`, `route_decisions` |
| 003 | file search index (FTS5) |
| 004 | `task_graphs`, `graph_nodes`, `graph_edges`, `planner_runs`, `plan_cache`, `capability_gaps` |
| 005 | security: `action_ledger`, audit log |
| 006 | layered memory, episodes, workflows, RAG collections |
| 007 | `todos`, `memory_facts`, `shortcuts`, `jde_decisions` |

Writes go through one background writer thread (`PersistenceWriter`), which batches inserts in 5 ms windows and never
blocks a command.

---

## 8. Integrations

### WhatsApp

A Node.js **Baileys** bridge (`integrations/whatsapp/bridge`, `ws://127.0.0.1:8768`) is transport only. All
intelligence stays in Python.

- **Sending.** "ask Rahul if he is free tonight" becomes *"Are you free tonight?"*. The confirmation shows the exact
  text and the resolved contact. Names resolve through `[whatsapp.contacts]` or an imported `contacts.vcf`.
- **Replies.** "reply to Rahul saying…" drafts a reply from the recent chat, then asks before sending.
- **Bulk reply.** "tell everyone who messaged me that…" writes one personal message per waiting contact and lists
  them all in a single confirmation. Personal chats only; groups are skipped.
- **Incoming messages** are announced on the PC. An AI draft is prepared: `mode = "DRAFT_ONLY"` keeps it as a draft,
  `ALLOWLIST_AUTO_REPLY` sends it to allow-listed contacts. Incoming text is untrusted data and can never trigger PC
  actions.
- **Group chats stay silent unless you name them.** Group messages are stored but never announced, drafted, read
  out, summarised or answered. Say the group to use it: "summarize the CSE group", "read my group messages",
  "reply in the CSE group saying I'll be there", "send a message to the family group saying happy diwali" (always
  confirmed first). "Summarize my WhatsApp" covers personal chats only, one line per person.
- **Owner remote control.** Messages from the owner numbers run as commands, and replies go back to WhatsApp.
- **Personal replies in your style.** Import a chat (or learn from history) on **Dashboard → WhatsApp → Contacts**.
  JARVIS learns how *you* write to each person (Tanglish or English, length, emojis, tone) from your own messages
  only, with a separate profile and example index per contact.
  - **Modes:** Off, Suggest, Ask before send, or automatic replies for a window you grant ("reply to Yoga
    automatically for the next hour", "for the next two hours, respond to everyone"). "Stop WhatsApp auto reply" ends
    everything at once.
  - **Never:** groups, "Waiting for this message" placeholders, a resend of an uncertain send, or PC actions.
  - **Held for you:** sensitive, unclear or low-confidence messages. Full guide:
    [docs/WHATSAPP_PERSONAL_REPLY_AGENT.md](docs/WHATSAPP_PERSONAL_REPLY_AGENT.md).
- **Diagnostics:** `python -m jarvis.integrations.whatsapp.doctor`.

### Android phone

The phone is controlled over ADB using USB debugging or ADB over Wi-Fi.

- **Controls:** keys (volume, lock/wake, media, home/back), typing, tapping and swiping, opening apps by spoken name,
  URLs, the dialer (you tap call), screenshots, notifications, tapping elements by label, toggles (Wi-Fi, Bluetooth,
  mobile data, airplane mode, do not disturb, rotation), status, and scrcpy screen mirroring.
- **No arbitrary shell.** All ADB calls are fixed templates.
- **Files:**
  - `android_pull_file`: newest photos, screenshots, videos, downloads, documents, recordings, WhatsApp media, or a
    file by name, copied to `Downloads/From Phone`;
  - `android_push_file`: a PC file to the phone's `Download` folder;
  - **LocalSend**: transfers over the local network.
- **Push notifications** to the phone through ntfy or Gotify. They are sent only after verification, with secrets
  redacted and duplicates removed.

### Google Workspace (Gmail, Calendar, Drive)

Uses the official APIs with the OAuth 2.0 desktop loopback flow. Put the client file at
`config/google_client_secret.json` (git-ignored), then run `connect_google.bat` or
`python -m jarvis.integrations.google.cli connect all`.

- Refresh tokens live in the Windows Credential Manager, never in files.
- Scopes are requested progressively.
- Sending e-mail and writing to the calendar always need confirmation.
- E-mail and Drive content is untrusted data.

Other commands: `accounts`, `status`, `disconnect`, `test`.

### Browser automation

Playwright runs on one dedicated event-loop thread.

- **`web_task`** is an AI web agent. It reads a numbered page snapshot and navigates, clicks, types, selects
  dropdowns, ticks boxes and scrolls, for 14 to 25 steps, with stuck detection.
- **Login pages** pause the task: sign in once in the JARVIS browser (the profile keeps the session), then say
  "continue".
- It **never** buys, pays, orders or deletes, and never types into password or OTP fields.
- Site searches ("search amazon for…") open directly in your default browser.

### Desktop apps and the screen

- `screen_click` clicks an element by description. It tries Windows UI Automation first (exact, instant), then the
  vision model locates the element in a DPI-aware screenshot.
- `computer_task` runs a see → act loop for goals like "in Settings turn on dark mode". It stops hard before send,
  pay, delete or uninstall clicks the goal didn't ask for. Slam the mouse into a screen corner to abort.
- `describe_screen` explains what is on the PC or phone screen using the local vision model.

### Morning briefing, focus, workspaces, routines, RSS, Node-RED

- **Morning briefing.** "Good morning Jarvis" gathers calendar, feeds, tasks, notes, PC status and downloads in
  parallel, with per-source timeouts, and speaks a summary.
- **Focus and workspaces.** Study/focus mode runs with a timer. Workspaces are saved and relaunched.
- **Learned workflows.** Workflows can be learned from repeated verified tasks. They are only proposed and need your
  approval; each run still gets fresh confirmation tickets.
- **Voice shortcuts** ([section 3](#3-everyday-command-cheat-sheet)) are the quick, explicit way to create routines.
- **RSS.** FreshRSS supplies news; feed text is untrusted data.
- **Node-RED** is only an event bridge, limited to allow-listed events and 10 per minute.

---

## 9. Safety and security model

- **Risk classes.** Every tool declares one: READ_ONLY, REVERSIBLE, EXTERNAL_EFFECT, DESTRUCTIVE or PRIVILEGED. The
  classification comes from trusted code, never from a model.
- **Policy** (`config/policy.toml`):
  - read-only and reversible actions are allowed;
  - external-effect actions need confirmation;
  - destructive and privileged actions always need confirmation.
- **More confirmations.** AI-originated calls to sensitive tools (PowerShell, installs, deletes, moves, renames,
  power, messages, file sends, emptying the recycle bin) also pause for you. A model-generated plan is read back once
  as a whole, and each step still gets its own ticket bound to its final arguments.
- **Confirmation tickets** are single-use, bound to the exact arguments, and expire after 30 s.
- **Action ledger.** Every action goes PREPARED → COMMITTED, with compare-and-swap claims. A write whose outcome is
  uncertain is reconciled, never blindly retried.
- **Protected paths.** Windows and Program Files are protected, and other users' profiles are denied.
- **Blocked outright:**
  - raw shell, arbitrary PowerShell and arbitrary ADB shell;
  - UAC automation;
  - typing passwords or OTPs, and solving captchas.
- **Untrusted content.** Web pages, e-mails, WhatsApp messages, documents, RSS items and OCR text are treated as data
  only. Instructions inside them are never executed.
- **Owner isolation.** Only the owner numbers can control the PC over WhatsApp. Everyone else gets conversation only.
- **Privacy.** Secrets are redacted before logs, notes and notifications. Memory refuses to store passwords. The
  password generator copies to the clipboard and never speaks or stores the password. OAuth tokens live in the OS
  credential store.
- **Unsupported requests.** Physical services (ride booking, food ordering, trading, medical services) are declined
  honestly. Organising or messaging *about* them ("remind me to call the doctor") works.

---

## 10. Performance

These figures were measured on this repository's CI-class 4-core machine. They are CPU only, with no GPU.

| Stage | Latency |
|---|---|
| Router, full deterministic cascade over the 500-case suite | **p50 1.0 ms, p95 3.9 ms**, down from 25 ms / 100 ms before the regex-cache fix |
| Instant answers (calculator, units, dates, world clock) | < 0.1 ms to compute, no LLM |
| JDE decision (cache miss / hit) | about 1.1 ms / 0.02 ms, about 850 decisions per second |
| Hot route cache | < 0.2 ms |
| Lane-1 LLM classification | model bound: 150 to 600 ms warm on a small model; cached per utterance for 15 minutes |
| Spoken answers | streamed; speech starts after the first sentence |

What makes it fast:
- **Regex compilation.** The router compiles a few thousand regular expressions. JARVIS raises Python's compiled
  pattern cache from 512 to 8192 (`jarvis/__init__.py`) and precompiles keyword patterns in retrieval. Without this,
  every request recompiled most patterns (about 90% of routing time).
- **Cheapest lane first.** The fast LLM only sees what the deterministic lanes can't handle, and only the relevant
  tools.
- **Warm models.** Models are warmed at start-up, the static prompt prefix is reused through the KV cache, answers
  stream, RAG is skipped while the knowledge base is empty, and query embeddings are cached.
- **Nothing blocks a command.** SQLite writes are batched on a background thread, and JDE runs off the hot path.

---

## 11. Configuration reference

| File | What it controls |
|---|---|
| `jarvis/config/jarvis.toml` | `[server]` host/port; `[performance]` queue sizes, verify timing; `[database]`; `[paths]` db/logs/models; `[features]` router_ai, planner, voice, tts, browser, vision; `[models]` Ollama roles, base URL, keep_alive, timeout, num_ctx, auto_start, warm_on_start; `[aliases]`; `[voice]` mic device, wake word on/off, push-to-talk, wake threshold, Whisper model/device/compute/beam, preroll, `endpoint_silence_ms`, `max_utterance_s`, `wake_ack` (chime/voice/none); `[search]` folders to index, exclusions, limits; `[decision]` JDE stage |
| `config/whatsapp.toml` | `[whatsapp]` mode, country code, remember_chats; `[whatsapp.owner]` owner numbers; `[whatsapp.allowlist]`; `[whatsapp.pulse]`; `[whatsapp.contacts]` name → number; `[whatsapp.personal_reply]` coalescing, maximum auto-reply hours, untrained contacts, your name in chat exports |
| `config/response.toml` | response style, spoken acknowledgements, progress updates, TTS backend and voice |
| `config/connectors.toml` | Android (ADB / scrcpy), LocalSend, browser, FreshRSS, ntfy/Gotify notifications, Memos, Node-RED |
| `config/integrations.toml` | Google OAuth: client file, token store (keyring), loopback host/ports, scope upgrades |
| `config/policy.toml` | policy per risk class, confirmation timeout, protected paths, execution restrictions |
| `config/google_client_secret.json` | your Google OAuth client (git-ignored; see the example file) |

Environment variables:
- `JARVIS_JDE_STAGE`: `off`, `shadow` or `read_only`.
- `JDE_LOCAL_ONLY`: default `true`.
- `JARVIS_UI_2D=1`: use the 2D reactor.
- `JARVIS_TEST_MODE`.

Restart JARVIS after configuration changes.

---

## 12. Command-line tools and scripts

| Command | Purpose |
|---|---|
| `python -m jarvis` | start the backend (HTTP + WebSocket on 127.0.0.1:8765) |
| `python -m jarvis.ui` | start the desktop UI |
| `python -m jarvis.cli "<command>" [--json] [--plan-only]` | send a command; `--plan-only` prints the task graph without running it |
| `python -m jarvis.diagnostics` | full health check: models per role, voice, devices, connectors |
| `python -m jarvis.report [final\|security]` | system / acceptance and security reports |
| `python -m jarvis.memory list\|inspect\|forget\|conflicts` | inspect and edit long-term memory |
| `python -m jarvis.integrations.whatsapp.doctor` | WhatsApp bridge / pairing / owner diagnostics |
| `python -m jarvis.integrations.google.cli connect\|accounts\|status\|disconnect\|test` | Google accounts |
| `python -m jarvis.voice_latency_debug [--command "..."]` | instrumented voice-to-action latency trials |
| `python -m jarvis.decision.train` / `python -m jarvis.decision.evaluation.evaluate` | train and evaluate the decision engine |
| `python scripts\setup_models.py [--check] [--no-ollama] [--jde]` | download or verify every local model |
| `python scripts\voice_doctor.py` | end-to-end microphone → STT → TTS diagnostics |
| `python scripts\safety_regression.py`, `python scripts\final_acceptance.py` | safety regression and acceptance suites |
| `python scripts\generate_policy_golden.py` | regenerate the policy golden dataset |
| `python scripts\build_generalization_datasets.py` | regenerate the generalization datasets |
| `python scripts\bench_*.py` | benchmarks: `bench_router`, `bench_core`, `bench_end_to_end`, `bench_realtime`, `bench_voice`, `bench_voice_streaming`, `bench_wake`, `bench_vad`, `bench_endpoint`, `bench_stt_models`, `bench_asr_candidates`, `bench_tts`, `bench_response`, `bench_planner`, `bench_planner_models`, `bench_model_routing`, `bench_router_models`, `bench_models`, `bench_intelligence`, `bench_search`, `bench_file_search`, `bench_embeddings`, `bench_execution`, `bench_connectors`, `bench_orchestration`, `bench_google`, `bench_browser_latency`, `bench_desktop_latency`, `bench_uia_latency`, `bench_ui`, `bench_ui_locator`, `bench_wake_ui`, `bench_capture_latency`, `bench_vision_latency`, `bench_vision_models`, `bench_visual_parser`, `bench_notepad`, `bench_jde_backbones` |
| `start.bat` / `start.ps1` | start everything |
| `setup_jarvis.ps1` / `diagnose_jarvis.ps1` / `connect_google.bat` | set up, diagnose, connect Google |

---

## 13. Development

```powershell
python -m pytest -q                                   # full test suite
python -m pytest -q jarvis/tests/test_everyday_tools.py jarvis/tests/test_jde.py
python -m tests.generalization.benchmark_runner       # deterministic generalization benchmark (no model)
python -m jarvis.decision.evaluation.evaluate         # decision-engine benchmark
python -m tests.whatsapp_personal.benchmark           # 500-case WhatsApp personal-reply benchmark (fake provider)
python -m tests.rag.benchmark                         # RAG precision / recall / abstention
```

Useful test infrastructure:
- `jarvis/tests/fake_ollama.py`: an in-process fake Ollama, so AI tests need no network.
- `jarvis/tests/ai_harness.py`: the full stack (router, planner, agent, RAG, WhatsApp AI) for end-to-end tests.
- `tests/generalization/`: about 1,650 paraphrase, implicit, noisy, ASR, compositional and ambiguity cases.
  Current score: 98.55%.
- `tests/jde/suite_{dev,holdout,adversarial}.txt`: the 500 labelled decision cases, one per line:
  `FAMILY | flags | text | context`.

**Adding a feature:**
1. Write a `Tool` with pydantic input/output models and a risk class.
2. Register it in its `create_*_tools()` factory.
3. Add a `CapabilityDefinition` with a description, examples and counterexamples.
4. If the phrasing is common, add a deterministic pattern in `jarvis/core/router/extended.py`.
5. Add tests.

The policy, confirmation, ledger, verifier, LLM tool catalog and JDE catalog pick the tool up automatically.

Tests that need Windows hardware (window management, UI Automation, the live HTTP server, Piper voices) fail or skip
on Linux CI. They pass on a configured Windows PC.

---

## 14. Project phases and feature history

| Phase | What it added |
|---|---|
| 1 | Core runtime and state, native OS tools, typed contracts, SQLite persistence, HTTP/WebSocket gateway |
| 2 | Ultra-fast multi-lane SmartRouter: control bypass, normalisation, guards, hot cache, grammar, fuzzy matching, Lane-1 local SLM |
| 3 | File and knowledge intelligence: multi-tier search cascade (FTS5 BM25 + dense), hot search cache, context memory, follow-ups |
| 4 | Adaptive complex planner and verified DAG scheduler (plan cache, validation, dependency scheduling) |
| 5 | Trusted execution: policy engine, confirmation tickets, verification, recovery and supervision, security ledger |
| 6 | Real-time voice input: wake word, VAD, adaptive endpointing, streaming STT (faster-whisper) |
| 7 | Instant voice responses: streaming local TTS (Piper), PULSE feedback lane, barge-in |
| 8 | ActionLedger and persistence (prepared/committed receipts, reconciliation) |
| 9 | Secure Google Workspace connectors (Gmail, Calendar, Drive; OAuth loopback, keyring tokens) |
| 10 | Structured computer and browser agent (Playwright, Windows UI Automation, typed locators) |
| 11 | Local vision fallback and screen grounding (candidate-first visual parsing, VLM) |
| 12 | Advanced intelligence: layered contextual memory, workflows, resource governor, RAG collections |
| F01–F32 | Feature pack: command palette, context actions, dictation, workspaces, universal search, downloads organiser, batch operations, duplicate finder, document Q&A, notes, meeting notes, media tools, durable reminders, event routines, personal briefing, focus mode, developer tools, error diagnosis, editable memory, teachable routines, pause/resume/undo, browser research and recipes, CalDAV/CardDAV, e-mail, Android companion, Home Assistant, backup, Node-RED, efficiency coach, health and offline controls |
| v1.0 | Desktop UI (PySide6/QML, 3D reactor), WhatsApp omnichannel (Baileys bridge, owner control, AI replies, bulk replies, chat memory) |
| AI integration | One Ollama client with roles, grounded chat with RAG and web, streaming answers, AI agent, web agent, phone control, software install, vision computer-use, phone ⇄ PC files |
| JDE | Local calibrated decision engine (read_only mode), with a 500-case benchmark |
| Everyday pack | Instant offline answers, battery, network, timers, stopwatch, to-do list, personal memory in SQLite + RAG, voice shortcuts, command history, "do that again", password generator, recycle bin; fixes for relative volume/mute/restore/WhatsApp status routing; 25× faster routing |

---

## 15. Troubleshooting

| Symptom | Fix |
|---|---|
| It doesn't wake up | Run `python -m jarvis.diagnostics` (look at Speech model, Wake word model, silero_vad_lite, sounddevice). Lower `[voice] threshold` (e.g. 0.4) if it wakes too rarely; raise it if it wakes by itself. Ctrl+Shift+J always works. |
| It cuts me off, or waits too long | Adjust `[voice] endpoint_silence_ms` (default 800). Unfinished sentences automatically get twice as long. |
| "AI model unavailable" / slow first answer | Install Ollama and `ollama pull` the models in `[models]`. Check `python -m jarvis.diagnostics` for which model each role uses. JARVIS starts Ollama itself when it is installed. |
| WhatsApp doesn't send | Run `python -m jarvis.integrations.whatsapp.doctor`. Check pairing, owner numbers and contacts in `config/whatsapp.toml`. |
| Phone commands fail | Enable USB debugging, accept the RSA prompt, check that `adb devices` lists the phone. |
| Browser task stops at a login | Sign in once in the JARVIS browser window, then say "continue". |
| Screen clicking misses | `ollama pull qwen2.5vl:3b`; `pip install -e .[windows]`. |
| Port 8765 in use | Another backend is already running; use it or stop it in its own window. |
| Decision engine shows as off | `python scripts\setup_models.py --check`. JDE falls back to the hash model when GloVe is missing. Routing is never affected. |

---

## 16. Licences

JARVIS depends only on free, open-source software; no paid service is required. Code licences and model-weight
licences are tracked separately.

| Component | Code licence | Weights / notes |
|---|---|---|
| FastAPI, Pydantic, psutil, mss, pycaw, httptools, h11, websockets, HTTPX, Uvicorn, pytest | MIT / BSD / Apache-2.0 | — |
| openWakeWord | Apache-2.0 | bundled pretrained models CC BY-NC-SA 4.0 (non-commercial) |
| Silero VAD | MIT | MIT |
| faster-whisper / CTranslate2 | MIT | Whisper weights MIT |
| Piper TTS | GPL-3.0 (run as an isolated library/process) | voices MIT / public domain |
| Qwen models, Llama 3.2 (via Ollama) | Apache-2.0 / Llama licence | see each model card |
| GloVe (decision engine, optional) | — | Public Domain Dedication and License (PDDL) |
| Playwright | Apache-2.0 | Chromium BSD-style |
| PySide6 / Qt | LGPL-3.0 (dynamically linked) | — |
| Baileys (WhatsApp bridge) | MIT | unofficial WhatsApp Web library |

Keep upstream copyright and licence notices when redistributing dependencies or model weights.
