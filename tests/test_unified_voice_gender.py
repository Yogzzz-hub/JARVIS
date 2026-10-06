from pathlib import Path
from unittest.mock import Mock
import pytest
from jarvis.core.tts import speech_service as module
from jarvis.core.response.ack_cache import AckCache


class FakePiper:
    fail_male = False
    def __init__(self, model_path=None):
        self.model_path = Path(model_path or module.voice_models('male')[0])
        self._voice = None
    def load(self):
        if self.fail_male and 'rasa_male' in str(self.model_path):
            raise RuntimeError('Missing Tamil male')
    def unload(self): pass
    def cancel(self): pass
    def synthesize(self, text): return b'\x01\x00' * 100


def service(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'PiperEngine', FakePiper)
    return module.JarvisSpeechResponseService(piper_engine=FakePiper(),
        sapi_engine=Mock(), keep_warm=False, preference_path=tmp_path/'voice.json')


def test_gender_switch_updates_both_languages_cache_and_saved_preference(tmp_path, monkeypatch):
    tts = service(tmp_path, monkeypatch)
    assert tts.voice_gender == 'male' and 'rasa_male' in str(tts.tamil.model_path)
    cache = AckCache(tmp_path/'acks')
    cache.add_phrase('Done.', b'OLD_VOICE')
    tts.ack_cache = cache
    tts.on_voice_change = Mock()
    assert tts.set_voice('women') == 'female'
    assert 'lessac' in str(tts.piper.model_path)
    assert 'rasa_female' in str(tts.tamil.model_path)
    assert {v['gender'] for v in tts.voice_registry.snapshot()} == {'female'}
    assert cache.get_phrase_bytes('Done.')[0] != b'OLD_VOICE'
    tts.on_voice_change.assert_called_once()
    tts.sapi.set_gender.assert_called_with('female')
    restored = service(tmp_path, monkeypatch)
    assert restored.voice_gender == 'female'
    assert 'lessac' in str(restored.piper.model_path)
    assert restored.set_voice('men') == 'male'
    assert 'ryan' in str(restored.piper.model_path) and 'rasa_male' in str(restored.tamil.model_path)


def test_failed_pair_load_preserves_both_voices_and_preference(tmp_path, monkeypatch):
    tts = service(tmp_path, monkeypatch)
    tts.set_voice('female')
    previous = tts.preference_path.read_bytes()
    monkeypatch.setattr(FakePiper, 'fail_male', True)
    with pytest.raises(RuntimeError): tts.set_voice('male')
    assert tts.voice_gender == 'female'
    assert 'lessac' in str(tts.piper.model_path) and 'rasa_female' in str(tts.tamil.model_path)
    assert tts.preference_path.read_bytes() == previous


@pytest.mark.parametrize('language', ['ENGLISH', 'TAMIL', 'TANGLISH', 'MIXED'])
def test_language_selection_cannot_change_gender(tmp_path, monkeypatch, language):
    tts = service(tmp_path, monkeypatch)
    for gender in ('female', 'male'):
        tts.set_voice(gender)
        pcm, _ = tts.synthesize('Hello enna தமிழ்', language=language)
        assert pcm and tts.voice_gender == gender
        assert {v['gender'] for v in tts.voice_registry.snapshot()} == {gender}


def test_listening_preview_follows_shared_gender_and_is_not_browser_cached(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jarvis.core.gateway.dashboard_api import register
    monkeypatch.chdir(tmp_path)
    evidence = Path('reports/voice_gender_evidence')
    evidence.mkdir(parents=True)
    for gender in ('male', 'female'):
        for language in ('english', 'tamil', 'tanglish', 'mixed'):
            (evidence/(gender+'_'+language+'.wav')).write_bytes((gender+language).encode())
    tts = SimpleNamespace(voice_gender='male')
    app = FastAPI()
    register(app, SimpleNamespace(service=SimpleNamespace(response=SimpleNamespace(tts=tts))))
    client = TestClient(app)
    for gender in ('male', 'female'):
        tts.voice_gender = gender
        for language in ('english', 'tamil', 'tanglish', 'mixed'):
            response = client.get('/dashboard/voice-benchmark/audio/'+language)
            assert response.status_code == 200
            assert response.headers['cache-control'] == 'no-store'
            assert response.content == Path('reports/voice_gender_evidence', gender+'_'+language+'.wav').read_bytes()
