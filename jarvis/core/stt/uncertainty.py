"""Preserve recognition evidence; never correct names or authorize tools.

Whisper probabilities are uncalibrated. The conservative 0.65 floor is a
development guard, not a measured semantic confidence or acceptance metric.
"""
import math


def transcript_evidence(text, segments):
    words = [w for s in (segments or []) if s.get('kept', True) for w in s.get('words', [])]
    uncertain = []
    cursor = 0
    scores = []
    for word in words:
        token = str(word.get('word', '')).strip()
        score = float(word.get('probability', 0) or 0)
        score = score if math.isfinite(score) else 0.0
        scores.append(score)
        start = text.find(token, cursor)
        if start >= 0:
            cursor = start + len(token)
        if score < .65:
            uncertain.append({'text': token, 'start': start if start >= 0 else None,
                'end': cursor if start >= 0 else None, 'probability': score,
                'audio_start_s': word.get('start'), 'audio_end_s': word.get('end')})
    omitted = any(not s.get('kept', True) and str(s.get('text', '')).strip() for s in (segments or []))
    return {'raw_text': text, 'confidence': min(scores) if scores else None,
        'uncertain_spans': uncertain, 'clarification_required': bool(text and (uncertain or not scores or omitted)),
        'alternatives': []}


def requires_clarification(transcript):
    return bool(getattr(transcript, 'clarification_required', False))
