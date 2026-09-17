"""Audio device inspection tool for JARVIS EDGE.

Lists available audio input and output devices with sample rates,
channels, and device indices.
"""
from __future__ import annotations

import argparse
import sys


def list_devices() -> None:
    """Print formatted audio devices separated into Input and Output."""
    try:
        import sounddevice as sd
    except ImportError:
        print("Error: sounddevice is not installed. Run: pip install sounddevice")
        sys.exit(1)

    devices = sd.query_devices()
    default_in, default_out = sd.default.device

    print("=" * 65)
    print("        JARVIS EDGE -- AUDIO DEVICES INSPECTOR")
    print("=" * 65)
    
    # Input Devices
    print("\n--- INPUT DEVICES (Microphones) ---")
    print(f"{'ID':<4} {'Name':<38} {'Channels':<10} {'Default Rate':<12}")
    print("-" * 65)
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            is_default = (i == default_in)
            tag = " [DEFAULT IN]" if is_default else ""
            name = dev["name"][:35] + ("..." if len(dev["name"]) > 35 else "")
            print(f"{i:<4} {name:<38} {dev['max_input_channels']:<10} {int(dev['default_samplerate']):<12}{tag}")

    # Output Devices
    print("\n--- OUTPUT DEVICES (Speakers / Headphones) ---")
    print(f"{'ID':<4} {'Name':<38} {'Channels':<10} {'Default Rate':<12}")
    print("-" * 65)
    for i, dev in enumerate(devices):
        if dev["max_output_channels"] > 0:
            is_default = (i == default_out)
            tag = " [DEFAULT OUT]" if is_default else ""
            name = dev["name"][:35] + ("..." if len(dev["name"]) > 35 else "")
            print(f"{i:<4} {name:<38} {dev['max_output_channels']:<10} {int(dev['default_samplerate']):<12}{tag}")

    print("\n" + "=" * 65)
    hostapis = sd.query_hostapis()
    print("Host APIs:")
    for api in hostapis:
        print(f"  [{api['name']}] default in: {api.get('default_input_device', 'none')}, out: {api.get('default_output_device', 'none')}")
    print("=" * 65)


def get_device_info() -> dict:
    """Get dictionary of default input and output device info."""
    try:
        import sounddevice as sd
        default_in, default_out = sd.default.device
        in_info = sd.query_devices(default_in) if default_in >= 0 else None
        out_info = sd.query_devices(default_out) if default_out >= 0 else None

        return {
            "status": "ok",
            "input": {
                "id": default_in,
                "name": in_info["name"] if in_info else "none",
                "channels": in_info["max_input_channels"] if in_info else 0,
                "samplerate": int(in_info["default_samplerate"]) if in_info else 0,
            } if in_info else None,
            "output": {
                "id": default_out,
                "name": out_info["name"] if out_info else "none",
                "channels": out_info["max_output_channels"] if out_info else 0,
                "samplerate": int(out_info["default_samplerate"]) if out_info else 0,
            } if out_info else None,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS Audio Device Inspector")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    if args.json:
        import json
        print(json.dumps(get_device_info(), indent=2))
    else:
        list_devices()


if __name__ == "__main__":
    main()
