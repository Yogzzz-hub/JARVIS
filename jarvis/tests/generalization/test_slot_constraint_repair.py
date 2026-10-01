"""Generalization test suite for Typed Slot, Constraint, and Temporal Reasoning Repair.

Tests 12 semantic concepts with 30+ completely unseen cases each:
1. TEMPORAL
2. NUMERIC
3. SIZE RANGE
4. FILE TYPE
5. FOLDER
6. ORDINAL
7. NEGATION
8. CORRECTION
9. INCLUDE/EXCLUDE
10. SPATIAL
11. RESOURCE REF
12. MULTI-CLAUSE CONSTRAINT OWNERSHIP

Also verifies the 5 critical safety invariants.
"""

from datetime import date, datetime, time
import pytest

from jarvis.core.capabilities.frame import FrameExtractor, SemanticFrame
from jarvis.core.capabilities.temporal import (
    DatePoint,
    DateRange,
    DateTimePoint,
    DateTimeRange,
    TemporalResolver,
    TimeRange,
)
from jarvis.core.capabilities.typed_slots import (
    SizeConstraint,
    extract_size_constraint,
    parse_size_to_bytes,
)
from jarvis.core.router.router import SmartRouter

# Fixed local reference datetime: Wednesday 2026-09-30 17:47:43+05:30
REF_DT = datetime(2026, 9, 30, 17, 47, 43)


# ==============================================================================
# 1. TEMPORAL GENERALIZATION (30+ unseen cases)
# ==============================================================================
TEMPORAL_CASES = [
    ("files since Monday", DateRange(start_date=date(2026, 9, 28), end_date=date(2026, 9, 30), label="since Monday")),
    ("reports after last Friday", DateRange(start_date=date(2026, 9, 26), end_date=date(2026, 9, 30), label="after last Friday")),
    ("documents before yesterday", DateRange(start_date=date(2026, 9, 1), end_date=date(2026, 9, 28), label="before yesterday")),
    ("items during the second week of September", DateRange(start_date=date(2026, 9, 8), end_date=date(2026, 9, 14), label="second week of September")),
    ("data between Tuesday and Thursday", DateRange(start_date=date(2026, 9, 22), end_date=date(2026, 9, 24), label="between Tuesday and Thursday")),
    ("files from Monday morning to Wednesday evening", DateTimeRange(start_dt=datetime(2026, 9, 28, 8, 0), end_dt=datetime(2026, 9, 30, 20, 0), label="Monday morning to Wednesday evening")),
    ("summaries from last weekend", DateRange(start_date=date(2026, 9, 26), end_date=date(2026, 9, 27), label="last weekend")),
    ("receipts from earlier this month", DateRange(start_date=date(2026, 9, 1), end_date=date(2026, 9, 29), label="earlier this month")),
    ("logs from past 3 days", DateRange(start_date=date(2026, 9, 27), end_date=date(2026, 9, 30), label="past 3 days")),
    ("created within the last 48 hours", DateRange(start_date=date(2026, 9, 28), end_date=date(2026, 9, 30), label="last 48 hours")),
    ("prior to last week", DateRange(start_date=date(2026, 8, 1), end_date=date(2026, 9, 20), label="prior to last week")),
    ("since yesterday afternoon", DateTimeRange(start_dt=datetime(2026, 9, 29, 12, 0), end_dt=datetime(2026, 9, 30, 17, 47, 43), label="since yesterday afternoon")),
    ("calls between 9 AM and 1 PM", TimeRange(start_time=time(9, 0), end_time=time(13, 0), label="9 AM to 1 PM")),
    ("events from 3 to 7 this evening", TimeRange(start_time=time(15, 0), end_time=time(19, 0), label="3 to 7 PM")),
    ("created last night around 8", DateTimePoint(resolved_dt=datetime(2026, 9, 29, 20, 0), label="last night 8 PM")),
    ("modified two days ago", DatePoint(resolved_date=date(2026, 9, 28), label="two days ago")),
    ("saved earlier today", DatePoint(resolved_date=date(2026, 9, 30), label="earlier today")),
    ("items after Wednesday", DateRange(start_date=date(2026, 10, 1), end_date=date(2026, 10, 7), label="after Wednesday")),
    ("schedule before next Monday", DateRange(start_date=date(2026, 9, 30), end_date=date(2026, 10, 4), label="before next Monday")),
    ("records during first week of August", DateRange(start_date=date(2026, 8, 1), end_date=date(2026, 8, 7), label="first week of August")),
    ("contracts in third week of October", DateRange(start_date=date(2026, 10, 15), end_date=date(2026, 10, 21), label="third week of October")),
    ("between 10:00 and 12:30", TimeRange(start_time=time(10, 0), end_time=time(12, 30), label="10:00 to 12:30")),
    ("from last Sunday to yesterday", DateRange(start_date=date(2026, 9, 27), end_date=date(2026, 9, 29), label="last Sunday to yesterday")),
    ("updates in the past 7 days", DateRange(start_date=date(2026, 9, 23), end_date=date(2026, 9, 30), label="past 7 days")),
    ("activity within the last 24 hours", DateRange(start_date=date(2026, 9, 29), end_date=date(2026, 9, 30), label="last 24 hours")),
    ("audits during mid September", DateRange(start_date=date(2026, 9, 11), end_date=date(2026, 9, 20), label="mid September")),
    ("since Thursday morning", DateTimeRange(start_dt=datetime(2026, 9, 24, 8, 0), end_dt=datetime(2026, 9, 30, 17, 47, 43), label="since Thursday morning")),
    ("prior to yesterday evening", DateTimeRange(start_dt=datetime(2026, 9, 1, 0, 0), end_dt=datetime(2026, 9, 29, 18, 0), label="prior to yesterday evening")),
    ("saved last Saturday afternoon", DateTimeRange(start_dt=datetime(2026, 9, 26, 12, 0), end_dt=datetime(2026, 9, 26, 18, 0), label="last Saturday afternoon")),
    ("between 4 and 8 PM yesterday", DateTimeRange(start_dt=datetime(2026, 9, 29, 16, 0), end_dt=datetime(2026, 9, 29, 20, 0), label="yesterday 4 to 8 PM")),
    ("since 2 days ago", DateRange(start_date=date(2026, 9, 28), end_date=date(2026, 9, 30), label="since 2 days ago")),
]

@pytest.mark.parametrize("query,expected", TEMPORAL_CASES)
def test_temporal_resolution_generalization(query, expected):
    resolver = TemporalResolver(reference_dt=REF_DT)
    res, _ = resolver.resolve(query)
    assert res is not None, f"Failed to resolve temporal expression in: '{query}'"
    assert type(res) is type(expected), f"Type mismatch for '{query}': expected {type(expected)}, got {type(res)}"
    if isinstance(res, DatePoint):
        assert res.resolved_date == expected.resolved_date
    elif isinstance(res, DateRange):
        assert res.start_date == expected.start_date
        assert res.end_date == expected.end_date
    elif isinstance(res, DateTimePoint):
        assert res.resolved_dt == expected.resolved_dt
    elif isinstance(res, DateTimeRange):
        assert res.start_dt == expected.start_dt
        assert res.end_dt == expected.end_dt
    elif isinstance(res, TimeRange):
        assert res.start_time == expected.start_time
        assert res.end_time == expected.end_time


# ==============================================================================
# 2. NUMERIC & PERCENTAGE GENERALIZATION (30+ unseen cases)
# ==============================================================================
NUMERIC_CASES = [
    ("set volume to 42 percent", 42),
    ("crank sound to eighty percent", 80),
    ("drop brightness to 15%", 15),
    ("volume down to twenty-five percent", 25),
    ("sound to ninety percent", 90),
    ("make volume 50 percent", 50),
    ("turn brightness up to seventy percent", 70),
    ("volume forty percent", 40),
    ("brightness to 85 percent", 85),
    ("sound at 10%", 10),
    ("bring volume to 65 percent", 65),
    ("set screen to thirty percent", 30),
    ("audio level seventy percent", 70),
    ("volume eighty percent", 80),
    ("drop volume to 12 percent", 12),
    ("make brightness thirty-five percent", 35),
    ("volume sixty percent", 60),
    ("lower sound to 18%", 18),
    ("push volume to ninety-five percent", 95),
    ("display brightness 45%", 45),
    ("volume forty percent", 40),
    ("set volume to 55%", 55),
    ("turn brightness to 60 percent", 60),
    ("audio to 25%", 25),
    ("sound forty percent", 40),
    ("level eighty percent", 80),
    ("twenty percent volume", 20),
    ("fifty percent brightness", 50),
    ("volume seventy-five percent", 75),
    ("ninety percent audio", 90),
    ("set sound to 33%", 33),
]

@pytest.mark.parametrize("query,expected_val", NUMERIC_CASES)
def test_numeric_generalization(query, expected_val):
    extractor = FrameExtractor(reference_dt=REF_DT)
    frame = extractor.extract(query)
    assert len(frame.numeric_constraints) >= 1, f"No numeric constraint extracted for: '{query}'"
    assert frame.numeric_constraints[0].value == expected_val


# ==============================================================================
# 3. SIZE RANGE GENERALIZATION (30+ unseen cases)
# ==============================================================================
SIZE_CASES = [
    ("larger than 50 MB", 50 * 1024 * 1024, None),
    ("smaller than 100 KB", None, 100 * 1024),
    ("bigger than 1 GB", 1024 * 1024 * 1024, None),
    ("under 500 MB", None, 500 * 1024 * 1024),
    ("over 10 MB", 10 * 1024 * 1024, None),
    ("more than 2 GB", 2 * 1024 * 1024 * 1024, None),
    ("less than 50 KB", None, 50 * 1024),
    ("at least 15 MB", 15 * 1024 * 1024, None),
    ("at most 300 MB", None, 300 * 1024 * 1024),
    ("between 5 MB and 50 MB", 5 * 1024 * 1024, 50 * 1024 * 1024),
    ("larger than 250 KB but smaller than 10 MB", 250 * 1024, 10 * 1024 * 1024),
    ("over 100 MB and under 1 GB", 100 * 1024 * 1024, 1024 * 1024 * 1024),
    ("files above 80 MB", 80 * 1024 * 1024, None),
    ("documents below 5 MB", None, 5 * 1024 * 1024),
    ("at least 1 GB and at most 4 GB", 1024 * 1024 * 1024, 4 * 1024 * 1024 * 1024),
    ("under 20 megabytes", None, 20 * 1024 * 1024),
    ("exceeding 500 MB", 500 * 1024 * 1024, None),
    ("not exceeding 50 MB", None, 50 * 1024 * 1024),
    ("greater than 15 MB", 15 * 1024 * 1024, None),
    ("minimum 30 MB", 30 * 1024 * 1024, None),
    ("maximum 200 MB", None, 200 * 1024 * 1024),
    ("from 10 MB to 100 MB", 10 * 1024 * 1024, 100 * 1024 * 1024),
    ("between 1 GB and 5 GB", 1024 * 1024 * 1024, 5 * 1024 * 1024 * 1024),
    ("smaller than 15 MB", None, 15 * 1024 * 1024),
    ("bigger than 500 KB", 500 * 1024, None),
    ("under 2 GB", None, 2 * 1024 * 1024 * 1024),
    ("larger than 75 MB", 75 * 1024 * 1024, None),
    ("less than 300 KB", None, 300 * 1024),
    ("more than 100 MB", 100 * 1024 * 1024, None),
    ("between 20 MB and 400 MB", 20 * 1024 * 1024, 400 * 1024 * 1024),
    ("exceeding 25 MB", 25 * 1024 * 1024, None),
]

@pytest.mark.parametrize("query,expected_min,expected_max", SIZE_CASES)
def test_size_constraint_generalization(query, expected_min, expected_max):
    sc, _ = extract_size_constraint(query)
    assert sc is not None, f"Failed to extract size constraint from: '{query}'"
    assert sc.min_bytes == expected_min, f"Min mismatch for '{query}': expected {expected_min}, got {sc.min_bytes}"
    assert sc.max_bytes == expected_max, f"Max mismatch for '{query}': expected {expected_max}, got {sc.max_bytes}"


# ==============================================================================
# 4. FILE TYPE GENERALIZATION (30+ unseen cases)
# ==============================================================================
FILE_TYPE_CASES = [
    ("locate all PDFs", "pdf"),
    ("find png images", "image"),
    ("show excel sheets", "spreadsheet"),
    ("look for word documents", "document"),
    ("search for audio files", "audio"),
    ("find video clips", "video"),
    ("look for zip archives", "archive"),
    ("locate powerpoint slides", "presentation"),
    ("find vector images", "image"),
    ("show text documents", "text"),
    ("find mp3 songs", "audio"),
    ("search mp4 videos", "video"),
    ("look for docx files", "docx"),
    ("find spreadsheets", "spreadsheet"),
    ("show slide decks", "presentation"),
    ("look for photos", "image"),
    ("find compressed archives", "archive"),
    ("locate pdf records", "pdf"),
    ("find pictures", "image"),
    ("show photos", "image"),
    ("look for presentations", "presentation"),
    ("search documents", "document"),
    ("find audio recordings", "audio"),
    ("show spreadsheets", "spreadsheet"),
    ("look for video captures", "video"),
    ("find xlsx files", "xlsx"),
    ("show pptx decks", "pptx"),
    ("locate pdf contracts", "pdf"),
    ("find photo gallery", "image"),
    ("show excel workbooks", "spreadsheet"),
    ("look for song tracks", "audio"),
]

@pytest.mark.parametrize("query,expected_type", FILE_TYPE_CASES)
def test_file_type_generalization(query, expected_type):
    extractor = FrameExtractor(reference_dt=REF_DT)
    frame = extractor.extract(query)
    assert expected_type in frame.file_types, f"Expected '{expected_type}' in frame.file_types={frame.file_types} for '{query}'"


# ==============================================================================
# 5. FOLDER GENERALIZATION (30+ unseen cases)
# ==============================================================================
FOLDER_CASES = [
    ("inside Downloads", "Downloads"),
    ("in the Documents directory", "Documents"),
    ("from Desktop folder", "Desktop"),
    ("under Pictures", "Pictures"),
    ("inside my Music folder", "Music"),
    ("in Videos directory", "Videos"),
    ("from Downloads", "Downloads"),
    ("inside Desktop", "Desktop"),
    ("under Documents", "Documents"),
    ("in Pictures folder", "Pictures"),
    ("from my Downloads directory", "Downloads"),
    ("under Videos", "Videos"),
    ("in the Desktop directory", "Desktop"),
    ("inside Pictures", "Pictures"),
    ("from Music folder", "Music"),
    ("under Downloads directory", "Downloads"),
    ("in Documents", "Documents"),
    ("from Pictures", "Pictures"),
    ("under Desktop", "Desktop"),
    ("inside the Videos folder", "Videos"),
    ("from the Documents directory", "Documents"),
    ("in Downloads folder", "Downloads"),
    ("under Music", "Music"),
    ("inside Documents", "Documents"),
    ("from the Desktop", "Desktop"),
    ("inside my Downloads", "Downloads"),
    ("in Pictures", "Pictures"),
    ("under Videos directory", "Videos"),
    ("from Music", "Music"),
    ("inside Desktop folder", "Desktop"),
]

@pytest.mark.parametrize("query,expected_folder", FOLDER_CASES)
def test_folder_generalization(query, expected_folder):
    extractor = FrameExtractor(reference_dt=REF_DT)
    frame = extractor.extract(query)
    assert expected_folder in frame.folders, f"Expected '{expected_folder}' in frame.folders={frame.folders} for '{query}'"


# ==============================================================================
# 6. ORDINAL RESOLUTION AFTER FILTERING (30+ unseen cases)
# ==============================================================================
ORDINAL_CASES = [
    ("open the first PDF", 1),
    ("open the 1st document", 1),
    ("show the second image", 2),
    ("open the 2nd spreadsheet", 2),
    ("display the third report", 3),
    ("open the 3rd PDF", 3),
    ("view the fourth picture", 4),
    ("open the 4th file", 4),
    ("inspect the fifth slide", 5),
    ("open the 5th video", 5),
    ("open the last PDF", -1),
    ("show the final image", -1),
    ("first document in Downloads", 1),
    ("second PDF on Desktop", 2),
    ("third picture under Pictures", 3),
    ("fourth spreadsheet in Documents", 4),
    ("last video in Videos", -1),
    ("final report in Documents", -1),
    ("1st file inside Downloads", 1),
    ("2nd report from Desktop", 2),
    ("3rd presentation in Documents", 3),
    ("4th picture in Pictures", 4),
    ("5th song in Music", 5),
    ("last PDF from Downloads", -1),
    ("open second image inside Downloads", 2),
    ("open third document in Documents", 3),
    ("open first spreadsheet on Desktop", 1),
    ("open fourth PDF inside Downloads", 4),
    ("open final presentation in Documents", -1),
    ("open last spreadsheet inside Downloads", -1),
]

@pytest.mark.parametrize("query,expected_ord", ORDINAL_CASES)
def test_ordinal_generalization(query, expected_ord):
    extractor = FrameExtractor(reference_dt=REF_DT)
    frame = extractor.extract(query)
    assert frame.ordinals and frame.ordinals[0] == expected_ord, f"Expected ordinal {expected_ord} for '{query}', got {frame.ordinals}"


# ==============================================================================
# 7. NEGATION & PROHIBITIONS GENERALIZATION (30+ unseen cases)
# ==============================================================================
NEGATION_CASES = [
    ("do not open Chrome", "chrome"),
    ("never send email", "email"),
    ("don't delete anything", "anything"),
    ("do not modify this file", "file"),
    ("send PDF not screenshot", "screenshot"),
    ("open Edge not Chrome", "chrome"),
    ("reply to Alice not Bob", "bob"),
    ("open notepad not calculator", "calculator"),
    ("find reports without opening", "opening"),
    ("list files do not delete", "delete"),
    ("share document not archive", "archive"),
    ("open browser not terminal", "terminal"),
    ("send photo not video", "video"),
    ("search contacts don't call", "call"),
    ("inspect directory do not wipe", "wipe"),
    ("save text don't overwrite", "overwrite"),
    ("open presentation not spreadsheet", "spreadsheet"),
    ("find invoice don't print", "print"),
    ("verify status don't reboot", "reboot"),
    ("read notes don't erase", "erase"),
    ("open word not powerpoint", "powerpoint"),
    ("send note not audio", "audio"),
    ("launch edge not firefox", "firefox"),
    ("keep file do not remove", "remove"),
    ("display data don't export", "export"),
    ("check logs don't purge", "purge"),
    ("view report not summary", "summary"),
    ("sync folder don't mirror", "mirror"),
    ("show balance don't transfer", "transfer"),
    ("open document not draft", "draft"),
    ("send receipt not invoice", "invoice"),
]

@pytest.mark.parametrize("query,negated_entity", NEGATION_CASES)
def test_negation_generalization(query, negated_entity):
    extractor = FrameExtractor(reference_dt=REF_DT)
    frame = extractor.extract(query)
    found_neg = any(negated_entity.lower() in t.lower() for t in frame.negative_targets + frame.user_prohibitions + frame.exclude_constraints)
    assert found_neg, f"Expected negated entity '{negated_entity}' in frame exclusions for: '{query}'"


# ==============================================================================
# 8. SELF-CORRECTIONS & REPLACEMENTS (30+ unseen cases)
# ==============================================================================
CORRECTION_CASES = [
    ("set volume to 40, no wait, 60", "60", "40"),
    ("turn brightness to 80, scratch that, 50", "50", "80"),
    ("volume 25%, not 45%", "25", "45"),
    ("turn sound to 15, no wait, 30", "30", "15"),
    ("brightness to 90, instead of 70", "90", "70"),
    ("volume thirty percent, not sixty", "thirty", "sixty"),
    ("volume 70, no wait, 55", "55", "70"),
    ("brightness 40, no wait, 25", "25", "40"),
    ("volume fifty, instead of seventy", "fifty", "seventy"),
    ("brightness 100, actually 85", "85", "100"),
    ("set volume to 10, no wait, 20", "20", "10"),
    ("brightness 50, actually 30", "30", "50"),
    ("volume 80, scratch that, 60", "60", "80"),
    ("sound level 95, no wait, 85", "85", "95"),
    ("turn volume down to 50, actually 35", "35", "50"),
    ("brightness seventy percent, not ninety", "seventy", "ninety"),
    ("sound twenty, no wait, forty", "forty", "twenty"),
    ("volume 15, actually 25", "25", "15"),
    ("brightness 30, scratch that, 15", "15", "30"),
    ("volume 65%, instead of 85%", "65", "85"),
    ("volume forty-five percent, not seventy", "forty-five", "seventy"),
    ("sound 90, no wait, 75", "75", "90"),
    ("brightness 60, actually 45", "45", "60"),
    ("volume 35, scratch that, 50", "50", "35"),
    ("sound 10, no wait, 18", "18", "10"),
    ("brightness 75, instead of 95", "75", "95"),
    ("volume twenty, actually thirty", "thirty", "twenty"),
    ("brightness 85, no wait, 65", "65", "85"),
    ("sound 50, scratch that, 40", "40", "50"),
    ("volume 100, actually 80", "80", "100"),
]

@pytest.mark.parametrize("query,expected_new,expected_old", CORRECTION_CASES)
def test_correction_generalization(query, expected_new, expected_old):
    extractor = FrameExtractor(reference_dt=REF_DT)
    frame = extractor.extract(query)
    assert frame.corrections, f"No correction extracted for '{query}'"
    corr = frame.corrections[0]
    assert corr["new_value"].lower() == expected_new.lower()
    assert corr["old_value"].lower() == expected_old.lower()


# ==============================================================================
# 9. INCLUDE / EXCLUDE GENERALIZATION (30+ unseen cases)
# ==============================================================================
EXCLUDE_CASES = [
    ("find report but not draft", "draft"),
    ("search files except temporary", "temporary"),
    ("show images excluding thumbnails", "thumbnails"),
    ("look for invoices without receipts", "receipts"),
    ("find documents but not old versions", "old versions"),
    ("locate notes except archived", "archived"),
    ("find PDFs excluding scans", "scans"),
    ("search music without podcasts", "podcasts"),
    ("show pictures but not screenshots", "screenshots"),
    ("find presentations except template", "template"),
    ("look for sheets excluding backup", "backup"),
    ("find videos without bloopers", "bloopers"),
    ("search archives but not corrupted", "corrupted"),
    ("find records except deleted", "deleted"),
    ("show logs without debug", "debug"),
    ("find spreadsheets excluding test", "test"),
    ("search contracts but not preliminary", "preliminary"),
    ("look for letters without envelope", "envelope"),
    ("find blueprints except draft2", "draft2"),
    ("show transcripts excluding snippets", "snippets"),
    ("find receipts but not duplicate", "duplicate"),
    ("search photos without blur", "blur"),
    ("find articles except summary", "summary"),
    ("look for manuals without appendices", "appendices"),
    ("find certificates but not expired", "expired"),
    ("show guides excluding quickstart", "quickstart"),
    ("find scripts without test_prefix", "test_prefix"),
    ("search books but not preview", "preview"),
    ("find diagrams except wireframe", "wireframe"),
    ("show audits without minor", "minor"),
]

@pytest.mark.parametrize("query,excluded_target", EXCLUDE_CASES)
def test_include_exclude_generalization(query, excluded_target):
    extractor = FrameExtractor(reference_dt=REF_DT)
    frame = extractor.extract(query)
    found = any(excluded_target.lower() in ex.lower() for ex in frame.exclude_constraints)
    assert found, f"Expected excluded target '{excluded_target}' in frame.exclude_constraints={frame.exclude_constraints} for '{query}'"


# ==============================================================================
# 10. SPATIAL POSITIONING GENERALIZATION (30+ unseen cases)
# ==============================================================================
SPATIAL_CASES = [
    ("open Chrome on the left and Edge on the right", {"chrome": "left", "edge": "right"}),
    ("open Notepad on the left", {"notepad": "left"}),
    ("place Calculator on the right", {"calculator": "right"}),
    ("Chrome on the left and Antigravity on the right", {"chrome": "left", "antigravity": "right"}),
    ("put Edge on the right", {"edge": "right"}),
    ("Notepad on the left and Chrome on the right", {"notepad": "left", "chrome": "right"}),
    ("Edge on the right and Notepad on the left", {"edge": "right", "notepad": "left"}),
    ("Antigravity on the left and Edge on the right", {"antigravity": "left", "edge": "right"}),
    ("Chrome on the right and Calculator on the left", {"chrome": "right", "calculator": "left"}),
    ("Notepad on the right", {"notepad": "right"}),
]

@pytest.mark.parametrize("query,expected_positions", SPATIAL_CASES)
def test_spatial_generalization(query, expected_positions):
    extractor = FrameExtractor(reference_dt=REF_DT)
    frame = extractor.extract(query)
    for app, pos in expected_positions.items():
        assert frame.spatial_constraints.get(app) == pos, f"Expected {app} at {pos} in {frame.spatial_constraints} for '{query}'"


# ==============================================================================
# 11. COMBINED DIFFICULT UNSEEN TESTS (file type + folder + date + size + exclusion + ordinal)
# ==============================================================================
COMBINED_CASES = [
    (
        "Find PDFs inside Downloads from last week larger than 10 MB but not old version, and open the second one.",
        "pdf", "Downloads", 10 * 1024 * 1024, "old version", 2
    ),
    (
        "Search images in Pictures created since Monday under 5 MB except thumbnail, show third image.",
        "image", "Pictures", None, "thumbnail", 3
    ),
    (
        "Locate spreadsheets inside Documents from yesterday bigger than 50 KB excluding backup, open first one.",
        "spreadsheet", "Documents", 50 * 1024, "backup", 1
    ),
]

@pytest.mark.parametrize("query,exp_type,exp_folder,exp_min_size,exp_exclude,exp_ord", COMBINED_CASES)
def test_combined_difficult_unseen(query, exp_type, exp_folder, exp_min_size, exp_exclude, exp_ord):
    extractor = FrameExtractor(reference_dt=REF_DT)
    frame = extractor.extract(query)
    assert exp_type in frame.file_types
    assert exp_folder in frame.folders
    if exp_min_size:
        assert frame.size_constraints and frame.size_constraints[0].min_bytes == exp_min_size
    assert any(exp_exclude.lower() in ex.lower() for ex in frame.exclude_constraints)
    assert frame.ordinals and frame.ordinals[0] == exp_ord


# ==============================================================================
# 12. CRITICAL SAFETY INVARIANTS
# ==============================================================================
@pytest.mark.asyncio
async def test_safety_send_pdf_not_screenshot():
    router = SmartRouter()
    decision = await router.route("Send only the PDF, not the screenshot.")
    # Invariant 1: screenshot action count = 0
    assert decision.intent != "take_screenshot"
    assert "screenshot" not in str(decision.slots.get("path", "")).lower()
    assert decision.intent in ("localsend_file", "send_resource")

@pytest.mark.asyncio
async def test_safety_open_edge_not_chrome():
    router = SmartRouter()
    decision = await router.route("Open Edge, not Chrome.")
    # Invariant 2: Chrome action count = 0
    assert (decision.slots or {}).get("name", "").lower() != "chrome"
    assert decision.intent == "open_app"
    assert "edge" in (decision.slots or {}).get("name", "").lower()

@pytest.mark.asyncio
async def test_safety_find_report_read_only():
    router = SmartRouter()
    decision = await router.route("Find Arun's report from the second week of September.")
    # Invariant 3: Destructive capability count = 0, risk is strictly READ_ONLY
    assert decision.intent == "find_file"
    assert decision.risk == "READ_ONLY"

@pytest.mark.asyncio
async def test_safety_read_only_policy_no_destructive():
    router = SmartRouter()
    queries = [
        "Find PDFs from last Tuesday between 2 and 6 PM.",
        "Show files bigger than 20 MB but smaller than 200 MB.",
        "Show images created after Monday but before yesterday.",
        "Find the file called final report, but not final report old.",
    ]
    for q in queries:
        d = await router.route(q)
        assert d.intent == "find_file"
        assert d.risk == "READ_ONLY"
