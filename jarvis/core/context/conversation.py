"""Bounded informational topic context. It cannot authorize a tool action."""
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from functools import lru_cache
import json
from pathlib import Path
import re
from time import monotonic, perf_counter

_PRIVATE = re.compile(r'\b(?:my|our|password|otp|token|secret|recipient|contact|filename)\b|@|https?://|[\\/]|\d', re.I)
_ACTION = re.compile(r'\b(?:send|delete|remove|install|uninstall|pay|buy|upload|download|open|launch|close|reply|remind)\b|அனுப்பு|நீக்கு', re.I)
_WEB = re.compile(r'\b(?:web|online|internet|google)\b|இணைய', re.I)
_SEARCH = re.compile(r'\b(?:search|check|look\s+up|find)\b|தேடு|தேடி|சுருக்க', re.I)
_SUMMARY = re.compile(r'\b(?:summari[sz]e|summary)\b|சுருக்க', re.I)
_REFERENCE = re.compile(r'^(?:it|this|that|this topic|that topic|that one|same thing|about it|about this|atha|ithu|அதை|இது)$', re.I)
_STRUCTURE = re.compile(r'\b(?:search|check|look|up|find|web|online|internet|google|in|on|the|and|then|for|about|it|this|that|topic|same|thing|summari[sz]e|summary|please|now|la|panni|pannu|panu|sollu|solu|bro)\b|இணையத்தில்|இணையம்|தேடுங்கள்|தேடி|தேடு|சுருக்கமாக|சுருக்கம்|சொல்லு', re.I)


@lru_cache(maxsize=1)
def terminology():
    root = Path(__file__).resolve().parents[3]
    terms = json.loads((root/'config/knowledge_terms.json').read_text(encoding='utf-8'))
    return {word.casefold(): canonical for canonical, aliases in terms.items()
            for word in [canonical, *aliases]}


def distance(a, b):
    previous = list(range(len(b)+1))
    for i, char in enumerate(a, 1):
        row = [i]
        for j, other in enumerate(b, 1):
            row.append(min(row[-1]+1, previous[j]+1, previous[j-1]+(char != other)))
        previous = row
    return previous[-1]


def resolve_term(subject):
    """Only glossary concepts in informational requests get lexical correction."""
    clean = subject.strip(' .?!,')
    words = terminology()
    if clean.casefold() in words:
        return words[clean.casefold()], None
    if _PRIVATE.search(clean) or not clean.isascii() or len(clean) < 6:
        return clean, None
    ranked = []
    for candidate, canonical in words.items():
        if not candidate.isascii() or abs(len(candidate)-len(clean)) > 2:
            continue
        edits = distance(clean.casefold(), candidate)
        if edits <= 2:
            ranked.append((1-edits/max(len(clean), len(candidate)), canonical))
    ranked = sorted(set(ranked), reverse=True)
    if ranked and ranked[0][0] >= .80 and (len(ranked)==1 or ranked[0][0]-ranked[1][0] >= .10):
        return ranked[0][1], dict(original=clean, resolved=ranked[0][1], confidence=ranked[0][0])
    return clean, None


@dataclass
class TopicFrame:
    active_topic: str = ''
    previous_user_intent: str = ''
    previous_resolved_entities: list = field(default_factory=list)
    previous_resource_refs: list = field(default_factory=list)
    pending_question: str = ''
    conversation_domain: str = 'KNOWLEDGE'
    last_answer_topic: str = ''
    last_search_query: str = ''
    topics: list = field(default_factory=list)
    updated: float = 0


class ConversationalTopics:
    def __init__(self, capacity=32, ttl=900, clock=monotonic):
        self.frames = OrderedDict()
        self.capacity, self.ttl, self.clock = capacity, ttl, clock

    def frame(self, channel):
        frame = self.frames.get(channel)
        if frame is None or self.clock()-frame.updated > self.ttl:
            frame = TopicFrame(updated=self.clock())
            self.frames[channel] = frame
        self.frames.move_to_end(channel)
        while len(self.frames)>self.capacity: self.frames.popitem(last=False)
        return frame

    def resolve(self, raw_text, channel='local'):
        started = perf_counter()
        text = ' '.join(raw_text.split()).strip(' .?!')
        text = re.sub(r'^(?:please\s+|now\s+)', '', text, flags=re.I)
        normalization_ms = (perf_counter()-started)*1000
        if _ACTION.search(text) or _PRIVATE.search(text): return None
        frame = self.frame(channel)
        subject = ''
        web = bool((_WEB.search(text) and (_SEARCH.search(text) or _SUMMARY.search(text)))
                   or re.match(r'^search\b', text, re.I))
        intent = 'EXPLAIN'
        explicit = False
        if web:
            subject = _STRUCTURE.sub(' ', re.sub(r'\bthat one\b', '', text, flags=re.I)).strip(' ,.')
            subject = ' '.join(subject.split())
            if _REFERENCE.fullmatch(subject): subject = ''
            intent = 'WEB_SEARCH_SUMMARIZE'
        else:
            match = re.fullmatch(r'(?:what\s+(?:is|are|about)|explain|define|tell\s+me\s+about)\s+(.+)', text, re.I)
            tanglish = re.fullmatch(r'(.+?)\s+(?:na|naa|endral|என்றால்)\s+(?:enna|ena|என்ன)', text, re.I)
            if match or tanglish:
                subject = (match or tanglish).group(1).strip()
            elif re.fullmatch(r'(?:tell me (?:more|causes)|why does (?:it|this|that) happen|give (?:an? )?example|more about (?:it|this|that)|tell me more about (?:it|this|that))', text, re.I):
                subject = ''
            elif re.fullmatch(r'(?:latest about (?:it|this|that)|summari[sz]e from web|check online)', text, re.I):
                web, intent = True, 'WEB_SEARCH_SUMMARIZE'
            elif re.fullmatch(r'compare (?:both|the two)', text, re.I):
                if len(frame.topics) < 2:
                    return self._result(raw_text, '', False, intent, 'Which two topics should I compare?', None, started)
                subject = ' and '.join(frame.topics[-2:])
                intent = 'COMPARE'
            else:
                return None
        if _REFERENCE.fullmatch(subject): subject = ''
        if _PRIVATE.search(subject) or _ACTION.search(subject): return None
        correction = None
        if subject:
            if intent != 'COMPARE':
                subject, correction = resolve_term(subject)
            # New local definitions use the glossary; unrecognized people,
            # files and other entities keep the existing production path.
            if not web and intent != 'COMPARE' and subject.casefold() not in terminology():
                self.invalidate(channel)
                return None
            explicit = True
        elif frame.active_topic:
            subject = frame.active_topic
        else:
            return self._result(raw_text, '', web, intent, 'Which topic should I search or explain?', None, started)
        if explicit and intent != 'COMPARE':
            frame.active_topic = subject
            if not frame.topics or frame.topics[-1] != subject:
                frame.topics.append(subject); del frame.topics[:-4]
        frame.previous_user_intent = intent
        frame.previous_resolved_entities = [subject]
        frame.updated = self.clock()
        intent_ms = (perf_counter()-started)*1000-normalization_ms
        query_started = perf_counter()
        query = subject
        if subject in ('hallucination','tokenization','transformer','embedding','quantization',
                       'retrieval augmented generation'):
            query = 'AI ' + subject
        elif subject in ('overfitting','underfitting','gradient descent','neural network','backpropagation',
                         'regularization','reinforcement learning'):
            query = subject + ' machine learning'
        elif intent == 'COMPARE':
            query = subject + ' in AI and machine learning'
        elif subject in ('Kafka','Flink','Hadoop','FastAPI','Postgres','PyTorch','TensorFlow','Docker','React','Next.js','Ollama'):
            query = subject + ' software'
        if web and re.search(r'\blatest\b', text, re.I) and not re.search(r'\blatest\b', query, re.I):
            query = 'latest ' + query
        if web: frame.last_search_query = query
        return self._result(raw_text, subject, web, intent, '', correction, started,
                            search_query=query, frame=asdict(frame),
                            normalization_ms=normalization_ms,intent_ms=intent_ms,
                            query_construction_ms=(perf_counter()-query_started)*1000)

    def _result(self, raw, topic, web, intent, clarification, correction, started, **extra):
        return dict(raw_text=raw, topic=topic, use_web=web, intent=intent,
            speech_act='QUESTION', domain='KNOWLEDGE', should_execute=False,
            clarification=clarification, typo=correction,
            context_ms=(perf_counter()-started)*1000, **extra)

    def answered(self, channel, topic):
        frame = self.frame(channel)
        frame.last_answer_topic = topic

    def snapshot(self, channel='local'):
        return asdict(self.frame(channel))

    def invalidate(self, channel='local'):
        self.frames.pop(channel, None)
