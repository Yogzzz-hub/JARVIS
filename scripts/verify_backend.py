"""
Verifies if JARVIS backend is reachable and responsive on http://127.0.0.1:8765/health.
Returns exit code:
  0 - JARVIS is healthy and ready
  1 - Port is open but responded with invalid/non-JARVIS payload or HTTP error (conflict!)
  2 - Connection refused / port is not listening
"""
import json
import sys
import urllib.request
import urllib.error

def main():
    url = "http://127.0.0.1:8765/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Launcher-HealthCheck"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if "tool_count" in data or data.get("status") in ("ready", "stopping"):
                    sys.exit(0)
            sys.exit(1)
    except urllib.error.HTTPError:
        # Received HTTP response (e.g. 404 from another app)
        sys.exit(1)
    except urllib.error.URLError:
        # Connection refused / host unreachable -> port is free or not listening
        sys.exit(2)
    except Exception:
        sys.exit(2)

if __name__ == "__main__":
    main()
