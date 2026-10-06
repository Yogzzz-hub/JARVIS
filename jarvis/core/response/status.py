"""Read-only, independently degraded voice/language health."""
import os
from jarvis.core.language_shadow import ShadowStore, get_language_service


def integration_status(runtime):
    voice = getattr(runtime, 'voice', None)
    response = getattr(getattr(runtime, 'service', None), 'response', None)
    tts = getattr(response, 'tts', None)
    wake = getattr(voice, 'wake_engine', None)
    stt = getattr(voice, 'stt', None)
    output = getattr(response, 'audio_output', None)
    mic = getattr(getattr(voice, 'hub', None), 'source', None)
    language = get_language_service()
    shadow = ShadowStore().state()
    from jarvis.core.audio.owner_benchmark import OwnerVoiceBenchmark
    benchmark = OwnerVoiceBenchmark(runtime).state()
    whatsapp = getattr(runtime, 'whatsapp_service', None)
    transport = getattr(whatsapp, 'transport', None)
    def state(value):
        return 'READY' if value else 'UNAVAILABLE'
    try:
        from jarvis.integrations.google.auth.manager import GoogleAuthManager
        auth = GoogleAuthManager()
        google = {'configured_accounts': len(auth.list_accounts()),
            'client_secret_present': auth.has_client_secret, 'credential_validity': 'NOT_PROBED_NO_NETWORK'}
    except Exception:
        google = {'state': 'UNAVAILABLE', 'credential_validity': 'NOT_PROBED_NO_NETWORK'}
    return {
        'deployment': 'INTEGRATED_SHADOW', 'production_authoritative': True,
        'voice_acceptance': 'VOICE_OWNER_TEST_REQUIRED',
        'benchmark': {k: v for k, v in benchmark.items() if k != 'prompts'},
        'wake': {'enabled': bool(voice and voice.wake_enabled), 'state': state(getattr(wake, '_loaded', False)),
            'threshold': getattr(wake, 'threshold', None), 'adaptive_threshold': getattr(wake, 'adaptive_threshold', None),
            'model': getattr(wake, '_model_name', None),
            'bare_jarvis': ('OWNER_ACCEPTANCE_REQUIRED' if getattr(wake, 'bare_model_state', '') ==
                'LOADED_OWNER_ACCEPTANCE_REQUIRED' else 'DEDICATED_MODEL_REQUIRED_UNVALIDATED'),
            'bare_model_state': getattr(wake, 'bare_model_state', 'MISSING'),
            'model_scores': getattr(wake, 'last_scores', {}),
            'hey_jarvis': state(getattr(wake, '_loaded', False)),
            'recent_events': getattr(voice, 'recent_wakes', []),
            'detections': getattr(voice, 'total_wake_triggers', 0),
            'false_trigger_diagnostics': getattr(voice, 'false_wake_triggers', 0),
            'inference_ms': getattr(wake, 'last_inference_ms', None), 'accuracy': 'NOT_MEASURED'},
        'microphone': state(voice and voice.is_running and getattr(mic, '_running', True)),
        'microphone_details': {'state': state(voice and voice.is_running and getattr(mic, '_running', True)),
            'selected': getattr(mic, 'selected_device', None), 'health': getattr(mic, 'device_health', None),
            'sample_rate': getattr(mic, '_native_rate', None), 'channels': 1,
            'rms': getattr(mic, 'last_rms', None), 'noise_floor': getattr(wake, 'noise_floor', None),
            'device_changes': getattr(mic, 'device_changes', [])[-5:]},
        'vad': state(getattr(getattr(voice, 'vad', None), '_loaded', False)),
        'stt': {'state': state(stt and stt.is_loaded), 'engine': getattr(stt, 'model_name_str', None),
            'device': getattr(stt, '_device_actual', None), 'language': getattr(stt, 'language', None),
            'timeline': getattr(voice, 'last_timeline', {}) if voice else {}},
        'latest_transcript': getattr(voice, 'last_transcript', {}),
        'production_route': getattr(voice, 'last_result', None),
        'session': {'state': 'FOLLOW_UP_ACTIVE' if getattr(response, 'active_followup_window', False) else 'WAKE_REQUIRED',
            'remaining_seconds': getattr(response, 'followup_remaining_seconds', 0),
            'recording': bool(voice and getattr(voice, 'benchmark_active', False))},
        'language': {'supported': ['ENGLISH', 'TANGLISH', 'TAMIL', 'MIXED', 'ASR'],
            'shadow_enabled': language.enabled(), 'worker': 'RUNNING' if language.process and language.process.poll() is None else 'LAZY_NOT_LOADED',
            'queue_length': language.pending.qsize(), 'candidate_controls_tools': False},
        'capability_brain': state(getattr(runtime, 'registry', None)),
        'tts': {'state': state(tts), 'engine': getattr(tts, 'active_backend', None),
            'gender': getattr(tts, 'voice_gender', None),
            'voice': str(getattr(getattr(tts, 'piper', None), 'model_path', '')),
            'response_language': getattr(tts, 'response_language', None),
            'voices': tts.voice_registry.snapshot() if hasattr(tts, 'voice_registry') else [],
            'last_synthesis_ms': getattr(tts, 'last_synthesis_ms', None),
            'first_audio_ms': getattr(tts, 'last_first_audio_ms', None),
            'warmup': getattr(tts, 'warmup_metrics', {}),
            'queue_length': len(output.queue) if output and hasattr(output, 'queue') else 0},
        'speaker': state(output and getattr(output, '_running', False)),
        'barge_in': {'available': bool(getattr(voice, 'barge_in', None)), 'speaking': bool(output and output.is_playing)},
        'whatsapp_bridge': state(transport and transport.is_connected),
        'google_auth': google,
        'phone_bridge': {'route': '/phone/voice', 'authentication_configured': len(os.environ.get('JARVIS_PHONE_TOKEN', '')) >= 32,
            'tls_required': True, 'client_pairing_verified': False},
        'shadow': {k: shadow.get(k) for k in ('counts', 'owner_reviewed', 'agreements', 'latency')},
    }
