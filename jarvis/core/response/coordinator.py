"""Shared response policy; production verification and transports stay authoritative."""
from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass
import re
from jarvis.core.language_layer import language

RESPONSE_LANGUAGE = ContextVar('unified_response_language', default='ENGLISH')
UNIFIED_RESPONSE_ACTIVE = ContextVar('unified_response_active', default=False)


class ResponseLanguagePolicy:
    aliases = {'english': 'ENGLISH', 'tamil': 'TAMIL', 'tanglish': 'TANGLISH',
        'thanglish': 'TANGLISH', 'mixed': 'MIXED', 'mixed_tamil_english': 'MIXED_TAMIL_ENGLISH'}

    @classmethod
    def choose(cls, text, *, explicit=None, conversation=None, contact=None, owner_default='ENGLISH'):
        # Output instructions are grammar, never command phrase patches.
        match = re.search(r'\b(?:reply|answer|respond|speak)\s+in\s+(english|tamil|tanglish|thanglish|mixed)\b', text, re.I)
        explicit = explicit or (match.group(1) if match else None)
        for value in (explicit, conversation, contact):
            canonical = cls.aliases.get(str(value).lower(), str(value).upper()) if value else None
            if canonical in {'ENGLISH', 'TAMIL', 'TANGLISH', 'MIXED', 'MIXED_TAMIL_ENGLISH'}:
                return canonical
        return language(text) if text.strip() else cls.aliases.get(owner_default.lower(), owner_default.upper())

    @staticmethod
    def render(text, selected):
        """Localize bounded outcome templates only; preserve names and arbitrary details."""
        if selected in {'TANGLISH', 'MIXED'}:
            from jarvis.core.multilingual import in_thanglish
            return in_thanglish(text)
        if selected in {'TAMIL', 'MIXED_TAMIL_ENGLISH'}:
            templates = {'Done.': 'முடிந்தது.', 'Stopped.': 'நிறுத்தப்பட்டது.',
                'Cancelled.': 'ரத்து செய்யப்பட்டது.', 'Please confirm.': 'உறுதி செய்யவும்.',
                "I couldn't verify that it completed.": 'முடிந்ததா என்பதை உறுதி செய்ய முடியவில்லை.',
                'Where should I type?': 'எங்கே தட்டச்சு செய்ய வேண்டும்?'}
            for pattern, suffix in [(r'^(.+) is running\.$', ' இயங்குகிறது.'),
                    (r'^(.+) is open\.$', ' திறக்கப்பட்டுள்ளது.')]:
                match = re.fullmatch(pattern, text)
                if match:
                    return match.group(1) + suffix
            return templates.get(text, text)
        return text

    @staticmethod
    def prompt_instruction(selected):
        if selected in {'TAMIL', 'MIXED_TAMIL_ENGLISH'}:
            return ('Reply in natural conversational Tamil' + (' mixed with English technical terms' if selected == 'MIXED_TAMIL_ENGLISH' else '')
                + '. Preserve names, identifiers and technical English. State only verified facts; never invent action completion.')
        from jarvis.core.multilingual import prompt_instruction, THANGLISH, ENGLISH
        return prompt_instruction(THANGLISH if selected in {'TANGLISH', 'MIXED'} else ENGLISH)


@dataclass(frozen=True)
class ResponsePlan:
    language: str
    text_destination: str
    voice_destination: str | None
    speak: bool


class ResponseCoordinator:
    def __init__(self, capacity=512):
        self.capacity = capacity
        self.finals = OrderedDict()

    @staticmethod
    def plan(envelope, language_hint=None):
        selected = language_hint or ResponseLanguagePolicy.choose(envelope.raw_text)
        silent = envelope.source in {'whatsapp', 'phone', 'benchmark', 'test', 'automation_builder'}
        # Phone owns playback: never also speak its response on PC speakers.
        return ResponsePlan(selected, envelope.reply_channel, None if silent else 'pc', not silent)

    def claim_final(self, request_id):
        if request_id in self.finals:
            return False
        self.finals[request_id] = True
        while len(self.finals) > self.capacity:
            self.finals.popitem(last=False)
        return True
