"""Audit of Blind-10's frozen expectations, written after the first run (the frozen cases are never edited).

Each entry is a case my expectation scored as wrong although JARVIS chose an equally correct action, or a typo I made
while rewording a case. The report gives both numbers: strict (as frozen) and audited (these counted as correct).
"""
ACCEPT = {
    "set the phone brightness to 45": "my typo: the reworded case kept the old number 40 in `need`",
    "type hi there on my phone": "my typo: the reworded case kept the old word 'hello' in `need`",
    "copy the selected text to my phone": "right tool (localsend_text); 'phone' is not one of its arguments",
    "copy the link of this page": "browser_op 'copy url' is the link",
    "screenshot only this window": "take_screenshot window='active' is this window",
    "close that popup window": "dialog_interaction 'dismiss' closes the popup",
    "click the third link": "ui_op target 'the third link' (ordinal in words)",
    "select the second option": "ui_op target 'the second option' (ordinal in words)",
    "go to the end of the line": "text_op caret / line / right is the end of the line",
    "continue the web task": "web_task resume=true",
    "fill the contact form on this page with my name and email": "browser_autofill on this page",
    "open task manager please": "pc_quick_action 'task manager' opens it",
    "how much ram am i using": "resource_usage reports CPU / RAM / GPU load (runtime handler)",
    "show cpu usage": "resource_usage reports CPU / RAM / GPU load (runtime handler)",
    "what failed just now": "previous_outcome reports the last command's result (runtime handler)",
    "what's running right now": "task_status lists running tasks (runtime handler)",
    "cancel that request": "cancel_task (same handler, executing lane instead of the control lane)",
    "undo the last change": "pc_quick_action undo presses Ctrl+Z",
    "copy the selection": "pc_quick_action copy presses Ctrl+C",
    "redo that": "pc_quick_action redo presses Ctrl+Y",
    "bring up the run box": "pc_quick_action 'run dialog' (Win+R)",
    "open task view": "pc_quick_action 'task view' (Win+Tab)",
    "open action center": "pc_quick_action 'notification center' (Win+N / Win+A)",
    "paste the clipboard into notepad": "deliver_op clipboard -> notepad",
    "summarise this page": "web_task reads and summarises the current page",
    "read this article to me": "web_task reads the current page",
    "sign in to github": "opens GitHub's sign-in page; it types no credentials",
}
