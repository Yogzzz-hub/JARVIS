from scripts.nlp_structural_slots import typed_slot,canonical_value,contacts,reconstruct,canonical_set


def test_canonical_particles_whitespace_unicode_and_identifiers():
    assert canonical_value('recipient',' Deepa ku ')=='Deepa'
    assert canonical_value('sender','Priya oda')=='Priya'
    assert canonical_value('file','Report.v2.pdf')=='Report.v2.pdf'
    assert canonical_value('URL','https://a.test/X?A=1')=='https://a.test/X?A=1'
    text='பிரியா ku கோப்பு';slot=typed_slot(text,'recipient',0,9)
    assert slot['span']['surface']==text[slot['span']['start']:slot['span']['end']]


def test_markers_not_name_position_and_owner():
    for text,name in [('Naveen ku','Naveen'),('Arun kitta','Arun'),('Deepa ku anuppu','Deepa'),('Mohan ku forward pannu','Mohan')]:
        assert contacts(text,'SEND')[0]['value']==name
        assert contacts(text,'SEND')[0]['slot']=='recipient'
    assert contacts('Priya anupuna','READ')[0]['slot']=='sender'
    assert contacts('Ravi oda file','SEND')[0]['relation']=='OWNER'
    assert contacts('Naveen file Arun','SEND')==[]


def test_repeated_recipient_latest_correction_and_reference_types():
    frame=reconstruct('Naveen ku... actually Arun ku',[],'SEND','WHATSAPP','MessageRef',has_correction=True)
    assert frame['recipient']=='Arun'
    assert frame['corrections']==[{'slot':'recipient','superseded':'Naveen','active':'Arun'}]
    assert reconstruct('that PDF',[],'OPEN','FILES','FileRef',has_reference=True)['references'][0]['type']=='SelectedFileRef'
    assert reconstruct('previous message',[],'READ','WHATSAPP','MessageRef',has_reference=True)['references'][0]['type']=='PreviousMessageRef'
    assert reconstruct('second one',[],'OPEN','FILES','FileRef',has_reference=True)['references'][0]['type']=='OrdinalRef'


def test_span_boundary_is_secondary_to_canonical_value():
    text=' Deepa ku '
    a=typed_slot(text,'recipient',0,len(text));b=typed_slot(text,'recipient',1,6)
    assert a['span']!=b['span']
    assert canonical_set([a])==canonical_set([b])
    assert canonical_value('time','4 pm')=='16:00'
    assert canonical_value('ordinal','second')==2


def test_numeric_time_markers_are_not_contacts_and_contextual_corrections():
    assert contacts('11 am ku illa 4 pm ku','SEND')==[]
    text='11 ku... illa 4 ku'
    f=reconstruct(text,[],'MOVE','CALENDAR','CalendarEventRef',has_correction=True,context={'afternoon_low_hours':True})
    assert f['corrections']==[{'slot':'time','superseded':'11:00','active':'16:00'}]
    assert canonical_value('time','4 ku')['requires_clarification']
