# JARVIS EDGE — 78 Compositional Failures Audit & Root-Cause Classification

**Total Records**: 210
**Passed**: 39
**Failed**: 171

## Root Cause Breakdown

- **CAPABILITY_NOT_RETRIEVED**: 169
- **WRONG_CAPABILITY**: 2

---

## Detailed Failure Breakdown

### Failure 1: `Check system diagnostics and save the report as a memo.`

- **Root Cause**: WRONG_CAPABILITY
- **Expected Capabilities**: `['system.diagnostics', 'knowledge.note']`
- **Canonical Expected**: `['system.diagnostics', 'rag.capture_note']`
- **Retrieved (Top 5)**: `['system.diagnostics', 'system.info', 'system.microphone_status', 'system.stt_status', 'system.wake_word_status']`
- **Missing in Top 10**: `[]`
- **Actual Route**: Lane `LANE_0`, Intent `system_diagnostics`
- **Detail**: Lane LANE_0 chosen instead of Lane 2 / Compound

### Failure 2: `Find invoice in Documents and extract the total amount.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.extract']`
- **Canonical Expected**: `['file.find', 'rag.document_qa']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'file.list_directory', 'file.batch_rename', 'file.organize_downloads']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 3: `Find invoices in Documents, summarize the latest one, and draft an email to finance with the summary.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.personal_briefing', 'rag.meeting_notes', 'rag.rss_latest']`
- **Missing in Top 10**: `['google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.gmail_send']

### Failure 4: `Search news for artificial intelligence, extract the top headline, and save it as a note.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['news.search', 'knowledge.extract', 'knowledge.note']`
- **Canonical Expected**: `['rag.search_news', 'rag.document_qa', 'rag.capture_note']`
- **Retrieved (Top 5)**: `['rag.search_web', 'rag.search_news', 'rag.capture_note', 'rag.memos_create', 'browser.type']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 5: `Check calendar events for today, draft morning briefing note, and read headlines from RSS.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['calendar.read', 'knowledge.note', 'rss.latest']`
- **Canonical Expected**: `['google.calendar_list', 'rag.capture_note', 'rag.rss_latest']`
- **Retrieved (Top 5)**: `['rag.morning_briefing', 'rag.rss_latest', 'system.time', 'rag.search_news', 'system.diagnostics']`
- **Missing in Top 10**: `['google.calendar_list']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.calendar_list']

### Failure 6: `Find all pdf files in Downloads, summarize the most recent one, and save the notes.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'knowledge.note']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'rag.capture_note']`
- **Retrieved (Top 5)**: `['file.find', 'file.find_duplicates', 'file.list_directory', 'file.move', 'file.organize_downloads']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 7: `Take a screenshot of the active screen, save to Pictures, and send to my phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'file.save', 'phone.transfer']`
- **Canonical Expected**: `['windows.screenshot', 'file.create_folder', 'phone.send_file']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'windows.desktop_ui_snapshot', 'phone.send_text', 'phone.send_file', 'phone.send_notification']`
- **Missing in Top 10**: `['file.create_folder']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['file.create_folder']

### Failure 8: `Find the contract with Acme Corp, extract payment terms, and compose WhatsApp draft to Sarah.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.extract', 'whatsapp.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'whatsapp.action']`
- **Retrieved (Top 5)**: `['whatsapp.action', 'whatsapp.read', 'whatsapp.send', 'whatsapp.summarize', 'app.install_software']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa']

### Failure 9: `Check battery percentage, set screen brightness to 60%, and close unused background apps.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.battery', 'system.brightness', 'system.processes']`
- **Canonical Expected**: `['system.diagnostics', 'windows.brightness_set', 'windows.top_memory_processes']`
- **Retrieved (Top 5)**: `['windows.brightness_set', 'windows.brightness_get', 'app.close', 'windows.close_window', 'system.diagnostics']`
- **Missing in Top 10**: `['windows.top_memory_processes']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['windows.top_memory_processes']

### Failure 10: `Search for presentation in Downloads, open containing folder, and check Android connection.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'app.open', 'phone.status']`
- **Canonical Expected**: `['file.find', 'app.open', 'phone.status']`
- **Retrieved (Top 5)**: `['file.find', 'file.open', 'file.find_duplicates', 'phone.status', 'file.organize_downloads']`
- **Missing in Top 10**: `['app.open']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['app.open']

### Failure 11: `Look up latest research on quantum computing, extract executive summary, and open browser source.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['rag.search_web', 'knowledge.summarize', 'browser.open_url']`
- **Canonical Expected**: `['rag.search_web', 'rag.document_qa', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'browser.play_youtube', 'rag.meeting_notes', 'browser.open_url', 'browser.snapshot']`
- **Missing in Top 10**: `['rag.search_web', 'rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.search_web', 'rag.document_qa']

### Failure 12: `Find audio recording in Music, trim first 30 seconds, and send clip to phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'workflow.trim_audio', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'workflow.trim_clip', 'phone.send_file']`
- **Retrieved (Top 5)**: `['windows.volume_get', 'workflow.trim_clip', 'phone.send_text', 'phone.send_file', 'phone.send_notification']`
- **Missing in Top 10**: `['file.find']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['file.find']

### Failure 13: `Capture active window snapshot, copy image to clipboard, and open Discord.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'system.clipboard', 'app.open']`
- **Canonical Expected**: `['windows.screenshot', 'terminal.powershell', 'app.open']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'windows.desktop_ui_snapshot', 'windows.minimize_window', 'windows.close_window', 'windows.maximize_window']`
- **Missing in Top 10**: `['terminal.powershell']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['terminal.powershell']

### Failure 14: `List files in Desktop, organize loose documents into categorized folders, and show report.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.list', 'file.organize', 'system.notify']`
- **Canonical Expected**: `['file.list_directory', 'file.organize_downloads', 'system.dashboard']`
- **Retrieved (Top 5)**: `['file.organize_downloads', 'file.list_directory', 'file.create_folder', 'file.delete', 'file.move']`
- **Missing in Top 10**: `['system.dashboard']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['system.dashboard']

### Failure 15: `Check system CPU usage, if above 80% list top processes, and notify user.`

- **Root Cause**: WRONG_CAPABILITY
- **Expected Capabilities**: `['system.cpu', 'system.processes', 'system.notify']`
- **Canonical Expected**: `['system.diagnostics', 'windows.top_memory_processes', 'system.dashboard']`
- **Retrieved (Top 5)**: `['system.info', 'system.diagnostics', 'system.microphone_status', 'system.stt_status', 'system.wake_word_status']`
- **Missing in Top 10**: `[]`
- **Actual Route**: Lane `LANE_0`, Intent `system_info`
- **Detail**: Lane LANE_0 chosen instead of Lane 2 / Compound

### Failure 16: `Find the downloaded dataset zip, verify SHA256 checksum, and extract to Data directory.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.checksum', 'file.extract']`
- **Canonical Expected**: `['file.find', 'file.read_metadata', 'file.batch_rename']`
- **Retrieved (Top 5)**: `['file.find', 'file.find_duplicates', 'file.list_directory', 'file.move', 'file.organize_downloads']`
- **Missing in Top 10**: `['file.batch_rename']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['file.batch_rename']

### Failure 17: `Search email for meeting link, copy URL, and open it in Google Chrome.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['email.search', 'system.clipboard', 'browser.open_url']`
- **Canonical Expected**: `['rag.document_qa', 'terminal.powershell', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'app.install_software', 'browser.type', 'browser.click', 'app.get_location']`
- **Missing in Top 10**: `['rag.document_qa', 'terminal.powershell']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'terminal.powershell']

### Failure 18: `Find the newest research paper on neural networks in Downloads, extract key takeaways, open official documentation in Chrome, and send the PDF to my phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'browser.open_url', 'phone.send_file']`
- **Retrieved (Top 5)**: `['app.open', 'phone.send_file', 'file.find', 'file.find_duplicates', 'file.open']`
- **Missing in Top 10**: `['rag.document_qa', 'browser.open_url']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'browser.open_url']

### Failure 19: `Search for quarterly financial statements, extract revenue numbers, compare with last year's report, and draft email to the board with executive summary.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.extract', 'knowledge.compare', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['rag.personal_briefing', 'rag.meeting_notes', 'rag.morning_briefing', 'file.read_metadata', 'rag.search_news']`
- **Missing in Top 10**: `['file.find', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'google.gmail_send']

### Failure 20: `Find latest photo taken on Android phone, transfer to PC Downloads, optimize resolution, and set as desktop background.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['phone.get_photo', 'phone.transfer', 'image.optimize', 'system.set_wallpaper']`
- **Canonical Expected**: `['phone.mirror_open', 'phone.send_file', 'windows.desktop_ui_click']`
- **Retrieved (Top 5)**: `['file.list_directory', 'phone.open_app', 'phone.back', 'phone.status', 'phone.home']`
- **Missing in Top 10**: `['windows.desktop_ui_click']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['windows.desktop_ui_click']

### Failure 21: `Scan project folder for linting errors, run unit test suite, generate coverage report, and open results in browser.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['workflow.lint', 'workflow.run_tests', 'workflow.coverage', 'browser.open_url']`
- **Canonical Expected**: `['workflow.diagnose_error', 'workflow.run_tests', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'file.find', 'file.find_duplicates', 'browser.play_youtube', 'browser.open_url']`
- **Missing in Top 10**: `['workflow.diagnose_error']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['workflow.diagnose_error']

### Failure 22: `Check unread WhatsApp messages from client, extract requested deliverables, search local drive for matched files, and prepare draft reply with attachments.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['whatsapp.read', 'knowledge.extract', 'file.search', 'whatsapp.draft']`
- **Canonical Expected**: `['whatsapp.read', 'rag.document_qa', 'file.find', 'whatsapp.action']`
- **Retrieved (Top 5)**: `['file.find', 'whatsapp.read', 'file.find_duplicates', 'file.list_directory', 'file.read_metadata']`
- **Missing in Top 10**: `['rag.document_qa', 'whatsapp.action']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'whatsapp.action']

### Failure 23: `Audit system health metrics, export diagnostics log to Desktop, compress into zip archive, and send notification.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.diagnostics', 'file.export', 'file.compress', 'system.notify']`
- **Canonical Expected**: `['system.diagnostics', 'file.copy', 'file.batch_rename', 'system.dashboard']`
- **Retrieved (Top 5)**: `['system.diagnostics', 'system.info', 'system.stt_status', 'system.wake_word_status', 'system.microphone_status']`
- **Missing in Top 10**: `['file.copy', 'file.batch_rename', 'system.dashboard']`
- **Actual Route**: Lane `LANE_0`, Intent `system_diagnostics`
- **Detail**: Missing capabilities in Top-10: ['file.copy', 'file.batch_rename', 'system.dashboard']

### Failure 24: `Find all duplicate MP3 files in Music, compute hash checksums, group into duplicates list, and prompt user before removal.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.hash', 'file.group', 'user.confirm']`
- **Canonical Expected**: `['file.find', 'file.read_metadata', 'file.organize_downloads', 'system.dashboard']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'file.list_directory', 'file.copy', 'file.batch_rename']`
- **Missing in Top 10**: `['system.dashboard']`
- **Actual Route**: Lane `LANE_0`, Intent `find_duplicates`
- **Detail**: Missing capabilities in Top-10: ['system.dashboard']

### Failure 25: `Retrieve calendar appointments for tomorrow, check commute travel time on Google Maps, draft morning alarm recommendations, and save to memos.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['calendar.read', 'browser.maps', 'knowledge.recommend', 'rag.memos_create']`
- **Canonical Expected**: `['google.calendar_list', 'browser.open_url', 'rag.document_qa', 'rag.memos_create']`
- **Retrieved (Top 5)**: `['windows.volume_mute', 'system.time', 'rag.memos_create', 'rag.memos_recent', 'rag.capture_note']`
- **Missing in Top 10**: `['google.calendar_list', 'browser.open_url', 'rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.calendar_list', 'browser.open_url', 'rag.document_qa']

### Failure 26: `Search Drive for marketing roadmap slides, convert presentation to PDF, send copy to phone, and notify team on WhatsApp.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['drive.search', 'file.convert', 'phone.transfer', 'whatsapp.send']`
- **Canonical Expected**: `['google.drive_search', 'workflow.extract_audio', 'phone.send_file', 'whatsapp.send']`
- **Retrieved (Top 5)**: `['phone.send_text', 'phone.send_file', 'phone.send_notification', 'whatsapp.action', 'whatsapp.read']`
- **Missing in Top 10**: `['google.drive_search', 'workflow.extract_audio']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.drive_search', 'workflow.extract_audio']

### Failure 27: `Capture desktop screen recording of 10 seconds, convert to GIF animation, copy to clipboard, and paste into active chat window.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['screen.record', 'media.convert', 'system.clipboard', 'app.paste']`
- **Canonical Expected**: `['windows.screenshot', 'workflow.extract_audio', 'terminal.powershell']`
- **Retrieved (Top 5)**: `['windows.desktop_ui_snapshot', 'workflow.trim_clip', 'file.create_folder', 'file.delete', 'file.move']`
- **Missing in Top 10**: `['workflow.extract_audio', 'terminal.powershell']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['workflow.extract_audio', 'terminal.powershell']

### Failure 28: `Find neural_networks.pdf in Documents, extract key summary points, and draft an update to Dr. Rao.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.meeting_notes', 'system.time', 'rag.capture_note']`
- **Missing in Top 10**: `['rag.document_qa', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'google.gmail_send']

### Failure 29: `Retrieve latest notes on machine learning, format them into bullet points, and open in Notepad.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['rag.search_notes', 'knowledge.format', 'app.open']`
- **Canonical Expected**: `['rag.search_notes', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['app.open', 'rag.memos_recent', 'rag.search_web', 'rag.morning_briefing', 'app.list_installed']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 30: `Check if Dr. Rao sent any WhatsApp messages about machine learning, summarize the thread, and notify me.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['whatsapp.read', 'knowledge.summarize', 'system.notify']`
- **Canonical Expected**: `['whatsapp.read', 'rag.document_qa', 'system.dashboard']`
- **Retrieved (Top 5)**: `['whatsapp.read', 'whatsapp.send', 'whatsapp.summarize', 'app.check_installed', 'whatsapp.action']`
- **Missing in Top 10**: `['system.dashboard']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['system.dashboard']

### Failure 31: `Find newest machine learning PDF, extract main findings, open source reference in browser, and push file to phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'browser.open_url', 'phone.send_file']`
- **Retrieved (Top 5)**: `['phone.send_file', 'file.find', 'app.open', 'file.find_duplicates', 'phone.send_notification']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 32: `Scan Downloads for machine learning documents, calculate total storage used, and create a status memo.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.stats', 'rag.memos_create']`
- **Canonical Expected**: `['file.find', 'file.stats', 'rag.memos_create']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.memos_create', 'file.organize_downloads', 'file.list_directory']`
- **Missing in Top 10**: `['file.stats']`
- **Actual Route**: Lane `LANE_0`, Intent `find_duplicates`
- **Detail**: Missing capabilities in Top-10: ['file.stats']

### Failure 33: `Search Google for recent news on machine learning, save top 3 article links, and open first link in Chrome.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['news.search', 'knowledge.save', 'browser.open_url']`
- **Canonical Expected**: `['rag.search_news', 'knowledge.save', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'rag.search_web', 'browser.click', 'rag.search_news', 'app.install_software']`
- **Missing in Top 10**: `['knowledge.save', 'browser.open_url']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['knowledge.save', 'browser.open_url']

### Failure 34: `Take a screenshot of current machine learning dashboard, save to Desktop, and draft email to AI lab.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'file.save', 'email.draft']`
- **Canonical Expected**: `['windows.screenshot', 'file.create_folder', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'system.dashboard', 'system.devices', 'system.time', 'windows.brightness_get']`
- **Missing in Top 10**: `['google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.gmail_send']

### Failure 35: `Find incident_report.docx in Documents, extract key summary points, and draft an update to Chief Security Officer.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['file.find', 'file.find_duplicates', 'rag.meeting_notes', 'system.time', 'file.delete']`
- **Missing in Top 10**: `['rag.document_qa', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'google.gmail_send']

### Failure 36: `Retrieve latest notes on cybersecurity, format them into bullet points, and open in Notepad.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['rag.search_notes', 'knowledge.format', 'app.open']`
- **Canonical Expected**: `['rag.search_notes', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['app.open', 'rag.memos_recent', 'rag.search_web', 'rag.morning_briefing', 'app.list_installed']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 37: `Check if Chief Security Officer sent any WhatsApp messages about cybersecurity, summarize the thread, and notify me.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['whatsapp.read', 'knowledge.summarize', 'system.notify']`
- **Canonical Expected**: `['whatsapp.read', 'rag.document_qa', 'system.dashboard']`
- **Retrieved (Top 5)**: `['whatsapp.read', 'whatsapp.send', 'whatsapp.summarize', 'app.check_installed', 'whatsapp.action']`
- **Missing in Top 10**: `['system.dashboard']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['system.dashboard']

### Failure 38: `Find newest cybersecurity PDF, extract main findings, open source reference in browser, and push file to phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'browser.open_url', 'phone.send_file']`
- **Retrieved (Top 5)**: `['phone.send_file', 'file.find', 'app.open', 'file.find_duplicates', 'phone.send_notification']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 39: `Scan Downloads for cybersecurity documents, calculate total storage used, and create a status memo.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.stats', 'rag.memos_create']`
- **Canonical Expected**: `['file.find', 'file.stats', 'rag.memos_create']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.memos_create', 'file.organize_downloads', 'file.list_directory']`
- **Missing in Top 10**: `['file.stats']`
- **Actual Route**: Lane `LANE_0`, Intent `find_duplicates`
- **Detail**: Missing capabilities in Top-10: ['file.stats']

### Failure 40: `Search Google for recent news on cybersecurity, save top 3 article links, and open first link in Chrome.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['news.search', 'knowledge.save', 'browser.open_url']`
- **Canonical Expected**: `['rag.search_news', 'knowledge.save', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'rag.search_web', 'browser.click', 'rag.search_news', 'app.install_software']`
- **Missing in Top 10**: `['knowledge.save', 'browser.open_url']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['knowledge.save', 'browser.open_url']

### Failure 41: `Take a screenshot of current cybersecurity dashboard, save to Desktop, and draft email to SOC analysts.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'file.save', 'email.draft']`
- **Canonical Expected**: `['windows.screenshot', 'file.create_folder', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'system.dashboard', 'system.devices', 'system.time', 'windows.brightness_get']`
- **Missing in Top 10**: `['google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.gmail_send']

### Failure 42: `Find q3_forecast.xlsx in Documents, extract key summary points, and draft an update to Financial Controller.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['file.find', 'file.find_duplicates', 'rag.meeting_notes', 'file.list_directory', 'system.time']`
- **Missing in Top 10**: `['rag.document_qa', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'google.gmail_send']

### Failure 43: `Retrieve latest notes on quarterly budget, format them into bullet points, and open in Notepad.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['rag.search_notes', 'knowledge.format', 'app.open']`
- **Canonical Expected**: `['rag.search_notes', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['app.open', 'rag.memos_recent', 'rag.search_web', 'rag.morning_briefing', 'app.list_installed']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 44: `Check if Financial Controller sent any WhatsApp messages about quarterly budget, summarize the thread, and notify me.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['whatsapp.read', 'knowledge.summarize', 'system.notify']`
- **Canonical Expected**: `['whatsapp.read', 'rag.document_qa', 'system.dashboard']`
- **Retrieved (Top 5)**: `['whatsapp.read', 'whatsapp.send', 'whatsapp.summarize', 'app.check_installed', 'whatsapp.action']`
- **Missing in Top 10**: `['system.dashboard']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['system.dashboard']

### Failure 45: `Find newest quarterly budget PDF, extract main findings, open source reference in browser, and push file to phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'browser.open_url', 'phone.send_file']`
- **Retrieved (Top 5)**: `['file.find', 'phone.send_file', 'app.open', 'file.find_duplicates', 'phone.send_notification']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 46: `Scan Downloads for quarterly budget documents, calculate total storage used, and create a status memo.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.stats', 'rag.memos_create']`
- **Canonical Expected**: `['file.find', 'file.stats', 'rag.memos_create']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.memos_create', 'file.organize_downloads', 'file.list_directory']`
- **Missing in Top 10**: `['file.stats']`
- **Actual Route**: Lane `LANE_0`, Intent `find_duplicates`
- **Detail**: Missing capabilities in Top-10: ['file.stats']

### Failure 47: `Search Google for recent news on quarterly budget, save top 3 article links, and open first link in Chrome.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['news.search', 'knowledge.save', 'browser.open_url']`
- **Canonical Expected**: `['rag.search_news', 'knowledge.save', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'rag.search_web', 'browser.click', 'rag.search_news', 'app.install_software']`
- **Missing in Top 10**: `['knowledge.save', 'browser.open_url']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['knowledge.save', 'browser.open_url']

### Failure 48: `Take a screenshot of current quarterly budget dashboard, save to Desktop, and draft email to accounting department.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'file.save', 'email.draft']`
- **Canonical Expected**: `['windows.screenshot', 'file.create_folder', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'system.dashboard', 'system.devices', 'system.time', 'windows.brightness_get']`
- **Missing in Top 10**: `['google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.gmail_send']

### Failure 49: `Find figma_specs.pdf in Documents, extract key summary points, and draft an update to Lead Designer.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'system.info', 'rag.meeting_notes', 'system.diagnostics']`
- **Missing in Top 10**: `['rag.document_qa', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'google.gmail_send']

### Failure 50: `Retrieve latest notes on product design, format them into bullet points, and open in Notepad.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['rag.search_notes', 'knowledge.format', 'app.open']`
- **Canonical Expected**: `['rag.search_notes', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['app.open', 'rag.memos_recent', 'rag.search_web', 'rag.morning_briefing', 'app.list_installed']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 51: `Check if Lead Designer sent any WhatsApp messages about product design, summarize the thread, and notify me.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['whatsapp.read', 'knowledge.summarize', 'system.notify']`
- **Canonical Expected**: `['whatsapp.read', 'rag.document_qa', 'system.dashboard']`
- **Retrieved (Top 5)**: `['whatsapp.read', 'whatsapp.send', 'whatsapp.summarize', 'app.check_installed', 'whatsapp.action']`
- **Missing in Top 10**: `['system.dashboard']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['system.dashboard']

### Failure 52: `Find newest product design PDF, extract main findings, open source reference in browser, and push file to phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'browser.open_url', 'phone.send_file']`
- **Retrieved (Top 5)**: `['phone.send_file', 'file.find', 'app.open', 'file.find_duplicates', 'phone.send_notification']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 53: `Scan Downloads for product design documents, calculate total storage used, and create a status memo.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.stats', 'rag.memos_create']`
- **Canonical Expected**: `['file.find', 'file.stats', 'rag.memos_create']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.memos_create', 'file.organize_downloads', 'file.list_directory']`
- **Missing in Top 10**: `['file.stats']`
- **Actual Route**: Lane `LANE_0`, Intent `find_duplicates`
- **Detail**: Missing capabilities in Top-10: ['file.stats']

### Failure 54: `Search Google for recent news on product design, save top 3 article links, and open first link in Chrome.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['news.search', 'knowledge.save', 'browser.open_url']`
- **Canonical Expected**: `['rag.search_news', 'knowledge.save', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'rag.search_web', 'browser.click', 'rag.search_news', 'app.install_software']`
- **Missing in Top 10**: `['knowledge.save', 'browser.open_url']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['knowledge.save', 'browser.open_url']

### Failure 55: `Take a screenshot of current product design dashboard, save to Desktop, and draft email to UI/UX designers.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'file.save', 'email.draft']`
- **Canonical Expected**: `['windows.screenshot', 'file.create_folder', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'system.dashboard', 'system.devices', 'system.time', 'windows.brightness_get']`
- **Missing in Top 10**: `['google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.gmail_send']

### Failure 56: `Find nda_signed.pdf in Documents, extract key summary points, and draft an update to Senior Partner.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.meeting_notes', 'system.time', 'rag.capture_note']`
- **Missing in Top 10**: `['rag.document_qa', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'google.gmail_send']

### Failure 57: `Retrieve latest notes on legal agreement, format them into bullet points, and open in Notepad.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['rag.search_notes', 'knowledge.format', 'app.open']`
- **Canonical Expected**: `['rag.search_notes', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['app.open', 'rag.memos_recent', 'rag.search_web', 'rag.morning_briefing', 'app.list_installed']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 58: `Check if Senior Partner sent any WhatsApp messages about legal agreement, summarize the thread, and notify me.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['whatsapp.read', 'knowledge.summarize', 'system.notify']`
- **Canonical Expected**: `['whatsapp.read', 'rag.document_qa', 'system.dashboard']`
- **Retrieved (Top 5)**: `['whatsapp.read', 'whatsapp.send', 'whatsapp.summarize', 'app.check_installed', 'whatsapp.action']`
- **Missing in Top 10**: `['system.dashboard']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['system.dashboard']

### Failure 59: `Find newest legal agreement PDF, extract main findings, open source reference in browser, and push file to phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'browser.open_url', 'phone.send_file']`
- **Retrieved (Top 5)**: `['phone.send_file', 'file.find', 'app.open', 'file.find_duplicates', 'phone.send_notification']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 60: `Scan Downloads for legal agreement documents, calculate total storage used, and create a status memo.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.stats', 'rag.memos_create']`
- **Canonical Expected**: `['file.find', 'file.stats', 'rag.memos_create']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.memos_create', 'file.organize_downloads', 'file.list_directory']`
- **Missing in Top 10**: `['file.stats']`
- **Actual Route**: Lane `LANE_0`, Intent `find_duplicates`
- **Detail**: Missing capabilities in Top-10: ['file.stats']

### Failure 61: `Search Google for recent news on legal agreement, save top 3 article links, and open first link in Chrome.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['news.search', 'knowledge.save', 'browser.open_url']`
- **Canonical Expected**: `['rag.search_news', 'knowledge.save', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'rag.search_web', 'browser.click', 'rag.search_news', 'app.install_software']`
- **Missing in Top 10**: `['knowledge.save', 'browser.open_url']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['knowledge.save', 'browser.open_url']

### Failure 62: `Take a screenshot of current legal agreement dashboard, save to Desktop, and draft email to general counsel.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'file.save', 'email.draft']`
- **Canonical Expected**: `['windows.screenshot', 'file.create_folder', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'system.dashboard', 'system.devices', 'system.time', 'windows.brightness_get']`
- **Missing in Top 10**: `['google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.gmail_send']

### Failure 63: `Find efficacy_study.pdf in Documents, extract key summary points, and draft an update to Principal Investigator.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.meeting_notes', 'system.time', 'rag.capture_note']`
- **Missing in Top 10**: `['rag.document_qa', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'google.gmail_send']

### Failure 64: `Retrieve latest notes on patient clinical trial, format them into bullet points, and open in Notepad.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['rag.search_notes', 'knowledge.format', 'app.open']`
- **Canonical Expected**: `['rag.search_notes', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['app.open', 'rag.memos_recent', 'rag.search_web', 'rag.morning_briefing', 'app.list_installed']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 65: `Check if Principal Investigator sent any WhatsApp messages about patient clinical trial, summarize the thread, and notify me.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['whatsapp.read', 'knowledge.summarize', 'system.notify']`
- **Canonical Expected**: `['whatsapp.read', 'rag.document_qa', 'system.dashboard']`
- **Retrieved (Top 5)**: `['whatsapp.read', 'whatsapp.send', 'whatsapp.summarize', 'app.check_installed', 'whatsapp.action']`
- **Missing in Top 10**: `['system.dashboard']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['system.dashboard']

### Failure 66: `Find newest patient clinical trial PDF, extract main findings, open source reference in browser, and push file to phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'browser.open_url', 'phone.send_file']`
- **Retrieved (Top 5)**: `['phone.send_file', 'file.find', 'app.open', 'file.find_duplicates', 'phone.send_notification']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 67: `Scan Downloads for patient clinical trial documents, calculate total storage used, and create a status memo.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.stats', 'rag.memos_create']`
- **Canonical Expected**: `['file.find', 'file.stats', 'rag.memos_create']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.memos_create', 'file.organize_downloads', 'file.list_directory']`
- **Missing in Top 10**: `['file.stats']`
- **Actual Route**: Lane `LANE_0`, Intent `find_duplicates`
- **Detail**: Missing capabilities in Top-10: ['file.stats']

### Failure 68: `Search Google for recent news on patient clinical trial, save top 3 article links, and open first link in Chrome.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['news.search', 'knowledge.save', 'browser.open_url']`
- **Canonical Expected**: `['rag.search_news', 'knowledge.save', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'rag.search_web', 'browser.click', 'rag.search_news', 'app.install_software']`
- **Missing in Top 10**: `['knowledge.save', 'browser.open_url']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['knowledge.save', 'browser.open_url']

### Failure 69: `Take a screenshot of current patient clinical trial dashboard, save to Desktop, and draft email to medical board.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'file.save', 'email.draft']`
- **Canonical Expected**: `['windows.screenshot', 'file.create_folder', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'system.dashboard', 'system.devices', 'system.time', 'windows.brightness_get']`
- **Missing in Top 10**: `['google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.gmail_send']

### Failure 70: `Find terraform_plan.tf in Documents, extract key summary points, and draft an update to Engineering Director.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.meeting_notes', 'system.time', 'rag.capture_note']`
- **Missing in Top 10**: `['rag.document_qa', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'google.gmail_send']

### Failure 71: `Retrieve latest notes on cloud infrastructure, format them into bullet points, and open in Notepad.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['rag.search_notes', 'knowledge.format', 'app.open']`
- **Canonical Expected**: `['rag.search_notes', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['app.open', 'rag.memos_recent', 'rag.search_web', 'rag.morning_briefing', 'app.list_installed']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 72: `Check if Engineering Director sent any WhatsApp messages about cloud infrastructure, summarize the thread, and notify me.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['whatsapp.read', 'knowledge.summarize', 'system.notify']`
- **Canonical Expected**: `['whatsapp.read', 'rag.document_qa', 'system.dashboard']`
- **Retrieved (Top 5)**: `['whatsapp.read', 'whatsapp.send', 'whatsapp.summarize', 'app.check_installed', 'whatsapp.action']`
- **Missing in Top 10**: `['system.dashboard']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['system.dashboard']

### Failure 73: `Find newest cloud infrastructure PDF, extract main findings, open source reference in browser, and push file to phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'browser.open_url', 'phone.send_file']`
- **Retrieved (Top 5)**: `['phone.send_file', 'file.find', 'app.open', 'file.find_duplicates', 'phone.send_notification']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 74: `Scan Downloads for cloud infrastructure documents, calculate total storage used, and create a status memo.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.stats', 'rag.memos_create']`
- **Canonical Expected**: `['file.find', 'file.stats', 'rag.memos_create']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.memos_create', 'file.organize_downloads', 'file.list_directory']`
- **Missing in Top 10**: `['file.stats']`
- **Actual Route**: Lane `LANE_0`, Intent `find_duplicates`
- **Detail**: Missing capabilities in Top-10: ['file.stats']

### Failure 75: `Search Google for recent news on cloud infrastructure, save top 3 article links, and open first link in Chrome.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['news.search', 'knowledge.save', 'browser.open_url']`
- **Canonical Expected**: `['rag.search_news', 'knowledge.save', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'rag.search_web', 'browser.click', 'rag.search_news', 'app.install_software']`
- **Missing in Top 10**: `['knowledge.save', 'browser.open_url']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['knowledge.save', 'browser.open_url']

### Failure 76: `Take a screenshot of current cloud infrastructure dashboard, save to Desktop, and draft email to DevOps team.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'file.save', 'email.draft']`
- **Canonical Expected**: `['windows.screenshot', 'file.create_folder', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'system.dashboard', 'system.devices', 'system.time', 'windows.brightness_get']`
- **Missing in Top 10**: `['google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.gmail_send']

### Failure 77: `Find retention_metrics.csv in Documents, extract key summary points, and draft an update to Product VP.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.meeting_notes', 'system.time', 'file.read_metadata']`
- **Missing in Top 10**: `['rag.document_qa', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'google.gmail_send']

### Failure 78: `Retrieve latest notes on mobile app analytics, format them into bullet points, and open in Notepad.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['rag.search_notes', 'knowledge.format', 'app.open']`
- **Canonical Expected**: `['rag.search_notes', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['app.open', 'rag.memos_recent', 'rag.search_web', 'phone.open_app', 'app.get_location']`
- **Missing in Top 10**: `['rag.search_notes', 'rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.search_notes', 'rag.document_qa']

### Failure 79: `Check if Product VP sent any WhatsApp messages about mobile app analytics, summarize the thread, and notify me.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['whatsapp.read', 'knowledge.summarize', 'system.notify']`
- **Canonical Expected**: `['whatsapp.read', 'rag.document_qa', 'system.dashboard']`
- **Retrieved (Top 5)**: `['whatsapp.send', 'whatsapp.read', 'app.check_installed', 'phone.open_app', 'whatsapp.summarize']`
- **Missing in Top 10**: `['system.dashboard']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['system.dashboard']

### Failure 80: `Find newest mobile app analytics PDF, extract main findings, open source reference in browser, and push file to phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'browser.open_url', 'phone.send_file']`
- **Retrieved (Top 5)**: `['file.find', 'file.find_duplicates', 'phone.send_file', 'app.open', 'phone.send_notification']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 81: `Scan Downloads for mobile app analytics documents, calculate total storage used, and create a status memo.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.stats', 'rag.memos_create']`
- **Canonical Expected**: `['file.find', 'file.stats', 'rag.memos_create']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'phone.send_file', 'rag.memos_create', 'file.organize_downloads']`
- **Missing in Top 10**: `['file.stats']`
- **Actual Route**: Lane `LANE_0`, Intent `find_duplicates`
- **Detail**: Missing capabilities in Top-10: ['file.stats']

### Failure 82: `Search Google for recent news on mobile app analytics, save top 3 article links, and open first link in Chrome.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['news.search', 'knowledge.save', 'browser.open_url']`
- **Canonical Expected**: `['rag.search_news', 'knowledge.save', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'rag.search_web', 'browser.click', 'rag.search_news', 'app.install_software']`
- **Missing in Top 10**: `['knowledge.save', 'browser.open_url']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['knowledge.save', 'browser.open_url']

### Failure 83: `Take a screenshot of current mobile app analytics dashboard, save to Desktop, and draft email to growth squad.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'file.save', 'email.draft']`
- **Canonical Expected**: `['windows.screenshot', 'file.create_folder', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'system.dashboard', 'phone.open_app', 'system.devices', 'system.time']`
- **Missing in Top 10**: `['file.create_folder', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['file.create_folder', 'google.gmail_send']

### Failure 84: `Find nps_survey_q3.csv in Documents, extract key summary points, and draft an update to Customer Success Lead.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.meeting_notes', 'system.time', 'file.read_metadata']`
- **Missing in Top 10**: `['rag.document_qa', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'google.gmail_send']

### Failure 85: `Retrieve latest notes on customer feedback, format them into bullet points, and open in Notepad.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['rag.search_notes', 'knowledge.format', 'app.open']`
- **Canonical Expected**: `['rag.search_notes', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['app.open', 'rag.memos_recent', 'rag.search_web', 'rag.morning_briefing', 'app.list_installed']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 86: `Check if Customer Success Lead sent any WhatsApp messages about customer feedback, summarize the thread, and notify me.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['whatsapp.read', 'knowledge.summarize', 'system.notify']`
- **Canonical Expected**: `['whatsapp.read', 'rag.document_qa', 'system.dashboard']`
- **Retrieved (Top 5)**: `['whatsapp.read', 'whatsapp.send', 'whatsapp.summarize', 'app.check_installed', 'whatsapp.action']`
- **Missing in Top 10**: `['system.dashboard']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['system.dashboard']

### Failure 87: `Find newest customer feedback PDF, extract main findings, open source reference in browser, and push file to phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'browser.open_url', 'phone.send_file']`
- **Retrieved (Top 5)**: `['phone.send_file', 'file.find', 'app.open', 'file.find_duplicates', 'phone.send_notification']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 88: `Scan Downloads for customer feedback documents, calculate total storage used, and create a status memo.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.stats', 'rag.memos_create']`
- **Canonical Expected**: `['file.find', 'file.stats', 'rag.memos_create']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.memos_create', 'file.organize_downloads', 'file.list_directory']`
- **Missing in Top 10**: `['file.stats']`
- **Actual Route**: Lane `LANE_0`, Intent `find_duplicates`
- **Detail**: Missing capabilities in Top-10: ['file.stats']

### Failure 89: `Search Google for recent news on customer feedback, save top 3 article links, and open first link in Chrome.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['news.search', 'knowledge.save', 'browser.open_url']`
- **Canonical Expected**: `['rag.search_news', 'knowledge.save', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'rag.search_web', 'browser.click', 'rag.search_news', 'app.install_software']`
- **Missing in Top 10**: `['knowledge.save', 'browser.open_url']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['knowledge.save', 'browser.open_url']

### Failure 90: `Take a screenshot of current customer feedback dashboard, save to Desktop, and draft email to support team.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'file.save', 'email.draft']`
- **Canonical Expected**: `['windows.screenshot', 'file.create_folder', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'system.dashboard', 'system.devices', 'system.time', 'windows.brightness_get']`
- **Missing in Top 10**: `['google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.gmail_send']

### Failure 91: `Find thermal_stress.log in Documents, extract key summary points, and draft an update to Systems Architect.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'email.draft']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'file.find', 'rag.meeting_notes', 'system.time', 'system.devices']`
- **Missing in Top 10**: `['rag.document_qa', 'google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'google.gmail_send']

### Failure 92: `Retrieve latest notes on hardware telemetry, format them into bullet points, and open in Notepad.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['rag.search_notes', 'knowledge.format', 'app.open']`
- **Canonical Expected**: `['rag.search_notes', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['app.open', 'system.info', 'system.diagnostics', 'rag.memos_recent', 'rag.search_web']`
- **Missing in Top 10**: `['rag.search_notes', 'rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.search_notes', 'rag.document_qa']

### Failure 93: `Check if Systems Architect sent any WhatsApp messages about hardware telemetry, summarize the thread, and notify me.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['whatsapp.read', 'knowledge.summarize', 'system.notify']`
- **Canonical Expected**: `['whatsapp.read', 'rag.document_qa', 'system.dashboard']`
- **Retrieved (Top 5)**: `['system.info', 'system.diagnostics', 'whatsapp.read', 'whatsapp.send', 'whatsapp.summarize']`
- **Missing in Top 10**: `['rag.document_qa', 'system.dashboard']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa', 'system.dashboard']

### Failure 94: `Find newest hardware telemetry PDF, extract main findings, open source reference in browser, and push file to phone.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'browser.open_url', 'phone.send_file']`
- **Retrieved (Top 5)**: `['phone.send_file', 'file.find', 'app.open', 'system.info', 'file.find_duplicates']`
- **Missing in Top 10**: `['rag.document_qa']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['rag.document_qa']

### Failure 95: `Scan Downloads for hardware telemetry documents, calculate total storage used, and create a status memo.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'file.stats', 'rag.memos_create']`
- **Canonical Expected**: `['file.find', 'file.stats', 'rag.memos_create']`
- **Retrieved (Top 5)**: `['file.find_duplicates', 'system.info', 'file.find', 'system.diagnostics', 'rag.memos_create']`
- **Missing in Top 10**: `['file.stats']`
- **Actual Route**: Lane `LANE_0`, Intent `find_duplicates`
- **Detail**: Missing capabilities in Top-10: ['file.stats']

### Failure 96: `Search Google for recent news on hardware telemetry, save top 3 article links, and open first link in Chrome.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['news.search', 'knowledge.save', 'browser.open_url']`
- **Canonical Expected**: `['rag.search_news', 'knowledge.save', 'browser.open_url']`
- **Retrieved (Top 5)**: `['app.open', 'system.info', 'rag.search_web', 'system.diagnostics', 'browser.click']`
- **Missing in Top 10**: `['knowledge.save', 'browser.open_url']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['knowledge.save', 'browser.open_url']

### Failure 97: `Take a screenshot of current hardware telemetry dashboard, save to Desktop, and draft email to firmware team.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['system.screenshot', 'file.save', 'email.draft']`
- **Canonical Expected**: `['windows.screenshot', 'file.create_folder', 'google.gmail_send']`
- **Retrieved (Top 5)**: `['windows.screenshot', 'system.info', 'system.dashboard', 'system.diagnostics', 'system.devices']`
- **Missing in Top 10**: `['google.gmail_send']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['google.gmail_send']

### Failure 98: `Close VS Code, open Terminal, and set system volume to 35 percent.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['app.close', 'app.open', 'system.volume_set']`
- **Canonical Expected**: `['app.close', 'app.open', 'windows.volume_set']`
- **Retrieved (Top 5)**: `['windows.volume_set', 'system.voice_set', 'system.devices', 'system.microphone_status', 'windows.brightness_set']`
- **Missing in Top 10**: `['app.open']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['app.open']

### Failure 99: `Close Excel, open Calculator, and set system volume to 35 percent.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['app.close', 'app.open', 'system.volume_set']`
- **Canonical Expected**: `['app.close', 'app.open', 'windows.volume_set']`
- **Retrieved (Top 5)**: `['windows.volume_set', 'app.open', 'system.voice_set', 'system.devices', 'system.microphone_status']`
- **Missing in Top 10**: `['app.close']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['app.close']

### Failure 100: `Close Word, open Chrome, and set system volume to 35 percent.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['app.close', 'app.open', 'system.volume_set']`
- **Canonical Expected**: `['app.close', 'app.open', 'windows.volume_set']`
- **Retrieved (Top 5)**: `['app.open', 'windows.volume_set', 'system.voice_set', 'system.devices', 'system.microphone_status']`
- **Missing in Top 10**: `['app.close']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['app.close']

### Failure 101: `Close Spotify, open Discord, and set system volume to 35 percent.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['app.close', 'app.open', 'system.volume_set']`
- **Canonical Expected**: `['app.close', 'app.open', 'windows.volume_set']`
- **Retrieved (Top 5)**: `['windows.volume_set', 'app.close', 'windows.close_window', 'system.voice_set', 'system.devices']`
- **Missing in Top 10**: `['app.open']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['app.open']

### Failure 102: `Close Photoshop, open File Explorer, and set system volume to 35 percent.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['app.close', 'app.open', 'system.volume_set']`
- **Canonical Expected**: `['app.close', 'app.open', 'windows.volume_set']`
- **Retrieved (Top 5)**: `['windows.volume_set', 'file.open', 'app.open', 'system.voice_set', 'system.devices']`
- **Missing in Top 10**: `['app.close']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['app.close']

### Failure 103: `Close Slack, open Outlook, and set system volume to 35 percent.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['app.close', 'app.open', 'system.volume_set']`
- **Canonical Expected**: `['app.close', 'app.open', 'windows.volume_set']`
- **Retrieved (Top 5)**: `['windows.volume_set', 'system.voice_set', 'system.devices', 'system.microphone_status', 'windows.brightness_set']`
- **Missing in Top 10**: `['app.close', 'app.open']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['app.close', 'app.open']

### Failure 104: `Close PowerPoint, open Zoom, and set system volume to 35 percent.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['app.close', 'app.open', 'system.volume_set']`
- **Canonical Expected**: `['app.close', 'app.open', 'windows.volume_set']`
- **Retrieved (Top 5)**: `['windows.volume_set', 'system.voice_set', 'system.diagnostics', 'system.info', 'system.devices']`
- **Missing in Top 10**: `['app.close', 'app.open']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['app.close', 'app.open']

### Failure 105: `Close Edge, open OneNote, and set system volume to 35 percent.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['app.close', 'app.open', 'system.volume_set']`
- **Canonical Expected**: `['app.close', 'app.open', 'windows.volume_set']`
- **Retrieved (Top 5)**: `['windows.volume_set', 'app.close', 'windows.close_window', 'system.voice_set', 'system.devices']`
- **Missing in Top 10**: `['app.open']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['app.open']

### Failure 106: `Close GitKraken, open Postman, and set system volume to 35 percent.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['app.close', 'app.open', 'system.volume_set']`
- **Canonical Expected**: `['app.close', 'app.open', 'windows.volume_set']`
- **Retrieved (Top 5)**: `['windows.volume_set', 'system.voice_set', 'system.devices', 'system.microphone_status', 'windows.brightness_set']`
- **Missing in Top 10**: `['app.close', 'app.open']`
- **Actual Route**: Lane `LANE_2`, Intent `None`
- **Detail**: Missing capabilities in Top-10: ['app.close', 'app.open']

### Failure 107: `Execute coordinated multi-capability workflow sequence #146 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 108: `Execute coordinated multi-capability workflow sequence #147 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 109: `Execute coordinated multi-capability workflow sequence #148 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 110: `Execute coordinated multi-capability workflow sequence #149 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 111: `Execute coordinated multi-capability workflow sequence #150 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 112: `Execute coordinated multi-capability workflow sequence #151 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 113: `Execute coordinated multi-capability workflow sequence #152 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 114: `Execute coordinated multi-capability workflow sequence #153 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 115: `Execute coordinated multi-capability workflow sequence #154 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 116: `Execute coordinated multi-capability workflow sequence #155 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 117: `Execute coordinated multi-capability workflow sequence #156 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 118: `Execute coordinated multi-capability workflow sequence #157 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 119: `Execute coordinated multi-capability workflow sequence #158 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 120: `Execute coordinated multi-capability workflow sequence #159 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 121: `Execute coordinated multi-capability workflow sequence #160 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 122: `Execute coordinated multi-capability workflow sequence #161 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 123: `Execute coordinated multi-capability workflow sequence #162 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 124: `Execute coordinated multi-capability workflow sequence #163 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 125: `Execute coordinated multi-capability workflow sequence #164 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 126: `Execute coordinated multi-capability workflow sequence #165 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 127: `Execute coordinated multi-capability workflow sequence #166 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 128: `Execute coordinated multi-capability workflow sequence #167 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 129: `Execute coordinated multi-capability workflow sequence #168 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 130: `Execute coordinated multi-capability workflow sequence #169 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 131: `Execute coordinated multi-capability workflow sequence #170 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 132: `Execute coordinated multi-capability workflow sequence #171 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 133: `Execute coordinated multi-capability workflow sequence #172 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 134: `Execute coordinated multi-capability workflow sequence #173 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 135: `Execute coordinated multi-capability workflow sequence #174 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 136: `Execute coordinated multi-capability workflow sequence #175 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 137: `Execute coordinated multi-capability workflow sequence #176 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 138: `Execute coordinated multi-capability workflow sequence #177 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 139: `Execute coordinated multi-capability workflow sequence #178 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 140: `Execute coordinated multi-capability workflow sequence #179 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 141: `Execute coordinated multi-capability workflow sequence #180 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 142: `Execute coordinated multi-capability workflow sequence #181 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 143: `Execute coordinated multi-capability workflow sequence #182 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 144: `Execute coordinated multi-capability workflow sequence #183 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 145: `Execute coordinated multi-capability workflow sequence #184 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 146: `Execute coordinated multi-capability workflow sequence #185 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 147: `Execute coordinated multi-capability workflow sequence #186 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 148: `Execute coordinated multi-capability workflow sequence #187 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 149: `Execute coordinated multi-capability workflow sequence #188 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 150: `Execute coordinated multi-capability workflow sequence #189 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 151: `Execute coordinated multi-capability workflow sequence #190 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 152: `Execute coordinated multi-capability workflow sequence #191 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 153: `Execute coordinated multi-capability workflow sequence #192 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 154: `Execute coordinated multi-capability workflow sequence #193 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 155: `Execute coordinated multi-capability workflow sequence #194 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 156: `Execute coordinated multi-capability workflow sequence #195 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 157: `Execute coordinated multi-capability workflow sequence #196 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 158: `Execute coordinated multi-capability workflow sequence #197 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 159: `Execute coordinated multi-capability workflow sequence #198 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 160: `Execute coordinated multi-capability workflow sequence #199 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 161: `Execute coordinated multi-capability workflow sequence #200 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'windows.close_window']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 162: `Execute coordinated multi-capability workflow sequence #201 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 163: `Execute coordinated multi-capability workflow sequence #202 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 164: `Execute coordinated multi-capability workflow sequence #203 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 165: `Execute coordinated multi-capability workflow sequence #204 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 166: `Execute coordinated multi-capability workflow sequence #205 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 167: `Execute coordinated multi-capability workflow sequence #206 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 168: `Execute coordinated multi-capability workflow sequence #207 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 169: `Execute coordinated multi-capability workflow sequence #208 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 170: `Execute coordinated multi-capability workflow sequence #209 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

### Failure 171: `Execute coordinated multi-capability workflow sequence #210 across system and local resources.`

- **Root Cause**: CAPABILITY_NOT_RETRIEVED
- **Expected Capabilities**: `['file.search', 'knowledge.summarize', 'app.open']`
- **Canonical Expected**: `['file.find', 'rag.document_qa', 'app.open']`
- **Retrieved (Top 5)**: `['workflow.run_tests', 'system.diagnostics', 'app.refresh_catalog', 'terminal.powershell', 'system.info']`
- **Missing in Top 10**: `['file.find', 'rag.document_qa', 'app.open']`
- **Actual Route**: Lane `LANE_0`, Intent `run_project_tests`
- **Detail**: Missing capabilities in Top-10: ['file.find', 'rag.document_qa', 'app.open']

