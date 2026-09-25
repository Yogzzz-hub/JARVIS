"""Contact resolution and safe disambiguation for WhatsApp integration."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import List, Optional, Tuple


@dataclass
class ContactEntry:
    jid: str
    display_name: str
    phone_number: str = ""
    is_owner: bool = False
    aliases: List[str] = field(default_factory=list)


class ContactResolver:
    """
    Safely resolves contact names to stable WhatsApp JIDs.
    Guarantees ambiguity resolution: never silently guesses between multiple matching contacts.
    """

    def __init__(self, contacts: Optional[List[ContactEntry]] = None) -> None:
        self._contacts: List[ContactEntry] = contacts if contacts is not None else []
        if contacts is None:
            self._load_from_database()
            self._load_from_config()

    def _load_from_database(self) -> None:
        try:
            from jarvis.integrations.whatsapp.vcf_importer import ContactDatabase, find_vcf_files
            db = ContactDatabase()
            for vcf in find_vcf_files():
                db.import_from_vcf_file(vcf)
            for row in db.get_all():
                self.add_contact(
                    jid=row["jid"],
                    display_name=row["name"],
                    phone=row["phone"],
                )
        except Exception:
            pass

    def _load_from_config(self) -> None:
        try:
            import tomllib
            from jarvis.config import ROOT
            for candidate in [ROOT / "config/whatsapp.toml", ROOT.parent / "config/whatsapp.toml"]:
                if candidate.exists():
                    with candidate.open("rb") as f:
                        data = tomllib.load(f)
                    contacts_dict = data.get("whatsapp", {}).get("contacts", {})
                    for name, num in contacts_dict.items():
                        clean_num = str(num).strip()
                        jid = f"{clean_num.lstrip('+')}@s.whatsapp.net" if "@" not in clean_num else clean_num
                        self.add_contact(jid=jid, display_name=name, phone=clean_num)
                    break
        except Exception:
            pass

    def add_contact(self, jid: str, display_name: str, phone: str = "", is_owner: bool = False) -> None:
        for c in self._contacts:
            if c.jid.casefold() == jid.casefold():
                if display_name and display_name.casefold() != c.display_name.casefold():
                    if display_name not in c.aliases:
                        c.aliases.append(display_name)
                if phone:
                    c.phone_number = phone
                return
        self._contacts.append(
            ContactEntry(
                jid=jid,
                display_name=display_name,
                phone_number=phone,
                is_owner=is_owner,
                aliases=[display_name] if display_name else [],
            )
        )

    def resolve(self, query: str) -> Tuple[Optional[ContactEntry], List[ContactEntry], Optional[str]]:
        """
        Resolves a contact query.
        Returns:
            (resolved_contact, ambiguous_matches, disambiguation_prompt)
        """
        q = query.strip().casefold()
        if not q:
            return None, [], "Please specify a recipient name."

        norm_q = re.sub(r"[^a-z0-9]", "", q)

        # 1. Exact JID or phone match
        for c in self._contacts:
            clean_p = re.sub(r"[^\d]", "", c.phone_number)
            clean_q = re.sub(r"[^\d]", "", q)
            if c.jid.casefold() == q or (clean_p and clean_p == clean_q):
                return c, [], None

        def _names_for(entry: ContactEntry) -> List[str]:
            res = [entry.display_name]
            for a in entry.aliases:
                if a not in res:
                    res.append(a)
            return res

        # 2. Exact name match (ignoring case, whitespace, symbols)
        exact_matches = []
        for c in self._contacts:
            for name in _names_for(c):
                cf = name.casefold()
                norm_name = re.sub(r"[^a-z0-9]", "", cf)
                if cf == q or (norm_q and norm_name == norm_q):
                    if c not in exact_matches:
                        exact_matches.append(c)
                    break

        if len(exact_matches) == 1:
            return exact_matches[0], [], None
        elif len(exact_matches) > 1:
            names = ", ".join(f"'{c.display_name}' ({c.phone_number or c.jid})" for c in exact_matches)
            prompt = f"Multiple contacts match '{query}': {names}. Which one would you like to message?"
            return None, exact_matches, prompt

        # 3. Substring / partial match
        partial_matches = []
        for c in self._contacts:
            for name in _names_for(c):
                cf = name.casefold()
                norm_name = re.sub(r"[^a-z0-9]", "", cf)
                if q in cf or (norm_q and norm_q in norm_name) or (c.phone_number and q in c.phone_number):
                    if c not in partial_matches:
                        partial_matches.append(c)
                    break

        if len(partial_matches) == 1:
            return partial_matches[0], [], None
        elif len(partial_matches) > 1:
            names = ", ".join(f"'{c.display_name}' ({c.phone_number or c.jid})" for c in partial_matches)
            prompt = f"Multiple contacts match '{query}': {names}. Which one did you mean?"
            return None, partial_matches, prompt

        return None, [], f"No contact found matching '{query}'."

