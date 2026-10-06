"""Repair measurement uses only preserved V2 DEV predictions and labels."""
import json
import hashlib
import time
from pathlib import Path
from jarvis.core.language_layer import repair
from scripts.nlp_structural_metrics import metrics, prf
from scripts.nlp_structural_capabilities import OfflineFrameRetriever


def main():
    config = json.loads(Path('jarvis/config/nlp_candidate.json').read_text(encoding='utf-8'))
    directory = Path(config['NLP_CANDIDATE']['dataset_directory'])
    rows = [json.loads(line) for line in (directory / 'DEV.jsonl').read_text(encoding='utf-8').splitlines()]
    cached = json.loads((directory / 'candidate/locked_evaluation_DEV.json').read_text(encoding='utf-8'))
    preds = [repair(p, row.get('working_context')) for row, p in zip(rows, cached['records'])]
    retriever = OfflineFrameRetriever()
    for p in preds:
        p['capabilities'] = retriever.retrieve_frame(p)
    def negation(predictions):
        tp = fp = fn = 0
        for r, p in zip(rows, predictions):
            gold, pred = bool(r['frame']['negations']), bool(p['negation'])
            tp += gold and pred; fp += not gold and pred; fn += gold and not pred
        return {**prf(tp, fp, fn), 'tp': tp, 'fp': fp, 'fn': fn}
    result = {'scope': 'DEV_ONLY_CACHED_PREDICTIONS; provisional labels; no test/holdout reads',
              'before': metrics(rows, cached['records']), 'after': metrics(rows, preds),
              'negation_before': negation(cached['records']), 'negation_after': negation(preds),
              'scope_accuracy': None, 'note': 'DEV gold does not independently annotate negation scope.',
              'languages': {lang: metrics([r for r in rows if r['language'] == lang], [p for r, p in zip(rows, preds) if r['language'] == lang]) for lang in sorted({r['language'] for r in rows})},
              'decoder_sha256': hashlib.sha256(Path('jarvis/core/language_layer.py').read_bytes()).hexdigest()}
    out = Path('data/nlp_shadow/development')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'decoder_DEV.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('negation_before', 'negation_after')}))
    print(json.dumps({'action': result['after']['action'], 'canonical': result['after']['canonical_slots'], 'references': result['after']['reference_type_accuracy'], 'correction': result['after']['correction_reconstruction']}))


if __name__ == '__main__':
    main()
