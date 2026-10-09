"""Offline voice-pair synthesis check; does not change the owner's saved preference."""
from pathlib import Path
import json
import tempfile
import wave
from jarvis.core.tts.speech_service import JarvisSpeechResponseService


def main():
    root = Path('reports/voice_gender_evidence')
    root.mkdir(exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        service = JarvisSpeechResponseService(keep_warm=False, preference_path=Path(tmp)/'voice.json')
        samples = {'ENGLISH': 'The backend is running.', 'TAMIL': 'வணக்கம். நேரம் என்ன?',
            'TANGLISH': 'Backend irukku. enna pannu?', 'MIXED': 'FastAPI backend இயங்குகிறது.'}
        for gender in ['female', 'male']:
            service.set_voice(gender)
            for language, text in samples.items():
                pcm, backend = service.synthesize(text, language=language)
                assert pcm, (gender, language, backend)
                with wave.open(str(root/(gender+'_'+language.lower()+'.wav')), 'wb') as out:
                    out.setnchannels(1); out.setsampwidth(2); out.setframerate(22050); out.writeframes(pcm)
                results.append({'gender': gender, 'language': language, 'bytes': len(pcm),
                    'backend': backend, 'voices': service.voice_registry.snapshot()})
        service.unload()
    (root/'functional.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('Eight real local synthesis cases passed')


if __name__ == '__main__': main()
