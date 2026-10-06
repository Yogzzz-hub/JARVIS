"""Typed semantic references use the existing WorkingContext resolver, advisory only."""
from dataclasses import asdict, is_dataclass
import copy
from jarvis.core.context.resolver import ReferenceResolver

TYPES = {'SelectedFileRef': 'file', 'PreviousFileRef': 'file', 'DriveFileRef': 'file',
    'ContactRef': 'contact', 'BrowserTabRef': 'browser', 'WhatsAppMessageRef': 'message',
    'EmailRef': 'email', 'CalendarEventRef': 'event', 'ProjectRef': 'project'}


def resolve_semantic_references(frame, working_memory):
    results = []
    # The legacy resolver may update selections; isolate those writes from
    # production WorkingContext during advisory analysis.
    resolver = ReferenceResolver(copy.deepcopy(working_memory))
    for reference in frame.get('references', []):
        slot = TYPES.get(reference.get('type'))
        # Unrecognized types (including untyped selections) must never guess.
        if not slot or slot in {'browser', 'message', 'email', 'event', 'project'}:
            results.append({'type': reference.get('type'), 'status': 'CLARIFY', 'reason': 'Typed resolver unavailable'})
            continue
        resolution = resolver.resolve_for_slot(frame.get('raw_text', ''), expected_slot_type=slot,
            intent=frame.get('action'), is_consequential=True)
        data = asdict(resolution) if is_dataclass(resolution) else {}
        confidence = getattr(resolution, 'confidence', None)
        high = str(getattr(confidence, 'value', confidence)).upper() == 'HIGH'
        results.append({'type': reference['type'], 'status': 'RESOLVED' if high and resolution.referent else 'CLARIFY',
            'resolution': data})
    return {'references': results, 'recommendation': 'CLARIFY' if any(r['status'] != 'RESOLVED' for r in results) else 'ADVISORY',
        'controls_tools': False}
