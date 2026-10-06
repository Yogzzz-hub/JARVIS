"""Shared, advisory multilingual understanding. No execution or reply authority.

The frozen V2 encoder remains unchanged. Development decoding lives here so
historical evaluation bytes and claims are never rewritten.
"""
from __future__ import annotations
import copy
import re
from dataclasses import asdict
from jarvis.core.capabilities.frame import SemanticFrame


def language(text):
    if re.search(r'[\u0b80-\u0bff]', text):
        return 'MIXED_TAMIL_ENGLISH' if re.search(r'[A-Za-z]', text) else 'TAMIL'
    from jarvis.integrations.whatsapp.personal_reply.language import detect
    return detect(text).label


def repair(frame, context=None):
    """Evidence-based scope/role/reference repairs; never authorize execution."""
    from scripts.nlp_structural_slots import typed_slot, reconstruct, ORDINALS
    result = copy.deepcopy(frame)
    text = result['raw_text']
    # Mask quotes with equal-length spaces, preserving original codepoint offsets.
    evidence = re.sub(r'"[^"\n]*"|“[^”\n]*”', lambda m: ' ' * len(m[0]), text)
    evidence = re.sub(r"(?<!\w)'[^'\n]*'(?!\w)", lambda m: ' ' * len(m[0]), evidence)
    prohibitions = list(re.finditer(r"\b(?:don['’]t|do\s+not|never)\s+\w+|\b[a-z]+(?:adha|atha)\b|\b(?:venam|vendam|venda)\b|[\u0b80-\u0bff]*ாதே|பண்ணாத|வேண்டாம்|அனுப்பாத", evidence, re.I))
    excluded = re.findall(r'\bnot\s+(gmail|whatsapp|drive|calendar)\b', evidence, re.I)
    reported = bool(re.search(r'\b(?:he|she|they|avan|aval)\b.*\b(?:said|told|sonnan|sonna)\b|\b(?:sonnan|sonna|history)\b|சொன்ன', evidence, re.I))
    hypothetical = bool(re.search(r'\b(?:pannalama|pannalaama|hypothetically|suppose)\b|\bwhat\s+if\b|லாமா', evidence, re.I))
    speech_evidence = re.sub(r'https?://[^\s<>]+', lambda m: ' ' * len(m[0]), evidence)
    question = '?' in speech_evidence or bool(re.search(r'\bah\s*[.?]*$|\b(?:what|why|how|when|whether)\b', speech_evidence, re.I))
    scoped = [] if reported else [{'scope': 'COMMAND', 'start': m.start(), 'end': m.end(), 'surface': text[m.start():m.end()]} for m in prohibitions]
    result['negation'] = bool(scoped)
    result['negations'] = scoped + [{'scope': 'DOMAIN', 'excluded': d.upper()} for d in excluded]
    result['negation_scope_uncertain'] = bool(prohibitions and reported)
    if reported:
        result['speech_act'] = result['speech_act'] if result['speech_act'] in {'HYPOTHETICAL', 'QUESTION'} else 'QUESTION' if question else 'STATEMENT'
    elif hypothetical:
        result['speech_act'] = 'HYPOTHETICAL'
    elif scoped:
        result['speech_act'] = 'NEGATED_COMMAND'
    elif question and (result.get('speech_act') not in {'COMMAND', 'CORRECTION', 'HYPOTHETICAL', 'CAPABILITY_QUERY', 'AMBIGUOUS'} or re.search(r'\b(?:running|irukka|iruka)\b.*\bah\s*[.?]*$', speech_evidence, re.I)):
        result['speech_act'] = 'STATUS_QUERY' if result['speech_act'] == 'STATUS_QUERY' or re.search(r'\b(?:status|running|health|irukka|iruka)\b', speech_evidence, re.I) else 'QUESTION'
        if result['speech_act'] == 'STATUS_QUERY' and (result['action'] in {'START', 'RUN', 'LAUNCH'} or re.search(r'\b(?:running|health|irukka|iruka)\b', speech_evidence, re.I)):
            result['action'] = 'CHECK'
    elif result.get('speech_act') == 'NEGATED_COMMAND':
        # Missing negation evidence cannot turn an uncertain model prediction
        # into a command; keep it advisory and record the uncertainty.
        from scripts.tanglish_stage24_ontology import ACTION_FAMILY
        imperative = re.match(r'^\s*(?:please\s+)?(?:' + '|'.join(re.escape(a.lower()) for a in ACTION_FAMILY) + r')\b', evidence, re.I)
        light_verb = re.search(r'\b(?:pannu|panu|pannunga)\b', speech_evidence, re.I)
        positive = result['action'] != 'UNKNOWN' and not question and (imperative or (light_verb and len(evidence.split()) >= 3))
        result['speech_act'] = 'COMMAND' if positive else 'UNKNOWN'
        result['negation_scope_uncertain'] = not bool(positive)
    slots = [s for s in result.get('slots', []) if s.get('source') == 'CONTEXT' or s.get('span')]
    # Open identifier grammar retains raw spelling; it is not a phrase lookup.
    for kind, pattern in [('URL', r'https?://[^\s<>"]+'), ('file', r'\b[\w.-]+\.(?:pdf|zip|txt|py|json|csv|docx|xlsx|png|jpg)\b')]:
        for m in re.finditer(pattern, evidence, re.I):
            slots = [s for s in slots if s['slot'] != kind] + [typed_slot(text, kind, *m.span())]
    for word, value in ORDINALS.items():
        m = re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', evidence, re.I)
        if m:
            slots = [s for s in slots if s['slot'] != 'ordinal'] + [typed_slot(text, 'ordinal', *m.span(), value=value)]
            break
    correction = bool(re.search(r'\b(?:actually|instead|illa|illai)\b|இல்லை', evidence, re.I))
    result.update(reconstruct(text, slots, result['action'], result['domain'], result.get('object_type'),
                              has_correction=correction, has_reference=False, context=context))
    result['correction'] = correction
    if result['corrections'] and not scoped and not reported and not hypothetical:
        result['speech_act'] = 'CORRECTION'
    references = []
    ref = re.search(r'\b(?:it|that|this|previous|second|him|her|avan|atha|athu|antha)\b|அந்த|அதை', evidence, re.I)
    if ref:
        domain = result['domain']
        resource = result.get('object_type')
        kind = ('DriveFileRef' if resource in {'FileRef', 'FolderRef'} and domain == 'DRIVE'
                else 'PreviousFileRef' if resource in {'FileRef', 'FolderRef'} and re.search(r'\bprevious\b', evidence, re.I)
                else 'SelectedFileRef' if resource in {'FileRef', 'FolderRef'} or re.search(r'\b(?:pdf|file|folder)\b', evidence, re.I)
                else 'ContactRef' if resource == 'ContactRef' or ref[0].lower() in {'him', 'her', 'avan'}
                else 'BrowserTabRef' if resource == 'BrowserTabRef'
                else 'WhatsAppMessageRef' if resource == 'MessageRef' and domain == 'WHATSAPP'
                else 'EmailRef' if resource == 'MessageRef' and domain == 'GMAIL'
                else 'PreviousMessageRef' if resource == 'MessageRef'
                else 'CalendarEventRef' if resource == 'CalendarEventRef'
                else 'ProjectRef' if resource == 'ProjectRef'
                else 'SelectedResourceRef')
        references.append({'type': kind, 'value': None, 'requires_context_resolution': True})
        if result['values'].get('ordinal') is not None:
            references.append({'type': 'OrdinalRef', 'ordinal': result['values']['ordinal'], 'value': None, 'requires_context_resolution': True})
    result['references'] = references
    result['reference'] = bool(references)
    result['language'] = language(text)
    values = result['values']
    result.update(source=values.get('source') or result.get('sender'), destination=values.get('destination') or result.get('recipient'),
                  target=values.get('contact'), query=values.get('query'), content=values.get('content'),
                  temporal={k: values[k] for k in ('date', 'time') if k in values},
                  quantity=values.get('count', values.get('number')), ordinal=values.get('ordinal'))
    from scripts.tanglish_stage24_ontology import ACTION_FAMILY
    result['action_family'] = ACTION_FAMILY.get(result['action'], result.get('action_family'))
    result['intent'] = result['action']
    result['target'] = values.get('contact') or result.get('sender') or result.get('owner')
    result['time'] = result['temporal']
    result['scope'] = 'latest' if result['ordinal'] == -1 else None
    result['resource'] = {'type': result.get('object_type'),
        'identifiers': {k: v for k, v in values.items() if k in {'file', 'folder', 'application', 'browser', 'URL', 'project', 'resource_type'}},
        'requires_context_resolution': bool(references or result.get('context_required'))}
    result['constraints'] = {
        'include': [s['value'] for s in result['slots'] if s['slot'] == 'include_constraint'],
        'exclude': [s['value'] for s in result['slots'] if s['slot'] == 'exclude_constraint'] + excluded}
    result['normalized_text'] = ' '.join(text.split())
    result['should_execute'] = False
    result['controls_tools'] = False
    result['recommendation'] = ('UNKNOWN' if result['action'] == 'UNKNOWN' or result['speech_act'] in {'UNKNOWN', 'AMBIGUOUS'}
                                else 'CLARIFY' if references or result.get('unresolved_correction') or result.get('ambiguous_time_evidence') or result.get('input_truncated')
                                else 'ESCALATE')
    native = SemanticFrame(intent=result['action'], actionability=False, raw_query=text,
                           confidence=result.get('confidence', 0), ambiguity=result['recommendation'] == 'CLARIFY')
    native.entities = [str(s['value']) for s in result['slots']]
    native.corrections = result['corrections']
    native.include_constraints = list(result.get('constraints', {}).get('include', []))
    native.exclude_constraints = list(result.get('constraints', {}).get('exclude', []))
    native.user_prohibitions = [result['action']] if scoped else []
    native.language_features = {k: result.get(k) for k in ('language', 'domain', 'action_family', 'speech_act', 'values', 'recipient', 'sender', 'references', 'negations')}
    native.language_features.update(controls_tools=False, should_execute=False, version='SHARED_LANGUAGE_V3_DEVELOPMENT')
    native.language_features.update(typed_references=references, resource=result['resource'], temporal_values=result['temporal'])
    result['jarvis_semantic_frame'] = asdict(native)
    return result


def clauses(text):
    """Construction-level sequential connectors, with quoted content protected."""
    masked = re.sub(r'"[^"\n]*"|“[^”\n]*”', lambda m: ' ' * len(m[0]), text)
    cuts = list(re.finditer(r'\s+(?:and\s+then|then|pannitu|பண்ணிட்டு)\s+', masked, re.I))
    start = 0
    result = []
    for m in cuts:
        result.append(text[start:m.start()].strip())
        start = m.end()
    result.append(text[start:].strip())
    return [s for s in result if s]


def automation_semantics(text):
    """Advisory trigger/condition extraction; existing planner owns installation."""
    m = re.search(r'\b(?:when|if)\s+(.+?)(?:,|\bthen\b)|(.+?)\s+\baana\b', text, re.I)
    daily = bool(re.search(r'\b(?:daily|every\s+day)\b|தினமும்', text, re.I))
    return {'trigger': 'SCHEDULE' if daily else 'CONDITION' if m else None,
            'condition': (m[1] or m[2]).strip() if m else None,
            'raw_instruction': text, 'requires_planner': True, 'should_execute': False}


def response_language(current_language, explicit_preference=None, contact_preference=None):
    return explicit_preference or contact_preference or current_language


def conversation_features(text, frame):
    """Conversation-only meaning. Personal Reply Brain keeps truth/style gates."""
    availability = bool(re.search(r'\b(?:free|available|busy|irukkiya|irukiya)\b|ஃப்ரீ', text, re.I))
    return {'language': frame['language'], 'speech_act': frame['speech_act'],
            'question_type': 'AVAILABILITY' if availability else 'OTHER',
            'personal_state_required': availability, 'references': frame['references'],
            'conversation_mode': 'EXTERNAL_MESSAGE_CONTENT', 'should_execute': False,
            'auto_reply': False, 'understanding_source': 'Unified JARVIS NLP'}
