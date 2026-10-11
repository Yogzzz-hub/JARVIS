import json, sqlite3, time, sys
from pathlib import Path

db_path = Path("jarvis/data/whatsapp_inbox.db")
conn = sqlite3.connect(str(db_path))

# Mark all messages older than 24h as read
conn.execute("UPDATE whatsapp_messages SET is_read = 1 WHERE is_read = 0 AND timestamp < ?", (time.time() - 24 * 3600,))

# Clear any bogus old unread chats in whatsapp_chats
conn.execute("UPDATE whatsapp_chats SET unread = 0")

# Load real chats from chat_index.json
p = Path("integrations/data/whatsapp_auth_fresh_latency_test/chat_index.json")
if p.exists():
    data = json.load(open(p, "r", encoding="utf-8"))
    for c in data.get("chats", []):
        cid = c["jid"]
        unread = max(0, int(c.get("unread") or 0))
        last_ts = float(c.get("lastTs") or 0)
        is_group = 1 if c.get("isGroup") else 0
        name = str(c.get("name") or "").strip()
        last_text = str(c.get("lastText") or "")[:300]
        last_sender = str(c.get("lastSender") or "").strip()
        last_from_me = 1 if c.get("lastFromMe") else 0
        conn.execute("""
            INSERT INTO whatsapp_chats (chat_id, name, unread, last_ts, is_group, last_text, last_sender, last_from_me, updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                name = CASE WHEN excluded.name != '' THEN excluded.name ELSE whatsapp_chats.name END,
                unread = excluded.unread, last_ts = MAX(whatsapp_chats.last_ts, excluded.last_ts),
                is_group = excluded.is_group, last_text = excluded.last_text,
                last_sender = excluded.last_sender, last_from_me = excluded.last_from_me,
                updated = excluded.updated
        """, (cid, name, unread, last_ts, is_group, last_text, last_sender, last_from_me, time.time()))

conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES ('chats_synced', '1')")
conn.execute("INSERT OR REPLACE INTO whatsapp_meta (key, value) VALUES ('connector_state', 'READY')")
conn.commit()

from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
inbox = WhatsAppInbox(db_path=db_path)
unread = inbox.unread_chats(include_groups=True)
sys.stdout.reconfigure(encoding="utf-8")
print(f"Total unread chats now: {len(unread)}")
for u in unread[:10]:
    print(f"  - {u['name']} (group={u['is_group']}): {u['unread']} unread | last: '{u['last_text'][:35]}'")
