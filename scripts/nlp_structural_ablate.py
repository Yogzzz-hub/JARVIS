"""DEV-only historical decoder and paired registry evidence; no retired reads."""
import argparse,json
from pathlib import Path
from collections import Counter
from scripts.nlp_structural_data import V1,read
from scripts.nlp_structural_slots import typed_slot
from scripts.nlp_structural_metrics import metrics
from scripts.nlp_structural_capabilities import OfflineFrameRetriever,oracle
from scripts.nlp_provisional_data import canonical,immutable

def historical(directory):
    rows=read(V1/'DEV.jsonl');old=json.loads((V1/'candidate/evaluation_DEV.json').read_text(encoding='utf-8'))
    pred=old['predictions'];adapted=[]
    for row,p in zip(rows,pred):
        slots=[typed_slot(row['text'],s['slot'],s['start'],s['end'],value=s['value']) for s in p['slots']]
        adapted.append({**p,'slots':slots})
    paired=oracle(rows,OfflineFrameRetriever())
    confusions=Counter((r['frame']['action_concept'] or 'UNKNOWN',p['action']) for r,p in zip(rows,pred) if (r['frame']['action_concept'] or 'UNKNOWN')!=p['action'])
    result={'A_v1_BIO_raw':old['candidate'],'A_v1_BIO_canonicalized_values':metrics(rows,adapted),
        'E_original_oracle':json.loads((V1/'candidate/capability_oracle_DEV.json').read_text(encoding='utf-8')) if (V1/'candidate/capability_oracle_DEV.json').exists() else None,
        'E_repaired_oracle_same_v1_DEV':paired,'old_top_action_confusions':[{'gold':a,'predicted':b,'count':n} for (a,b),n in confusions.most_common(12)],
        'scope':'Historical V1 DEV only. Canonicalization changes scoring, not model. Paired registry oracle uses same allowed DEV rows. No retired TEST/HOLDOUT read.'}
    immutable(directory/'historical_DEV_ablations.json',canonical(result));print(json.dumps({k:v for k,v in result.items() if k.startswith('E_')},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);historical(p.parse_args().directory)
