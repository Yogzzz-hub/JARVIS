"""Clap to wake: a clap is sharp (quiet before, instant rise, collapse inside ~130 ms); speech, music, a door thud
or a sustained noise are not. Synthetic 16 kHz audio, run on the detector's sample clock."""
from __future__ import annotations

import math
import random
from array import array

from jarvis.core.audio.clap import ClapDetector

SR = 16000


def _pcm(samples) -> bytes:
    return array("h", [max(-32767, min(32767, int(s))) for s in samples]).tobytes()


def silence(ms, level=60.0, seed=1):
    rnd = random.Random(seed)
    return [rnd.gauss(0, level) for _ in range(SR * ms // 1000)]


def clap(peak=20000.0, seed=2):
    """A few ms of broadband attack, then an exponential decay of ~15 ms."""
    rnd = random.Random(seed)
    n = SR * 80 // 1000
    return [rnd.gauss(0, 1) * peak * math.exp(-i / (SR * 0.015)) for i in range(n)]


def speech(ms, amp=9000.0, seed=3):
    """A voiced vowel-like tone that swells in over ~60 ms and holds - sustained, with no silence before the peak."""
    rnd = random.Random(seed)
    n = SR * ms // 1000
    return [amp * min(1.0, i / (SR * 0.06)) * (math.sin(2 * math.pi * 180 * i / SR) + 0.3 * rnd.gauss(0, 1))
            for i in range(n)]


def thud(peak=18000.0, seed=4):
    """A door / dropped object: sharp start but a long ringing body (~400 ms)."""
    rnd = random.Random(seed)
    n = SR * 500 // 1000
    return [peak * math.exp(-i / (SR * 0.35)) * (math.sin(2 * math.pi * 90 * i / SR) + 0.2 * rnd.gauss(0, 1))
            for i in range(n)]


def run(detector, *parts):
    audio = [s for part in parts for s in part]
    woke = 0
    pcm = _pcm(audio)
    step = 2 * 1280                                   # 80 ms chunks, like the wake-word feed
    for i in range(0, len(pcm), step):
        woke += detector.feed(pcm[i:i + step])
    return woke


def test_double_clap_wakes():
    det = ClapDetector()
    assert run(det, silence(600), clap(), silence(350), clap(seed=5), silence(600)) == 1
    assert det.diag.claps == 2


def test_single_clap_does_not_wake_in_double_mode_but_does_in_single_mode():
    assert run(ClapDetector(), silence(600), clap(), silence(1500)) == 0
    assert run(ClapDetector(claps_needed=1), silence(600), clap(), silence(600)) == 1


def test_speech_music_and_thuds_never_wake():
    det = ClapDetector(claps_needed=1)
    assert run(det, silence(500), speech(900), silence(300), speech(700, seed=8), silence(300)) == 0
    assert run(ClapDetector(claps_needed=1), silence(500), thud(), silence(300), thud(seed=9), silence(300)) == 0


def test_claps_too_far_apart_do_not_pair_and_quiet_taps_are_ignored():
    assert run(ClapDetector(), silence(600), clap(), silence(2000), clap(seed=6), silence(600)) == 0
    assert run(ClapDetector(claps_needed=1), silence(600), clap(peak=900.0), silence(600)) == 0


def test_works_in_a_noisy_room_and_after_a_wake_cools_down():
    det = ClapDetector()
    noisy = lambda ms, seed: silence(ms, level=700.0, seed=seed)
    assert run(det, noisy(800, 11), clap(peak=26000.0), noisy(300, 12), clap(peak=26000.0, seed=7), noisy(400, 13)) == 1
    # a third clap right after the wake is not half of a new wake
    assert run(det, clap(peak=26000.0, seed=10), noisy(300, 14)) == 0


def test_pipeline_wakes_on_clap_only_when_enabled():
    from jarvis.core.audio.pipeline import VoicePipeline
    assert VoicePipeline(clap_wake="off").clap is None
    assert VoicePipeline(clap_wake="double").clap.claps_needed == 2
    assert VoicePipeline(clap_wake="single").clap.claps_needed == 1
    assert VoicePipeline(clap_wake="1").clap.claps_needed == 2
