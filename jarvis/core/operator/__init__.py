"""Universal Operator: a small set of typed, verifiable primitives for operating windows, controls, text, the
clipboard, the screen, browsers, media, the IDE and an Android phone.

Every user-level behaviour ("open Chrome full screen", "paste that screenshot in Antigravity", "skip the ad when
it lets you") is a composition of these primitives:

    window   target / set_state / arrange / focus            (+ foreground history)
    ui       find / invoke / set_value / read / scroll        (one resolver, platform adapters)
    text     insert / edit                                    (named key chords only)
    dictate  live session fed by the speech recogniser's stable words
    clip     get / set / save+restore                         (ClipboardResource)
    screen   capture / read                                   (ScreenshotResource, structured text first)
    deliver  resource -> control/app/device as paste / attach / upload / send
    browser  attach / navigate / tab / page / results         (owner's browser over DevTools, keys as fallback)
    media    play / pause / seek / speed / captions / ...      (MediaResource)
    watch    a scoped, time-bounded condition -> action        (skip-ad, download done, generation done)
    ide      prompt / tabs / panes / attach / send / wait      (built on ui + text + deliver)
    device   phone ui / app / key / media / notification / dev (ADB adapter; no lock or security bypass)

The router maps any wording to these schemas; the tools validate, the policy decides, the executor runs, a
verifier checks the real effect. Platform differences live in adapters; nothing guesses coordinates.
"""
