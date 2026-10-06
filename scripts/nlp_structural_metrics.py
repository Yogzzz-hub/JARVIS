"""Independent canonical-value, evidence-span and reconstruction scoring."""
import json
from collections import Counter
from scripts.nlp_structural_slots import canonical_set,canonical_value,reference_type

def ratio(a,b):return a/b if b else None
def prf(tp,fp,fn):
    p=ratio(tp,tp+fp);r=ratio(tp,tp+fn)
    return {'precision':p,'recall':r,'f1':ratio(2*tp,2*tp+fp+fn)}
def gold_corrections(row):
    out=[]
    for c in row['frame']['corrections']:
        if isinstance(c.get('superseded'),dict):
            old=c['superseded'];kind=old['slot'];active=next((s['value'] for s in row['frame']['slots'] if s['slot']==kind),None)
            out.append({'slot':kind,'superseded':canonical_value(kind,old['value']),'active':canonical_value(kind,active)})
        elif 'slot' in c and 'active' in c:out.append(c)
    return out
def correction_set(items):return {json.dumps(c,sort_keys=True,ensure_ascii=False) for c in items}
def joint_correct(row,p):
    f=row['frame']
    return (p['action']==(f['action_concept'] or 'UNKNOWN') and p['domain']==f['domain']
        and canonical_set(p['slots'])==canonical_set(f['slots'])
        and p['negation']==bool(f['negations']) and p['should_execute']==f['should_execute']
        and p['speech_act']==f['speech_act'] and p['reference']==bool(f['references'])
        and p['correction']==bool(f['corrections'])
        and (not f['corrections'] or correction_set(p['corrections'])==correction_set(gold_corrections(row))))
def metrics(rows,predictions):
    c=Counter();ct=cf=cn=st=sf=sn=0
    for row,p in zip(rows,predictions):
        f=row['frame'];gold=canonical_set(f['slots']);pred=canonical_set(p['slots'])
        ct+=len(gold&pred);cf+=len(pred-gold);cn+=len(gold-pred)
        gs={(s['slot'],s['start'],s['end']) for s in f['slots'] if s['source']=='TEXT'}
        ps={(s['slot'],s['span']['start'],s['span']['end']) for s in p['slots'] if s.get('span')}
        st+=len(gs&ps);sf+=len(ps-gs);sn+=len(gs-ps)
        for key,truth in [('domain',f['domain']),('action',f['action_concept'] or 'UNKNOWN'),('speech_act',f['speech_act'])]:c[key]+=p[key]==truth
        for kind in ('recipient','sender','time','ordinal'):
            g={x for k,x in gold if k==kind};v={x for k,x in pred if k==kind}
            if g:c[kind+'_n']+=1;c[kind+'_ok']+=g==v
        for feature in ('negation','correction','reference'):
            truth=bool(f[feature+'s' if feature!='negation' else 'negations'])
            c[feature+'_accuracy']+=p[feature]==truth
            if truth:c[feature+'_n']+=1;c[feature+'_positive']+=p[feature]
        if f['corrections']:c['correction_reconstruction']+=correction_set(gold_corrections(row))==correction_set(p['corrections'])
        if f['references']:c['reference_type']+=bool(p['references']) and p['references'][0]['type']==reference_type(f['object_type'],f['domain'])
        unknown=f['action_concept'] is None or f['speech_act']=='AMBIGUOUS'
        c['unknown_n']+=unknown;c['unknown_ok']+=unknown and p['recommendation'] in ('CLARIFY','UNKNOWN')
        eligible=f['should_execute'] and not f['negations'] and not f['context_required'] and f['speech_act']!='AMBIGUOUS'
        c['executable_n']+=eligible;executed=p['recommendation']=='EXECUTE';c['execute']+=executed
        correct=joint_correct(row,p) and eligible;c['execute_correct']+=executed and correct
        c['critical_recommendations']+=executed and not correct
        c['raw_wrong_action']+=p['action']!=(f['action_concept'] or 'UNKNOWN')
        c['raw_wrong_domain']+=p['domain']!=f['domain']
        gr={v for k,v in gold if k=='recipient'};pr={v for k,v in pred if k=='recipient'}
        c['raw_wrong_recipient']+=bool(gr or pr) and gr!=pr
        c['missed_negation']+=bool(f['negations']) and not p['negation']
        c['missed_correction']+=bool(f['corrections']) and not p['correction']
        c['negation_violation_recommendations']+=executed and bool(f['negations'])
        c['correction_violation_recommendations']+=executed and bool(f['corrections']) and correction_set(p['corrections'])!=correction_set(gold_corrections(row))
        c['wrong_recipient_recommendations']+=executed and gr!=pr
        c['wrong_domain_recommendations']+=executed and p['domain']!=f['domain']
        c['ambiguity_execution_recommendations']+=executed and (unknown or f['context_required'])
        if row.get('capability_gold'):
            c['cap_n']+=1
            for k in (1,3,5,10):c['cap_'+str(k)]+=row['capability_gold'] in p.get('capabilities',[])[:k]
    return {'n':len(rows),**{k:ratio(c[k],len(rows)) for k in ('domain','action','speech_act')},
        'canonical_slots':prf(ct,cf,cn),'exact_spans':prf(st,sf,sn),
        **{k+'_accuracy':ratio(c[k+'_ok'],c[k+'_n']) for k in ('recipient','sender','time','ordinal')},
        'negation_positive_recall':ratio(c['negation_positive'],c['negation_n']),
        'negation_accuracy':ratio(c['negation_accuracy'],len(rows)),
        'correction_reconstruction':ratio(c['correction_reconstruction'],c['correction_n']),
        'reference_type_accuracy':ratio(c['reference_type'],c['reference_n']),
        'unknown_clarify':ratio(c['unknown_ok'],c['unknown_n']),
        'execute_precision':ratio(c['execute_correct'],c['execute']),
        'execute_coverage':ratio(c['execute'],c['executable_n']),
        'capability':{'cases':c['cap_n'],**{f'recall_at_{k}':ratio(c['cap_'+str(k)],c['cap_n']) for k in (1,3,5,10)}},'counts':dict(c)}
