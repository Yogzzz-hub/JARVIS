"""DEV-only capability metadata overlay. No changes to the production registry."""
from __future__ import annotations
import json
from pathlib import Path
from jarvis.core.capabilities.registry import CapabilityRegistry
from jarvis.core.capabilities.retrieval import CapabilityRetriever
from jarvis.core.capabilities.models import CapabilityDefinition, CapabilityCategory

# Semantic contracts for existing tools, independent of utterance strings/gold IDs.
CONTRACTS={
 'app.open':('PC',{'OPEN','START'},'AppRef'), 'app.close':('PC',{'CLOSE','STOP'},'AppRef'),
 'file.open':('FILES',{'OPEN'},'FileRef'),'file.delete':('FILES',{'DELETE'},'FileRef'),
 'file.find':('FILES',{'FIND','SEARCH'},'FileRef'),'file.list_directory':('FILES',{'LIST'},'FolderRef'),
 'file.copy':('FILES',{'COPY'},'FileRef'),'file.move':('FILES',{'MOVE'},'FileRef'),
 'file.rename':('FILES',{'RENAME'},'FileRef'),'file.read_metadata':('FILES',{'INSPECT','CHECK'},'FileRef'),
 'browser.open_url':('BROWSER',{'NAVIGATE','OPEN'},'URLRef'),'rag.search_web':('BROWSER',{'SEARCH'},'WebQueryRef'),
 'google.read_emails':('GMAIL',{'READ','LIST','FIND','SEARCH'},'MessageRef'),'google.gmail_send':('GMAIL',{'SEND'},'MessageRef'),
 'google.calendar_create':('CALENDAR',{'CREATE'},'CalendarEventRef'),
 'whatsapp.read':('WHATSAPP',{'READ','LIST'},'MessageRef'),'whatsapp.send':('WHATSAPP',{'SEND','REPLY','FORWARD','SHARE'},'MessageRef'),
 'windows.screenshot':('PC',{'CAPTURE'},'ScreenshotRef'),'windows.volume_set':('PC',{'SET'},'Volume'),
 'windows.volume_mute':('PC',{'MUTE'},'Volume'),'windows.volume_unmute':('PC',{'UNMUTE'},'Volume'),
 'system.info':('PC',{'CHECK'},'SystemStatusRef'),
 'google.drive_search':('DRIVE',{'SEARCH','FIND'},'FileRef'),
 'google.drive_download':('DRIVE',{'DOWNLOAD'},'FileRef'),
 'google.drive_upload':('DRIVE',{'UPLOAD'},'FileRef'),
}


class OfflineFrameRetriever:
    def __init__(self):
        self.registry=CapabilityRegistry()
        self.added=[]
        # Definitions exist in the repository; only metadata is registered here.
        # Do not instantiate clients, obtain credentials, check availability, or run tools.
        from jarvis.integrations.google.drive.tools import DriveSearchTool,DriveDownloadFileTool,DriveUploadFileTool
        for cap_id,cls in [('google.drive_search',DriveSearchTool),('google.drive_download',DriveDownloadFileTool),('google.drive_upload',DriveUploadFileTool)]:
            d=cls.definition
            if self.registry.get(cap_id) is None:
                self.registry.register(CapabilityDefinition(id=cap_id,category=CapabilityCategory.GOOGLE,
                    description=d.description,keywords=list(d.tags)+d.name.split('_'),target_tool=d.name,
                    risk_level=d.risk,family='DRIVE',required_slots=[k for k,v in d.input_model.model_fields.items() if v.is_required()],
                    optional_slots=[k for k,v in d.input_model.model_fields.items() if not v.is_required()],
                    input_schema=d.input_model.model_json_schema(),output_schema=d.output_model.model_json_schema()))
                self.added.append(cap_id)
        self.lexical=CapabilityRetriever(self.registry)
        self.contracts={k:v for k,v in CONTRACTS.items() if self.registry.get(k)}
        self.missing_contracts=sorted(set(CONTRACTS)-set(self.contracts))

    def retrieve_frame(self,frame,k=10):
        query=' '.join([frame['domain'],frame['action'],frame.get('object_type') or '',
                        *[str(s['value']) for s in frame.get('slots',[])]])
        lexical=self.lexical.retrieve(query,top_k=len(self.registry.list_all()),min_score=0)
        scores={c.id:score for c,score in lexical}
        ranked=[]
        for cap in self.registry.list_all():
            descriptor=self.contracts.get(cap.id)
            # Typed contracts dominate lexical homonyms. An unmatched contract is not invented.
            score=scores.get(cap.id,0)*.01
            if descriptor:
                domain,actions,resource=descriptor
                score+=10*(frame['domain']==domain)+10*(frame['action'] in actions)+5*(frame.get('object_type')==resource)
                if frame['domain']!=domain:score-=20
            ranked.append((cap.id,score))
        return [identifier for identifier,_ in sorted(ranked,key=lambda x:(-x[1],x[0]))[:k]]

    def validate_gold(self,identifier):
        return self.registry.get(identifier) is not None


def oracle(rows,retriever):
    cases=[r for r in rows if r.get('capability_gold')]
    unknown=sorted({r['capability_gold'] for r in cases if not retriever.validate_gold(r['capability_gold'])})
    if unknown:raise ValueError('Stale/nonexistent gold capability IDs: '+str(unknown))
    ranks=[retriever.retrieve_frame({'domain':r['frame']['domain'],'action':r['frame']['action_concept'],
            'object_type':r['frame']['object_type'],'slots':r['frame']['slots']}) for r in cases]
    return {'cases':len(cases),**{f'recall_at_{k}':sum(r['capability_gold'] in rank[:k] for r,rank in zip(cases,ranks))/len(cases) if cases else None for k in (1,3,5,10)},'added_offline_metadata':retriever.added,'missing_contracts':retriever.missing_contracts,'scope':'DEV-only explicit atomic action/domain/resource contracts; live availability not checked; no tools executed'}
