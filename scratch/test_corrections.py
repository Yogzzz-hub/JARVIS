import re

samples = [
    "Open Chrome—actually Edge.",
    "Open Chrome, wait no, open Firefox.",
    "Launch Notepad... actually Calculator.",
    "Adjust speaker volume to 30—sorry, make it exactly 15 percent.",
    "Send message to Vikram—actually send it to Vikram Malhotra.",
    "Search for files in Documents... no, search in Downloads instead.",
    "Prepare email to David, wait make that David Miller.",
    "Set volume to 60... make that 40."
]

def resolve_discourse_correction(text: str) -> str:
    cleaned = text.strip().rstrip(".!?")
    
    # Check for correction markers
    # e.g. text — actually <corr> or text, wait no, <corr> or text... make that <corr>
    pattern = re.compile(
        r"^(?P<initial>.+?)(?:—|\.\.\.|,)\s*(?:actually|wait\s+no|sorry\s*,?\s*make\s+(?:it|that)|make\s+that|scratch\s+that|\bno\b)\s*,?\s*(?P<corr>.+)$",
        re.I
    )
    m = pattern.match(cleaned)
    if not m:
        pattern2 = re.compile(
            r"^(?P<initial>.+?)\s+(?:actually|wait\s+no|sorry\s+make\s+(?:it|that)|make\s+that|scratch\s+that)\s+(?P<corr>.+)$",
            re.I
        )
        m = pattern2.match(cleaned)
        
    if not m:
        return text

    initial = m.group("initial").strip()
    corr = m.group("corr").strip()
    
    # Check if correction is a full clause/verb phrase
    verb_prefix = re.match(r"^(?:open|launch|start|bring\s+up|send|message|search|find|adjust|set)\b", corr, re.I)
    if verb_prefix:
        return corr
    
    # Check if correction is a single entity replacing an entity in initial
    # e.g. "Open Chrome" + "Edge" -> "Open Edge"
    # e.g. "Launch Notepad" + "Calculator" -> "Launch Calculator"
    m_open = re.match(r"^(?P<cmd>open|launch|start|bring\s+up)\s+(.+)$", initial, re.I)
    if m_open:
        return f"{m_open.group('cmd')} {corr}"

    # e.g. "Set volume to 60" + "40" or "exactly 15 percent"
    m_vol = re.match(r"^(?P<cmd>set\s+volume\s+to|adjust\s+speaker\s+volume\s+to|volume\s+to)\s+\d+%?", initial, re.I)
    if m_vol:
        corr_num = re.search(r"\d+", corr)
        if corr_num:
            return f"{m_vol.group('cmd')} {corr_num.group(0)}"

    # e.g. "Send message to Vikram" + "Vikram Malhotra"
    m_send = re.match(r"^(?P<cmd>(?:send\s+(?:a\s+)?message\s+to|tell|message))\s+[a-zA-Z\s]+(?P<rest>.*)$", initial, re.I)
    if m_send and ("to" not in corr.lower()):
        return f"{m_send.group('cmd')} {corr}{m_send.group('rest')}"

    # e.g. "Search for files in Documents" + "in Downloads instead" or "Downloads"
    m_search = re.match(r"^(?P<cmd>search\s+(?:for\s+files\s+)?in)\s+\w+(?P<rest>.*)$", initial, re.I)
    if m_search:
        clean_corr = re.sub(r"^(?:in\s+)?|(?:\s+instead)$", "", corr, flags=re.I).strip()
        return f"{m_search.group('cmd')} {clean_corr}{m_search.group('rest')}"

    # Fallback: if correction has substantial length, return it
    if len(corr.split()) >= 2:
        return corr
    return f"{initial} {corr}"

for s in samples:
    res = resolve_discourse_correction(s)
    print(f"'{s}'\n  -> '{res}'\n")
