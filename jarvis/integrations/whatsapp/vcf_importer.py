"""VCF / vCard Contact Importer and SQLite Database Manager for JARVIS."""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from jarvis.config import ROOT

logger = logging.getLogger("jarvis.whatsapp.contacts")

import os

DB_PATH = ROOT / "data/contacts.db"
DEFAULT_VCF_PATH = ROOT / "data/contacts.vcf"


def find_vcf_files() -> List[Path]:
    """Finds available .vcf files in data directories or the user's Downloads folder."""
    candidates = [
        ROOT / "contacts.vcf",
        ROOT.parent / "contacts.vcf",
        ROOT / "data/contacts.vcf",
        ROOT.parent / "data/contacts.vcf",
    ]
    user_home = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
    downloads = user_home / "Downloads"
    if downloads.exists():
        candidates.extend(sorted(downloads.glob("*contact*.vcf"), key=lambda p: p.stat().st_mtime, reverse=True))
        candidates.extend(sorted(downloads.glob("*.vcf"), key=lambda p: p.stat().st_mtime, reverse=True))

    found: List[Path] = []
    seen = set()
    for c in candidates:
        if c.exists() and str(c.resolve()) not in seen:
            seen.add(str(c.resolve()))
            found.append(c)
    return found


@dataclass
class ParsedContact:
    name: str
    phone: str
    jid: str


def clean_phone_number(raw: str, default_country_code: str = "91") -> str:
    """Normalizes phone numbers to standard E.164 without leading plus for JID."""
    digits = re.sub(r"[^\d+]", "", raw.strip())
    if digits.startswith("+"):
        clean = digits[1:]
    else:
        clean = digits

    # If it's a 10-digit Indian number without country code, prepend default
    if len(clean) == 10 and default_country_code:
        clean = f"{default_country_code}{clean}"

    return clean


def parse_vcf(vcf_content: str, default_country_code: str = "91") -> List[ParsedContact]:
    """Parses a .vcf (vCard 2.1 / 3.0 / 4.0) text into a list of ParsedContact."""
    contacts: List[ParsedContact] = []
    lines = vcf_content.splitlines()

    # Unfold wrapped lines (lines starting with space or tab)
    unfolded: List[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line.strip())

    current_fn: Optional[str] = None
    current_phones: List[str] = []

    for line in unfolded:
        upper = line.upper()
        if upper == "BEGIN:VCARD":
            current_fn = None
            current_phones = []
        elif upper == "END:VCARD":
            if current_fn and current_phones:
                for ph in current_phones:
                    clean = clean_phone_number(ph, default_country_code)
                    if clean and len(clean) >= 7:
                        contacts.append(
                            ParsedContact(
                                name=current_fn.strip(),
                                phone=f"+{clean}",
                                jid=f"{clean}@s.whatsapp.net",
                            )
                        )
            current_fn = None
            current_phones = []
        elif re.search(r"(?:^|\.)FN[;:]", upper):
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[1].strip():
                current_fn = parts[1].strip()
        elif re.search(r"(?:^|\.)N[;:]", upper):
            if not current_fn:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    name_parts = [p.strip() for p in parts[1].split(";") if p.strip()]
                    if name_parts:
                        # Reconstruct "Given Family"
                        current_fn = " ".join(reversed(name_parts))
        elif re.search(r"(?:^|\.)TEL[;:]", upper) and ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[1].strip():
                current_phones.append(parts[1].strip())

    return contacts


class ContactDatabase:
    """Manages SQLite storage for imported address book contacts."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    jid TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL DEFAULT 'vcf',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_contact_name ON contacts(name);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_contact_jid ON contacts(jid);")
            conn.commit()

    def import_contacts(self, contacts: List[ParsedContact], source: str = "vcf") -> int:
        """Inserts or updates contacts in the database."""
        inserted = 0
        with self._get_conn() as conn:
            for c in contacts:
                try:
                    conn.execute(
                        """
                        INSERT INTO contacts (name, phone, jid, source)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(jid) DO UPDATE SET
                            name = excluded.name,
                            phone = excluded.phone,
                            source = excluded.source
                        """,
                        (c.name, c.phone, c.jid, source),
                    )
                    inserted += 1
                except Exception as e:
                    logger.warning("Error saving contact %s: %s", c.name, e)
            conn.commit()
        return inserted

    def import_from_vcf_file(self, vcf_path: Path, default_country_code: str = "91") -> int:
        """Imports contacts directly from a .vcf file."""
        if not vcf_path.exists():
            return 0
        content = vcf_path.read_text(encoding="utf-8", errors="ignore")
        parsed = parse_vcf(content, default_country_code)
        count = self.import_contacts(parsed, source="vcf")
        logger.info("Imported %d contacts from %s", count, vcf_path)
        return count

    def get_all(self) -> List[sqlite3.Row]:
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM contacts ORDER BY name ASC").fetchall()

    def search(self, query: str) -> List[sqlite3.Row]:
        q = f"%{query.strip()}%"
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM contacts WHERE name LIKE ? OR phone LIKE ? ORDER BY name ASC",
                (q, q),
            ).fetchall()
