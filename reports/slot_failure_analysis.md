# JARVIS EDGE — Slot Extraction Failure Analysis Report

**Total Records Evaluated**: 575
**Precision**: 88.05%
**Recall**: 93.57%
**F1 Score**: 90.73%
**Total Failure Cases**: 110

## Root Cause Breakdown

- **APP**: 79
- **NEGATED SLOT**: 8
- **SEARCH QUERY**: 7
- **CORRECTED SLOT**: 5
- **CONSTRAINT**: 4
- **CONTACT**: 2
- **RESOURCE REF**: 1
- **PERCENTAGE**: 1
- **ORDINAL**: 1
- **FILE TYPE**: 1
- **FOLDER**: 1

---

## Detailed Failure Audit

### Failure 1: `What is it about?`

- **Category**: contextual
- **Root Cause**: RESOURCE REF
- **Expected Slots**: `{"pronoun": "it"}`
- **Actual Slots**: `{}`
- **Missing**: `[('pronoun', 'it')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 2: `Send this to Arun on WhatsApp.`

- **Category**: contextual
- **Root Cause**: CONTACT
- **Expected Slots**: `{"pronoun": "this", "recipient": "Arun"}`
- **Actual Slots**: `{"pronoun": "this", "name": "send this to arun on whatsapp"}`
- **Missing**: `[('recipient', 'Arun')]`
- **Wrong Value**: `[]`
- **Extra**: `[('name', 'send this to arun on whatsapp')]`

### Failure 3: `Start VLC player—sorry, Spotify instead.`

- **Category**: corrections
- **Root Cause**: CORRECTED SLOT
- **Expected Slots**: `{"name": "spotify"}`
- **Actual Slots**: `{"name": "vlc player\u2014sorry , spotify instead"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'spotify', 'vlc player—sorry , spotify instead')]`
- **Extra**: `[]`

### Failure 4: `Send message to Arun—no, Arun Kumar.`

- **Category**: corrections
- **Root Cause**: CONTACT
- **Expected Slots**: `{"recipient": "Arun Kumar"}`
- **Actual Slots**: `{"contact": "arun kumar", "recipient": "Arun"}`
- **Missing**: `[]`
- **Wrong Value**: `[('recipient', 'Arun Kumar', 'Arun')]`
- **Extra**: `[('contact', 'arun kumar')]`

### Failure 5: `Draft email to Sarah, actually make that Sarah Jenkins.`

- **Category**: corrections
- **Root Cause**: CORRECTED SLOT
- **Expected Slots**: `{"recipient": "Sarah Jenkins"}`
- **Actual Slots**: `{"pronoun": "that", "text": "Draft email to Sarah, actually make that Sarah Jenkins."}`
- **Missing**: `[('recipient', 'Sarah Jenkins')]`
- **Wrong Value**: `[]`
- **Extra**: `[('pronoun', 'that'), ('text', 'Draft email to Sarah, actually make that Sarah Jenkins.')]`

### Failure 6: `Volume 80—sorry, 50 percent.`

- **Category**: corrections
- **Root Cause**: PERCENTAGE
- **Expected Slots**: `{"percent": 50}`
- **Actual Slots**: `{"percent": 80}`
- **Missing**: `[]`
- **Wrong Value**: `[('percent', 50, 80)]`
- **Extra**: `[]`

### Failure 7: `Turn volume down to 30, no wait, 20.`

- **Category**: corrections
- **Root Cause**: CORRECTED SLOT
- **Expected Slots**: `{"percent": 20}`
- **Actual Slots**: `{"percent": 30}`
- **Missing**: `[]`
- **Wrong Value**: `[('percent', 20, 30)]`
- **Extra**: `[]`

### Failure 8: `Find yesterday's PDF. Actually, Monday's.`

- **Category**: corrections
- **Root Cause**: CORRECTED SLOT
- **Expected Slots**: `{"day": "Monday"}`
- **Actual Slots**: `{"query": "yesterday's pdf. actually , monday's", "extension": "pdf", "limit": 100}`
- **Missing**: `[('day', 'Monday')]`
- **Wrong Value**: `[]`
- **Extra**: `[('query', "yesterday's pdf. actually , monday's"), ('extension', 'pdf'), ('limit', 100)]`

### Failure 9: `Open the second file—sorry, the third.`

- **Category**: corrections
- **Root Cause**: ORDINAL
- **Expected Slots**: `{"ordinal": 3}`
- **Actual Slots**: `{"ordinals": [2, 3]}`
- **Missing**: `[('ordinal', 3)]`
- **Wrong Value**: `[]`
- **Extra**: `[('ordinals', [2, 3])]`

### Failure 10: `Open Notepad—actually VS Code.`

- **Category**: corrections
- **Root Cause**: CORRECTED SLOT
- **Expected Slots**: `{"name": "vs code"}`
- **Actual Slots**: `{"name": "vscode"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'vs code', 'vscode')]`
- **Extra**: `[]`

### Failure 11: `Launch Notepad, sorry I meant VS Code.`

- **Category**: corrections
- **Root Cause**: APP
- **Expected Slots**: `{"name": "vs code"}`
- **Actual Slots**: `{"name": "vscode"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'vs code', 'vscode')]`
- **Extra**: `[]`

### Failure 12: `Bring up Notepad... wait, VS Code please.`

- **Category**: corrections
- **Root Cause**: APP
- **Expected Slots**: `{"name": "vs code"}`
- **Actual Slots**: `{"name": "vscode"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'vs code', 'vscode')]`
- **Extra**: `[]`

### Failure 13: `Chrome on screen please.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{"name": "chrome on screen"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'chrome', 'chrome on screen')]`
- **Extra**: `[]`

### Failure 14: `Latest tech news?`

- **Category**: implicit
- **Root Cause**: SEARCH QUERY
- **Expected Slots**: `{"query": "tech"}`
- **Actual Slots**: `{}`
- **Missing**: `[('query', 'tech')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 15: `File Explorer window please.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "explorer"}`
- **Actual Slots**: `{"name": "explorer window"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'explorer', 'explorer window')]`
- **Extra**: `[]`

### Failure 16: `I need to write something in Notepad.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"name": "to write something in notepad", "text": "I need to write something in Notepad."}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'notepad', 'to write something in notepad')]`
- **Extra**: `[('text', 'I need to write something in Notepad.')]`

### Failure 17: `Need to do some math calculations.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "calculator"}`
- **Actual Slots**: `{"name": "need to do some math calculations"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'calculator', 'need to do some math calculations')]`
- **Extra**: `[]`

### Failure 18: `Need to browse the web.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'chrome')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 19: `Spotify on screen please.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "spotify"}`
- **Actual Slots**: `{"name": "spotify on screen"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'spotify', 'spotify on screen')]`
- **Extra**: `[]`

### Failure 20: `I need Terminal.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "terminal"}`
- **Actual Slots**: `{"raw_app": "terminal", "candidates": ["Windows Terminal", "Command Prompt", "PowerShell"]}`
- **Missing**: `[('name', 'terminal')]`
- **Wrong Value**: `[]`
- **Extra**: `[('raw_app', 'terminal'), ('candidates', ['Windows Terminal', 'Command Prompt', 'PowerShell'])]`

### Failure 21: `Terminal on screen please.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "terminal"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'terminal')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 22: `I need Word.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "word"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'word')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 23: `Word on screen please.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "word"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'word')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 24: `I need Excel.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "excel"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'excel')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 25: `Excel on screen please.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "excel"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'excel')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 26: `I need Edge.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "edge"}`
- **Actual Slots**: `{"name": "i need edge"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'edge', 'i need edge')]`
- **Extra**: `[]`

### Failure 27: `Edge on screen please.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "edge"}`
- **Actual Slots**: `{"name": "edge on screen"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'edge', 'edge on screen')]`
- **Extra**: `[]`

### Failure 28: `I need Powerpoint.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "powerpoint"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'powerpoint')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 29: `Powerpoint on screen please.`

- **Category**: implicit
- **Root Cause**: APP
- **Expected Slots**: `{"name": "powerpoint"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'powerpoint')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 30: `Don't open Chrome.`

- **Category**: negation
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'chrome')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 31: `Do not launch Notepad.`

- **Category**: negation
- **Root Cause**: NEGATED SLOT
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'notepad')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 32: `Never open Calculator.`

- **Category**: negation
- **Root Cause**: APP
- **Expected Slots**: `{"name": "calculator"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'calculator')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 33: `Open Calculator but not Notepad.`

- **Category**: negation
- **Root Cause**: NEGATED SLOT
- **Expected Slots**: `{"name": "calculator"}`
- **Actual Slots**: `{"raw_app": "calculator but not notepad", "candidates": ["notepad", "calculator"], "name": "calculator but not notepad"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'calculator', 'calculator but not notepad')]`
- **Extra**: `[('raw_app', 'calculator but not notepad'), ('candidates', ['notepad', 'calculator'])]`

### Failure 34: `Search for files about budget but do not delete anything.`

- **Category**: negation
- **Root Cause**: NEGATED SLOT
- **Expected Slots**: `{"query": "budget"}`
- **Actual Slots**: `{"query": "files about budget but do not delete anything", "limit": 100}`
- **Missing**: `[]`
- **Wrong Value**: `[('query', 'budget', 'files about budget but do not delete anything')]`
- **Extra**: `[('limit', 100)]`

### Failure 35: `Please run Edge but definitely not Chrome.`

- **Category**: negation
- **Root Cause**: NEGATED SLOT
- **Expected Slots**: `{"name": "edge"}`
- **Actual Slots**: `{"raw_app": "edge but definitely not chrome", "candidates": ["chrome", "edge"], "name": "edge but definitely not chrome"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'edge', 'edge but definitely not chrome')]`
- **Extra**: `[('raw_app', 'edge but definitely not chrome'), ('candidates', ['chrome', 'edge'])]`

### Failure 36: `Please run Word but definitely not Notepad.`

- **Category**: negation
- **Root Cause**: NEGATED SLOT
- **Expected Slots**: `{"name": "word"}`
- **Actual Slots**: `{"name": "word but definitely not notepad"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'word', 'word but definitely not notepad')]`
- **Extra**: `[]`

### Failure 37: `Please run Excel but definitely not Calculator.`

- **Category**: negation
- **Root Cause**: NEGATED SLOT
- **Expected Slots**: `{"name": "excel"}`
- **Actual Slots**: `{"name": "excel but definitely not calculator"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'excel', 'excel but definitely not calculator')]`
- **Extra**: `[]`

### Failure 38: `Please run Spotify but definitely not VLC.`

- **Category**: negation
- **Root Cause**: NEGATED SLOT
- **Expected Slots**: `{"name": "spotify"}`
- **Actual Slots**: `{"raw_app": "spotify but definitely not vlc", "candidates": ["vlc", "spotify"], "name": "spotify but definitely not vlc"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'spotify', 'spotify but definitely not vlc')]`
- **Extra**: `[('raw_app', 'spotify but definitely not vlc'), ('candidates', ['vlc', 'spotify'])]`

### Failure 39: `Please run Chrome but definitely not Firefox.`

- **Category**: negation
- **Root Cause**: NEGATED SLOT
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{"raw_app": "chrome but definitely not firefox", "candidates": ["chrome", "firefox"], "name": "chrome but definitely not firefox"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'chrome', 'chrome but definitely not firefox')]`
- **Extra**: `[('raw_app', 'chrome but definitely not firefox'), ('candidates', ['chrome', 'firefox'])]`

### Failure 40: `chekc if vlc installed`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "vlc"}`
- **Actual Slots**: `{"name": "chekc if vlc installed"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'vlc', 'chekc if vlc installed')]`
- **Extra**: `[]`

### Failure 41: `wher is chrom installed`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{"package_name": "wher is chrom"}`
- **Missing**: `[('name', 'chrome')]`
- **Wrong Value**: `[]`
- **Extra**: `[('package_name', 'wher is chrom')]`

### Failure 42: `launsh calc`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "calculator"}`
- **Actual Slots**: `{"name": "launsh calc"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'calculator', 'launsh calc')]`
- **Extra**: `[]`

### Failure 43: `strt calc`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "calculator"}`
- **Actual Slots**: `{"name": "strt calc"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'calculator', 'strt calc')]`
- **Extra**: `[]`

### Failure 44: `launsh chrom`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'chrome')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 45: `strt chrom`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'chrome')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 46: `opn notepd`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"name": "notepd", "text": "opn notepd"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'notepad', 'notepd')]`
- **Extra**: `[('text', 'opn notepd')]`

### Failure 47: `launsh notepd`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"text": "launsh notepd"}`
- **Missing**: `[('name', 'notepad')]`
- **Wrong Value**: `[]`
- **Extra**: `[('text', 'launsh notepd')]`

### Failure 48: `strt notepd`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"text": "strt notepd"}`
- **Missing**: `[('name', 'notepad')]`
- **Wrong Value**: `[]`
- **Extra**: `[('text', 'strt notepd')]`

### Failure 49: `open up notepd`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"name": "notepd"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'notepad', 'notepd')]`
- **Extra**: `[]`

### Failure 50: `opn spotfy`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "spotify"}`
- **Actual Slots**: `{"name": "spotfy"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'spotify', 'spotfy')]`
- **Extra**: `[]`

### Failure 51: `launsh spotfy`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "spotify"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'spotify')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 52: `strt spotfy`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "spotify"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'spotify')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 53: `open up spotfy`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "spotify"}`
- **Actual Slots**: `{"name": "spotfy"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'spotify', 'spotfy')]`
- **Extra**: `[]`

### Failure 54: `opn explorr`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "explorer"}`
- **Actual Slots**: `{"name": "explorr"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'explorer', 'explorr')]`
- **Extra**: `[]`

### Failure 55: `launsh explorr`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "explorer"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'explorer')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 56: `strt explorr`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "explorer"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'explorer')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 57: `open up explorr`

- **Category**: noisy
- **Root Cause**: APP
- **Expected Slots**: `{"name": "explorer"}`
- **Actual Slots**: `{"name": "explorr"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'explorer', 'explorr')]`
- **Extra**: `[]`

### Failure 58: `Please fire up Google Chrome.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{"name": "fire up chrome"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'chrome', 'fire up chrome')]`
- **Extra**: `[]`

### Failure 59: `Get VLC media player rolling.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "vlc"}`
- **Actual Slots**: `{"action": "play"}`
- **Missing**: `[('name', 'vlc')]`
- **Wrong Value**: `[]`
- **Extra**: `[('action', 'play')]`

### Failure 60: `Would you mind opening VS Code?`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "vscode"}`
- **Actual Slots**: `{"name": "mind opening vs code"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'vscode', 'mind opening vs code')]`
- **Extra**: `[]`

### Failure 61: `Can you spawn a Notepad window?`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"name": "spawn a notepad"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'notepad', 'spawn a notepad')]`
- **Extra**: `[]`

### Failure 62: `I would like to have Chrome opened up.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{"name": "i would like to have chrome opened"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'chrome', 'i would like to have chrome opened')]`
- **Extra**: `[]`

### Failure 63: `Jarvis, start up my calculator app.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "calculator"}`
- **Actual Slots**: `{"name": "up my calculator"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'calculator', 'up my calculator')]`
- **Extra**: `[]`

### Failure 64: `Run the notepad editor.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"name": "notepad editor"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'notepad', 'notepad editor')]`
- **Extra**: `[]`

### Failure 65: `Display the Chrome web browser.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'chrome')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 66: `Please to open calculator window.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "calculator"}`
- **Actual Slots**: `{"name": "to open calculator window"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'calculator', 'to open calculator window')]`
- **Extra**: `[]`

### Failure 67: `Could you bring Excel onto the desktop?`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "excel"}`
- **Actual Slots**: `{"folder": "Desktop", "path": "Desktop"}`
- **Missing**: `[('name', 'excel')]`
- **Wrong Value**: `[]`
- **Extra**: `[('folder', 'Desktop'), ('path', 'Desktop')]`

### Failure 68: `Initialize Powerpoint presentation software.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "powerpoint"}`
- **Actual Slots**: `{}`
- **Missing**: `[('name', 'powerpoint')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 69: `Let us open Word document app.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "word"}`
- **Actual Slots**: `{"name": "let us open word document"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'word', 'let us open word document')]`
- **Extra**: `[]`

### Failure 70: `Fire up Microsoft Edge for browsing.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "edge"}`
- **Actual Slots**: `{"name": "fire up edge for browsing"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'edge', 'fire up edge for browsing')]`
- **Extra**: `[]`

### Failure 71: `Pop open a fresh Notepad sheet.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"name": "pop open a fresh notepad sheet"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'notepad', 'pop open a fresh notepad sheet')]`
- **Extra**: `[]`

### Failure 72: `Put Chrome in front of me.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{"name": "chrome in front of me"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'chrome', 'chrome in front of me')]`
- **Extra**: `[]`

### Failure 73: `Start up terminal console.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "terminal"}`
- **Actual Slots**: `{"name": "up terminal console"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'terminal', 'up terminal console')]`
- **Extra**: `[]`

### Failure 74: `Shut down Notepad immediately.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"name": "shut down notepad"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'notepad', 'shut down notepad')]`
- **Extra**: `[]`

### Failure 75: `Kill Chrome browser process.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{"name": "chrome browser process"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'chrome', 'chrome browser process')]`
- **Extra**: `[]`

### Failure 76: `Terminate VLC player.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "vlc"}`
- **Actual Slots**: `{"name": "terminate vlc player"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'vlc', 'terminate vlc player')]`
- **Extra**: `[]`

### Failure 77: `Could you close down Spotify?`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "spotify"}`
- **Actual Slots**: `{"name": "down spotify"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'spotify', 'down spotify')]`
- **Extra**: `[]`

### Failure 78: `Search for files matching quarterly budget in Documents.`

- **Category**: paraphrase
- **Root Cause**: SEARCH QUERY
- **Expected Slots**: `{"folder": "Documents", "query": "quarterly budget"}`
- **Actual Slots**: `{"query": "files matching quarterly budget in documents", "folder": "Documents", "limit": 100}`
- **Missing**: `[]`
- **Wrong Value**: `[('query', 'quarterly budget', 'files matching quarterly budget in documents')]`
- **Extra**: `[('limit', 100)]`

### Failure 79: `Check whether Microsoft Visual Studio Code exists on my PC.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "vscode"}`
- **Actual Slots**: `{"name": "check whether microsoft vscode exists"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'vscode', 'check whether microsoft vscode exists')]`
- **Extra**: `[]`

### Failure 80: `Is Google Chrome installed anywhere on this machine?`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{"pronoun": "this", "package_name": "google chrome installed anywhere"}`
- **Missing**: `[('name', 'chrome')]`
- **Wrong Value**: `[]`
- **Extra**: `[('pronoun', 'this'), ('package_name', 'google chrome installed anywhere')]`

### Failure 81: `Where is the executable path for Notepad located?`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"name": "executable path for notepad"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'notepad', 'executable path for notepad')]`
- **Extra**: `[]`

### Failure 82: `Give me the file system location of VLC player.`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "vlc"}`
- **Actual Slots**: `{"name": "vlc player"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'vlc', 'vlc player')]`
- **Extra**: `[]`

### Failure 83: `Jot down a quick note: remember to review project pull request.`

- **Category**: paraphrase
- **Root Cause**: CONSTRAINT
- **Expected Slots**: `{"text": "remember to review project pull request"}`
- **Actual Slots**: `{"text": "jot down a quick note remember to review project pull request"}`
- **Missing**: `[]`
- **Wrong Value**: `[('text', 'remember to review project pull request', 'jot down a quick note remember to review project pull request')]`
- **Extra**: `[]`

### Failure 84: `Capture memo saying submit expenses before Friday.`

- **Category**: paraphrase
- **Root Cause**: CONSTRAINT
- **Expected Slots**: `{"text": "submit expenses before Friday"}`
- **Actual Slots**: `{"text": "capture memo saying submit expenses before friday"}`
- **Missing**: `[]`
- **Wrong Value**: `[('text', 'submit expenses before Friday', 'capture memo saying submit expenses before friday')]`
- **Extra**: `[]`

### Failure 85: `Look through my saved notes for machine learning.`

- **Category**: paraphrase
- **Root Cause**: SEARCH QUERY
- **Expected Slots**: `{"query": "machine learning"}`
- **Actual Slots**: `{"query": "look through my saved notes for machine learning"}`
- **Missing**: `[]`
- **Wrong Value**: `[('query', 'machine learning', 'look through my saved notes for machine learning')]`
- **Extra**: `[]`

### Failure 86: `What are the breaking headlines in India today?`

- **Category**: paraphrase
- **Root Cause**: SEARCH QUERY
- **Expected Slots**: `{"query": "India"}`
- **Actual Slots**: `{}`
- **Missing**: `[('query', 'India')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 87: `Launch notepad text editor right away`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"name": "notepad text editor right away"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'notepad', 'notepad text editor right away')]`
- **Extra**: `[]`

### Failure 88: `Start up Google Chrome please`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{"name": "up chrome"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'chrome', 'up chrome')]`
- **Extra**: `[]`

### Failure 89: `Get calculator open on desktop`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "calculator"}`
- **Actual Slots**: `{"name": "calculator open on desktop", "folder": "Desktop"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'calculator', 'calculator open on desktop')]`
- **Extra**: `[('folder', 'Desktop')]`

### Failure 90: `Open up paint application`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "paint"}`
- **Actual Slots**: `{"raw_app": "paint", "candidates": ["MS Paint", "Paint.NET"], "name": "up paint"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'paint', 'up paint')]`
- **Extra**: `[('raw_app', 'paint'), ('candidates', ['MS Paint', 'Paint.NET'])]`

### Failure 91: `Launch vlc video player`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "vlc"}`
- **Actual Slots**: `{"name": "vlc video"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'vlc', 'vlc video')]`
- **Extra**: `[]`

### Failure 92: `Find word documents in Documents directory`

- **Category**: paraphrase
- **Root Cause**: FILE TYPE
- **Expected Slots**: `{"folder": "Documents", "extension": "docx"}`
- **Actual Slots**: `{"query": "word documents in documents directory", "folder": "Documents", "directory": "Documents"}`
- **Missing**: `[('extension', 'docx')]`
- **Wrong Value**: `[]`
- **Extra**: `[('query', 'word documents in documents directory'), ('directory', 'Documents')]`

### Failure 93: `Sort out all downloaded files into neat folders`

- **Category**: paraphrase
- **Root Cause**: FOLDER
- **Expected Slots**: `{"folder": "Downloads"}`
- **Actual Slots**: `{}`
- **Missing**: `[('folder', 'Downloads')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 94: `Verify if Visual Studio is installed`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "visual studio"}`
- **Actual Slots**: `{"name": "verify if visual studio"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'visual studio', 'verify if visual studio')]`
- **Extra**: `[]`

### Failure 95: `Find the location of Chrome on disk`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{"query": "the location of chrome on disk", "name": "find the location of chrome on disk"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'chrome', 'find the location of chrome on disk')]`
- **Extra**: `[('query', 'the location of chrome on disk')]`

### Failure 96: `Write a note: call bank tomorrow at 10 AM`

- **Category**: paraphrase
- **Root Cause**: CONSTRAINT
- **Expected Slots**: `{"text": "call bank tomorrow at 10 AM"}`
- **Actual Slots**: `{"text": "a note call bank tomorrow at 10 am"}`
- **Missing**: `[]`
- **Wrong Value**: `[('text', 'call bank tomorrow at 10 AM', 'a note call bank tomorrow at 10 am')]`
- **Extra**: `[]`

### Failure 97: `Query saved notes for budget 2026`

- **Category**: paraphrase
- **Root Cause**: SEARCH QUERY
- **Expected Slots**: `{"query": "budget 2026"}`
- **Actual Slots**: `{"query": "query saved notes for budget 2026"}`
- **Missing**: `[]`
- **Wrong Value**: `[('query', 'budget 2026', 'query saved notes for budget 2026')]`
- **Extra**: `[]`

### Failure 98: `Check if Spotify desktop player is installed`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "spotify"}`
- **Actual Slots**: `{"name": "spotify desktop player", "folder": "Desktop"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'spotify', 'spotify desktop player')]`
- **Extra**: `[('folder', 'Desktop')]`

### Failure 99: `Where is python executable installed?`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "python"}`
- **Actual Slots**: `{"name": "python executable"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'python', 'python executable')]`
- **Extra**: `[]`

### Failure 100: `Bring Chrome forward`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "chrome"}`
- **Actual Slots**: `{"name": "bring chrome forward"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'chrome', 'bring chrome forward')]`
- **Extra**: `[]`

### Failure 101: `Pop up Calculator right here`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "calculator"}`
- **Actual Slots**: `{"name": "pop up calculator right here"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'calculator', 'pop up calculator right here')]`
- **Extra**: `[]`

### Failure 102: `Fire up Notepad quickly`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"name": "fire up notepad"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'notepad', 'fire up notepad')]`
- **Extra**: `[]`

### Failure 103: `Search headlines for tech news`

- **Category**: paraphrase
- **Root Cause**: SEARCH QUERY
- **Expected Slots**: `{"query": "tech"}`
- **Actual Slots**: `{}`
- **Missing**: `[('query', 'tech')]`
- **Wrong Value**: `[]`
- **Extra**: `[]`

### Failure 104: `Record a note: buy groceries tonight`

- **Category**: paraphrase
- **Root Cause**: CONSTRAINT
- **Expected Slots**: `{"text": "buy groceries tonight"}`
- **Actual Slots**: `{"text": "record a note buy groceries tonight"}`
- **Missing**: `[]`
- **Wrong Value**: `[('text', 'buy groceries tonight', 'record a note buy groceries tonight')]`
- **Extra**: `[]`

### Failure 105: `Search my notes for password hints`

- **Category**: paraphrase
- **Root Cause**: SEARCH QUERY
- **Expected Slots**: `{"query": "password hints"}`
- **Actual Slots**: `{"query": "my notes for password hints"}`
- **Missing**: `[]`
- **Wrong Value**: `[('query', 'password hints', 'my notes for password hints')]`
- **Extra**: `[]`

### Failure 106: `Is VLC media player installed here?`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "vlc"}`
- **Actual Slots**: `{"package_name": "vlc media player installed here"}`
- **Missing**: `[('name', 'vlc')]`
- **Wrong Value**: `[]`
- **Extra**: `[('package_name', 'vlc media player installed here')]`

### Failure 107: `Find executable directory for VS Code`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "vscode"}`
- **Actual Slots**: `{"query": "executable directory for vscode", "name": "find executable directory for vs code"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'vscode', 'find executable directory for vs code')]`
- **Extra**: `[('query', 'executable directory for vscode')]`

### Failure 108: `Check whether Firefox is on this computer`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "firefox"}`
- **Actual Slots**: `{"pronoun": "this", "name": "check whether firefox is"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'firefox', 'check whether firefox is')]`
- **Extra**: `[('pronoun', 'this')]`

### Failure 109: `Open the calculator tool`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "calculator"}`
- **Actual Slots**: `{"name": "calculator tool"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'calculator', 'calculator tool')]`
- **Extra**: `[]`

### Failure 110: `Launch the text editor notepad`

- **Category**: paraphrase
- **Root Cause**: APP
- **Expected Slots**: `{"name": "notepad"}`
- **Actual Slots**: `{"name": "text editor notepad"}`
- **Missing**: `[]`
- **Wrong Value**: `[('name', 'notepad', 'text editor notepad')]`
- **Extra**: `[]`

