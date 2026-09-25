"""Live Voice Testing Script for JARVIS EDGE Desktop Dashboard.
Tests voice command processing, wake-word stripping, speech response generation,
barge-in cancellation, and voice conversational continuity through the live server.
"""

import json
import time
import urllib.request
import urllib.error

BACKEND_URL = "http://127.0.0.1:8765/command"

VOICE_TEST_SCENARIOS = [
    ("Wake + Simple Command", "Hey Jarvis, what time is it?"),
    ("Wake + App Launch", "Ok Jarvis, launch Calculator please"),
    ("Colloquial Wake + Colloquial App", "Jarvis bro, open Notepad da"),
    ("Voice Negation", "Hey Jarvis, don't open Chrome"),
    ("Voice Date Query", "Hey Jarvis, what is today's date?"),
    ("Voice Phone Status", "Hey Jarvis, is my phone connected?"),
    ("Voice Cancellation / Barge-in", "Stop"),
    ("Voice Continuity Turn 1", "Hey Jarvis, what is Ollama?"),
    ("Voice Continuity Turn 2 (Pronoun)", "Install it"),
]


def send_voice_command(text: str, req_id: str) -> dict:
    payload = json.dumps({
        "text": text,
        "request_id": req_id,
        "source": "voice"  # Authenticated voice source
    }).encode("utf-8")
    req = urllib.request.Request(
        BACKEND_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_voice_tests():
    print("=" * 80)
    print("  JARVIS EDGE -- LIVE VOICE TESTING PIPELINE")
    print("  Target: Live Desktop UI Dashboard Voice Overlay & Pipeline")
    print("=" * 80)

    passed = 0
    total = len(VOICE_TEST_SCENARIOS)

    for idx, (label, spoken_utterance) in enumerate(VOICE_TEST_SCENARIOS, 1):
        req_id = f"voice_test_{idx}_{int(time.time()*1000)}"
        print(f"\n[Voice Test {idx}/{total}] {label}")
        print(f"  SPOKEN INPUT: \"{spoken_utterance}\" (source='voice')")
        
        t0 = time.time()
        try:
            res = send_voice_command(spoken_utterance, req_id)
            elapsed_ms = (time.time() - t0) * 1000
            
            state = res.get("state")
            msg = res.get("message", "")
            tool_name = res.get("tool_result", {}).get("tool_name") if res.get("tool_result") else None
            
            print(f"  STATE:        {state}")
            print(f"  TOOL:         {tool_name}")
            print(f"  RESPONSE:     {msg}")
            print(f"  LATENCY:      {elapsed_ms:.2f} ms")
            
            # Evaluate test
            if "don't" in spoken_utterance.lower():
                assert any(w in msg.lower() for w in ("negat", "no action", "stopped")), "Negation failed"
            elif label == "Voice Cancellation / Barge-in":
                assert "cancellation" in msg.lower() or "stopped" in msg.lower(), "Barge-in failed"
            elif label == "Voice Continuity Turn 2 (Pronoun)":
                assert "ollama" in msg.lower(), "Voice continuity failed to resolve Ollama"
            else:
                assert state == "SUCCESS", f"Expected SUCCESS but got {state}"
                
            print(f"  -> RESULT:    PASS")
            passed += 1
        except Exception as exc:
            print(f"  -> RESULT:    FAIL ({exc})")

        time.sleep(0.5)

    print("\n" + "=" * 80)
    print(f"  VOICE TESTING COMPLETE: {passed}/{total} ({passed/total*100:.1f}%) PASSED")
    print("=" * 80)


if __name__ == "__main__":
    run_voice_tests()
