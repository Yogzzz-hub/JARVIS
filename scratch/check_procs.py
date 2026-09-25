import psutil

for p in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmd = " ".join(p.info['cmdline'] or [])
        name = p.info['name'].lower()
        if 'python' in name or 'jarvis' in cmd.lower() or 'node' in name:
            print(f"{p.info['pid']}: {p.info['name']} -> {cmd[:120]}")
    except Exception:
        pass
