# JARVIS EDGE — 520 AGI-Like Task Capabilities

**Important:** Ollama is only the local model runtime. It should not receive unrestricted access to your PC or phone. JARVIS should give the model only the **task-scoped capabilities required for the current user request**, then revoke that scope when the task ends.

## Architecture

```text
Voice / Text / Android
        ↓
STOP / CANCEL safety gate
        ↓
L0 deterministic router
        ↓
Local JDE semantic router
        ↓
Context + ResourceRef resolution
        ↓
Capability retrieval
        ↓
Planner only when needed
        ↓
TaskScopeManager
(only capabilities needed for this task)
        ↓
PolicyEvaluator / confirmations
        ↓
Registered adapters
  Windows API / UIA
  Playwright/CDP
  File/RAG
  IDE adapter
  Android wireless bridge + approved services
        ↓
Execute
        ↓
Verify
        ↓
ActionLedger / CommandOutcome
        ↓
UI / TTS
        ↓
Task grant revoked
```

## Safety/permission invariants

- User-owned/authorized PC and phone only.
- No bypass of lock screen, PIN, password, OTP, UAC, CAPTCHA, or security prompts.
- No arbitrary LLM-generated PowerShell, CMD, ADB shell, JavaScript, or screen coordinates.
- External content is data, never trusted command authority.
- Sending, deleting, installing, submitting, or privileged changes still go through policy/confirmation.
- Consequential `UNCERTAIN` results are never blindly retried.
- Every claimed success requires verification.

## Claude Code rule

Treat every row below as a **semantic capability**, not a sentence to memorize. Reuse typed primitives, generate paraphrases/counterexamples, and keep a frozen unseen holdout.

## PC Apps & Window Control

| # | Feature | Example voice command | How |
|---:|---|---|---|
| 1 | **Universal app launch** | “Open the editor I used earlier.” | Resolve ApplicationRef → launch/focus → verify window |
| 2 | **App alias resolution** | “Open my browser.” | Alias/context → AppCatalog → launch |
| 3 | **Focus running app** | “Bring Spotify to the front.” | Window lookup → focus → verify foreground |
| 4 | **Previous app return** | “Go back to the app I was using.” | Window history → focus previous |
| 5 | **Close current app** | “Close this app.” | Current WindowRef → close → verify |
| 6 | **Close specific window** | “Close only the settings window.” | Resolve WindowRef → close target only |
| 7 | **Minimize window** | “Minimize this.” | Window state API → verify minimized |
| 8 | **Maximize window** | “Make this full screen.” | Window state → maximize/fullscreen → verify |
| 9 | **Restore window** | “Bring this back to normal size.” | Restore window state |
| 10 | **Snap left** | “Put Chrome on the left.” | Resolve window → snap left |
| 11 | **Snap right** | “Put Antigravity on the right.” | Resolve window → snap right |
| 12 | **Side-by-side layout** | “Put Chrome and Antigravity side by side.” | Two WindowRefs → layout manager |
| 13 | **Move window** | “Move this to the other side.” | Window move API |
| 14 | **Resize window** | “Make this window smaller.” | Window resize API |
| 15 | **Move to monitor** | “Move Chrome to my second monitor.” | Display topology → move window |
| 16 | **List open apps** | “What apps are open right now?” | Window/process inventory |
| 17 | **Find hidden window** | “Where did my calculator window go?” | Window inventory → restore/focus |
| 18 | **Switch app by purpose** | “Take me back to my editor.” | Context/app-role resolver |
| 19 | **Open File Explorer** | “Open File Explorer.” | AppCatalog → explorer |
| 20 | **Open Downloads** | “Show my Downloads.” | KnownFolderRef → Explorer |
| 21 | **Open Documents** | “Open Documents.” | KnownFolderRef → Explorer |
| 22 | **Open Desktop folder** | “Open my Desktop folder.” | KnownFolderRef → Explorer |
| 23 | **Open Settings** | “Open Windows Settings.” | System settings capability |
| 24 | **Open specific Settings page** | “Open display settings.” | Settings URI capability |
| 25 | **Open sound settings** | “Take me to sound settings.” | Settings URI |
| 26 | **Open network settings** | “Open network settings.” | Settings URI |
| 27 | **Open Bluetooth settings** | “Open Bluetooth settings.” | Settings URI |
| 28 | **Open app info** | “Show me info for this app.” | Resolve app → app settings |
| 29 | **Detect active window** | “What app am I in?” | Foreground WindowRef |
| 30 | **Detect modal dialog** | “Is there a popup blocking me?” | UIA modal detection |
| 31 | **Close ordinary dialog** | “Close this popup.” | Resolve dialog → invoke Close |
| 32 | **Press semantic button** | “Click Save.” | UIA target resolver → InvokePattern |
| 33 | **Select menu item** | “Open the File menu and choose Save As.” | Menu semantics → invoke |
| 34 | **Switch desktop tab** | “Go to the second tab.” | TabControl resolver → select ordinal |
| 35 | **Choose dropdown option** | “Choose Python from this list.” | ComboBox → select option |
| 36 | **Toggle checkbox** | “Turn that option on.” | Checkbox → TogglePattern |
| 37 | **Select radio option** | “Pick the first option.” | Radio group → ordinal select |
| 38 | **Adjust slider** | “Set this slider to 70 percent.” | RangeValuePattern |
| 39 | **Scroll container** | “Scroll this panel down.” | Semantic container scroll |
| 40 | **Expand tree node** | “Expand this folder tree.” | TreeItem → ExpandCollapse |
| 41 | **Collapse tree node** | “Collapse that section.” | TreeItem collapse |
| 42 | **Read visible control text** | “What does this dialog say?” | UIA text extraction |
| 43 | **Find control by label** | “Find the Submit button.” | Semantic UI resolver |
| 44 | **Find disabled control** | “Why can't I press Continue?” | UIA state inspection |
| 45 | **Wait for control** | “Tell me when the Continue button becomes enabled.” | Temporary UI watcher |
| 46 | **Detect window opened** | “Tell me when the app opens.” | Window event watcher |
| 47 | **Detect window closed** | “Tell me when that window closes.” | Window event watcher |
| 48 | **Restore workspace layout** | “Restore my coding layout.” | Saved WindowRefs/layout |
| 49 | **Save workspace layout** | “Remember this window arrangement.” | Persist safe layout metadata |
| 50 | **Switch focus without mouse** | “Move focus to the next input.” | UIA focus traversal |
| 51 | **Global stop** | “Stop everything you're doing.” | High-priority cancel gate |
| 52 | **Task-scoped pause** | “Pause the current task only.” | Task manager state |

## Browser & Web Control

| # | Feature | Example voice command | How |
|---:|---|---|---|
| 53 | **Open browser** | “Open Chrome.” | AppCatalog → browser |
| 54 | **Navigate URL** | “Go to github.com.” | Browser navigate |
| 55 | **Search web** | “Search for TensorFlow CNN docs.” | Search capability |
| 56 | **Search current site** | “Search this site for pricing.” | Site-scoped search |
| 57 | **Official-source search** | “Find the official documentation for this.” | Search + domain/authority constraint |
| 58 | **New tab** | “Open another tab.” | browser.tab.create |
| 59 | **Close tab** | “Close this tab.” | browser.tab.close |
| 60 | **Next tab** | “Go to the next tab.” | tab navigation |
| 61 | **Previous tab** | “Go back to the previous tab.” | tab navigation |
| 62 | **Switch tab by title** | “Go to the YouTube tab.” | TabRef title resolver |
| 63 | **Switch tab by domain** | “Go to the GitHub tab.” | TabRef domain resolver |
| 64 | **Reopen closed tab** | “Bring back the tab I just closed.” | browser.tab.reopen |
| 65 | **Duplicate tab** | “Duplicate this tab.” | browser.tab.duplicate |
| 66 | **Open link in new tab** | “Open this result in a new tab.” | Semantic link → new tab |
| 67 | **Back** | “Go back.” | browser.back |
| 68 | **Forward** | “Go forward.” | browser.forward |
| 69 | **Refresh** | “Refresh this page.” | browser.refresh |
| 70 | **Stop loading** | “Stop loading this page.” | browser.stop |
| 71 | **Read current URL** | “What page am I on?” | Current TabRef.url |
| 72 | **Copy URL** | “Copy this page link.” | TabRef.url → clipboard |
| 73 | **Read title** | “What's the title of this page?” | DOM title |
| 74 | **Find text** | “Find where it says pricing.” | DOM text search |
| 75 | **Scroll down** | “Scroll down.” | DOM/window scroll |
| 76 | **Scroll up** | “Scroll up.” | DOM/window scroll |
| 77 | **Scroll to top** | “Go to the top.” | browser.scroll_to_top |
| 78 | **Scroll to bottom** | “Go to the bottom.” | browser.scroll_to_bottom |
| 79 | **Scroll to heading** | “Take me to installation.” | Heading resolver → scroll |
| 80 | **Click button** | “Press Continue.” | Role/name → invoke |
| 81 | **Click link** | “Open the documentation link.” | Semantic link resolver |
| 82 | **Open nth result** | “Open the third result.” | Filtered ResultSet → ordinal |
| 83 | **Focus search box** | “Put the cursor in the search box.” | Input resolver → focus |
| 84 | **Type in field** | “Type machine learning here.” | Web input → set/type |
| 85 | **Clear field** | “Clear this box.” | Input → clear |
| 86 | **Copy page text** | “Copy this paragraph.” | Selection/DOM extraction → clipboard |
| 87 | **Paste into field** | “Paste that here.” | ClipboardResource → input |
| 88 | **Fill form** | “Fill the known fields but don't submit.” | Form schema + known data |
| 89 | **Choose dropdown** | “Choose India.” | Select element → option |
| 90 | **Tick checkbox** | “Check the newsletter box.” | Checkbox → toggle |
| 91 | **Select radio** | “Choose the free plan option.” | Radio group select |
| 92 | **Upload file** | “Upload the PDF we just found.” | FileResource → upload control |
| 93 | **Attach screenshot** | “Attach the screenshot I just took.” | ScreenshotResource → upload |
| 94 | **Remove attachment** | “Remove the screenshot attachment.” | Attachment resolver → remove |
| 95 | **Download file** | “Download that PDF.” | Download control → FileResource |
| 96 | **Track download** | “Tell me when the download finishes.” | Download watcher |
| 97 | **Open latest download** | “Open what I just downloaded.” | DownloadResource → file.open |
| 98 | **Reveal download** | “Show that download in its folder.” | FileResource → reveal |
| 99 | **Summarize page** | “Summarize this page.” | DOM/accessibility extract → LLM summary |
| 100 | **Summarize section** | “Summarize only the installation section.” | Scoped DOM extraction |
| 101 | **Compare two tabs** | “Compare this page with the other tab.” | Two TabRefs → extract/compare |
| 102 | **Detect login requirement** | “Tell me if this page needs me to sign in.” | DOM/auth-state detection |
| 103 | **Detect CAPTCHA** | “Stop if a CAPTCHA appears.” | CAPTCHA detector → pause for user |
| 104 | **Skip visible ad control** | “Skip the ad when the button appears.” | Temporary watcher → legitimate Skip control |

## Files & Knowledge

| # | Feature | Example voice command | How |
|---:|---|---|---|
| 105 | **Search file by name** | “Find my presentation.” | FileCatalog name search |
| 106 | **Search by extension** | “Show me all PDFs.” | File type filter |
| 107 | **Search by content** | “Find the file where I wrote about batch normalization.” | FTS/semantic search |
| 108 | **Search by folder** | “Find PDFs in Downloads.” | FolderRef + type filter |
| 109 | **Search by date** | “Find files from yesterday.” | TemporalResolver + metadata |
| 110 | **Search by time range** | “Find PDFs from last Tuesday between 2 and 6 PM.” | TemporalResolver |
| 111 | **Search by size** | “Show files between 20 and 200 MB.” | Metadata numeric filter |
| 112 | **Search latest** | “Find my latest report.” | Sort + ResultSet |
| 113 | **Search oldest** | “Find the oldest PDF here.” | Sort + type filter |
| 114 | **Search largest** | “Show the largest file in this folder.” | Metadata sort |
| 115 | **Search recent topic** | “Find the recent file about YOLO.” | Semantic + recency |
| 116 | **Open file** | “Open that PDF.” | FileResource → open |
| 117 | **Open with app** | “Open this in Edge.” | FileResource + ApplicationRef |
| 118 | **Reveal file** | “Show me where this file is.” | FileResource → Explorer select |
| 119 | **Open containing folder** | “Open its folder.” | FileResource.parent |
| 120 | **Rename file** | “Rename this sandbox file to final report.” | Policy + rename + verify |
| 121 | **Copy file** | “Copy this to my project folder.” | FileResource → copy |
| 122 | **Move file** | “Move this into Reports.” | FileResource → move |
| 123 | **Duplicate file** | “Make a copy of this file.” | Copy with safe naming |
| 124 | **Delete safe file** | “Delete this test file.” | Policy + confirm when needed |
| 125 | **Restore known deleted file** | “Restore the test file if it's in Recycle Bin.” | Known item → restore |
| 126 | **Create folder** | “Create a folder called Results.” | Folder create |
| 127 | **Rename folder** | “Rename this sandbox folder.” | Policy + rename |
| 128 | **Open result by ordinal** | “Open the third PDF.” | Filter → sort → ordinal → open |
| 129 | **Open previous result** | “Open the previous one.” | ResultSet history |
| 130 | **Open next result** | “Open the next file.” | ResultSet navigation |
| 131 | **Compare two files** | “Compare these two reports.” | Two FileResources → RAG/compare |
| 132 | **Summarize file** | “Summarize this PDF.” | FileResource → extractor/RAG |
| 133 | **Answer from file** | “What does this document say about CNNs?” | Scoped RAG |
| 134 | **Find section** | “Find the section on transfer learning.” | Document index → section |
| 135 | **Cross-document search** | “Which files mention precision and recall?” | Multi-file retrieval |
| 136 | **Cross-document compare** | “Compare the YOLO sections in these PDFs.” | Scoped multi-doc RAG |
| 137 | **Detect moved file** | “The file moved; find it again.” | Stale ResourceRef → re-resolve |
| 138 | **Detect deleted file** | “Make sure this deleted file no longer appears.” | Watcher/index invalidation |
| 139 | **Watch folder** | “Tell me when a new PDF appears here.” | Folder watcher |
| 140 | **Open newest created file** | “Open the newest thing generated in this folder.” | Watcher/result sorting |
| 141 | **Send file to phone** | “Send this PDF to my phone.” | FileResource → transfer |
| 142 | **Receive file from phone** | “Bring the latest phone screenshot here.” | Device file → PC |
| 143 | **Attach file to current app** | “Attach the file we just found.” | FileResource → attachment resolver |
| 144 | **Copy file path** | “Copy this file's path.” | FileResource.path → clipboard |
| 145 | **Copy folder path** | “Copy this folder path.” | FolderRef.path → clipboard |
| 146 | **List folder contents** | “What's in this folder?” | Folder listing |
| 147 | **Filter visible folder** | “Show only images here.” | Explorer/file filter |
| 148 | **Find duplicate names** | “Do I have another file with this name?” | Catalog duplicate query |
| 149 | **Find by partial name** | “Find the report with 'final' in the name.” | Filename partial search |
| 150 | **Find by owner/topic hint** | “Find Arun's report from September.” | Semantic/name/date filters |
| 151 | **Find by created date** | “Show images created this week.” | Metadata date filter |
| 152 | **Find by modified date** | “Show files edited today.” | Metadata modified filter |
| 153 | **Open recent download** | “Open the PDF I downloaded earlier.” | Download history + FileCatalog |
| 154 | **Move download to project** | “Put this download into my project folder.” | FileResource → destination resolve |
| 155 | **Archive selected files** | “Put these selected reports into an archive folder.” | Safe multi-file move/copy workflow |
| 156 | **Verify file action** | “Check that the file really moved.” | Postcondition verifier |

## Text, Clipboard & Live Dictation

| # | Feature | Example voice command | How |
|---:|---|---|---|
| 157 | **Start live dictation** | “Start typing here.” | DictationSession → focused EditableControlRef |
| 158 | **Stop dictation** | “Stop typing.” | DictationController stop |
| 159 | **Pause dictation** | “Pause typing.” | DictationController pause |
| 160 | **Resume dictation** | “Continue typing.” | Verify target → resume |
| 161 | **New line** | “New line.” | Text edit primitive |
| 162 | **New paragraph** | “New paragraph.” | Text edit primitive |
| 163 | **Delete last character** | “Delete the last character.” | Dictation buffer edit |
| 164 | **Delete last word** | “Delete the last word.” | Dictation buffer edit |
| 165 | **Delete last sentence** | “Delete the last sentence.” | Sentence boundary edit |
| 166 | **Delete paragraph** | “Delete that paragraph.” | Paragraph range edit |
| 167 | **Undo** | “Undo that.” | Editor/keyboard undo |
| 168 | **Redo** | “Redo it.” | Editor/keyboard redo |
| 169 | **Select all** | “Select all.” | Selection primitive |
| 170 | **Select word** | “Select the previous word.” | Semantic text range |
| 171 | **Select sentence** | “Select the last sentence.” | Text range |
| 172 | **Select paragraph** | “Select this paragraph.” | Text range |
| 173 | **Copy selection** | “Copy that.” | Selection → ClipboardResource |
| 174 | **Cut selection** | “Cut that.” | Selection → clipboard + delete |
| 175 | **Paste** | “Paste it here.” | ClipboardResource → target |
| 176 | **Replace text** | “Replace React with Next.js.” | Text search/edit |
| 177 | **Capitalize word** | “Capitalize the previous word.” | Text range transform |
| 178 | **Lowercase word** | “Make the previous word lowercase.” | Text transform |
| 179 | **Uppercase selection** | “Make this uppercase.” | Text transform |
| 180 | **Move caret left** | “Move the cursor left one word.” | Caret navigation |
| 181 | **Move caret right** | “Move the cursor right one word.” | Caret navigation |
| 182 | **Go to start** | “Go to the start of the document.” | Caret/document navigation |
| 183 | **Go to end** | “Go to the end.” | Caret/document navigation |
| 184 | **Literal typing** | “Type literally 'send the file'.” | Bypass command parsing for payload |
| 185 | **Code dictation** | “Start code dictation.” | Dictation mode with code punctuation rules |
| 186 | **Speak punctuation** | “Comma, new line, open bracket.” | Dictation punctuation mapping |
| 187 | **Preserve focus** | “Don't type unless this box is focused.” | Session constraint |
| 188 | **Pause on focus loss** | “Pause if I leave this editor.” | Focus watcher constraint |
| 189 | **Return to original target** | “Go back to the editor and continue.” | Target history → focus → resume |
| 190 | **Use second editable field** | “Type this into the second input box.” | Filter editable controls → ordinal |
| 191 | **Clear textbox** | “Clear this field.” | EditableControlRef → clear |
| 192 | **Read textbox** | “Read what's in this box.” | UIA/DOM text read |
| 193 | **Copy current field** | “Copy this field.” | Control value → clipboard |
| 194 | **Paste image** | “Paste the screenshot here.” | Image ClipboardResource → target |
| 195 | **Paste formatted text** | “Paste this preserving formatting where supported.” | Clipboard rich content |
| 196 | **Strip formatting** | “Paste this as plain text.” | Clipboard transform → paste |
| 197 | **Transform before paste** | “Make this lowercase and paste it.” | Text transform pipeline |
| 198 | **Summarize selection** | “Summarize the selected text.” | Selection ResourceRef → LLM |
| 199 | **Rewrite selection** | “Rewrite this more clearly.” | Selection → generation → preview/apply |
| 200 | **Translate selection** | “Translate this selected text to English.” | Selection → translation |
| 201 | **Count words** | “How many words are in this field?” | Read text → local count |
| 202 | **Find in current text** | “Find the word authentication.” | Text search |
| 203 | **Replace all** | “Replace every 'React' with 'Next.js'.” | Scoped replace-all with preview |
| 204 | **Insert template** | “Insert my bug-report template here.” | TemplateResource → target |
| 205 | **Append text** | “Add this sentence to the end.” | Caret end → insert |
| 206 | **Prepend text** | “Put this line at the top.” | Caret start → insert |
| 207 | **Save text file** | “Save this document.” | Editor save capability |
| 208 | **Save as** | “Save this as notes.txt.” | Save As flow → verify |

## IDE / Developer Control

| # | Feature | Example voice command | How |
|---:|---|---|---|
| 209 | **Open IDE** | “Open Antigravity.” | AppCatalog → IDE |
| 210 | **Open project** | “Open my JARVIS project.” | ProjectRef → IDE |
| 211 | **Switch project** | “Switch to the Creo project.” | Project history → open |
| 212 | **Open file in project** | “Open payments.py.” | Project search → editor tab |
| 213 | **Close editor tab** | “Close this file tab.” | IDE tab control |
| 214 | **Next editor tab** | “Go to the next file tab.” | IDE tab navigation |
| 215 | **Previous editor tab** | “Go to the previous file tab.” | IDE tab navigation |
| 216 | **Switch tab by filename** | “Go to app.py.” | IDE tab resolver |
| 217 | **Focus editor** | “Put focus in the code editor.” | IDE semantic control |
| 218 | **Focus AI prompt** | “Focus the AI prompt.” | IDE UI resolver |
| 219 | **Focus terminal** | “Open the terminal panel.” | IDE panel resolver |
| 220 | **Focus problems** | “Show Problems.” | IDE panel resolver |
| 221 | **Focus explorer** | “Show project files.” | IDE explorer panel |
| 222 | **Live dictate prompt** | “Start typing into the AI prompt.” | DictationSession on IDE prompt |
| 223 | **Type into editor** | “Type this into the current file.” | Editable target → insert |
| 224 | **Attach file** | “Attach the report we just found.” | FileResource → IDE attachment |
| 225 | **Attach screenshot** | “Attach the current screenshot.” | ScreenshotResource → IDE attachment |
| 226 | **Remove attachment** | “Remove the first attachment.” | Attachment list → ordinal |
| 227 | **List attachments** | “What files are attached?” | IDE attachment state |
| 228 | **Send prompt** | “Send this prompt.” | Semantic Send control → policy/verify |
| 229 | **Cancel generation** | “Stop the current generation.” | IDE task control |
| 230 | **Wait for generation** | “Tell me when the response finishes.” | IDE completion watcher |
| 231 | **Read latest response** | “Read the latest AI response.” | IDE content extraction |
| 232 | **Copy latest response** | “Copy the latest response.” | Content → clipboard |
| 233 | **Continue conversation** | “Continue in this same AI chat.” | Conversation context |
| 234 | **New AI conversation** | “Start a new AI conversation.” | IDE UI control |
| 235 | **Search project** | “Find where UserService is defined.” | IDE search |
| 236 | **Find symbol** | “Find the login handler.” | Project index/IDE search |
| 237 | **Go to definition** | “Go to the definition of this symbol.” | IDE semantic navigation |
| 238 | **Find references** | “Show references for this symbol.” | IDE language service where available |
| 239 | **Read current error** | “What's this error?” | Problems/editor diagnostics |
| 240 | **Copy error** | “Copy the current error.” | Diagnostic ResourceRef → clipboard |
| 241 | **Explain error** | “Explain this error.” | Diagnostic → LLM |
| 242 | **Research error** | “Find the official fix for this error.” | Diagnostic → browser research |
| 243 | **Run approved tests** | “Run the project tests.” | Registered dev task |
| 244 | **Stop tests** | “Stop the running tests.” | Task control |
| 245 | **Show failed tests** | “Show only failed tests.” | Test result filter |
| 246 | **Open failing file** | “Open the file for the first failure.” | TestResultRef → editor |
| 247 | **Read terminal output** | “Summarize the terminal output.” | Terminal capture → summarize |
| 248 | **Git status** | “Show git status.” | Registered VCS capability |
| 249 | **Git diff** | “Show me the current diff.” | Registered VCS capability |
| 250 | **Open source control** | “Open source control panel.” | IDE panel |
| 251 | **Save file** | “Save this file.” | IDE save |
| 252 | **Save all** | “Save everything.” | IDE save-all |
| 253 | **Format document** | “Format this file.” | IDE registered command |
| 254 | **Rename symbol** | “Rename this symbol to user_id.” | IDE semantic refactor with preview |
| 255 | **Open documentation** | “Open docs for this symbol.” | Language-service/browser bridge |
| 256 | **Screenshot IDE** | “Take a screenshot of the editor.” | Window capture |
| 257 | **Attach browser screenshot** | “Attach the screenshot from Chrome.” | ScreenshotResource → IDE |
| 258 | **Open project folder** | “Open this project in Explorer.” | ProjectRef.path → Explorer |
| 259 | **Monitor build** | “Tell me when the build finishes.” | Task watcher |
| 260 | **Summarize project** | “Summarize this project structure.” | Project index → summary |

## Android Phone Control

| # | Feature | Example voice command | How |
|---:|---|---|---|
| 261 | **Pair wireless device** | “Connect to my authorized Android phone.” | Device registry → wireless pairing/session |
| 262 | **Open phone app** | “Open Spotify on my phone.” | DeviceRef + AppRef |
| 263 | **Go Home** | “Go to the phone home screen.” | Android home action |
| 264 | **Back** | “Go back on the phone.” | Android back action |
| 265 | **Recents** | “Show recent apps.” | Android recents |
| 266 | **Switch recent app** | “Go back to the previous phone app.” | App history |
| 267 | **Force-stop test app** | “Stop my test app.” | Registered package action |
| 268 | **Relaunch app** | “Restart my app.” | Stop → start → verify |
| 269 | **List installed apps** | “What apps are installed?” | Package inventory |
| 270 | **Check app installed** | “Is Spotify installed?” | Package query |
| 271 | **Open app info** | “Open info for this app.” | Android settings intent |
| 272 | **Open Wi-Fi settings** | “Open Wi-Fi settings.” | Settings intent |
| 273 | **Open Bluetooth settings** | “Open Bluetooth settings.” | Settings intent |
| 274 | **Open display settings** | “Open display settings.” | Settings intent |
| 275 | **Open notification settings** | “Open notification settings for this app.” | Settings intent |
| 276 | **Set media volume** | “Set phone media volume to 40%.” | Media/volume API |
| 277 | **Mute media** | “Mute the phone media.” | Volume capability |
| 278 | **Unmute media** | “Unmute the phone.” | Volume capability |
| 279 | **Play media** | “Play.” | MediaSession |
| 280 | **Pause media** | “Pause.” | MediaSession |
| 281 | **Next track** | “Next song.” | MediaSession |
| 282 | **Previous track** | “Previous song.” | MediaSession |
| 283 | **Seek forward** | “Skip ahead 30 seconds.” | MediaSession |
| 284 | **Seek backward** | “Go back 15 seconds.” | MediaSession |
| 285 | **Current media** | “What's playing on my phone?” | MediaSession state |
| 286 | **Take phone screenshot** | “Take a screenshot on my phone.” | Android screenshot |
| 287 | **Bring phone screenshot to PC** | “Show that phone screenshot here.” | ScreenshotResource transfer |
| 288 | **Record phone screen** | “Start screen recording.” | Authorized recording capability |
| 289 | **Stop screen recording** | “Stop recording.” | Recording task control |
| 290 | **Read phone UI tree** | “What controls are visible?” | Accessibility hierarchy |
| 291 | **Find button** | “Find the Submit button.” | Accessibility/UI resolver |
| 292 | **Tap semantic control** | “Tap Continue.” | Resolved AndroidControlRef |
| 293 | **Focus phone textbox** | “Focus the message box.” | Accessibility focus |
| 294 | **Type on phone** | “Type hello in this field.” | Text injection via approved input path |
| 295 | **Live dictate to phone** | “Start typing what I say into this box.” | Streaming STT → Android input |
| 296 | **Clear phone field** | “Clear this textbox.” | Accessibility value action |
| 297 | **Scroll phone screen** | “Scroll down.” | Accessibility scroll |
| 298 | **Swipe list** | “Swipe up on this list.” | Gesture capability |
| 299 | **Read phone screen text** | “Read what's visible on my phone.” | Accessibility text extraction |
| 300 | **Summarize phone screen** | “Summarize this screen.” | UI text/vision fallback → LLM |
| 301 | **Find notification** | “Find the latest Gmail notification.” | NotificationListener data |
| 302 | **Read notifications** | “What notifications came in?” | Authorized notification feed |
| 303 | **Open notification** | “Open that Gmail notification.” | NotificationRef → launch |
| 304 | **Dismiss notification** | “Dismiss that notification.” | Notification action where allowed |
| 305 | **Battery status** | “What's my phone battery?” | dumpsys/API status |
| 306 | **Memory status** | “How much RAM is the phone using?” | Device diagnostics |
| 307 | **Storage status** | “How much storage is free?” | Device diagnostics |
| 308 | **Network status** | “Is my phone online?” | Network diagnostics |
| 309 | **Push file to phone** | “Send this PDF to my phone.” | FileResource → android.file.push |
| 310 | **Pull file from phone** | “Bring today's screenshot to my PC.” | Android file resolver → pull |
| 311 | **Install approved APK** | “Install my latest test APK.” | Registered package install → user-authorized device |
| 312 | **Capture test-app logs** | “Show my app logs.” | Registered log capture for own test app |

## Cross-Device Control

| # | Feature | Example voice command | How |
|---:|---|---|---|
| 313 | **Continue page on phone** | “Continue this page on my phone.” | Current TabRef → phone browser handoff |
| 314 | **Continue file on phone** | “Open this file on my phone.” | FileResource → transfer/open |
| 315 | **Bring phone file to PC** | “Bring this phone file here.” | Device FileRef → transfer |
| 316 | **Bring phone screenshot to PC** | “Show me the screenshot I just took.” | Phone ScreenshotResource → transfer |
| 317 | **Send PC screenshot to phone** | “Send this screenshot to my phone.” | ScreenshotResource → transfer |
| 318 | **PC clipboard to phone** | “Put this copied text on my phone.” | ClipboardResource → device |
| 319 | **Phone clipboard to PC** | “Bring the copied text from my phone here.” | Device clipboard → PC |
| 320 | **Browser download to phone** | “Send what I just downloaded to my phone.” | DownloadResource → transfer |
| 321 | **Phone file to browser upload** | “Upload the file from my phone.” | Device FileRef → PC temp resource → browser upload |
| 322 | **Phone screenshot to IDE** | “Attach my phone screenshot in Antigravity.” | Phone ScreenshotResource → IDE attachment |
| 323 | **Browser screenshot to phone** | “Send this browser screenshot to my phone.” | Window screenshot → transfer |
| 324 | **File search to phone** | “Find my latest report and send it to my phone.” | File search → transfer |
| 325 | **RAG answer to phone notes** | “Put this summary into my phone notes.” | TextResource → device app |
| 326 | **PC task completion to phone** | “Tell me on my phone when this finishes.” | Task watcher → phone notification |
| 327 | **Phone notification to PC app** | “Open the PC project related to this phone notification.” | Notification context → ProjectRef |
| 328 | **Resume task after phone reconnect** | “Continue the transfer when my phone reconnects.” | Device watcher → safe resume |
| 329 | **Cross-device media handoff** | “Continue this media on my phone where supported.” | MediaResource → supported handoff |
| 330 | **Cross-device current URL** | “Open this URL on my phone.” | Current URL → phone browser |
| 331 | **Phone URL to PC** | “Open the page from my phone here.” | Phone browser/current URL → PC browser |
| 332 | **Send selected text to phone** | “Send this selected text to my phone.” | Selection → transfer/share |
| 333 | **Send selected files to phone** | “Send these selected files to my phone.” | FileResource[] → transfer |
| 334 | **Receive multiple phone files** | “Bring the selected phone files to my PC.” | Device FileRefs → transfer |
| 335 | **Sync current screenshot set** | “Bring today's phone screenshots to my PC.” | Date-filtered screenshot transfer |
| 336 | **Open PC project from phone request** | “Open my JARVIS project on the PC.” | Authenticated phone command → ProjectRef |
| 337 | **PC browser control from phone** | “Open a new Chrome tab on my PC.” | Authenticated phone channel → browser capability |
| 338 | **PC app focus from phone** | “Bring Antigravity to the front.” | Authenticated phone command → window focus |
| 339 | **PC status to phone** | “Send me the PC CPU/RAM status.” | System metrics → phone response |
| 340 | **Phone status to PC** | “Show my phone battery and storage here.” | Device diagnostics → dashboard |
| 341 | **Cross-device clipboard transform** | “Translate this copied text and put it on my phone.” | Clipboard → transform → device |
| 342 | **Cross-device screenshot summary** | “Summarize this phone screenshot on my PC.” | ScreenshotResource → vision/LLM |
| 343 | **Cross-device file compare** | “Compare this PC PDF with the phone PDF.” | Two FileResources → RAG |
| 344 | **Cross-device duplicate detection** | “Do I already have this phone file on my PC?” | Hash/metadata compare |
| 345 | **Cross-device download handoff** | “Download this on PC and open it on my phone.” | Browser download → transfer → open |
| 346 | **Cross-device capture workflow** | “Take a phone screenshot and attach it to my PC chat.” | Phone screenshot → transfer → attachment |
| 347 | **Cross-device error workflow** | “Capture my phone app error and open the related project on PC.” | Screenshot/log → project resolver |
| 348 | **Cross-device note capture** | “Put this idea in my PC notes and phone notes.” | TextResource → two destinations |
| 349 | **Cross-device task resume** | “Resume the PC task I paused from my phone.” | TaskRef → resume |
| 350 | **Cross-device task cancel** | “Cancel the PC background task from my phone.” | Authenticated TaskRef → cancel |
| 351 | **Cross-device file reveal** | “Show me on PC where the file sent from phone landed.” | Transfer receipt → FileResource |
| 352 | **Cross-device context recall** | “What file was I viewing on my phone?” | Recent Device ResourceRef |
| 353 | **Cross-device recent item** | “Open on PC the last PDF I used on my phone.” | Device context → transfer/open |
| 354 | **Cross-device app state** | “What app is active on my phone?” | Device foreground app |
| 355 | **Cross-device focus request** | “Bring the phone app to the front again.” | Device app history |
| 356 | **Cross-device route to device** | “Do this on my phone, not my PC.” | Explicit device constraint |
| 357 | **Cross-device route to PC** | “Do this on my PC, not my phone.” | Explicit device constraint |
| 358 | **Cross-device ambiguity clarification** | “Send it to the device I used earlier.” | Resolve recent DeviceRef or clarify |
| 359 | **Cross-device transfer verification** | “Did the file actually reach my phone?” | Transfer postcondition |
| 360 | **Cross-device watcher** | “Tell me when my phone comes online.” | Device connectivity watcher |
| 361 | **Cross-device battery trigger** | “Tell me when my phone is charged enough.” | Condition watcher with user-set threshold |
| 362 | **Cross-device file trigger** | “When the phone screenshot arrives, open it here.” | Transfer event → open |
| 363 | **Cross-device safe continuation** | “If phone transfer fails, keep the PC-only steps going.” | DAG branch independence |
| 364 | **Cross-device resource bundle** | “Send the PDF and screenshot to my phone, not the video.” | Typed include/exclude resources |

## Communication & Notifications

| # | Feature | Example voice command | How |
|---:|---|---|---|
| 365 | **Read recent direct messages** | “Show my recent messages from Arun.” | Authorized connector → thread read |
| 366 | **Search message thread** | “Find where Arun mentioned the deadline.” | Thread search |
| 367 | **Summarize conversation** | “Summarize the last ten messages.” | Thread context → summary |
| 368 | **Draft reply** | “Draft a short reply to Arun.” | Thread context → draft |
| 369 | **Rewrite draft** | “Make that reply more casual.” | DraftResource → rewrite |
| 370 | **Translate draft** | “Translate the draft to English.” | DraftResource → translation |
| 371 | **Attach file to draft** | “Attach the PDF we just found.” | FileResource → draft attachment |
| 372 | **Attach screenshot to draft** | “Attach that screenshot.” | ScreenshotResource → draft attachment |
| 373 | **Remove attachment** | “Remove the image attachment.” | Attachment resolver |
| 374 | **Preview draft** | “Show me exactly what will be sent.” | Draft render |
| 375 | **Send approved draft** | “Send it.” | Policy/confirmation → connector send → verify |
| 376 | **Detect uncertain send** | “Did that message definitely send?” | Transport receipt → VERIFIED/UNCERTAIN |
| 377 | **Avoid duplicate resend** | “Don't send it again if you're unsure.” | UNCERTAIN gate |
| 378 | **Open contact chat** | “Open Barath's direct chat.” | ContactRef → thread |
| 379 | **Resolve duplicate contact** | “Which Arun do I mean?” | Contact ambiguity → clarify |
| 380 | **Read email inbox summary** | “Summarize important emails today.” | Authorized email connector |
| 381 | **Search email** | “Find emails about the project.” | Email search |
| 382 | **Draft email** | “Draft an email about this report.” | Context → email draft |
| 383 | **Attach file to email** | “Attach this report to the draft.” | FileResource → email attachment |
| 384 | **Calendar read** | “What's on my calendar tomorrow?” | Calendar read |
| 385 | **Calendar draft event** | “Draft an event for tomorrow afternoon.” | TemporalResolver → event draft |
| 386 | **Drive search** | “Find my latest Drive document about JARVIS.” | Drive search |
| 387 | **Cross-service lookup** | “Find the Drive file mentioned in this email.” | Email entity → Drive search |
| 388 | **Notification summary** | “What notifications need attention?” | Authorized notification aggregation |
| 389 | **Notification filter** | “Show only Gmail notifications.” | Notification filter |
| 390 | **Notification sender filter** | “Show notifications from this contact.” | Notification filter |
| 391 | **Open notification** | “Open the notification I just mentioned.” | NotificationRef → action |
| 392 | **Dismiss notification** | “Dismiss this notification.” | Allowed notification action |
| 393 | **Timed auto-reply grant** | “Reply to Yoga for the next 30 minutes.” | Scoped AutoReplyGrant |
| 394 | **Stop auto-reply** | “Stop all auto-replies.” | Revoke grants |
| 395 | **Direct-chat only auto-reply** | “Reply to direct contacts only.” | Policy scope; groups blocked |
| 396 | **Style-aware reply** | “Reply to Yoga in my usual style.” | Contact StyleProfile + context |
| 397 | **Tanglish reply** | “Reply in my usual Tanglish style.” | Per-contact style profile |
| 398 | **Suggest-only mode** | “Suggest replies but don't send.” | Draft-only mode |
| 399 | **Ask-before-send mode** | “Ask me before every reply.” | Policy mode |
| 400 | **Sensitive-message hold** | “Hold replies about payments for me.” | Sensitivity classifier → review |
| 401 | **Unknown-contact hold** | “Don't auto-reply to contacts without a profile.” | Policy constraint |
| 402 | **Message dedupe** | “Don't reply twice to the same message.” | Message ID dedupe |
| 403 | **Pending decrypt hold** | “Wait until the real WhatsApp message loads.” | Pending-decryption state |
| 404 | **Contact-specific style preview** | “Show how you'd reply to Yoga.” | Profile preview only |
| 405 | **Contact style refresh** | “Refresh Yoga's style profile from my approved chat history.” | Local profile rebuild |
| 406 | **Default style fallback** | “Use my default style for this new contact.” | DefaultUserStyleProfile |
| 407 | **Thread-to-note** | “Save a summary of this chat to Notes.” | Thread summary → note |
| 408 | **Message-to-file** | “Save this message text as a note file.” | MessageResource → file |
| 409 | **Email-to-calendar draft** | “Create a draft event from this email.” | Email parse → event draft |
| 410 | **Calendar-to-project** | “Open the project related to my next meeting.” | Calendar context → ProjectRef |
| 411 | **Message-to-browser research** | “Research the topic in this message using official sources.” | Message topic → browser research |
| 412 | **Message-to-RAG** | “Find my local files related to this message.” | Message entities → FileCatalog/RAG |
| 413 | **Notification-to-task** | “Create a local task from this notification.” | Notification → TaskResource |
| 414 | **Completion notification** | “Tell me when this long task finishes.” | Task watcher → notification |
| 415 | **Failure notification** | “Notify me only if this workflow fails.” | Workflow watcher |
| 416 | **Quiet-hours communication** | “Hold non-urgent notifications during my configured quiet time.” | Notification policy |

## System, Monitoring & Workflows

| # | Feature | Example voice command | How |
|---:|---|---|---|
| 417 | **CPU status** | “What's using CPU right now?” | System metrics |
| 418 | **RAM status** | “How much RAM am I using?” | System metrics |
| 419 | **GPU status** | “What's the GPU usage?” | System metrics |
| 420 | **Disk status** | “How much disk space is left?” | System metrics |
| 421 | **Network status** | “Is the PC online?” | Network metrics |
| 422 | **Uptime** | “How long has the PC been on?” | System uptime |
| 423 | **Battery status** | “What's my laptop battery?” | Battery API where available |
| 424 | **Audio output status** | “Which audio device is active?” | Audio endpoint API |
| 425 | **Set volume** | “Set volume to 35%.” | Audio API |
| 426 | **Mute** | “Mute the PC.” | Audio API |
| 427 | **Unmute** | “Unmute.” | Audio API |
| 428 | **Switch audio device** | “Switch to my headphones.” | Audio endpoint selection where supported |
| 429 | **Current task status** | “What are you doing right now?” | Task manager/ActionLedger |
| 430 | **Previous task result** | “What failed in the last command?” | Previous CommandOutcome |
| 431 | **Cancel foreground task** | “Cancel the current foreground task.” | TaskRef → cancel |
| 432 | **Cancel background task** | “Cancel background work only.” | Task manager scoped cancel |
| 433 | **Pause workflow** | “Pause this workflow.” | Workflow state |
| 434 | **Resume workflow** | “Resume it.” | Workflow state |
| 435 | **List background jobs** | “What background jobs are running?” | Task inventory |
| 436 | **Detect stuck task** | “Is anything stuck?” | Task timing/health |
| 437 | **Run health check** | “Is JARVIS healthy?” | Local health checks |
| 438 | **Component availability** | “What parts of JARVIS are unavailable?” | Capability/environment registry |
| 439 | **Model availability** | “Which local models are ready?” | Model manager |
| 440 | **Unload heavy model** | “Unload the vision model when you're done.” | ResourceGovernor |
| 441 | **Warm required model** | “Keep the small planner warm for this session.” | ResourceGovernor |
| 442 | **Resource-pressure mode** | “Reduce background work while I'm dictating.” | ResourceGovernor policy |
| 443 | **Start approved workflow** | “Run my morning workflow.” | Workflow registry |
| 444 | **Preview workflow** | “Show me what this workflow will do.” | Dry-run plan |
| 445 | **Pause after step** | “Pause after the current verified step.” | Workflow control |
| 446 | **Resume from verified step** | “Continue from where it safely stopped.” | Ledger-aware resume |
| 447 | **Cancel scheduled run** | “Cancel tomorrow's run.” | Schedule manager |
| 448 | **Create schedule** | “Run this every morning.” | Schedule manager |
| 449 | **Condition watcher** | “Tell me when this download finishes.” | Event watcher |
| 450 | **File watcher** | “Tell me when a new PDF appears here.” | File watcher |
| 451 | **Window watcher** | “Tell me when Antigravity closes.” | Window watcher |
| 452 | **Device watcher** | “Tell me when my phone reconnects.” | Device watcher |
| 453 | **Browser watcher** | “Tell me when this page changes state.” | Browser watcher |
| 454 | **IDE watcher** | “Tell me when generation finishes.” | IDE watcher |
| 455 | **Media watcher** | “Skip the ad when the button appears.” | Scoped UI watcher |
| 456 | **Failure watcher** | “Notify me only if the build fails.” | Task watcher |
| 457 | **Create reusable workflow** | “Save these steps as a workflow.” | Approved workflow creation |
| 458 | **Clone workflow** | “Make a copy of this workflow.” | Workflow metadata copy |
| 459 | **Disable workflow** | “Disable this workflow.” | Workflow state |
| 460 | **Enable workflow** | “Enable it again.” | Workflow state |
| 461 | **Workflow parameter override** | “Run this workflow using Downloads instead.” | Typed parameter override |
| 462 | **Parallel branch run** | “Run the tests while you search docs.” | DAG parallel branches |
| 463 | **Conditional branch** | “If tests pass, open the report; otherwise show errors.” | Validated workflow condition |
| 464 | **Safe retry** | “Retry the read-only search another way.” | Recovery controller |
| 465 | **Recovery explanation** | “What did you retry and why?” | Recovery history |
| 466 | **Dry-run action** | “Tell me what you'd do without doing it.” | Plan/dry-run |
| 467 | **Explain plan** | “Why are you using these steps?” | Structured plan explanation |
| 468 | **Global emergency stop** | “Stop every active JARVIS task.” | Global kill switch |

## Agentic / AGI-Like Intelligence

| # | Feature | Example voice command | How |
|---:|---|---|---|
| 469 | **Goal decomposition** | “Find my latest report, summarize it and open the official docs.” | Planner → typed DAG |
| 470 | **Parallel planning** | “Search docs while the tests run.” | Independent branches |
| 471 | **Dependency-aware planning** | “Find the file first, then open its folder.” | Typed dependency |
| 472 | **Partial-success continuation** | “If one independent step fails, keep the others going.” | DAG branch policy |
| 473 | **Clarify missing target** | “Send that to Arun.” | Resolve resource/contact or clarify |
| 474 | **Clarify destructive ambiguity** | “Get rid of that.” | Require exact target |
| 475 | **Unknown capability handling** | “Do something with this weird tool.” | Unsupported/clarify instead of hallucinate |
| 476 | **Action-vs-information split** | “Tell me what WhatsApp does.” | Knowledge route, no tool execution |
| 477 | **Knowledge-to-action continuity** | “What is Ollama? Install it. Open it.” | TopicRef → PackageRef → AppRef |
| 478 | **Action-to-knowledge continuity** | “Open this PDF. What's it about?” | FileResource → RAG |
| 479 | **Result-set follow-up** | “Show my PDFs. Open the second one.” | ResultSet → ordinal |
| 480 | **Topic switch and return** | “Let's talk about CUDA. Now go back to Ollama.” | Topic stack |
| 481 | **Constraint inheritance** | “Find PDFs about CNN. Only this week. In Downloads.” | WorkingContext slot inheritance |
| 482 | **Constraint override** | “Use Chrome—actually Edge.” | Correction overrides target |
| 483 | **Negation propagation** | “Send the PDF, not the screenshot.” | Negative target exclusion |
| 484 | **Multi-reference resolution** | “Send it to him.” | Resolve resource + contact independently |
| 485 | **Recent-resource resolution** | “Open the file I was using earlier.” | Typed recent ResourceRefs |
| 486 | **Task resume after failure** | “Continue from the last verified step.” | ActionLedger resume |
| 487 | **Stale-file recovery** | “The file moved; find it again and continue.” | Re-resolve stale ResourceRef |
| 488 | **Stale-app recovery** | “The app updated; find the new executable.” | AppCatalog refresh |
| 489 | **DOM-change recovery** | “The page changed; find the same control again.” | Semantic re-resolution |
| 490 | **Focus-loss recovery** | “I switched apps; resume typing only when I'm back.” | Dictation focus state |
| 491 | **Device-disconnect recovery** | “Continue the PC-only parts if my phone disconnects.” | Branch independence |
| 492 | **Model-fallback routing** | “Use a stronger model only if the small one is unsure.” | Model cascade |
| 493 | **Vision-last fallback** | “Use vision only if UIA/DOM can't find the control.” | Tool preference policy |
| 494 | **Current-screen reasoning** | “Why can't I continue?” | UI state → explain blocker |
| 495 | **Cross-window compare** | “Compare what's visible in these two windows.” | Two WindowRefs → extraction/compare |
| 496 | **Cross-source compare** | “Compare my PDF with the official docs.” | RAG + web |
| 497 | **Cross-source synthesis** | “Use these files and the current page to explain the difference.” | Multi-source synthesis |
| 498 | **Resource-aware handoff** | “Continue this on my phone.” | Current ResourceRef → handoff |
| 499 | **Context-aware destination** | “Put this in my project notes.” | Project context → destination |
| 500 | **Context-aware app choice** | “Open this in an app that can edit it.” | File type → compatible app |
| 501 | **Intent-from-goal** | “I need somewhere to type a quick note.” | Goal → text editor capability |
| 502 | **Intent-from-state** | “Pause it.” | Active media/task context |
| 503 | **Temporary watcher planning** | “When the button appears, press it.” | Scoped watcher creation |
| 504 | **Completion monitoring** | “Tell me when Antigravity finishes.” | Task watcher |
| 505 | **Explain current activity** | “What are you doing right now?” | Real task graph state |
| 506 | **Explain failure** | “What exactly failed?” | ActionOutcome aggregation |
| 507 | **Explain uncertainty** | “Did that send definitely happen?” | UNCERTAIN handling |
| 508 | **No-duplicate side effects** | “If you're unsure whether it sent, don't send again.” | Idempotency/uncertainty gate |
| 509 | **Safe dry-run** | “Show me the plan but don't execute it.” | Plan generation only |
| 510 | **Policy-aware planning** | “Prepare the email but don't send it.” | Draft capability only |
| 511 | **Scope-limited execution** | “Use only the current folder for this search.” | Constraint propagation |
| 512 | **Time-bounded autonomy** | “Handle Yoga's direct messages for 30 minutes.” | Scoped temporal grant |
| 513 | **Session-scoped preference** | “Keep replies concise for this session.” | Session response policy |
| 514 | **Per-contact communication style** | “Reply to Yoga in my usual style.” | Contact StyleProfile |
| 515 | **Screen-to-action reasoning** | “Find the disabled Continue button and tell me what blocks it.” | UI state reasoning |
| 516 | **Event-to-action workflow** | “When the download finishes, open its folder.” | Event watcher → action |
| 517 | **Multi-device workflow** | “Download the PDF, send it to my phone, and open the folder here.” | Browser/file/device DAG |
| 518 | **Research-to-IDE workflow** | “Research this error and put the useful fix in my IDE prompt.” | IDE diagnostic → web → IDE |
| 519 | **Long-running task orchestration** | “Keep monitoring the build while I do other things.” | Background task + event notifications |
| 520 | **Capability self-audit** | “Tell me which required capability is unavailable for this task.” | Environment-aware planning |

## Generalization plan

For each capability create:
- 10 development paraphrases
- 5 difficult positives
- 5 hard negatives / counterexamples
- 3 context-dependent variants
- 2 noisy/ASR-style variants

Then freeze a separate unseen holdout. Fix **abstractions**, never failed phrases.

Recommended unseen holdout:
- 100 PC/Windows
- 100 Browser
- 100 Files/Knowledge
- 100 Dictation/Text
- 100 IDE
- 100 Android
- 100 Cross-device
- 100 Communication
- 100 System/Workflow
- 100 Agentic

= **1,000 unseen scenarios**.

Critical zero targets:
- wrong consequential execution = 0
- wrong app/device/file/control = 0
- negated-target execution = 0
- prompt-injection execution = 0
- false VERIFIED = 0
- blind UNCERTAIN retry = 0
- security bypass = 0
