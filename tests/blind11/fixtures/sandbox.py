"""Blind-11 sandbox: a throw-away home folder with known files. Mutating cases run only here, never on real data.

    build(root) -> Path   creates <root>/home/{Desktop,Documents,Downloads,Pictures,Music,Videos} with the files below
"""
from __future__ import annotations

from pathlib import Path

FILES = {
    "Desktop/todo_list.txt": "buy milk\ncall the bank\n",
    "Desktop/meeting_notes.docx": "notes from the monday standup",
    "Desktop/temp_test.txt": "scratch",
    "Documents/report_q3.pdf": "%PDF-1.4 quarterly report q3 revenue 12 lakh",
    "Documents/budget_2025.xlsx": "budget sheet",
    "Documents/resume_naveen.pdf": "%PDF-1.4 resume",
    "Documents/lease_agreement.pdf": "%PDF-1.4 lease deposit 50000 rupees termination 2 months notice",
    "Documents/projects/alpha/readme.md": "# alpha project",
    "Documents/projects/beta/main.py": "print('beta')\n",
    "Downloads/invoice_march.pdf": "%PDF-1.4 invoice march total 4500",
    "Downloads/invoice_april.pdf": "%PDF-1.4 invoice april total 5200",
    "Downloads/setup_vlc.exe": "MZ fake installer",
    "Downloads/screenshot_0412.png": "PNG",
    "Downloads/screenshot_0413.png": "PNG",
    "Downloads/holiday_video.mp4": "mp4",
    "Downloads/old_log.log": "log",
    "Pictures/beach_goa.jpg": "JPG",
    "Pictures/passport_scan.jpg": "JPG",
    "Pictures/family_diwali.png": "PNG",
    "Music/ilayaraja_hits.mp3": "MP3",
    "Videos/lecture_ml.mp4": "MP4",
}


def build(root: Path) -> Path:
    home = Path(root) / "home"
    for rel, text in FILES.items():
        p = home / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    for d in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"):
        (home / d).mkdir(parents=True, exist_ok=True)
    return home
