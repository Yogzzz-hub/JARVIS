"""Visual and spoken views of one verified WhatsApp result; never changes tool evidence."""
from datetime import datetime
from zoneinfo import ZoneInfo
import re

IDENTIFIER = re.compile(r'\b[\w.+:-]+@(?:s\.whatsapp\.net|lid|g\.us)\b|\b[a-fA-F0-9]{24,}\b|\+?\b\d[\d ()-]{7,}\d\b')
SECRET = re.compile(r'\b(?:otp|one.time.password|verification.code|password|passwd|api.key|access.token|secret|bearer)\b', re.I)


def public_text(text):
    return IDENTIFIER.sub('one contact', str(text or ''))


def display_name(message, resolver=None):
    # Saved exact identity first; no fuzzy match or fabricated contact.
    identity = message.get('sender_id') or message.get('chat_id') or ''
    if resolver and identity:
        contact, _, _ = resolver.resolve(identity)
        if contact:
            candidate = contact.display_name
            if candidate and not IDENTIFIER.search(candidate) and not SECRET.search(candidate): return candidate
    for key in ('sender', 'sender_display_name', 'display_name', 'alias', 'chat_name', 'name'):
        value = str(message.get(key) or '').strip()
        if value and not IDENTIFIER.search(value) and not SECRET.search(value) and not value.isdigit() and '@' not in value:
            return value
    return 'one contact'


def preview(text, limit=8):
    if SECRET.search(str(text or '')): return '[private message; view securely]'
    words = public_text(text).split()
    return ' '.join(words[:limit]) + ('…' if len(words) > limit else '')


def local_time(value):
    try:
        stamp = float(value)
        if stamp > 1e12: stamp /= 1000
        return datetime.fromtimestamp(stamp, ZoneInfo('Asia/Kolkata')).strftime('%H:%M')
    except (TypeError, ValueError, OverflowError, OSError): return ''


def render(tool, data, language='ENGLISH', resolver=None):
    if tool not in {'read_whatsapp_messages', 'summarize_whatsapp_messages'}: return None
    messages = data.get('messages') or [*data.get('urgent_messages', []), *data.get('normal_messages', [])]
    messages = sorted(messages, key=lambda m: float(m.get('timestamp') or 0), reverse=True)
    sync = data.get('sync_state') not in {None, 'READY'} or data.get('status') == 'PARTIAL_SYNC'
    if tool == 'read_whatsapp_messages' and len(messages) == 1 and data.get('count') == 1 and (data.get('filter') != 'unread' or data.get('selected_sender')):
        m = messages[0]
        name = display_name(m, resolver)
        clock = local_time(m.get('timestamp'))
        said = preview(m.get('text') or m.get('summary'),120 if data.get('selected_sender') else 8)
        text = f'Your latest WhatsApp message is from {name}' + (f' at {clock}' if clock else '') + f'. They said, “{said}.”'
        if language in {'TANGLISH', 'MIXED'}:
            text = f'Latest WhatsApp msg {name} kitta irundhu' + (f' {clock} ku' if clock else '') + f' vandhirukku. “{said}.”'
        elif language in {'TAMIL', 'MIXED_TAMIL_ENGLISH'}:
            text = f'சமீபத்திய WhatsApp செய்தி {name} அனுப்பியது' + (f', நேரம் {clock}' if clock else '') + f'. “{said}.”'
        if sync: text += ' Sync is still incomplete.'
        return dict(visual=text, spoken=text)
    count = data.get('unread_count', data.get('count', data.get('total_pending', 0)))
    chats = data.get('unread_direct_chats')
    group_count = data.get('groups_unread_count', 0)
    direct = [m for m in messages if not m.get('is_group')][:3]
    head = f'You have {count} unread WhatsApp messages' + (f' across {chats} personal chats.' if chats is not None else '.')
    if sync and not count:
        head = 'The unread count is not yet verified.'
    warning = ' Sync is still incomplete.' if sync else ''
    details = [f'• {display_name(m, resolver)} — “{preview(m.get("text") or m.get("summary"))}”' for m in direct]
    groups = f'Group chats have {group_count} more unread messages.' if group_count else ''
    next_action = 'Want personal chats, groups, or priority messages first?'
    spoken = head + warning
    # All unread chats supply names; urgent/question snippets are not the unread inventory.
    contacts = data.get('unread_chats') or direct
    contacts = sorted(contacts,key=lambda c:float(c.get('timestamp') or 0),reverse=True)
    names = []
    for contact in contacts:
        if contact.get('is_group'): continue
        name = display_name(contact,resolver)
        if name not in names: names.append(name)
    named = ', '.join(names[:5])
    if named: spoken += ' Latest unread contacts: '+named+'.'
    spoken += ' Say a name to read their message.'
    if language in {'TANGLISH', 'MIXED'}:
        spoken = f'{count} unread messages irukku.' + (' Sync innum complete aagala.' if sync else '') + (f' Latest unread contacts: {named}.' if named else '') + ' Yaaroda msg padikkanum nu name sollunga.'
    elif language in {'TAMIL', 'MIXED_TAMIL_ENGLISH'}:
        spoken = f'{count} படிக்காத செய்திகள் உள்ளன.' + (' ஒத்திசைவு இன்னும் முடியவில்லை.' if sync else '') + (f' சமீபத்திய தொடர்புகள்: {named}.' if named else '') + ' யாருடைய செய்தியைப் படிக்க வேண்டும் என்று பெயரைச் சொல்லுங்கள்.'
    visual = '\n'.join(x for x in ['WhatsApp Summary', head, warning.strip(), 'Important:' if details else '', *details, groups, 'Next: Personal chats · Groups · Priority'] if x)
    if named: visual += '\nLatest unread contacts: '+named+'\nSay a name to read their message.'
    return dict(visual=public_text(visual), spoken=public_text(spoken.strip()))
