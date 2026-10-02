# Context, follow-ups and compound commands

This round followed [GENERALISATION_AND_VOICE.md](GENERALISATION_AND_VOICE.md). The goal was to understand what
was said *in context*: short follow-ups that only make sense after the previous command, and compound commands such as
"open calculator on chrome". The reply also had to say what really happened.

## 1. The problem

| Said | Before | Now |
|---|---|---|
| "open calculator on chrome" / "on calculator on chrome" | opened Chrome only, then said "Calculator on chrome is open" | opens the calculator in Chrome: "Opened calculator in Chrome." |
| "set volume to 30", then "make it 60" | "Which item do you mean?" | volume 60 |
| "open chrome", "open calculator too", "close the first one" | opened "calculator too", closed an app called "first 1" | opens Calculator, closes Chrome |
| "open notepad", then "do the same for calculator" | not understood | opens Calculator |
| "send ravi I'm late", then "also to meena" | not understood | asks to confirm "send meena I'm late" |
| "what's the weather in chennai", then "and in pune?" | asked the chat model "and in pune?" | asks "what's the weather in pune" |
| "open calculator", then "no, notepad" | not understood | opens Notepad |
| "open notepad", then "close it" | closed whatever window was in front | closes Notepad |
| "open youtube", then "play lofi on it" | searched for "lofi on it" | plays lofi on YouTube |
| "find report.pdf", then "open it" | searched every PDF ("report" was dropped), then could not open "it" | finds report.pdf, opens it |

## 2. How it works

**Conversation carry-over** (`jarvis/core/context/carryover.py`).

- After each command that ran (or is waiting for confirmation), the command service records:
  - what was routed;
  - the tool and its arguments;
  - which apps are open from this conversation (closed ones are removed).
- Before routing, a short follow-up is rewritten into the full sentence it stands for. That sentence then goes
  through the normal router, policy and confirmation. Nothing is executed directly, so a carried-over "send" asks for
  confirmation exactly like a typed one.
- It works on construction shapes, never on particular sentences:

| Shape | Examples |
|---|---|
| new number | make it 60, actually 40%, no I said 17, change it to 6 |
| relative change | a bit louder, quieter, make it brighter |
| new target | do the same for X, same with X, now X, and X as well, no, X, sorry I meant X, what about X |
| new place or person after the same preposition | and in pune?, also to meena |
| pronoun for the app or site just used | close it, minimize it, bring it back, play X on it, open it (after a find) |
| ordinal over the apps opened in this conversation | close the first one, minimize the last one, close both |
| additive word | open calculator too, and paint as well |

**What it never does**

- Resolve "it" for delete, uninstall, send, share, pay, install, rename or reply. "delete it" still asks which file.
- Change the number of a call, send or other consequential action. A new number for those has to be said in full.
- Use a bare "5" for anything but a volume or brightness just set.
- Treat "no, don't", "and then?", "thanks" or "never mind" as a new target.
- Run while JARVIS is waiting for an answer or a confirmation.
- Use context older than 15 minutes.

**App inside a browser.** "open X on/in/using <browser>" opens X's web version in that browser. The calculator, Maps,
Translate, Docs, Office, WhatsApp Web and similar are known; anything else becomes a search. This does not apply to:

- the browser's own things (tabs, incognito, history);
- the owner's files ("my resume in chrome");
- activities ("start typing in chrome").

**Talkback.** The `open_app` reply names what really opened, from the launch target. If the words asked for a second app
that didn't open, it says so: "I opened Chrome, but not calculator - I couldn't find that as part of it."

**Bluetooth and Wi-Fi on the PC.** "turn on bluetooth" opens the right Settings page. It says honestly that Windows
doesn't let JARVIS flip that switch.

## 3. Other fixes found by Blind-9 (generic, no sentence-specific rules)

| Was | Now |
|---|---|
| "find report.pdf" / "find my resume pdf" searched every PDF | the name is the query, the extension only the type |
| "set an alarm for 7 am" → network info; "wake me up at 6 pm" → chat | a wake-up reminder at that time |
| "what reminders do i have" *created* a reminder with that text | lists reminders |
| "after 45 minutes pause the music" paused now | scheduled in 45 minutes |
| "go to the paint window", "show the scheduled jobs", "how much charge is on my phone", "hey there" | switch window / list scheduled tasks / phone battery / greeting |
| "look up X for me" searched for "X for me" | courtesy words are not search words |
| "stop that" paused dictation | stops, like "stop" |
| "pause" / "resume" with no JARVIS task running did nothing | pause / resume the media |
| "wipe the d drive" went to chat | refused |
| "zip report.pdf" had no tool | new `compress_files` tool. It zips next to the file, never overwrites, and reads the archive back to check it. |
| "open paint" asked "MS Paint or Paint.NET?" every time | opens Windows Paint (one existing generalisation case expected the question, see below) |
| "rleoad the page" | reload |

## 4. Measurements (honest)

Two new sets were written and frozen (`FROZEN.sha256`) before the fixes they measure:

- **Blind-9** (`tests/blind9`): 2,338 new unseen commands, with more compound and qualified ones.
- **Context suite** (`tests/context`): 34 multi-turn conversations, 67 scored turns. It runs on the full command service
  with every tool replaced by a recorder.

| Set | First run (blind) | After the fixes |
|---|---:|---:|
| Blind-9 | **87.72%**, 0 criticals | 94.14%, 0 criticals (not blind: its failures were used) |
| Context suite, all turns | **67.2%** | 98.5% (not blind) |
| Context suite, follow-up turns | **39.4%** | 97.0% (not blind) |

**Notes on these numbers**

- **Blind-9's first run was after this round's "app in a browser" fix.** It was before the carry-over and the Blind-9
  fixes.
- **Two harness bugs in the context runner were fixed before its baseline.** Tuple outputs were built as lists, and the
  stubbed chat tool was not counted as a chat answer. The expectations were not changed, and the baseline above is
  from the fixed runner on the code without carry-over.
- **The one remaining context failure is the frozen expectation, not the behaviour.** "and in pune?" now asks the chat
  model "what's the weather in pune". That is the designed path, because weather is answered with live web
  grounding. The frozen expectation wanted the web-search tool.
- **The same author wrote both sets and the fixes,** so even the first-run numbers may be optimistic.
- **The carry-over itself is not measured blind.** The context suite was the set it was built against.

**Earlier sets (all spent):**

| Set | Before this round | Now |
|---|---:|---:|
| Blind-7 | 94.00% | 94.03%, 0 criticals |
| Blind-8 | 85.59% | 86.64%, 0 criticals |

## 5. Context-2: follow-ups measured on unseen conversations

The context suite above was the set the carry-over was built against, so its 97% says nothing about unseen follow-ups.
Context-2 (`tests/context2`) was written and frozen afterwards to measure that honestly:

- **Size:** 92 conversation templates, 2 fills each.
- **Surface forms:** the final follow-up turn is said six ways: plain, "jarvis, …", "um …", "… please", "okay …"
  and with a typo. That makes 991 scored follow-up turns.
- **Split:** templates are split by hash into **dev** (441) and **holdout** (550).
- **Rules:** fixes used only dev failures and two fresh probe lists written for this purpose. The runner never prints
  holdout failures. The holdout was run three times, and only its score was read.

| | Dev | Holdout (unseen) |
|---|---:|---:|
| Before any work on it | 54.6% | **54.7%** |
| After cleaning up spoken noise and adding more follow-up shapes | 98.9% | 81.3% |
| After the first fresh probe (more number verbs, pronoun phrasings and corrections) | 98.9% | 88.0% |
| After the second fresh probe (stacked corrections, connectors, time changes) | 98.9% | **91.6%** |

By surface form, the final holdout run gave 93% for each of the plain, wake, filler, please and okay forms. The typo
form scored 78% (39 of 50).

**Honest notes**

- **The goal of 95% on unseen follow-ups is not met.** The final number is **91.6%**.
- **There is a gap between dev (98.9%) and holdout.** That gap is wording the fixes have not seen.
- **The holdout is not fully independent.** I wrote it and the fixes, and its score was read three times. Each
  reading leaks a little, so 91.6% may be slightly optimistic. A set written by someone else, or taken from real use,
  would be the true test.
- **The remaining dev failure is the judge, not the behaviour.** "same with file explorer" closes "explorer", which
  is the same app.

**What was generalised**

- **Spoken noise is cleaned before the follow-up is read.** That covers the wake word, "um / hmm / okay", "please /
  now" tails and swapped-letter typos.
- **Number changes** accept more verbs (bump / drop / push / move / raise … to N), times ("move it to 5:30 pm"),
  "N would be better" and "N instead".
- **Relative changes** cover "too loud / too bright", "max it", and "louder" while music plays.
- **New target or correction** now also covers:
  - "X too", "do X too", "and then X", "repeat that for X";
  - "not A, B" and "B, not A";
  - "I wanted X", "my bad, X", "wrong one / person, X";
  - "no no, open X" (a correction before a full command);
  - "now open X".
- **Pronoun phrasings** now include "get rid of it", "make it bigger", "move it to the right", "go back to it", "open
  the pdf" (after a find) and "search X there".
- **Ordinals** gained "go to / switch to the first one".
- **Messages:**
  - "send the same to X", "no, send it to X" and "wrong person, X" work right after a message. The recipient is
    said, only the message comes from context, and confirmation is still asked.
  - "send kavya on the way" / "in a meeting" now reach the send step (with confirmation as usual). Before, they
    were read as a condition or a channel and never routed.
- **Searches:** right after a web search, "search X" stays a web search. On its own, bare "search X" still means
  files. "search again for X" and bare "skip" were also fixed.

**Still never resolved from context**

- "it" for delete, uninstall, send, share or remove;
- a new number for a call or a send;
- "move it to downloads";
- "no, don't …";
- a bare "pune?".

## 6. Checks

| Check | Previous round | Now |
|---|---|---|
| `pytest jarvis/tests tests` | 2,629 passed, 21 failed | **2,724 passed**, the same 21 failed (they fail on earlier code too), 0 new |
| Phase-500 (16,502) | 16,389, 0 criticals | 16,389, 0 criticals, 0 new failures |
| Phase command suite: dev / blind 1–6 / torture failures | 40 / 16·4·3·3·0·0 | 40 / 16·4·**0**·3·0·0, 0 new |
| Generalisation fixtures | 41 | 41: 2 new ("Open Paint" expected the MS Paint / Paint.NET question, removed on purpose), 2 fixed |
| Universal Operator | 99.95%, 1 wrong capability | 99.95%, 1 wrong capability (the same one), 0 negated executed |
| AGI-520 | dev 93.66%, holdout 69.86% (spent) | dev **96.15%**, holdout 72.69%, 0 critical |
| Blind-7 / Blind-8 (spent) | 94.00% / 85.59% | 94.03% / **87.09%**, 0 criticals |
| New tests (`test_context_carryover.py`) | - | 95 passed |
