"""Streaming noise suppression for the microphone path (VAD, speech recognition, live transcription).

A short-time spectral Wiener filter, built only on numpy so it runs everywhere with a few hundred microseconds per
20 ms frame:

    high-pass  ->  STFT (20 ms sqrt-Hann window, 10 ms hop)  ->  noise spectrum tracking  ->  Wiener gain
    (decision-directed a-priori SNR, gain floor, smoothed over time and frequency)  ->  overlap-add

* The noise spectrum follows the quietest recent level of every frequency band (fans, AC hum, traffic, PC fans): it
  drops at once to a quieter level and rises only slowly, so speech never becomes "noise".
* A gain floor (default -15 dB) keeps a little of the background: removing everything produces "musical noise" that
  makes Whisper invent words, which is worse than the noise itself.
* Speech-band frames get a gentle automatic gain so a quiet or distant voice reaches the level the VAD and Whisper
  expect; the gain never exceeds 4x and never amplifies silence.
* The wake-word model keeps the raw microphone audio: it was trained on unprocessed speech.

Output has the same length as the input with one hop (10 ms) of latency. ``levels`` gives the UI the speech level,
noise floor and SNR.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

STRENGTH_FLOOR_DB = {"low": -9.0, "medium": -15.0, "high": -22.0}


@dataclass
class NoiseLevels:
    level_db: float = -90.0     # current frame level (dBFS)
    noise_db: float = -90.0     # tracked background level (dBFS)
    snr_db: float = 0.0
    gain_db: float = 0.0        # automatic gain applied to speech
    reduction_db: float = 0.0   # how much noise was removed from the last frame


class NoiseSuppressor:
    def __init__(self, sample_rate: int = 16000, strength: str = "medium", auto_gain: bool = True,
                 window_ms: float = 20.0, highpass_hz: float = 80.0):
        self.sr = sample_rate
        self.win = int(sample_rate * window_ms / 1000)            # 320
        self.hop = self.win // 2                                   # 160
        n = np.arange(self.win)
        self.window = np.sqrt(0.5 - 0.5 * np.cos(2 * np.pi * n / self.win))   # periodic sqrt-Hann: perfect reconstruction
        self.bins = self.win // 2 + 1
        freqs = np.fft.rfftfreq(self.win, 1.0 / sample_rate)
        self.highpass = np.clip((freqs - highpass_hz * 0.5) / (highpass_hz * 0.5), 0.0, 1.0)  # soft cut below ~80 Hz
        self.floor = 10 ** (STRENGTH_FLOOR_DB.get(strength, -15.0) / 20)
        self.strength = strength
        self.auto_gain = auto_gain
        self.reset()

    def reset(self) -> None:
        self._in = np.zeros(self.win, dtype=np.float64)           # analysis buffer (last window)
        self._pending = np.zeros(0, dtype=np.float64)              # samples not yet analysed
        self._ola = np.zeros(self.win, dtype=np.float64)           # overlap-add accumulator
        self._out = np.zeros(0, dtype=np.float64)                  # finished samples waiting to be returned
        self._noise = None                                          # noise power per bin
        self._smooth = None
        self._prev_gain = np.ones(self.bins)
        self._prev_post = np.ones(self.bins)
        self._frames = 0
        self._agc = 1.0
        self.levels = NoiseLevels()

    # ------------------------------------------------------------------------------------------------ streaming
    def process(self, pcm: bytes) -> bytes:
        """PCM16 mono in -> the same number of PCM16 samples out (cleaned, one hop late)."""
        x = np.frombuffer(pcm, dtype=np.int16).astype(np.float64) / 32768.0
        if x.size == 0:
            return pcm
        self._pending = np.concatenate([self._pending, x])
        while self._pending.size >= self.hop:
            self._step(self._pending[: self.hop])
            self._pending = self._pending[self.hop:]
        need = x.size
        if self._out.size < need:   # can only happen on odd frame sizes: pad with silence, never stall
            self._out = np.concatenate([self._out, np.zeros(need - self._out.size)])
        y, self._out = self._out[:need], self._out[need:]
        return (np.clip(y, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()

    def _step(self, hop: np.ndarray) -> None:
        self._in = np.concatenate([self._in[self.hop:], hop])
        spec = np.fft.rfft(self._in * self.window)
        power = spec.real ** 2 + spec.imag ** 2
        self._frames += 1

        # ---- noise tracking: follow the quietest recent level of each band
        if self._smooth is None:
            self._smooth = power.copy()
            self._noise = power.copy() + 1e-12
        else:
            self._smooth = 0.7 * self._smooth + 0.3 * power
        if self._frames <= 25:      # first 250 ms: learn the room quickly
            self._noise = np.minimum(self._noise * 1.05, 0.8 * self._noise + 0.2 * self._smooth) + 1e-12
        else:
            down = self._smooth < self._noise
            self._noise = np.where(down, 0.6 * self._noise + 0.4 * self._smooth, self._noise * 1.004) + 1e-12

        # ---- decision-directed Wiener gain
        post = power / self._noise
        prio = 0.96 * (self._prev_gain ** 2) * self._prev_post + 0.04 * np.maximum(post - 1.0, 0.0)
        gain = prio / (1.0 + prio)
        gain = np.convolve(gain, np.array([0.25, 0.5, 0.25]), mode="same")   # smooth across frequency
        gain = np.maximum(gain, self.floor) * self.highpass
        self._prev_gain, self._prev_post = gain, post

        clean = np.fft.irfft(spec * gain, n=self.win) * self.window
        self._ola += clean
        out = self._ola[: self.hop].copy()
        self._ola = np.concatenate([self._ola[self.hop:], np.zeros(self.hop)])

        # ---- levels and automatic gain for speech
        sig_p = float(np.mean(power)) + 1e-20
        noise_p = float(np.mean(self._noise)) + 1e-20
        scale = self.win / 2.0   # Parseval with a sqrt-Hann window: mean bin power ~ (N / 2) x mean square of the signal
        level_db = 10 * math.log10(sig_p / scale + 1e-12)
        noise_db = 10 * math.log10(noise_p / scale + 1e-12)
        snr = level_db - noise_db
        if self.auto_gain:
            rms = float(np.sqrt(np.mean(out ** 2))) + 1e-9
            if snr > 6.0 and rms > 1e-4:            # speech: steer toward about -24 dBFS, at most 4x
                target = min(4.0, max(1.0, 0.063 / rms))
                self._agc += 0.05 * (target - self._agc)
            else:                                    # background: relax back to unity, never amplify silence
                self._agc += 0.02 * (1.0 - self._agc)
            out = out * self._agc
        removed = float(np.mean(gain ** 2))
        self.levels = NoiseLevels(level_db=round(level_db, 1), noise_db=round(noise_db, 1), snr_db=round(snr, 1),
                                  gain_db=round(20 * math.log10(self._agc), 1),
                                  reduction_db=round(-10 * math.log10(max(removed, 1e-6)), 1))
        self._out = np.concatenate([self._out, out])


def snr_db(clean: np.ndarray, noisy: np.ndarray) -> float:
    """SNR of ``noisy`` against the reference ``clean`` (both float arrays, same length)."""
    noise = noisy - clean
    return 10 * math.log10((np.sum(clean ** 2) + 1e-12) / (np.sum(noise ** 2) + 1e-12))
