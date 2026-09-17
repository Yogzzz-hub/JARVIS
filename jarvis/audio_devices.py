"""Audio device inspection tool for JARVIS EDGE.

Lists available audio input and output devices with sample rates,
channels, and device indices.
"""
from __future__ import annotations

import argparse
import sys


def list_devices() -> None:
    """Print formatted audio devices."""
    try:
        import sounddevice as sd
    except ImportError:
        print("Error: sounddevice is not installed. Run: pip install sounddevice")
        sys.exit(1)

    devices = sd.query_devices()
    default_in, default_out = sd.default.device

    print("=" * 60)
    print("        JARVIS EDGE -- AUDIO DEVICES")
    print("=" * 60)
    print(f"{'ID':<4} {'Name':<35} {'In':<4} {'Out':<4} {'Default Rate':<12}")
    print("-" * 60)

    for i, dev in enumerate(devices):
        is_default_in = (i == default_in)
        is_default_out = (i == default_out)
        tag = ""
        if is_default_in and is_default_out:
            tag = " [DEFAULT IN/OUT]"
        elif is_default_in:
            tag = " [DEFAULT IN]"
        elif is_default_out:
            tag = " [DEFAULT OUT]"

        name = dev["name"][:32] + ("..." if len(dev["name"]) > 32 else "")
        print(
            f"{i:<4} {name:<35} {dev['max_input_channels']:<4} "
            f"{dev['max_output_channels']:<4} {int(dev['default_samplerate']):<12}{tag}"
        )

    print("=" * 60)
    hostapis = sd.query_hostapis()
    print("Host APIs:")
    for api in hostapis:
        print(f"  [{api['name']}] default in: {api.get('default_input_device', 'none')}, out: {api.get('default_output_device', 'none')}")
    print("=" * 60)


def get_default_input_device_info() -> dict:
    """Get dictionary of default input device info."""
    try:
        import sounddevice as sd
        device_id = sd.default.device[0]
        if device_id < 0:
            return {"status": "none"}
        info = sd.query_devices(device_id)
        return {
            "status": "ok",
            "id": device_id,
            "name": info["name"],
            "channels": info["max_input_channels"],
            "samplerate": int(info["default_samplerate"]),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS Audio Device Inspector")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    if args.json:
        import json
        print(json.dumps(get_default_input_device_info(), indent=2))
    else:
        list_devices()


if __name__ == "__main__":
    main()
