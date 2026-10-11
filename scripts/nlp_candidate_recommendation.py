"""Pure candidate confidence policy; no model loads or optional ML imports."""
def recommend(frame,calibration):
    if frame['action']=='UNKNOWN':return 'UNKNOWN'
    if frame['speech_act']=='AMBIGUOUS' or frame['context_required'] or frame['reference'] or frame.get('unresolved_slot'):return 'CLARIFY'
    if frame['negation'] or frame['unresolved_correction'] or not frame['should_execute'] or frame['speech_act'] not in {'COMMAND','CORRECTION'}:return 'ESCALATE'
    if frame['confidence']>=calibration['execute_threshold']:return 'EXECUTE'
    if frame['confidence']>=calibration['escalate_threshold']:return 'ESCALATE'
    if frame['confidence']>=calibration['clarify_threshold']:return 'CLARIFY'
    return 'UNKNOWN'
