"""Common local speech service, retaining Piper/SAPI and playback barge-in."""
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import threading
import json
import os
from time import perf_counter
import numpy as np
from jarvis.core.tts.manager import TTSManager
from jarvis.core.tts.piper_engine import PiperEngine
from jarvis.core.tts.speech_text import speech_text
from jarvis.core.response.coordinator import RESPONSE_LANGUAGE

ROOT = Path(__file__).resolve().parents[3]
TAMIL_MODEL = ROOT / 'models/piper/ta/ta_IN/rasa_female/medium/ta_IN-rasa_female-medium.onnx'
TAMIL_MALE_MODEL = ROOT / 'models/piper/ta/ta_IN/rasa_male/medium/ta_IN-rasa_male-medium.onnx'
VOICE_PREFERENCES = ROOT / 'config/voice_preferences.json'


def voice_models(gender):
    english = ROOT / ('models/piper/en/en_US/lessac/medium/en_US-lessac-medium.onnx'
        if gender == 'female' else 'models/piper/en/en_US/ryan/medium/en_US-ryan-medium.onnx')
    return english, TAMIL_MODEL if gender == 'female' else TAMIL_MALE_MODEL
# Pronunciation-only lexicon. It never sees or rewrites semantic input.
PRONUNCIATION = {'pannu': 'பண்ணு', 'pannunga': 'பண்ணுங்க', 'iruku': 'இருக்கு',
    'irukku': 'இருக்கு', 'solu': 'சொல்லு', 'sollu': 'சொல்லு', 'anupu': 'அனுப்பு',
    'anuppu': 'அனுப்பு', 'venam': 'வேணாம்', 'okay': 'ஓகே', 'um': 'உம்',
    'illa': 'இல்ல', 'enna': 'என்ன', 'epdi': 'எப்படி'}


@dataclass(frozen=True)
class TTSVoice:
    language: str
    locale: str
    engine: str
    voice: str
    sample_rate: int
    availability: bool
    quality_rank: int
    fallback: str
    gender: str = 'male'


class TTSVoiceRegistry:
    def __init__(self, english_model=None, tamil_model=TAMIL_MALE_MODEL, gender='male'):
        en = Path(english_model or ROOT / 'models/piper/en/en_US/ryan/medium/en_US-ryan-medium.onnx')
        self.voices = [TTSVoice('ENGLISH', 'en-US', 'piper', str(en), 22050, en.exists(), 1, 'sapi', gender),
            TTSVoice('TAMIL', 'ta-IN', 'piper', str(tamil_model), 22050, Path(tamil_model).exists(), 1, 'text_only', gender)]

    def snapshot(self):
        return [asdict(v) for v in self.voices]


def speech_segments(text, selected):
    clean = speech_text(text)
    if selected in {'TANGLISH', 'MIXED', 'MIXED_TAMIL_ENGLISH'}:
        clean = re.sub(r'\b(?:' + '|'.join(PRONUNCIATION) + r')\b',
            lambda m: PRONUNCIATION[m.group().lower()], clean, flags=re.I)
    # Whole English technical tokens stay intact. Segment only at script changes.
    segments = []
    for token in re.findall(r'\S+\s*', clean):
        locale = 'TAMIL' if re.search(r'[\u0b80-\u0bff]', token) else 'ENGLISH'
        if segments and segments[-1][0] == locale:
            segments[-1] = (locale, segments[-1][1] + token)
        else:
            segments.append((locale, token))
    return [(locale, value.strip()) for locale, value in segments]


class JarvisSpeechResponseService(TTSManager):
    complete_sentence_chunks = True
    def __init__(self, *args, **kwargs):
        self.preference_path = Path(kwargs.pop('preference_path', VOICE_PREFERENCES))
        super().__init__(*args, **kwargs)
        self.voice_gender = 'male'
        if self.preference_path.exists():
            preference = json.loads(self.preference_path.read_text(encoding='utf-8'))
            self.voice_gender = preference.get('gender', 'male')
            if self.voice_gender not in {'male', 'female'}:
                raise ValueError('Invalid saved voice gender')
            self.piper = PiperEngine(voice_models(self.voice_gender)[0])
        self.tamil = PiperEngine(voice_models(self.voice_gender)[1])
        self.voice_registry = TTSVoiceRegistry(getattr(self.piper, 'model_path', None),
            self.tamil.model_path, self.voice_gender)
        self._synthesis_lock = threading.RLock()
        self.response_language = 'ENGLISH'
        self.last_synthesis_ms = None
        self.secrets_suppressed = 0
        self.warmup_metrics = {}
        self.last_first_audio_ms = None
        self._cancel_generation = 0
        self.ack_cache = None
        self.on_voice_change = None
        self.sapi.set_gender(self.voice_gender)

    def refresh_ack_cache(self, cache):
        """Regenerate RAM acknowledgements using the selected voice; no stale disk clips."""
        from jarvis.core.response.ack_cache import ACK_PHRASES_MAP, WAKE_VOICE_ACKS
        with self._synthesis_lock:
            self.ack_cache = cache
            cache._ram_cache.clear(); cache._durations.clear()
            cache._norm_cache.clear(); cache._norm_durations.clear()
            for phrase in dict.fromkeys([*ACK_PHRASES_MAP, *WAKE_VOICE_ACKS]):
                pcm, _ = self.synthesize(phrase, language='ENGLISH')
                if pcm:
                    cache.add_phrase(phrase, pcm)

    def set_voice(self, gender):
        """Switch the entire bilingual voice pair, or leave both unchanged."""
        value = gender.lower().strip()
        if value in {'female', 'woman', 'women'}:
            label = 'female'
        elif value in {'male', 'man', 'men'}:
            label = 'male'
        else:
            raise ValueError('Voice gender must be male or female')
        with self._synthesis_lock:
            english_path, tamil_path = voice_models(label)
            english, tamil = PiperEngine(english_path), PiperEngine(tamil_path)
            try:
                english.length_scale = tamil.length_scale = 1.0 / getattr(self, 'speech_rate', 1.0)
                english.load()
                tamil.load()
                self.preference_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.preference_path.with_suffix('.tmp')
                temporary.write_text(json.dumps({'gender': label})+'\n', encoding='utf-8')
                os.replace(temporary, self.preference_path)
            except Exception:
                english.unload(); tamil.unload()
                raise
            self.cancel()
            if self.on_voice_change:
                self.on_voice_change()
            old_english, old_tamil = self.piper, self.tamil
            self.piper, self.tamil = english, tamil
            self.voice_gender = label
            self.voice_registry = TTSVoiceRegistry(english_path, tamil_path, label)
            self._generic_phrase_cache.clear()
            self.sample_rate = 22050
            self.active_backend = 'piper'
            self.sapi.set_gender(label)
            old_english.unload(); old_tamil.unload()
            if self.ack_cache is not None:
                self.refresh_ack_cache(self.ack_cache)
            return label

    def warm_up(self):
        import psutil
        started = perf_counter()
        before = psutil.Process().memory_info().rss
        with self._synthesis_lock:
            super().warm_up()
            english_ms = (perf_counter()-started)*1000
            tamil_start = perf_counter()
            tamil_error = None
            if self.keep_warm and Path(self.tamil.model_path).exists():
                try:
                    self.tamil.load()
                except Exception as exc:
                    tamil_error = type(exc).__name__
            self.warmup_metrics = {'english_load_cache_ms': english_ms,
                'tamil_load_warm_ms': (perf_counter()-tamil_start)*1000,
                'ram_delta_mib': (psutil.Process().memory_info().rss-before)/1048576,
                'tamil_error': tamil_error, 'total_ms': (perf_counter()-started)*1000}

    def synthesize(self, text, language=None, *, priority='final', interruptibility=True,
                   response_type='final', device_target='pc'):
        from jarvis.core.language_shadow import safe_text
        if not safe_text(text):
            self.secrets_suppressed += 1
            return b'', 'sensitive_text_suppressed'
        selected = language or RESPONSE_LANGUAGE.get()
        if re.search(r'[\u0b80-\u0bff]', text) and selected == 'ENGLISH':
            selected = 'MIXED_TAMIL_ENGLISH'
        started = perf_counter()
        with self._synthesis_lock:
            self.response_language = selected
            pcm_parts = []
            backends = []
            for locale, part in speech_segments(text, selected):
                if locale == 'TAMIL':
                    try:
                        pcm = self.tamil.synthesize(part)
                        rate = getattr(getattr(self.tamil._voice, 'config', None), 'sample_rate', 22050)
                        backend = 'piper_tamil'
                    except Exception:
                        # Never read Tamil using an English-only voice and claim success.
                        self.text_only_fallbacks += 1
                        return b'', 'tamil_text_only'
                else:
                    pcm, backend = super().synthesize(part)
                    rate = self.sample_rate
                if not pcm:
                    return b'', backend
                if rate != 22050:
                    samples = np.frombuffer(pcm, dtype=np.int16)
                    positions = np.linspace(0, len(samples)-1, round(len(samples)*22050/rate))
                    pcm = np.interp(positions, np.arange(len(samples)), samples).astype(np.int16).tobytes()
                pcm_parts.append(pcm)
                backends.append(backend)
            self.sample_rate = 22050
            self.active_backend = '+'.join(dict.fromkeys(backends)) or 'none'
            self.last_synthesis_ms = (perf_counter()-started)*1000
            return b''.join(pcm_parts), self.active_backend

    async def stream(self, text):
        # One shared normalization/privacy/voice-selection path for every caller.
        import asyncio
        from jarvis.core.tts.base import TTSChunk
        from jarvis.core.language_shadow import safe_text
        if not safe_text(text):
            self.secrets_suppressed += 1
            return
        # Completed sentences only; never split identifiers such as Next.js.
        parts = re.split(r'(?<=[.!?])\s+(?=\S)', text.strip())
        started = perf_counter()
        generation = self._cancel_generation
        first = True
        for index, part in enumerate(parts):
            if generation != self._cancel_generation:
                break
            pcm, backend = await asyncio.to_thread(self.synthesize, part)
            if generation != self._cancel_generation:
                break
            if not pcm:
                raise RuntimeError('Sentence synthesis unavailable: ' + backend)
            if pcm:
                if first:
                    self.last_first_audio_ms = (perf_counter()-started)*1000
                yield TTSChunk(pcm=pcm, sample_rate=self.sample_rate, sample_width=2, channels=1,
                    is_final=index == len(parts)-1, first_chunk=first, text=part,
                    duration_ms=len(pcm)/44.1), backend
                first = False

    def cancel(self):
        self._cancel_generation += 1
        super().cancel()
        self.tamil.cancel()

    def unload(self):
        super().unload()
        self.tamil.unload()
