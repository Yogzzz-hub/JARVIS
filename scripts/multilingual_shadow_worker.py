"""CPU-only isolated V2 inference IPC. No routing, tool execution or sending."""
import contextlib
import json
import sys
import time
import hashlib
from pathlib import Path


def compare(production, candidate, retriever=None):
    from jarvis.core.router.catalog import IntentCatalog
    from scripts.nlp_structural_capabilities import OfflineFrameRetriever, CONTRACTS
    intent = (production or {}).get('intent')
    catalog_entry = IntentCatalog.get_default().intents.get(intent)
    registry = (retriever or OfflineFrameRetriever()).registry
    matches = [c for c in registry.list_all() if catalog_entry and c.target_tool == catalog_entry.tool and c.id in CONTRACTS]
    contract = CONTRACTS.get(matches[0].id) if matches else None
    slots = (production or {}).get('slots', {})
    action = str(slots.get('action') or (intent or '').split('_')[0]).upper()
    action = {'LAUNCH': 'OPEN', 'TAKE': 'CAPTURE'}.get(action, action)
    # Contract equivalence handles FIND/SEARCH without consulting expected labels.
    domain_agrees = contract[0] == candidate['domain'] if contract else None
    action_agrees = candidate['action'] in contract[1] if contract and action in contract[1] else action == candidate['action'] if action else None
    recipient = slots.get('recipient') or slots.get('contact')
    native = (production or {}).get('semantic_frame') or {}
    mapping = {'app': 'application', 'path': 'file', 'url': 'URL'}
    comparable_slots = {mapping.get(k, k): v for k, v in slots.items() if k in {'app', 'application', 'recipient', 'sender', 'source', 'destination', 'file', 'folder', 'url', 'date', 'time', 'ordinal', 'project'}}
    # Compare only actually represented production fields. Missing is N/A.
    return {'domain': domain_agrees, 'action': action_agrees,
            'slots': all(candidate.get('values', {}).get(k) == v for k, v in comparable_slots.items()) if comparable_slots else None,
            'recipient': recipient == candidate.get('recipient') if recipient is not None else None,
            'reference': bool(native['references']) == candidate['reference'] if 'references' in native else None,
            'negation': bool(native['user_prohibitions']) == candidate['negation'] if 'user_prohibitions' in native else None,
            'correction': bool(native['corrections']) == candidate['correction'] if 'corrections' in native else None}


def main():
    # Windows console defaults must never reinterpret Tamil IPC bytes.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='strict')
    # Third-party libraries may print diagnostics; stdout is strictly JSON IPC.
    with contextlib.redirect_stdout(sys.stderr):
        import torch
        from scripts.nlp_structural_evaluate import verify_config
        from scripts.nlp_structural_policy import GuardedCandidate
        from scripts.nlp_structural_capabilities import OfflineFrameRetriever
        from jarvis.core.language_layer import repair, conversation_features, clauses, automation_semantics
        config = json.loads(Path('jarvis/config/nlp_candidate.json').read_text(encoding='utf-8'))
        shadow_manifest = Path('data/nlp_shadow/shadow_configuration.json')
        if shadow_manifest.exists():
            for filename, digest in json.loads(shadow_manifest.read_text())['source_hashes'].items():
                if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
                    raise RuntimeError('Shadow decoder configuration drift')
        configuration_digest = hashlib.sha256(shadow_manifest.read_bytes()).hexdigest() if shadow_manifest.exists() else None
        directory = Path(config['NLP_CANDIDATE']['dataset_directory'])
        verify_config(directory, 'candidate')
        torch.set_num_threads(1)
        model = GuardedCandidate(directory / 'candidate', device='cpu')
        retriever = OfflineFrameRetriever()
    for line in sys.stdin:
        try:
            item = json.loads(line)
            started = time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr):
                frame = repair(model.infer({'text': item['raw_text'], 'working_context': item['context']}), item['context'])
                frame['capabilities'] = retriever.retrieve_frame(frame)
                parts = clauses(item['raw_text'])
                if len(parts) > 1:
                    frame['steps'] = [repair(model.infer({'text': p, 'working_context': item['context']}), item['context']) for p in parts[:8]]
                    frame['requires_planner'] = True
                if item['mode'] == 'automation_builder' or frame['domain'] == 'AUTOMATIONS':
                    frame['automation'] = automation_semantics(item['raw_text'])
                result = {'candidate': frame, 'agreements': compare(item['production'], frame, retriever) if item['mode'] == 'command' else {},
                          'language': frame['language'], 'version': 'V2_WEIGHTS_V3_DECODER_SHADOW', 'controls_tools': False}
                if item['mode'] == 'conversation':
                    result = {'candidate': conversation_features(item['raw_text'], frame), 'agreements': {}, 'language': frame['language'], 'controls_tools': False}
                result['latency_ms'] = (time.perf_counter() - started) * 1000
                result['device'] = 'cpu'
                result['auto_reply'] = False
                result['configuration_sha256'] = configuration_digest
                import psutil
                result['resources'] = {'process_ram_mib': psutil.Process().memory_info().rss / 1048576, 'allocated_vram_mib': 0}
            print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({'error': type(exc).__name__}), flush=True)


if __name__ == '__main__':
    main()
