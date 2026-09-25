# Capability Retrieval Audit & Root Cause Analysis

## 1. Executive Summary

- **Total Evaluated Benchmark Items with Expected Capabilities**: `1104`
- **Total Fast-Path / Lane 0 Bypasses**: `731` (66.2%)
- **Original Raw Metric Recall@1**: `16.85%`
- **Original Raw Metric Recall@10**: `19.02%`
- **Canonical Primary Capability Recall@1**: `40.76%`
- **Canonical Primary Capability Recall@10**: `49.18%`

### Root Causes of Metric Underreporting & Retrieval Gaps

| Root Cause Category | Count | Percentage | Explanation |
|---|---|---|---|
| **DETERMINISTIC_LANE0_BYPASS** | 271 | 24.5% | Command routes deterministically via Lane 0 in <1ms; capability retriever is bypassed by design, yet test penalizes it as retrieval failure.
| **LEXICAL_SEMANTIC_GAP** | 158 | 14.3% | Paraphrased phrasing or indirect verbs have no keyword overlap with BM25 indexed examples, requiring hybrid semantic expansion.
| **RETRIEVER_ZERO_RESULTS** | 145 | 13.1% | BM25 score fell below min_score threshold because query words were not in capability keywords/examples.
| **ALIAS_LABEL_MISMATCH** | 69 | 6.2% | Dataset uses abstract names ('file.search', 'system.volume_set') while registry uses canonical IDs ('file.find', 'windows.volume_set').
| **RANK_SUPPRESSED_BY_OTHER_CANDIDATE** | 7 | 0.6% | Another related capability scored slightly higher due to common stopword/verb overlap.
| **MULTI_CAPABILITY_RANK_ORDER** | 4 | 0.4% | Multi-capability compositional query retrieved valid secondary capability at rank 1 instead of primary capability.

---

## 2. Failed Retrieval Examples Audit (Detailed Log)

### Test ID: `asr_006` (asr_variants)

**USER QUERY**:
`valume thirty`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=asr_variants`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `asr_007` (asr_variants)

**USER QUERY**:
`close this window like right now`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.close']`

**ACTUAL ROUTE**:
`close_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.close_window 35.29
2 phone.mirror_close 9.82
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=asr_variants`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `asr_008` (asr_variants)

**USER QUERY**:
`minimize like window`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.minimize']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.minimize_window 35.55
2 windows.show_desktop 22.72
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=asr_variants`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `asr_013` (asr_variants)

**USER QUERY**:
`check if c h r o m e is there`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.check_installed']`

**ACTUAL ROUTE**:
`search_web (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=asr_variants`

**INTENT FAMILY**:
`APP`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_008` (canonical)

**USER QUERY**:
`open file explorer`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.open 19.20
2 app.open 14.83
3 workflow.trim_clip 6.68
4 file.batch_rename 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`app:explorer`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_009` (canonical)

**USER QUERY**:
`close window`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.close']`

**ACTUAL ROUTE**:
`close_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.close_window 56.29
2 windows.desktop_ui_snapshot 5.17
3 app.refresh_catalog 3.00
4 file.delete 3.00
5 file.open 3.00
6 windows.show_desktop 3.00
7 windows.volume_mute 3.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_010` (canonical)

**USER QUERY**:
`minimize window`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.minimize']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.minimize_window 66.55
2 windows.show_desktop 22.72
3 windows.desktop_ui_snapshot 5.17
4 phone.mirror_close 4.03
5 windows.desktop_ui_click 4.03
6 app.refresh_catalog 3.00
7 file.delete 3.00
8 file.open 3.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_011` (canonical)

**USER QUERY**:
`maximize window`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.maximize']`

**ACTUAL ROUTE**:
`maximize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.maximize_window 66.84
2 windows.close_window 5.38
3 windows.desktop_ui_snapshot 5.17
4 phone.mirror_close 4.03
5 windows.desktop_ui_click 4.03
6 app.refresh_catalog 3.00
7 file.delete 3.00
8 file.open 3.00
9 windows.show_desktop 3.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_012` (canonical)

**USER QUERY**:
`restore window`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.restore']`

**ACTUAL ROUTE**:
`restore_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 workflow.launch_workspace 6.12
2 windows.close_window 5.38
3 windows.minimize_window 5.33
4 windows.maximize_window 5.32
5 windows.desktop_ui_snapshot 5.17
6 phone.mirror_close 4.03
7 windows.desktop_ui_click 4.03
8 app.refresh_catalog 3.00
9 file.delete 3.00
10 file.open 3.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_013` (canonical)

**USER QUERY**:
`show desktop`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.show_desktop']`

**ACTUAL ROUTE**:
`show_desktop (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.show_desktop 54.52
2 file.list_directory 8.87
3 phone.mirror_open 8.43
4 windows.desktop_ui_snapshot 4.76
5 file.create_folder 4.47
6 file.delete 4.47
7 file.move 4.47
8 windows.desktop_ui_click 3.88
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_016` (canonical)

**USER QUERY**:
`volume up`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_up']`

**ACTUAL ROUTE**:
`volume_up (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_unmute 5.15
2 windows.volume_mute 4.97
3 system.devices 3.00
4 system.microphone_status 3.00
5 system.wake_greeting 3.00
6 windows.media_control 3.00
7 workflow.extract_audio 3.00
8 workflow.trim_clip 3.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_017` (canonical)

**USER QUERY**:
`volume down`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_down']`

**ACTUAL ROUTE**:
`volume_down (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 15.70
2 windows.volume_set 15.70
3 windows.volume_unmute 5.15
4 windows.volume_mute 4.97
5 system.devices 3.00
6 system.microphone_status 3.00
7 system.wake_greeting 3.00
8 windows.media_control 3.00
9 workflow.extract_audio 3.00
10 workflow.trim_clip 3.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `can_025` (canonical)

**USER QUERY**:
`find files in Downloads`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 21.08
2 file.find 14.99
3 file.organize_downloads 10.35
4 browser.click 6.00
5 file.move 6.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`folder:downloads`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `can_026` (canonical)

**USER QUERY**:
`search files in Documents`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 20.63
2 file.find 19.67
3 file.find_duplicates 13.14
4 file.batch_rename 10.14
5 file.organize_downloads 9.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `can_028` (canonical)

**USER QUERY**:
`find duplicate files in Downloads`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.find_duplicates']`

**ACTUAL ROUTE**:
`list_directory (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 21.08
2 file.find_duplicates 16.56
3 file.copy 13.83
4 file.organize_downloads 10.35
5 file.find 9.99
6 browser.click 6.00
7 file.move 6.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`folder:downloads`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_033` (canonical)

**USER QUERY**:
`show system specs`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.diagnostics']`

**ACTUAL ROUTE**:
`system_info (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.info 50.51
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_034` (canonical)

**USER QUERY**:
`check microphone status`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.diagnostics']`

**ACTUAL ROUTE**:
`microphone_status (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.microphone_status 50.51
2 phone.status 14.14
3 workflow.git_status 9.32
4 system.wake_word_status 9.04
5 system.diagnostics 8.91
6 windows.volume_get 8.11
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`5`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_040` (canonical)

**USER QUERY**:
`where is chrome installed`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.location']`

**ACTUAL ROUTE**:
`get_app_location (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.check_installed 24.43
2 app.install_software 12.83
3 app.get_location 10.19
4 app.list_installed 5.60
5 app.refresh_catalog 5.27
6 app.close 4.83
7 app.open 4.83
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`3`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`APP`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `can_045` (canonical)

**USER QUERY**:
`close calculator`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close']`

**ACTUAL ROUTE**:
`close_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.close_window 5.91
2 phone.mirror_close 5.78
3 app.open 5.70
4 app.close 5.70
5 windows.volume_mute 3.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`4`

**ENTITY RESOLUTION**:
`app:calculator`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_047` (canonical)

**USER QUERY**:
`connected devices`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.diagnostics']`

**ACTUAL ROUTE**:
`connected_devices (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.devices 53.66
2 phone.status 8.07
3 phone.back 4.03
4 phone.home 4.03
5 phone.open_app 4.03
6 phone.send_file 4.03
7 whatsapp.action 3.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_048` (canonical)

**USER QUERY**:
`cancel current task`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['control.cancel']`

**ACTUAL ROUTE**:
`cancel_task (CONTROL)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`CONTROL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_049` (canonical)

**USER QUERY**:
`pause task`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['control.pause']`

**ACTUAL ROUTE**:
`pause_task (CONTROL)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.media_control 6.24
2 phone.send_notification 5.70
3 rag.morning_briefing 3.00
4 rag.personal_briefing 3.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`CONTROL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `can_050` (canonical)

**USER QUERY**:
`resume task`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['control.resume']`

**ACTUAL ROUTE**:
`resume_task (CONTROL)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 phone.send_notification 5.70
2 file.find 5.13
3 file.open 5.13
4 windows.media_control 5.13
5 rag.morning_briefing 3.00
6 rag.personal_briefing 3.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=canonical`

**INTENT FAMILY**:
`CONTROL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `comp_005` (compositional)

**USER QUERY**:
`Find the latest PDF in Downloads and open its folder in File Explorer.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 file.organize_downloads 18.46
2 app.open 18.13
3 file.find 17.44
4 file.list_directory 17.19
5 file.rename 16.64
6 file.move 16.46
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`3`

**ENTITY RESOLUTION**:
`app:explorer, folder:downloads, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `comp_007` (compositional)

**USER QUERY**:
`Mute the sound and minimize the active window.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_mute', 'window.minimize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.minimize_window 39.84
2 windows.volume_mute 34.96
3 windows.show_desktop 26.02
4 windows.media_control 22.33
5 windows.desktop_ui_snapshot 12.77
6 windows.volume_get 12.15
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `comp_009` (compositional)

**USER QUERY**:
`Search for contract files and check phone connectivity.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 file.find_duplicates 15.49
2 file.find 12.97
3 workflow.git_status 12.74
4 phone.status 12.40
5 file.read_metadata 10.49
6 file.rename 9.30
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `comp_012` (compositional)

**USER QUERY**:
`Find python files modified today and check git status.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'workflow.git_status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 workflow.git_status 61.11
2 file.find_duplicates 17.76
3 file.read_metadata 16.21
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_014` (compositional)

**USER QUERY**:
`Check weather forecast in browser and make a note of it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['browser.open_url', 'knowledge.note']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 rag.memos_recent 10.32
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`BROWSER`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_015` (compositional)

**USER QUERY**:
`Find invoice in Documents and extract the total amount.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 file.find_duplicates 13.54
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_016` (compositional)

**USER QUERY**:
`Open Edge and search Google for Python documentation.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open', 'browser.search']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 rag.search_web 19.73
2 app.open 18.13
3 browser.play_youtube 17.54
4 app.refresh_catalog 9.30
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`app:edge`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`MULTI_CAPABILITY_RANK_ORDER`

---

### Test ID: `comp_017` (compositional)

**USER QUERY**:
`Close Calculator and bring up Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close', 'app.open']`

**ACTUAL ROUTE**:
`compound (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 31.14
2 workflow.dictate_text 11.44
3 app.close 10.83
4 browser.play_youtube 6.55
5 rag.morning_briefing 6.43
6 workflow.launch_workspace 6.43
7 app.list_installed 6.30
8 app.refresh_catalog 6.30
9 system.diagnostics 6.30
10 windows.show_desktop 6.30
```

**EXPECTED CAPABILITY RANK**:
`3`

**ENTITY RESOLUTION**:
`app:notepad, app:calculator`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `comp_018` (compositional)

**USER QUERY**:
`Maximize the current window and take a screenshot.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.maximize', 'system.screenshot']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.screenshot 46.69
2 windows.maximize_window 38.84
3 windows.desktop_ui_snapshot 11.48
4 workflow.save_workspace 10.70
5 system.devices 8.55
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_019` (compositional)

**USER QUERY**:
`Check disk space and list top memory consuming apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.disk_info', 'system.processes']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.top_memory_processes 48.20
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_020` (compositional)

**USER QUERY**:
`Find all zip files in Downloads and organize them into Archives.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.organize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 24.38
2 file.organize_downloads 19.97
3 file.find_duplicates 13.74
4 file.find 13.29
5 app.install_software 12.30
6 file.move 11.70
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`4`

**ENTITY RESOLUTION**:
`folder:downloads, ext:zip`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `comp_021` (compositional)

**USER QUERY**:
`Find invoices in Documents, summarize the latest one, and draft an email to finance with the summary.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_023` (compositional)

**USER QUERY**:
`Check calendar events for today, draft morning briefing note, and read headlines from RSS.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['calendar.read', 'knowledge.note', 'rss.latest']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 rag.morning_briefing 34.96
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`KnowledgeResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GOOGLE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_024` (compositional)

**USER QUERY**:
`Find all pdf files in Downloads, summarize the most recent one, and save the notes.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'knowledge.note']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 19.38
2 file.find 17.92
3 rag.personal_briefing 16.40
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`folder:downloads, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `comp_026` (compositional)

**USER QUERY**:
`Find the contract with Acme Corp, extract payment terms, and compose WhatsApp draft to Sarah.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.extract', 'whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_027` (compositional)

**USER QUERY**:
`Check battery percentage, set screen brightness to 60%, and close unused background apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.battery', 'system.brightness', 'system.processes']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.brightness_get 43.34
2 windows.brightness_set 40.71
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_028` (compositional)

**USER QUERY**:
`Search for presentation in Downloads, open containing folder, and check Android connection.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'app.open', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.13
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_029` (compositional)

**USER QUERY**:
`Look up latest research on quantum computing, extract executive summary, and open browser source.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_web', 'knowledge.summarize', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.13
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_030` (compositional)

**USER QUERY**:
`Find audio recording in Music, trim first 30 seconds, and send clip to phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'workflow.trim_audio', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 workflow.trim_clip 42.35
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:music`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_031` (compositional)

**USER QUERY**:
`Capture active window snapshot, copy image to clipboard, and open Discord.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.screenshot', 'system.clipboard', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.13
2 windows.desktop_ui_snapshot 17.74
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_033` (compositional)

**USER QUERY**:
`Check system CPU usage, if above 80% list top processes, and notify user.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.cpu', 'system.processes', 'system.notify']`

**ACTUAL ROUTE**:
`system_info (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.info 44.29
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `comp_034` (compositional)

**USER QUERY**:
`Find the downloaded dataset zip, verify SHA256 checksum, and extract to Data directory.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.checksum', 'file.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:zip`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_035` (compositional)

**USER QUERY**:
`Search email for meeting link, copy URL, and open it in Google Chrome.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['email.search', 'system.clipboard', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 36.96
2 app.check_installed 18.83
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_036` (compositional)

**USER QUERY**:
`Find the newest research paper on neural networks in Downloads, extract key takeaways, open official documentation in Chrome, and send the PDF to my phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 36.96
2 app.check_installed 18.83
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome, folder:downloads, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_037` (compositional)

**USER QUERY**:
`Search for quarterly financial statements, extract revenue numbers, compare with last year's report, and draft email to the board with executive summary.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.extract', 'knowledge.compare', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_038` (compositional)

**USER QUERY**:
`Find latest photo taken on Android phone, transfer to PC Downloads, optimize resolution, and set as desktop background.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['phone.get_photo', 'phone.transfer', 'image.optimize', 'system.set_wallpaper']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:desktop`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`PHONE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_039` (compositional)

**USER QUERY**:
`Scan project folder for linting errors, run unit test suite, generate coverage report, and open results in browser.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['workflow.lint', 'workflow.run_tests', 'workflow.coverage', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 workflow.run_tests 38.07
2 app.open 30.25
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WORKFLOW`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_042` (compositional)

**USER QUERY**:
`Find all duplicate MP3 files in Music, compute hash checksums, group into duplicates list, and prompt user before removal.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.hash', 'file.group', 'user.confirm']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:music, ext:mp3`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_043` (compositional)

**USER QUERY**:
`Retrieve calendar appointments for tomorrow, check commute travel time on Google Maps, draft morning alarm recommendations, and save to memos.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['calendar.read', 'browser.maps', 'knowledge.recommend', 'rag.memos_create']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.time 36.23
2 windows.volume_mute 5.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GOOGLE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_044` (compositional)

**USER QUERY**:
`Search Drive for marketing roadmap slides, convert presentation to PDF, send copy to phone, and notify team on WhatsApp.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['drive.search', 'file.convert', 'phone.transfer', 'whatsapp.send']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GOOGLE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_046` (compositional)

**USER QUERY**:
`Find neural_networks.pdf in Documents, extract key summary points, and draft an update to Dr. Rao.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.time 8.30
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_047` (compositional)

**USER QUERY**:
`Search for files related to machine learning, organize them into a dedicated folder, and check phone status.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.organize', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.status 34.35
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_048` (compositional)

**USER QUERY**:
`Retrieve latest notes on machine learning, format them into bullet points, and open in Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_notes', 'knowledge.format', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 37.26
2 rag.memos_recent 14.27
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_049` (compositional)

**USER QUERY**:
`Check if Dr. Rao sent any WhatsApp messages about machine learning, summarize the thread, and notify me.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.read', 'knowledge.summarize', 'system.notify']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 30.65
2 whatsapp.send 13.46
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_050` (compositional)

**USER QUERY**:
`Find newest machine learning PDF, extract main findings, open source reference in browser, and push file to phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.13
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_051` (compositional)

**USER QUERY**:
`Scan Downloads for machine learning documents, calculate total storage used, and create a status memo.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.stats', 'rag.memos_create']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_052` (compositional)

**USER QUERY**:
`Search Google for recent news on machine learning, save top 3 article links, and open first link in Chrome.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['news.search', 'knowledge.save', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 36.96
2 app.check_installed 18.83
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_054` (compositional)

**USER QUERY**:
`Find incident_report.docx in Documents, extract key summary points, and draft an update to Chief Security Officer.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.time 8.30
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents, ext:docx`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_055` (compositional)

**USER QUERY**:
`Search for files related to cybersecurity, organize them into a dedicated folder, and check phone status.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.organize', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.status 34.35
2 file.organize_downloads 18.60
3 workflow.git_status 17.69
4 file.find_duplicates 15.49
5 file.rename 13.70
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_056` (compositional)

**USER QUERY**:
`Retrieve latest notes on cybersecurity, format them into bullet points, and open in Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_notes', 'knowledge.format', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 37.26
2 rag.memos_recent 14.27
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_057` (compositional)

**USER QUERY**:
`Check if Chief Security Officer sent any WhatsApp messages about cybersecurity, summarize the thread, and notify me.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.read', 'knowledge.summarize', 'system.notify']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 30.65
2 whatsapp.send 13.46
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_058` (compositional)

**USER QUERY**:
`Find newest cybersecurity PDF, extract main findings, open source reference in browser, and push file to phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.13
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_059` (compositional)

**USER QUERY**:
`Scan Downloads for cybersecurity documents, calculate total storage used, and create a status memo.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.stats', 'rag.memos_create']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_060` (compositional)

**USER QUERY**:
`Search Google for recent news on cybersecurity, save top 3 article links, and open first link in Chrome.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['news.search', 'knowledge.save', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 36.96
2 app.check_installed 18.83
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_062` (compositional)

**USER QUERY**:
`Find q3_forecast.xlsx in Documents, extract key summary points, and draft an update to Financial Controller.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.time 8.30
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_063` (compositional)

**USER QUERY**:
`Search for files related to quarterly budget, organize them into a dedicated folder, and check phone status.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.organize', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.status 34.35
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_064` (compositional)

**USER QUERY**:
`Retrieve latest notes on quarterly budget, format them into bullet points, and open in Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_notes', 'knowledge.format', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 37.26
2 rag.memos_recent 14.27
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_065` (compositional)

**USER QUERY**:
`Check if Financial Controller sent any WhatsApp messages about quarterly budget, summarize the thread, and notify me.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.read', 'knowledge.summarize', 'system.notify']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 30.65
2 whatsapp.send 13.46
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_066` (compositional)

**USER QUERY**:
`Find newest quarterly budget PDF, extract main findings, open source reference in browser, and push file to phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.13
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_067` (compositional)

**USER QUERY**:
`Scan Downloads for quarterly budget documents, calculate total storage used, and create a status memo.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.stats', 'rag.memos_create']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_068` (compositional)

**USER QUERY**:
`Search Google for recent news on quarterly budget, save top 3 article links, and open first link in Chrome.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['news.search', 'knowledge.save', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 36.96
2 app.check_installed 18.83
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_070` (compositional)

**USER QUERY**:
`Find figma_specs.pdf in Documents, extract key summary points, and draft an update to Lead Designer.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.info 8.30
2 system.time 8.30
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_071` (compositional)

**USER QUERY**:
`Search for files related to product design, organize them into a dedicated folder, and check phone status.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.organize', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.status 34.35
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_072` (compositional)

**USER QUERY**:
`Retrieve latest notes on product design, format them into bullet points, and open in Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_notes', 'knowledge.format', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 37.26
2 rag.memos_recent 14.27
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_073` (compositional)

**USER QUERY**:
`Check if Lead Designer sent any WhatsApp messages about product design, summarize the thread, and notify me.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.read', 'knowledge.summarize', 'system.notify']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 30.65
2 whatsapp.send 13.46
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_074` (compositional)

**USER QUERY**:
`Find newest product design PDF, extract main findings, open source reference in browser, and push file to phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.13
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_075` (compositional)

**USER QUERY**:
`Scan Downloads for product design documents, calculate total storage used, and create a status memo.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.stats', 'rag.memos_create']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_076` (compositional)

**USER QUERY**:
`Search Google for recent news on product design, save top 3 article links, and open first link in Chrome.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['news.search', 'knowledge.save', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 36.96
2 app.check_installed 18.83
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_078` (compositional)

**USER QUERY**:
`Find nda_signed.pdf in Documents, extract key summary points, and draft an update to Senior Partner.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.time 8.30
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_079` (compositional)

**USER QUERY**:
`Search for files related to legal agreement, organize them into a dedicated folder, and check phone status.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.organize', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.status 34.35
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_080` (compositional)

**USER QUERY**:
`Retrieve latest notes on legal agreement, format them into bullet points, and open in Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_notes', 'knowledge.format', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 37.26
2 rag.memos_recent 14.27
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_081` (compositional)

**USER QUERY**:
`Check if Senior Partner sent any WhatsApp messages about legal agreement, summarize the thread, and notify me.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.read', 'knowledge.summarize', 'system.notify']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 30.65
2 whatsapp.send 13.46
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_082` (compositional)

**USER QUERY**:
`Find newest legal agreement PDF, extract main findings, open source reference in browser, and push file to phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.13
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_083` (compositional)

**USER QUERY**:
`Scan Downloads for legal agreement documents, calculate total storage used, and create a status memo.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.stats', 'rag.memos_create']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_084` (compositional)

**USER QUERY**:
`Search Google for recent news on legal agreement, save top 3 article links, and open first link in Chrome.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['news.search', 'knowledge.save', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 36.96
2 app.check_installed 18.83
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_086` (compositional)

**USER QUERY**:
`Find efficacy_study.pdf in Documents, extract key summary points, and draft an update to Principal Investigator.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.time 8.30
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_087` (compositional)

**USER QUERY**:
`Search for files related to patient clinical trial, organize them into a dedicated folder, and check phone status.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.organize', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.status 34.35
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_088` (compositional)

**USER QUERY**:
`Retrieve latest notes on patient clinical trial, format them into bullet points, and open in Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_notes', 'knowledge.format', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 37.26
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_089` (compositional)

**USER QUERY**:
`Check if Principal Investigator sent any WhatsApp messages about patient clinical trial, summarize the thread, and notify me.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.read', 'knowledge.summarize', 'system.notify']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 30.65
2 whatsapp.send 13.46
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_090` (compositional)

**USER QUERY**:
`Find newest patient clinical trial PDF, extract main findings, open source reference in browser, and push file to phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.13
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_091` (compositional)

**USER QUERY**:
`Scan Downloads for patient clinical trial documents, calculate total storage used, and create a status memo.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.stats', 'rag.memos_create']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_092` (compositional)

**USER QUERY**:
`Search Google for recent news on patient clinical trial, save top 3 article links, and open first link in Chrome.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['news.search', 'knowledge.save', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 36.96
2 app.check_installed 18.83
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_094` (compositional)

**USER QUERY**:
`Find terraform_plan.tf in Documents, extract key summary points, and draft an update to Engineering Director.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.time 8.30
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_095` (compositional)

**USER QUERY**:
`Search for files related to cloud infrastructure, organize them into a dedicated folder, and check phone status.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.organize', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.status 34.35
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_096` (compositional)

**USER QUERY**:
`Retrieve latest notes on cloud infrastructure, format them into bullet points, and open in Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_notes', 'knowledge.format', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 37.26
2 rag.memos_recent 14.27
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_097` (compositional)

**USER QUERY**:
`Check if Engineering Director sent any WhatsApp messages about cloud infrastructure, summarize the thread, and notify me.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.read', 'knowledge.summarize', 'system.notify']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 30.65
2 whatsapp.send 13.46
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_098` (compositional)

**USER QUERY**:
`Find newest cloud infrastructure PDF, extract main findings, open source reference in browser, and push file to phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.13
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_099` (compositional)

**USER QUERY**:
`Scan Downloads for cloud infrastructure documents, calculate total storage used, and create a status memo.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.stats', 'rag.memos_create']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_100` (compositional)

**USER QUERY**:
`Search Google for recent news on cloud infrastructure, save top 3 article links, and open first link in Chrome.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['news.search', 'knowledge.save', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 36.96
2 app.check_installed 18.83
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_102` (compositional)

**USER QUERY**:
`Find retention_metrics.csv in Documents, extract key summary points, and draft an update to Product VP.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.time 8.30
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_103` (compositional)

**USER QUERY**:
`Search for files related to mobile app analytics, organize them into a dedicated folder, and check phone status.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.organize', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.status 34.35
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_104` (compositional)

**USER QUERY**:
`Retrieve latest notes on mobile app analytics, format them into bullet points, and open in Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_notes', 'knowledge.format', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 41.81
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_105` (compositional)

**USER QUERY**:
`Check if Product VP sent any WhatsApp messages about mobile app analytics, summarize the thread, and notify me.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.read', 'knowledge.summarize', 'system.notify']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 30.65
2 whatsapp.send 16.46
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_106` (compositional)

**USER QUERY**:
`Find newest mobile app analytics PDF, extract main findings, open source reference in browser, and push file to phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 22.67
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_107` (compositional)

**USER QUERY**:
`Scan Downloads for mobile app analytics documents, calculate total storage used, and create a status memo.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.stats', 'rag.memos_create']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_108` (compositional)

**USER QUERY**:
`Search Google for recent news on mobile app analytics, save top 3 article links, and open first link in Chrome.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['news.search', 'knowledge.save', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 41.51
2 app.check_installed 18.83
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_110` (compositional)

**USER QUERY**:
`Find nps_survey_q3.csv in Documents, extract key summary points, and draft an update to Customer Success Lead.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.time 8.30
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_111` (compositional)

**USER QUERY**:
`Search for files related to customer feedback, organize them into a dedicated folder, and check phone status.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.organize', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.status 34.35
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_112` (compositional)

**USER QUERY**:
`Retrieve latest notes on customer feedback, format them into bullet points, and open in Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_notes', 'knowledge.format', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 37.26
2 rag.memos_recent 14.27
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_113` (compositional)

**USER QUERY**:
`Check if Customer Success Lead sent any WhatsApp messages about customer feedback, summarize the thread, and notify me.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.read', 'knowledge.summarize', 'system.notify']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 30.65
2 whatsapp.send 13.46
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_114` (compositional)

**USER QUERY**:
`Find newest customer feedback PDF, extract main findings, open source reference in browser, and push file to phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.13
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_115` (compositional)

**USER QUERY**:
`Scan Downloads for customer feedback documents, calculate total storage used, and create a status memo.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.stats', 'rag.memos_create']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_116` (compositional)

**USER QUERY**:
`Search Google for recent news on customer feedback, save top 3 article links, and open first link in Chrome.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['news.search', 'knowledge.save', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 36.96
2 app.check_installed 18.83
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_118` (compositional)

**USER QUERY**:
`Find thermal_stress.log in Documents, extract key summary points, and draft an update to Systems Architect.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 rag.meeting_notes 23.08
2 system.time 8.30
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_119` (compositional)

**USER QUERY**:
`Search for files related to hardware telemetry, organize them into a dedicated folder, and check phone status.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.organize', 'phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.status 34.35
2 system.info 18.32
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_120` (compositional)

**USER QUERY**:
`Retrieve latest notes on hardware telemetry, format them into bullet points, and open in Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_notes', 'knowledge.format', 'app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 37.26
2 system.info 21.32
3 rag.memos_recent 14.27
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_121` (compositional)

**USER QUERY**:
`Check if Systems Architect sent any WhatsApp messages about hardware telemetry, summarize the thread, and notify me.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.read', 'knowledge.summarize', 'system.notify']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.info 35.32
2 whatsapp.summarize 30.65
3 whatsapp.send 13.46
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_122` (compositional)

**USER QUERY**:
`Find newest hardware telemetry PDF, extract main findings, open source reference in browser, and push file to phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'browser.open_url', 'phone.transfer']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.info 18.32
2 app.open 18.13
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_123` (compositional)

**USER QUERY**:
`Scan Downloads for hardware telemetry documents, calculate total storage used, and create a status memo.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'file.stats', 'rag.memos_create']`

**ACTUAL ROUTE**:
`system_info (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.info 18.32
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `comp_124` (compositional)

**USER QUERY**:
`Search Google for recent news on hardware telemetry, save top 3 article links, and open first link in Chrome.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['news.search', 'knowledge.save', 'browser.open_url']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 36.96
2 app.check_installed 18.83
3 system.info 18.32
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_127` (compositional)

**USER QUERY**:
`Close VS Code, open Terminal, and set system volume to 35 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close', 'app.open', 'system.volume_set']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 41.69
2 app.close 29.25
3 windows.volume_set 26.52
4 windows.volume_get 19.00
5 terminal.powershell 13.31
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`MULTI_CAPABILITY_RANK_ORDER`

---

### Test ID: `comp_129` (compositional)

**USER QUERY**:
`Close Excel, open Calculator, and set system volume to 35 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close', 'app.open', 'system.volume_set']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 37.83
2 windows.volume_set 26.52
3 windows.volume_get 19.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:calculator`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_131` (compositional)

**USER QUERY**:
`Close Word, open Chrome, and set system volume to 35 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close', 'app.open', 'system.volume_set']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 34.96
2 windows.volume_set 26.52
3 windows.volume_get 19.00
4 app.check_installed 18.83
5 app.close 4.53
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`5`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`MULTI_CAPABILITY_RANK_ORDER`

---

### Test ID: `comp_133` (compositional)

**USER QUERY**:
`Close Spotify, open Discord, and set system volume to 35 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close', 'app.open', 'system.volume_set']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 37.10
2 windows.volume_set 26.52
3 app.close 22.66
4 windows.volume_get 19.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`3`

**ENTITY RESOLUTION**:
`app:spotify`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`MULTI_CAPABILITY_RANK_ORDER`

---

### Test ID: `comp_135` (compositional)

**USER QUERY**:
`Close Photoshop, open File Explorer, and set system volume to 35 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close', 'app.open', 'system.volume_set']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_set 26.52
2 file.open 19.20
3 windows.volume_get 19.00
4 app.open 18.13
5 workflow.trim_clip 12.99
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:explorer`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_137` (compositional)

**USER QUERY**:
`Close Firefox, open Notepad, and set system volume to 35 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close', 'app.open', 'system.volume_set']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 35.26
2 windows.volume_set 26.52
3 windows.volume_get 19.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_139` (compositional)

**USER QUERY**:
`Close Slack, open Outlook, and set system volume to 35 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close', 'app.open', 'system.volume_set']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_set 26.52
2 windows.volume_get 19.00
3 app.open 18.13
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_141` (compositional)

**USER QUERY**:
`Close PowerPoint, open Zoom, and set system volume to 35 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close', 'app.open', 'system.volume_set']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_set 26.52
2 windows.volume_get 19.00
3 app.open 18.13
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_143` (compositional)

**USER QUERY**:
`Close Edge, open OneNote, and set system volume to 35 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close', 'app.open', 'system.volume_set']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_set 26.52
2 windows.volume_get 19.00
3 app.open 18.13
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:edge`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_145` (compositional)

**USER QUERY**:
`Close GitKraken, open Postman, and set system volume to 35 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close', 'app.open', 'system.volume_set']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_set 26.52
2 windows.volume_get 19.00
3 app.open 18.13
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `comp_146` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #146 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_147` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #147 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_148` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #148 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_149` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #149 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_150` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #150 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_151` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #151 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_152` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #152 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_153` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #153 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_154` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #154 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_155` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #155 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_156` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #156 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_157` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #157 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_158` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #158 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_159` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #159 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_160` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #160 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_161` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #161 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_162` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #162 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_163` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #163 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_164` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #164 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_165` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #165 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_166` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #166 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_167` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #167 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_168` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #168 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_169` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #169 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_170` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #170 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_171` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #171 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_172` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #172 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_173` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #173 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_174` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #174 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_175` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #175 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_176` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #176 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_177` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #177 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_178` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #178 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_179` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #179 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_180` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #180 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_181` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #181 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_182` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #182 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_183` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #183 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_184` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #184 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_185` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #185 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_186` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #186 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_187` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #187 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_188` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #188 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_189` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #189 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_190` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #190 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_191` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #191 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_192` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #192 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_193` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #193 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_194` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #194 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_195` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #195 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_196` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #196 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_197` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #197 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_198` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #198 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_199` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #199 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_200` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #200 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_201` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #201 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_202` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #202 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_203` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #203 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_204` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #204 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_205` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #205 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_206` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #206 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_207` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #207 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_208` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #208 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_209` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #209 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `comp_210` (compositional)

**USER QUERY**:
`Execute coordinated multi-capability workflow sequence #210 across system and local resources.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize', 'app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=compositional`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_001` (constraints)

**USER QUERY**:
`Find the latest PDF, summarize it, but don't open or modify anything.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.27
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_002` (constraints)

**USER QUERY**:
`Search for invoices in Downloads in read-only mode.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_003` (constraints)

**USER QUERY**:
`Prepare an email to Alex about the meeting as a draft only without sending.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['email.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`GOOGLE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_004` (constraints)

**USER QUERY**:
`Draft a WhatsApp message to Rahul but do not send.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.send 46.84
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_006` (constraints)

**USER QUERY**:
`Search the web for python tutorials, but only show results, don't click links.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_web']`

**ACTUAL ROUTE**:
`search_web (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 browser.click 26.83
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_008` (constraints)

**USER QUERY**:
`Inspect active network connections in read-only mode without disconnecting.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.network']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_009` (constraints)

**USER QUERY**:
`Extract financial figures from the balance sheet, but do not alter the spreadsheet.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_011` (constraints)

**USER QUERY**:
`Check disk space across all drives without running cleanup.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.disk_info']`

**ACTUAL ROUTE**:
`search_web (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_012` (constraints)

**USER QUERY**:
`Scan system event logs for critical errors, read-only without clearing logs.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.event_logs']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_013` (constraints)

**USER QUERY**:
`Find all zip archives in Documents but under no circumstances extract them.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents, ext:zip`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_014` (constraints)

**USER QUERY**:
`Look up hardware temperatures without adjusting fan curves.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.hardware']`

**ACTUAL ROUTE**:
`search_web (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.info 15.02
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_015` (constraints)

**USER QUERY**:
`Summarize today's news headlines, text only, do not play audio.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.search_news']`

**ACTUAL ROUTE**:
`volume_get (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 22.95
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`KnowledgeResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_016` (constraints)

**USER QUERY**:
`Compose a project memo from meeting notes, save as draft, don't publish.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['rag.memos_create']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 rag.meeting_notes 15.63
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`KnowledgeResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_018` (constraints)

**USER QUERY**:
`Search contacts for doctors in Bangalore, list names only, do not initiate calls.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['contacts.search']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`MessageResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`CONTACTS`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_019` (constraints)

**USER QUERY**:
`Audit installed applications and show versions, don't uninstall or update.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.list_installed']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 33.54
2 app.list_installed 32.95
3 app.refresh_catalog 19.95
4 app.install_software 14.60
5 system.time 8.30
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`APP`

**ROOT CAUSE**:
`RANK_SUPPRESSED_BY_OTHER_CANDIDATE`

---

### Test ID: `const_020` (constraints)

**USER QUERY**:
`Preview the presentation slides without entering full-screen presenter mode.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.preview']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_021` (constraints)

**USER QUERY**:
`Find the quarterly report in Documents, summarize key points, but do not open or modify the original.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.27
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_022` (constraints)

**USER QUERY**:
`Draft a message to financials regarding the quarterly report, strictly as draft, do not send.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`MessageResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_023` (constraints)

**USER QUERY**:
`Organize files related to quarterly report in Documents, but never delete or overwrite existing files.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_024` (constraints)

**USER QUERY**:
`Extract text from quarterly report in Documents, read-only mode, without launching external apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 11.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_025` (constraints)

**USER QUERY**:
`Find the tax return 2025 in Downloads, summarize key points, but do not open or modify the original.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.27
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_026` (constraints)

**USER QUERY**:
`Draft a message to accounting regarding the tax return 2025, strictly as draft, do not send.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`MessageResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_027` (constraints)

**USER QUERY**:
`Organize files related to tax return 2025 in Downloads, but never delete or overwrite existing files.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_028` (constraints)

**USER QUERY**:
`Extract text from tax return 2025 in Downloads, read-only mode, without launching external apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 11.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_029` (constraints)

**USER QUERY**:
`Find the design mockups in Desktop, summarize key points, but do not open or modify the original.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.27
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_030` (constraints)

**USER QUERY**:
`Draft a message to creative team regarding the design mockups, strictly as draft, do not send.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`MessageResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_031` (constraints)

**USER QUERY**:
`Organize files related to design mockups in Desktop, but never delete or overwrite existing files.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_032` (constraints)

**USER QUERY**:
`Extract text from design mockups in Desktop, read-only mode, without launching external apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 11.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_033` (constraints)

**USER QUERY**:
`Find the vendor agreement in Contracts, summarize key points, but do not open or modify the original.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.27
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_034` (constraints)

**USER QUERY**:
`Draft a message to legal regarding the vendor agreement, strictly as draft, do not send.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`MessageResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_035` (constraints)

**USER QUERY**:
`Organize files related to vendor agreement in Contracts, but never delete or overwrite existing files.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_036` (constraints)

**USER QUERY**:
`Extract text from vendor agreement in Contracts, read-only mode, without launching external apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 11.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_037` (constraints)

**USER QUERY**:
`Find the server access logs in Logs, summarize key points, but do not open or modify the original.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.27
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_038` (constraints)

**USER QUERY**:
`Draft a message to DevOps regarding the server access logs, strictly as draft, do not send.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`MessageResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_039` (constraints)

**USER QUERY**:
`Organize files related to server access logs in Logs, but never delete or overwrite existing files.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_040` (constraints)

**USER QUERY**:
`Extract text from server access logs in Logs, read-only mode, without launching external apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 11.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_041` (constraints)

**USER QUERY**:
`Find the patient intake records in Medical, summarize key points, but do not open or modify the original.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.27
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_042` (constraints)

**USER QUERY**:
`Draft a message to clinic regarding the patient intake records, strictly as draft, do not send.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`MessageResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_043` (constraints)

**USER QUERY**:
`Organize files related to patient intake records in Medical, but never delete or overwrite existing files.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_044` (constraints)

**USER QUERY**:
`Extract text from patient intake records in Medical, read-only mode, without launching external apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 11.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_045` (constraints)

**USER QUERY**:
`Find the student grades roster in Academic, summarize key points, but do not open or modify the original.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.27
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_046` (constraints)

**USER QUERY**:
`Draft a message to faculty regarding the student grades roster, strictly as draft, do not send.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`MessageResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_047` (constraints)

**USER QUERY**:
`Organize files related to student grades roster in Academic, but never delete or overwrite existing files.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_048` (constraints)

**USER QUERY**:
`Extract text from student grades roster in Academic, read-only mode, without launching external apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 11.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_049` (constraints)

**USER QUERY**:
`Find the inventory audit sheet in Warehouse, summarize key points, but do not open or modify the original.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 33.24
2 app.open 18.27
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_050` (constraints)

**USER QUERY**:
`Draft a message to logistics regarding the inventory audit sheet, strictly as draft, do not send.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 30.24
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`MessageResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_051` (constraints)

**USER QUERY**:
`Organize files related to inventory audit sheet in Warehouse, but never delete or overwrite existing files.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 30.24
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_052` (constraints)

**USER QUERY**:
`Extract text from inventory audit sheet in Warehouse, read-only mode, without launching external apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 33.24
2 app.open 11.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_053` (constraints)

**USER QUERY**:
`Find the employee survey results in HR, summarize key points, but do not open or modify the original.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 18.27
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_054` (constraints)

**USER QUERY**:
`Draft a message to management regarding the employee survey results, strictly as draft, do not send.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`MessageResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_055` (constraints)

**USER QUERY**:
`Organize files related to employee survey results in HR, but never delete or overwrite existing files.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_056` (constraints)

**USER QUERY**:
`Extract text from employee survey results in HR, read-only mode, without launching external apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 11.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_057` (constraints)

**USER QUERY**:
`Find the code review comments in Repository, summarize key points, but do not open or modify the original.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search', 'knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 22.99
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_058` (constraints)

**USER QUERY**:
`Draft a message to core dev team regarding the code review comments, strictly as draft, do not send.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.draft']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`MessageResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_059` (constraints)

**USER QUERY**:
`Organize files related to code review comments in Repository, but never delete or overwrite existing files.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_060` (constraints)

**USER QUERY**:
`Extract text from code review comments in Repository, read-only mode, without launching external apps.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.extract']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 15.72
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_061` (constraints)

**USER QUERY**:
`Search for duplicate photos in Pictures without deleting any copies.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.find_duplicates']`

**ACTUAL ROUTE**:
`search_web (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:pictures`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_063` (constraints)

**USER QUERY**:
`List all Bluetooth devices paired with this PC without unpairing anything.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.bluetooth']`

**ACTUAL ROUTE**:
`list_directory (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.devices 21.43
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_064` (constraints)

**USER QUERY**:
`Analyze network latency to gateway without resetting the adapter.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.ping']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_065` (constraints)

**USER QUERY**:
`Show Wi-Fi passwords for saved profiles on screen without exporting.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.wifi']`

**ACTUAL ROUTE**:
`android_open_control (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 phone.mirror_open 18.01
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_066` (constraints)

**USER QUERY**:
`Check WhatsApp status updates without downloading media files.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.status']`

**ACTUAL ROUTE**:
`media_control (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.media_control 15.02
2 file.find_duplicates 14.55
3 workflow.git_status 14.38
4 file.move 9.00
5 system.time 5.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_067` (constraints)

**USER QUERY**:
`Search PDF books on machine learning in Downloads, show paths only, don't open.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 9.83
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_068` (constraints)

**USER QUERY**:
`Check system uptime and boot diagnostics without restarting the PC.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.uptime']`

**ACTUAL ROUTE**:
`system_diagnostics (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 43.20
2 app.open 8.30
3 system.time 8.30
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_069` (constraints)

**USER QUERY**:
`Inspect task scheduler jobs, read-only without disabling or modifying any tasks.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.tasks']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_070` (constraints)

**USER QUERY**:
`Check antivirus definition dates without initiating full system scan.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.antivirus']`

**ACTUAL ROUTE**:
`search_web (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.time 22.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_071` (constraints)

**USER QUERY**:
`Review active audio input devices without changing default microphone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.audio_devices']`

**ACTUAL ROUTE**:
`microphone_status (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.devices 28.56
2 system.microphone_status 25.42
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `const_072` (constraints)

**USER QUERY**:
`Examine firewall inbound rules, display only, do not block or allow ports.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.firewall']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_073` (constraints)

**USER QUERY**:
`Find all python scripts modified today, list them, but do not execute any scripts.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_074` (constraints)

**USER QUERY**:
`Inspect environment variables in read-only mode without setting new values.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.env']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `const_075` (constraints)

**USER QUERY**:
`Search email inbox for subject line Security Alert, read summary, don't click links.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['email.search']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 browser.click 18.84
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_076` (constraints)

**USER QUERY**:
`Audit system service #75 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_077` (constraints)

**USER QUERY**:
`Audit system service #76 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_078` (constraints)

**USER QUERY**:
`Audit system service #77 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_079` (constraints)

**USER QUERY**:
`Audit system service #78 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_080` (constraints)

**USER QUERY**:
`Audit system service #79 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_081` (constraints)

**USER QUERY**:
`Audit system service #80 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_082` (constraints)

**USER QUERY**:
`Audit system service #81 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_083` (constraints)

**USER QUERY**:
`Audit system service #82 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_084` (constraints)

**USER QUERY**:
`Audit system service #83 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_085` (constraints)

**USER QUERY**:
`Audit system service #84 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_086` (constraints)

**USER QUERY**:
`Audit system service #85 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_087` (constraints)

**USER QUERY**:
`Audit system service #86 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_088` (constraints)

**USER QUERY**:
`Audit system service #87 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_089` (constraints)

**USER QUERY**:
`Audit system service #88 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_090` (constraints)

**USER QUERY**:
`Audit system service #89 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_091` (constraints)

**USER QUERY**:
`Audit system service #90 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_092` (constraints)

**USER QUERY**:
`Audit system service #91 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_093` (constraints)

**USER QUERY**:
`Audit system service #92 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_094` (constraints)

**USER QUERY**:
`Audit system service #93 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_095` (constraints)

**USER QUERY**:
`Audit system service #94 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_096` (constraints)

**USER QUERY**:
`Audit system service #95 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_097` (constraints)

**USER QUERY**:
`Audit system service #96 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_098` (constraints)

**USER QUERY**:
`Audit system service #97 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_099` (constraints)

**USER QUERY**:
`Audit system service #98 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_100` (constraints)

**USER QUERY**:
`Audit system service #99 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_101` (constraints)

**USER QUERY**:
`Audit system service #100 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_102` (constraints)

**USER QUERY**:
`Audit system service #101 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_103` (constraints)

**USER QUERY**:
`Audit system service #102 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_104` (constraints)

**USER QUERY**:
`Audit system service #103 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `const_105` (constraints)

**USER QUERY**:
`Audit system service #104 status in read-only mode without restarting or stopping it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.services']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 system.diagnostics 39.79
2 app.open 8.44
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=constraints`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `ctx_001` (contextual)

**USER QUERY**:
`Open the second one.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 workflow.trim_clip 6.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_002` (contextual)

**USER QUERY**:
`Open that file.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_file (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 file.open 9.20
3 workflow.trim_clip 6.68
4 file.batch_rename 6.00
5 browser.open_url 4.83
6 phone.open_app 4.83
7 system.dashboard 4.73
8 phone.mirror_open 4.62
9 file.read_metadata 4.47
10 file.move 4.44
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RANK_SUPPRESSED_BY_OTHER_CANDIDATE`

---

### Test ID: `ctx_003` (contextual)

**USER QUERY**:
`Where is it stored?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.location']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_004` (contextual)

**USER QUERY**:
`What is it about?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.summarize']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `ctx_005` (contextual)

**USER QUERY**:
`Send that one to my phone.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['phone.send_file']`

**ACTUAL ROUTE**:
`send_whatsapp_message (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 phone.send_text 10.12
2 phone.send_file 9.97
3 phone.send_notification 9.97
4 whatsapp.send 8.96
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`PHONE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_006` (contextual)

**USER QUERY**:
`Open the first result.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 browser.click 11.06
3 workflow.trim_clip 8.36
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_007` (contextual)

**USER QUERY**:
`Open the last one.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_008` (contextual)

**USER QUERY**:
`Show its folder.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`list_directory (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 9.78
2 file.create_folder 5.15
3 file.organize_downloads 4.95
4 file.delete 4.77
5 file.move 4.39
6 file.rename 4.39
7 app.get_location 3.98
8 workflow.launch_workspace 3.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `ctx_009` (contextual)

**USER QUERY**:
`Close it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.close']`

**ACTUAL ROUTE**:
`close_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.close_window 5.91
2 phone.mirror_close 5.78
3 app.close 5.70
4 windows.volume_mute 3.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_010` (contextual)

**USER QUERY**:
`Minimize it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.minimize']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.minimize_window 16.22
2 windows.show_desktop 5.72
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_011` (contextual)

**USER QUERY**:
`Maximize it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.maximize']`

**ACTUAL ROUTE**:
`maximize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.maximize_window 30.52
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_014` (contextual)

**USER QUERY**:
`Attach that PDF to an email.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['email.draft']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`GOOGLE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `ctx_015` (contextual)

**USER QUERY**:
`Compare the first one with the third one.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.compare']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `ctx_016` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_017` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_018` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_019` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_020` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_021` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_022` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_023` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_024` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_025` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_026` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_027` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_028` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_029` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_030` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_031` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_032` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_033` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_034` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_035` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_036` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_037` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_038` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_039` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_040` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_041` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_042` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_043` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_044` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_045` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_046` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_047` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_048` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_049` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_050` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_051` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_052` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_053` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_054` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_055` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_056` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_057` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_058` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_059` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_060` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_061` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_062` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_063` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_064` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_065` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_066` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_067` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_068` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_069` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_070` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_071` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_072` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_073` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_074` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_075` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_076` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_077` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_078` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_079` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_080` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_081` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_082` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_083` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_084` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_085` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_086` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_087` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_088` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_089` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_090` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_091` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_092` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_093` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_094` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_095` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_096` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_097` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_098` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_099` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_100` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_101` (contextual)

**USER QUERY**:
`Open item number 1 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_102` (contextual)

**USER QUERY**:
`Open item number 2 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_103` (contextual)

**USER QUERY**:
`Open item number 3 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_104` (contextual)

**USER QUERY**:
`Open item number 4 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `ctx_105` (contextual)

**USER QUERY**:
`Open item number 5 from the list.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 app.list_installed 8.12
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=contextual`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `corr_006` (corrections)

**USER QUERY**:
`Draft email to Sarah, actually make that Sarah Jenkins.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['email.draft']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=corrections`

**INTENT FAMILY**:
`GOOGLE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `corr_010` (corrections)

**USER QUERY**:
`Find yesterday's PDF. Actually, Monday's.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=corrections`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `corr_011` (corrections)

**USER QUERY**:
`Search Documents—actually search Downloads.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.organize_downloads 11.29
2 file.list_directory 10.99
3 browser.click 9.25
4 file.find_duplicates 7.97
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=corrections`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `corr_012` (corrections)

**USER QUERY**:
`Open the second file—sorry, the third.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 workflow.trim_clip 9.69
3 file.open 9.20
4 file.batch_rename 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`3`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=corrections`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `corr_013` (corrections)

**USER QUERY**:
`Pick the first result, wait, take the last one.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=corrections`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `corr_015` (corrections)

**USER QUERY**:
`Maximize this window... actually minimize it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.minimize']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.maximize_window 35.84
2 windows.minimize_window 35.55
3 windows.show_desktop 22.72
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=corrections`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `corr_016` (corrections)

**USER QUERY**:
`Show desktop, no wait, just close the window.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.close']`

**ACTUAL ROUTE**:
`close_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.show_desktop 29.52
2 windows.desktop_ui_snapshot 9.94
3 phone.mirror_close 9.82
4 file.list_directory 8.87
5 phone.mirror_open 8.43
6 windows.desktop_ui_click 7.91
7 file.delete 7.47
8 windows.close_window 5.29
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=corrections`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `corr_031` (corrections)

**USER QUERY**:
`Bring up Word... wait, PowerPoint please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=corrections`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `corr_034` (corrections)

**USER QUERY**:
`Bring up Paint... wait, Photoshop please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:paint`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=corrections`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `impl_001` (implicit)

**USER QUERY**:
`I need Calculator right now.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:calculator`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `impl_003` (implicit)

**USER QUERY**:
`Chrome on screen please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.check_installed 18.83
2 windows.screenshot 4.92
3 windows.brightness_set 4.86
4 app.close 4.83
5 app.get_location 4.83
6 app.install_software 4.83
7 app.open 4.83
8 phone.mirror_open 4.76
9 phone.home 4.70
10 windows.desktop_ui_snapshot 4.70
```

**EXPECTED CAPABILITY RANK**:
`7`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `impl_008` (implicit)

**USER QUERY**:
`Too loud in here.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_down']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `impl_009` (implicit)

**USER QUERY**:
`Can't hear anything from the speakers.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_up']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `impl_014` (implicit)

**USER QUERY**:
`How are my system resources doing?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.info']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `impl_016` (implicit)

**USER QUERY**:
`I need a photo of what is on screen.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.screenshot']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `impl_018` (implicit)

**USER QUERY**:
`Duplicates in my downloads?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.find_duplicates']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 file.organize_downloads 6.32
2 file.list_directory 5.72
3 file.find_duplicates 5.31
4 app.install_software 3.00
5 browser.click 3.00
6 file.copy 3.00
7 file.move 3.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`3`

**ENTITY RESOLUTION**:
`folder:downloads`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RANK_SUPPRESSED_BY_OTHER_CANDIDATE`

---

### Test ID: `impl_022` (implicit)

**USER QUERY**:
`Phone connectivity?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.mirror_open 4.92
2 phone.status 4.91
3 phone.home 4.85
4 phone.open_app 4.85
5 phone.send_file 4.85
6 phone.send_notification 4.85
7 phone.send_text 4.85
8 phone.mirror_close 4.83
9 phone.back 4.77
10 whatsapp.action 4.62
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`PHONE`

**ROOT CAUSE**:
`RANK_SUPPRESSED_BY_OTHER_CANDIDATE`

---

### Test ID: `impl_023` (implicit)

**USER QUERY**:
`Phone screen on my monitor.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['phone.screen_mirror']`

**ACTUAL ROUTE**:
`take_screenshot (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.screenshot 10.27
2 phone.mirror_open 9.69
3 phone.home 9.54
4 phone.mirror_close 9.43
5 windows.maximize_window 8.88
6 system.dashboard 7.26
7 system.devices 6.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`PHONE`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_027` (implicit)

**USER QUERY**:
`File Explorer window please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.desktop_ui_click 8.18
2 file.delete 7.32
3 file.open 7.32
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:explorer`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `impl_028` (implicit)

**USER QUERY**:
`I need to write something in Notepad.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `impl_029` (implicit)

**USER QUERY**:
`Need to do some math calculations.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `impl_030` (implicit)

**USER QUERY**:
`Need to browse the web.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`browser_open_url (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 browser.open_url 10.04
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_031` (implicit)

**USER QUERY**:
`Get rid of this window.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.close']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `impl_032` (implicit)

**USER QUERY**:
`Hide this window for now.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.minimize']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.minimize_window 24.65
2 windows.show_desktop 20.00
3 windows.close_window 5.38
4 windows.maximize_window 5.32
5 windows.desktop_ui_snapshot 5.17
6 phone.mirror_close 4.03
7 windows.desktop_ui_click 4.03
8 app.refresh_catalog 3.00
9 file.delete 3.00
10 file.open 3.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `impl_033` (implicit)

**USER QUERY**:
`Make this bigger to fill screen.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.maximize']`

**ACTUAL ROUTE**:
`brightness_set (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.brightness_set 10.21
2 windows.maximize_window 8.88
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_034` (implicit)

**USER QUERY**:
`Back to desktop.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.show_desktop']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 phone.back 6.17
2 windows.volume_unmute 6.14
3 windows.show_desktop 4.97
4 windows.desktop_ui_snapshot 4.76
5 file.create_folder 4.47
6 file.delete 4.47
7 file.move 4.47
8 file.list_directory 4.26
9 phone.mirror_open 3.88
10 system.dashboard 3.88
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_037` (implicit)

**USER QUERY**:
`Volume eighty please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 15.70
2 windows.volume_set 15.70
3 windows.volume_unmute 5.15
4 windows.volume_mute 4.97
5 system.devices 3.00
6 system.microphone_status 3.00
7 system.wake_greeting 3.00
8 windows.media_control 3.00
9 workflow.extract_audio 3.00
10 workflow.trim_clip 3.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_040` (implicit)

**USER QUERY**:
`Find all PDF files in Downloads.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 16.08
2 file.find 14.62
3 file.move 10.63
4 file.find_duplicates 10.44
5 file.organize_downloads 10.35
6 file.open 7.88
7 rag.document_qa 7.88
8 file.read_metadata 7.63
9 file.rename 7.63
10 phone.send_file 7.63
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`folder:downloads, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_041` (implicit)

**USER QUERY**:
`I need Spotify.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 5.70
2 app.check_installed 4.97
3 app.close 4.97
4 app.open 4.97
5 phone.open_app 4.97
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`4`

**ENTITY RESOLUTION**:
`app:spotify`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `impl_042` (implicit)

**USER QUERY**:
`Spotify on screen please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.check_installed 4.97
2 app.close 4.97
3 app.open 4.97
4 phone.open_app 4.97
5 windows.screenshot 4.92
6 windows.brightness_set 4.86
7 phone.mirror_open 4.76
8 phone.home 4.70
9 windows.desktop_ui_snapshot 4.70
10 phone.mirror_close 4.60
```

**EXPECTED CAPABILITY RANK**:
`3`

**ENTITY RESOLUTION**:
`app:spotify`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `impl_043` (implicit)

**USER QUERY**:
`I need Paint.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 5.70
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:paint`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_044` (implicit)

**USER QUERY**:
`Paint on screen please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.screenshot 4.92
2 windows.brightness_set 4.86
3 phone.mirror_open 4.76
4 phone.home 4.70
5 windows.desktop_ui_snapshot 4.70
6 phone.mirror_close 4.60
7 windows.brightness_get 4.60
8 windows.maximize_window 4.47
9 system.dashboard 4.26
10 system.devices 3.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:paint`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_045` (implicit)

**USER QUERY**:
`I need Terminal.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`clarify (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 terminal.powershell 10.31
2 whatsapp.summarize 5.70
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_046` (implicit)

**USER QUERY**:
`Terminal on screen please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`powershell_command (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 terminal.powershell 15.31
2 windows.screenshot 4.92
3 windows.brightness_set 4.86
4 phone.mirror_open 4.76
5 phone.home 4.70
6 windows.desktop_ui_snapshot 4.70
7 phone.mirror_close 4.60
8 windows.brightness_get 4.60
9 windows.maximize_window 4.47
10 system.dashboard 4.26
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_047` (implicit)

**USER QUERY**:
`I need Word.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`wake_word_status (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.wake_word_status 6.68
2 whatsapp.summarize 5.70
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `impl_048` (implicit)

**USER QUERY**:
`Word on screen please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`wake_word_status (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.wake_word_status 6.68
2 windows.screenshot 4.92
3 windows.brightness_set 4.86
4 phone.mirror_open 4.76
5 phone.home 4.70
6 windows.desktop_ui_snapshot 4.70
7 phone.mirror_close 4.60
8 windows.brightness_get 4.60
9 windows.maximize_window 4.47
10 system.dashboard 4.26
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `impl_049` (implicit)

**USER QUERY**:
`I need Excel.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 5.70
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_050` (implicit)

**USER QUERY**:
`Excel on screen please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.screenshot 4.92
2 windows.brightness_set 4.86
3 phone.mirror_open 4.76
4 phone.home 4.70
5 windows.desktop_ui_snapshot 4.70
6 phone.mirror_close 4.60
7 windows.brightness_get 4.60
8 windows.maximize_window 4.47
9 system.dashboard 4.26
10 system.devices 3.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_051` (implicit)

**USER QUERY**:
`I need Edge.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 5.70
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:edge`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_052` (implicit)

**USER QUERY**:
`Edge on screen please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.screenshot 4.92
2 windows.brightness_set 4.86
3 phone.mirror_open 4.76
4 phone.home 4.70
5 windows.desktop_ui_snapshot 4.70
6 phone.mirror_close 4.60
7 windows.brightness_get 4.60
8 windows.maximize_window 4.47
9 system.dashboard 4.26
10 system.devices 3.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:edge`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_053` (implicit)

**USER QUERY**:
`I need Powerpoint.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.summarize 5.70
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_054` (implicit)

**USER QUERY**:
`Powerpoint on screen please.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.screenshot 4.92
2 windows.brightness_set 4.86
3 phone.mirror_open 4.76
4 phone.home 4.70
5 windows.desktop_ui_snapshot 4.70
6 phone.mirror_close 4.60
7 windows.brightness_get 4.60
8 windows.maximize_window 4.47
9 system.dashboard 4.26
10 system.devices 3.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `impl_055` (implicit)

**USER QUERY**:
`Show me my Desktop folder.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.list']`

**ACTUAL ROUTE**:
`show_desktop (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.show_desktop 23.52
2 file.list_directory 14.04
3 file.create_folder 9.62
4 file.delete 9.24
5 file.move 8.86
6 phone.mirror_open 8.43
7 system.dashboard 8.43
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_060` (implicit)

**USER QUERY**:
`Volume level 69 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_061` (implicit)

**USER QUERY**:
`Volume level 70 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_062` (implicit)

**USER QUERY**:
`Volume level 71 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_063` (implicit)

**USER QUERY**:
`Volume level 72 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_064` (implicit)

**USER QUERY**:
`Volume level 73 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_065` (implicit)

**USER QUERY**:
`Volume level 74 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_066` (implicit)

**USER QUERY**:
`Volume level 75 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_067` (implicit)

**USER QUERY**:
`Volume level 76 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_068` (implicit)

**USER QUERY**:
`Volume level 77 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_069` (implicit)

**USER QUERY**:
`Volume level 78 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_070` (implicit)

**USER QUERY**:
`Volume level 79 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_072` (implicit)

**USER QUERY**:
`Volume level 81 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_073` (implicit)

**USER QUERY**:
`Volume level 82 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_074` (implicit)

**USER QUERY**:
`Volume level 83 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_075` (implicit)

**USER QUERY**:
`Volume level 84 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_076` (implicit)

**USER QUERY**:
`Volume level 85 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_077` (implicit)

**USER QUERY**:
`Volume level 86 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_078` (implicit)

**USER QUERY**:
`Volume level 87 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_079` (implicit)

**USER QUERY**:
`Volume level 88 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_080` (implicit)

**USER QUERY**:
`Volume level 89 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_081` (implicit)

**USER QUERY**:
`Volume level 90 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_082` (implicit)

**USER QUERY**:
`Volume level 91 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_083` (implicit)

**USER QUERY**:
`Volume level 92 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_084` (implicit)

**USER QUERY**:
`Volume level 93 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_085` (implicit)

**USER QUERY**:
`Volume level 94 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_086` (implicit)

**USER QUERY**:
`Volume level 95 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_087` (implicit)

**USER QUERY**:
`Volume level 96 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_088` (implicit)

**USER QUERY**:
`Volume level 97 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_089` (implicit)

**USER QUERY**:
`Volume level 98 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_090` (implicit)

**USER QUERY**:
`Volume level 99 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_091` (implicit)

**USER QUERY**:
`Volume level 10 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_092` (implicit)

**USER QUERY**:
`Volume level 11 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_093` (implicit)

**USER QUERY**:
`Volume level 12 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_094` (implicit)

**USER QUERY**:
`Volume level 13 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_095` (implicit)

**USER QUERY**:
`Volume level 14 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_096` (implicit)

**USER QUERY**:
`Volume level 15 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_097` (implicit)

**USER QUERY**:
`Volume level 16 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_098` (implicit)

**USER QUERY**:
`Volume level 17 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_099` (implicit)

**USER QUERY**:
`Volume level 18 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_100` (implicit)

**USER QUERY**:
`Volume level 19 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_102` (implicit)

**USER QUERY**:
`Volume level 21 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_103` (implicit)

**USER QUERY**:
`Volume level 22 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_104` (implicit)

**USER QUERY**:
`Volume level 23 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `impl_105` (implicit)

**USER QUERY**:
`Volume level 24 percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 21.13
2 windows.volume_set 21.06
3 windows.volume_unmute 9.33
4 system.microphone_status 6.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=implicit`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `long_001` (long_form)

**USER QUERY**:
`Hey Jarvis good morning I hope you are having a wonderful day listen I was thinking earlier that my computer has been running a little bit warm so could you please check my system diagnostics and tell me how much RAM is free right now?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.diagnostics', 'system.info']`

**ACTUAL ROUTE**:
`system_diagnostics (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.info 49.24
2 system.diagnostics 43.20
3 system.wake_greeting 30.78
4 windows.top_memory_processes 23.70
5 system.time 23.46
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=long_form`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `long_003` (long_form)

**USER QUERY**:
`Well I was working on that report late last night and I am pretty sure I downloaded the latest draft into my Downloads folder could you please search through my Downloads directory and find any PDF files that were saved there?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=long_form`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `long_005` (long_form)

**USER QUERY**:
`Listen carefully I do not want to delete or modify anything at all on disk but I do need to know if there are any duplicate files sitting in my Downloads folder just scan it and report back without moving anything.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.find_duplicates']`

**ACTUAL ROUTE**:
`copy_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.copy 13.83
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=long_form`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `neg_008` (negation)

**USER QUERY**:
`Don't close Chrome, just minimize it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.minimize']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.close 22.53
2 app.check_installed 18.83
3 windows.minimize_window 16.22
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=negation`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `neg_011` (negation)

**USER QUERY**:
`Find the PDF in Downloads but don't open it.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 14.83
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=negation`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `neg_015` (negation)

**USER QUERY**:
`Show my notes but do not edit them.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.search_notes']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 rag.memos_recent 7.34
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`KnowledgeResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=negation`

**INTENT FAMILY**:
`KNOWLEDGE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `neg_017` (negation)

**USER QUERY**:
`Don't mute the sound, just turn it down to 20.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`brightness_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_mute 34.96
2 windows.volume_set 29.94
3 windows.media_control 22.33
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=negation`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `neg_018` (negation)

**USER QUERY**:
`Don't maximize, just restore the window.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.restore']`

**ACTUAL ROUTE**:
`launch_workspace (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.maximize_window 30.84
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=negation`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_001` (noisy)

**USER QUERY**:
`ope notpad`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_002` (noisy)

**USER QUERY**:
`opn chrom`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_003` (noisy)

**USER QUERY**:
`opne calculatr`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_004` (noisy)

**USER QUERY**:
`volum 40`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_005` (noisy)

**USER QUERY**:
`valume 60`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_006` (noisy)

**USER QUERY**:
`tkae screenshoot`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.screenshot']`

**ACTUAL ROUTE**:
`take_screenshot (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 system.devices 5.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_007` (noisy)

**USER QUERY**:
`clsoe windwo`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.close']`

**ACTUAL ROUTE**:
`close_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_008` (noisy)

**USER QUERY**:
`minmize windw`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.minimize']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_009` (noisy)

**USER QUERY**:
`maxmize windw`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.maximize']`

**ACTUAL ROUTE**:
`maximize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_011` (noisy)

**USER QUERY**:
`systm infomation`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.info']`

**ACTUAL ROUTE**:
`system_info (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_012` (noisy)

**USER QUERY**:
`fnd pdf downlods`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`move_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_013` (noisy)

**USER QUERY**:
`organiz downlods`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`organize_downloads (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_014` (noisy)

**USER QUERY**:
`what tiime is it`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.time']`

**ACTUAL ROUTE**:
`get_time (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_015` (noisy)

**USER QUERY**:
`shwo desktp`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.show_desktop']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `noise_016` (noisy)

**USER QUERY**:
`mut volum`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_mute']`

**ACTUAL ROUTE**:
`volume_get (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_017` (noisy)

**USER QUERY**:
`unmut valume`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_unmute']`

**ACTUAL ROUTE**:
`volume_get (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_019` (noisy)

**USER QUERY**:
`wher is chrom installed`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.location']`

**ACTUAL ROUTE**:
`install_software (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.install_software 8.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`APP`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_020` (noisy)

**USER QUERY**:
`andrpid phon status`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['phone.status']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`PHONE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `noise_021` (noisy)

**USER QUERY**:
`opn calc`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_022` (noisy)

**USER QUERY**:
`launsh calc`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_023` (noisy)

**USER QUERY**:
`strt calc`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_025` (noisy)

**USER QUERY**:
`opn chrom`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_026` (noisy)

**USER QUERY**:
`launsh chrom`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `noise_027` (noisy)

**USER QUERY**:
`strt chrom`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `noise_029` (noisy)

**USER QUERY**:
`opn notepd`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`KnowledgeResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_030` (noisy)

**USER QUERY**:
`launsh notepd`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`KnowledgeResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `noise_031` (noisy)

**USER QUERY**:
`strt notepd`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`KnowledgeResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `noise_033` (noisy)

**USER QUERY**:
`opn spotfy`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_034` (noisy)

**USER QUERY**:
`launsh spotfy`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `noise_035` (noisy)

**USER QUERY**:
`strt spotfy`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `noise_037` (noisy)

**USER QUERY**:
`opn explorr`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_038` (noisy)

**USER QUERY**:
`launsh explorr`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `noise_039` (noisy)

**USER QUERY**:
`strt explorr`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `noise_041` (noisy)

**USER QUERY**:
`volum set to 50 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.brightness_set 10.82
2 windows.volume_set 10.82
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `noise_042` (noisy)

**USER QUERY**:
`volum set to 51 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_043` (noisy)

**USER QUERY**:
`volum set to 52 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_044` (noisy)

**USER QUERY**:
`volum set to 53 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_045` (noisy)

**USER QUERY**:
`volum set to 54 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_046` (noisy)

**USER QUERY**:
`volum set to 55 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_047` (noisy)

**USER QUERY**:
`volum set to 56 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_048` (noisy)

**USER QUERY**:
`volum set to 57 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_049` (noisy)

**USER QUERY**:
`volum set to 58 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_050` (noisy)

**USER QUERY**:
`volum set to 59 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_051` (noisy)

**USER QUERY**:
`volum set to 60 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_052` (noisy)

**USER QUERY**:
`volum set to 61 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_053` (noisy)

**USER QUERY**:
`volum set to 62 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_054` (noisy)

**USER QUERY**:
`volum set to 63 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_055` (noisy)

**USER QUERY**:
`volum set to 64 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_056` (noisy)

**USER QUERY**:
`volum set to 65 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_057` (noisy)

**USER QUERY**:
`volum set to 66 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_058` (noisy)

**USER QUERY**:
`volum set to 67 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_059` (noisy)

**USER QUERY**:
`volum set to 68 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_060` (noisy)

**USER QUERY**:
`volum set to 69 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_061` (noisy)

**USER QUERY**:
`volum set to 70 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_062` (noisy)

**USER QUERY**:
`volum set to 71 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_063` (noisy)

**USER QUERY**:
`volum set to 72 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_064` (noisy)

**USER QUERY**:
`volum set to 73 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_065` (noisy)

**USER QUERY**:
`volum set to 74 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_066` (noisy)

**USER QUERY**:
`volum set to 75 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_067` (noisy)

**USER QUERY**:
`volum set to 76 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_068` (noisy)

**USER QUERY**:
`volum set to 77 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_069` (noisy)

**USER QUERY**:
`volum set to 78 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_070` (noisy)

**USER QUERY**:
`volum set to 79 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_072` (noisy)

**USER QUERY**:
`volum set to 81 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_073` (noisy)

**USER QUERY**:
`volum set to 82 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_074` (noisy)

**USER QUERY**:
`volum set to 83 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_075` (noisy)

**USER QUERY**:
`volum set to 84 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_076` (noisy)

**USER QUERY**:
`volum set to 85 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_077` (noisy)

**USER QUERY**:
`volum set to 86 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_078` (noisy)

**USER QUERY**:
`volum set to 87 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_079` (noisy)

**USER QUERY**:
`volum set to 88 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_080` (noisy)

**USER QUERY**:
`volum set to 89 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_081` (noisy)

**USER QUERY**:
`volum set to 10 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_082` (noisy)

**USER QUERY**:
`volum set to 11 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_083` (noisy)

**USER QUERY**:
`volum set to 12 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_084` (noisy)

**USER QUERY**:
`volum set to 13 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_085` (noisy)

**USER QUERY**:
`volum set to 14 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_086` (noisy)

**USER QUERY**:
`volum set to 15 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_087` (noisy)

**USER QUERY**:
`volum set to 16 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_088` (noisy)

**USER QUERY**:
`volum set to 17 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_089` (noisy)

**USER QUERY**:
`volum set to 18 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_090` (noisy)

**USER QUERY**:
`volum set to 19 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_091` (noisy)

**USER QUERY**:
`volum set to 20 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.brightness_set 10.82
2 windows.volume_set 10.82
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `noise_092` (noisy)

**USER QUERY**:
`volum set to 21 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_093` (noisy)

**USER QUERY**:
`volum set to 22 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_094` (noisy)

**USER QUERY**:
`volum set to 23 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_095` (noisy)

**USER QUERY**:
`volum set to 24 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_096` (noisy)

**USER QUERY**:
`volum set to 25 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_097` (noisy)

**USER QUERY**:
`volum set to 26 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_098` (noisy)

**USER QUERY**:
`volum set to 27 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_099` (noisy)

**USER QUERY**:
`volum set to 28 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_100` (noisy)

**USER QUERY**:
`volum set to 29 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_101` (noisy)

**USER QUERY**:
`volum set to 30 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.brightness_set 10.60
2 windows.volume_set 10.60
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `noise_102` (noisy)

**USER QUERY**:
`volum set to 31 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_103` (noisy)

**USER QUERY**:
`volum set to 32 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_104` (noisy)

**USER QUERY**:
`volum set to 33 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `noise_105` (noisy)

**USER QUERY**:
`volum set to 34 percet`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=noisy`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_004` (paraphrase)

**USER QUERY**:
`Get VLC media player rolling.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`media_control (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.media_control 15.02
2 app.install_software 9.82
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:vlc`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_007` (paraphrase)

**USER QUERY**:
`Pull up File Explorer right now.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:explorer`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_014` (paraphrase)

**USER QUERY**:
`Could you bring Excel onto the desktop?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.show_desktop 7.97
2 phone.mirror_open 6.88
3 system.dashboard 6.88
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `para_015` (paraphrase)

**USER QUERY**:
`Initialize Powerpoint presentation software.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `para_017` (paraphrase)

**USER QUERY**:
`Fire up Microsoft Edge for browsing.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:edge`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `para_019` (paraphrase)

**USER QUERY**:
`Put Chrome in front of me.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.check_installed 18.83
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_020` (paraphrase)

**USER QUERY**:
`Start up terminal console.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.open']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 terminal.powershell 18.31
2 app.open 15.01
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_023` (paraphrase)

**USER QUERY**:
`Please exit Calculator program.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close']`

**ACTUAL ROUTE**:
`close_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 11.01
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:calculator`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_024` (paraphrase)

**USER QUERY**:
`Terminate VLC player.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.close']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:vlc`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`GENERAL`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_026` (paraphrase)

**USER QUERY**:
`Dismiss the open Notepad window.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.close']`

**ACTUAL ROUTE**:
`open_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.open 31.96
2 windows.close_window 24.70
3 windows.maximize_window 8.31
4 app.close 8.13
5 workflow.dictate_text 8.13
6 file.open 7.88
7 phone.mirror_close 7.03
8 windows.show_desktop 6.84
9 app.refresh_catalog 6.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:notepad`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_027` (paraphrase)

**USER QUERY**:
`Get rid of this active window.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.close']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.minimize_window 9.63
2 windows.close_window 9.57
3 windows.desktop_ui_snapshot 9.47
4 windows.maximize_window 9.03
5 browser.snapshot 8.98
6 phone.mirror_close 7.75
7 windows.desktop_ui_click 7.75
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_028` (paraphrase)

**USER QUERY**:
`Minimize this foreground application.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.minimize']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.minimize_window 30.50
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_029` (paraphrase)

**USER QUERY**:
`Drop this window down to taskbar.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.minimize']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.minimize_window 26.95
2 windows.show_desktop 20.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_030` (paraphrase)

**USER QUERY**:
`Expand this window to full monitor size.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.maximize']`

**ACTUAL ROUTE**:
`maximize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.maximize_window 34.31
2 windows.screenshot 9.54
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_031` (paraphrase)

**USER QUERY**:
`Make the current window full screen.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.maximize']`

**ACTUAL ROUTE**:
`maximize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.maximize_window 32.05
2 windows.brightness_set 10.21
3 windows.close_window 10.01
4 windows.desktop_ui_snapshot 9.87
5 windows.brightness_get 9.55
6 windows.screenshot 9.10
7 phone.mirror_close 8.63
8 windows.minimize_window 8.33
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_032` (paraphrase)

**USER QUERY**:
`Un-maximize the active window.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.restore']`

**ACTUAL ROUTE**:
`maximize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.maximize_window 34.55
2 windows.minimize_window 9.63
3 windows.close_window 9.57
4 windows.desktop_ui_snapshot 9.47
5 phone.mirror_close 7.75
6 windows.desktop_ui_click 7.75
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_033` (paraphrase)

**USER QUERY**:
`Hide all open windows and reveal my desktop.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.show_desktop']`

**ACTUAL ROUTE**:
`show_desktop (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.show_desktop 34.39
2 windows.minimize_window 22.31
3 app.open 18.13
4 windows.desktop_ui_snapshot 11.06
5 app.refresh_catalog 10.48
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_034` (paraphrase)

**USER QUERY**:
`Clear screen to see desktop icons.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.show_desktop']`

**ACTUAL ROUTE**:
`list_directory (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 9.57
2 windows.desktop_ui_snapshot 9.46
3 phone.mirror_open 8.64
4 system.dashboard 8.14
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_035` (paraphrase)

**USER QUERY**:
`Dial master sound level to thirty-five percent.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_get (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 24.42
2 windows.volume_set 14.89
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `para_037` (paraphrase)

**USER QUERY**:
`Turn down audio loudness a bit.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_down']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_unmute 10.08
2 windows.volume_set 9.30
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `para_038` (paraphrase)

**USER QUERY**:
`Boost the audio volume up.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_up']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `para_040` (paraphrase)

**USER QUERY**:
`Un-silence the computer speakers.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_unmute']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_mute 28.52
2 windows.media_control 20.00
3 windows.volume_get 6.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_042` (paraphrase)

**USER QUERY**:
`Restore audio sound playback.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_unmute']`

**ACTUAL ROUTE**:
`media_control (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.media_control 10.52
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_055` (paraphrase)

**USER QUERY**:
`Find all PDF documents inside my Downloads directory.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 21.77
2 file.find_duplicates 14.16
3 file.move 11.55
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:downloads, folder:documents, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_060` (paraphrase)

**USER QUERY**:
`Sort files in Downloads according to their extension.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.organize']`

**ACTUAL ROUTE**:
`list_directory (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 21.08
2 file.organize_downloads 15.38
3 file.move 6.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`folder:downloads`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `para_064` (paraphrase)

**USER QUERY**:
`Is Google Chrome installed anywhere on this machine?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.check_installed']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.install_software 32.19
2 app.check_installed 24.43
3 app.get_location 10.19
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`APP`

**ROOT CAUSE**:
`RANK_SUPPRESSED_BY_OTHER_CANDIDATE`

---

### Test ID: `para_066` (paraphrase)

**USER QUERY**:
`Give me the file system location of VLC player.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.location']`

**ACTUAL ROUTE**:
`get_app_location (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`app:vlc`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`APP`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_070` (paraphrase)

**USER QUERY**:
`Capture memo saying submit expenses before Friday.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.note']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`KnowledgeResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`RAG`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `para_071` (paraphrase)

**USER QUERY**:
`Look through my saved notes for machine learning.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.search_notes']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`KnowledgeResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`KNOWLEDGE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `para_078` (paraphrase)

**USER QUERY**:
`Check whether WhatsApp local bridge is connected.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.status']`

**ACTUAL ROUTE**:
`read_whatsapp_messages (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.read 17.97
2 whatsapp.action 14.11
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_079` (paraphrase)

**USER QUERY**:
`Inspect Google Workspace OAuth synchronization state.`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['google.status']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`GOOGLE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `para_088` (paraphrase)

**USER QUERY**:
`Please close the top window`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.close']`

**ACTUAL ROUTE**:
`close_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.close_window 25.29
2 phone.mirror_close 9.82
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_089` (paraphrase)

**USER QUERY**:
`Shut current window down`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.close']`

**ACTUAL ROUTE**:
`close_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.close_window 27.01
2 windows.minimize_window 8.33
3 windows.maximize_window 8.31
4 phone.mirror_close 7.03
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_090` (paraphrase)

**USER QUERY**:
`Send active app to taskbar`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.minimize']`

**ACTUAL ROUTE**:
`send_whatsapp_message (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.minimize_window 8.91
2 windows.desktop_ui_click 8.04
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_091` (paraphrase)

**USER QUERY**:
`Enlarge active window`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.maximize']`

**ACTUAL ROUTE**:
`maximize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.maximize_window 26.03
2 windows.minimize_window 9.63
3 windows.close_window 9.57
4 windows.desktop_ui_snapshot 9.47
5 phone.mirror_close 7.75
6 windows.desktop_ui_click 7.75
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_092` (paraphrase)

**USER QUERY**:
`Reveal desktop icons immediately`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.show_desktop']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.media_control 5.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `para_093` (paraphrase)

**USER QUERY**:
`Change sound level to 45`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_get (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 20.00
2 windows.volume_unmute 9.66
3 workflow.trim_clip 8.36
4 system.microphone_status 7.10
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_094` (paraphrase)

**USER QUERY**:
`Turn sound up to 75%`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_set']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_unmute 10.95
2 windows.volume_set 10.58
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `para_095` (paraphrase)

**USER QUERY**:
`Lower audio output`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_down']`

**ACTUAL ROUTE**:
`volume_set (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_mute 8.83
2 system.devices 8.78
3 windows.volume_unmute 8.72
4 windows.volume_get 8.50
5 windows.volume_set 7.94
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`5`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `para_096` (paraphrase)

**USER QUERY**:
`Increase master volume`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_up']`

**ACTUAL ROUTE**:
`volume_up (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.volume_get 20.11
2 windows.volume_set 20.11
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `para_102` (paraphrase)

**USER QUERY**:
`How much total memory is fitted in this computer?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.info']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 windows.top_memory_processes 16.29
2 system.info 10.72
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`KnowledgeResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`RANK_SUPPRESSED_BY_OTHER_CANDIDATE`

---

### Test ID: `para_104` (paraphrase)

**USER QUERY**:
`Rebuild application index cache`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.refresh']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`APP`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `para_105` (paraphrase)

**USER QUERY**:
`Locate PDF files inside Downloads`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 16.91
2 file.find 14.66
3 file.move 10.63
4 file.organize_downloads 10.35
5 file.find_duplicates 8.18
6 file.open 7.88
7 rag.document_qa 7.88
8 file.read_metadata 7.63
9 file.rename 7.63
10 phone.send_file 7.63
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`folder:downloads, ext:pdf`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `para_106` (paraphrase)

**USER QUERY**:
`Find word documents in Documents directory`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.search']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.find_duplicates 16.13
2 file.list_directory 12.49
3 file.batch_rename 10.86
4 app.get_location 9.29
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:documents`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_108` (paraphrase)

**USER QUERY**:
`Detect repeated files in Downloads`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['file.find_duplicates']`

**ACTUAL ROUTE**:
`list_directory (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.list_directory 21.08
2 file.organize_downloads 10.35
3 file.find_duplicates 8.18
4 file.copy 6.00
5 file.move 6.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`3`

**ENTITY RESOLUTION**:
`folder:downloads`

**RESOURCE TYPE**:
`FileResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`FILE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_110` (paraphrase)

**USER QUERY**:
`Find the location of Chrome on disk`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.location']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 app.check_installed 18.83
2 app.get_location 9.80
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`app:chrome`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`APP`

**ROOT CAUSE**:
`ALIAS_LABEL_MISMATCH`

---

### Test ID: `para_113` (paraphrase)

**USER QUERY**:
`Check if WhatsApp connector is live`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['whatsapp.status']`

**ACTUAL ROUTE**:
`read_whatsapp_messages (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 whatsapp.read 9.87
2 app.check_installed 9.50
3 terminal.powershell 8.47
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WHATSAPP`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_116` (paraphrase)

**USER QUERY**:
`Query saved notes for budget 2026`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.search_notes']`

**ACTUAL ROUTE**:
`copy_file (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 file.copy 10.08
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`KnowledgeResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`KNOWLEDGE`

**ROOT CAUSE**:
`LEXICAL_SEMANTIC_GAP`

---

### Test ID: `para_118` (paraphrase)

**USER QUERY**:
`Lock my Windows session`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.lock']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `para_120` (paraphrase)

**USER QUERY**:
`Show clipboard saved items`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.clipboard']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`TERMINAL`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `para_121` (paraphrase)

**USER QUERY**:
`Look up current network wifi connection`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.network']`

**ACTUAL ROUTE**:
`search_web (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_132` (paraphrase)

**USER QUERY**:
`Kill current active window`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.close']`

**ACTUAL ROUTE**:
`close_app (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.close_window 31.20
2 windows.minimize_window 12.63
3 windows.maximize_window 12.03
4 phone.mirror_close 10.74
5 windows.desktop_ui_snapshot 9.47
6 windows.desktop_ui_click 7.75
7 browser.navigate 7.29
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_133` (paraphrase)

**USER QUERY**:
`Drop foreground window`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.minimize']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.minimize_window 26.61
2 windows.show_desktop 20.00
3 windows.close_window 9.66
4 windows.maximize_window 9.60
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_134` (paraphrase)

**USER QUERY**:
`Blow up active window to maximum`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.maximize']`

**ACTUAL ROUTE**:
`minimize_window (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.minimize_window 9.63
2 windows.close_window 9.57
3 windows.desktop_ui_snapshot 9.47
4 windows.maximize_window 9.03
5 phone.mirror_close 7.75
6 windows.desktop_ui_click 7.75
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_136` (paraphrase)

**USER QUERY**:
`Check processor specifications`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.info']`

**ACTUAL ROUTE**:
`search_web (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 file.read_metadata 7.19
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`SYSTEM`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_139` (paraphrase)

**USER QUERY**:
`Is android handset reachable?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['phone.status']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`DeviceResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`PHONE`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `para_142` (paraphrase)

**USER QUERY**:
`Search my notes for password hints`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['knowledge.search_notes']`

**ACTUAL ROUTE**:
`find_file (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 rag.search_notes 10.15
2 rag.search_web 9.84
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`KNOWLEDGE`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_143` (paraphrase)

**USER QUERY**:
`Is VLC media player installed here?`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['app.check_installed']`

**ACTUAL ROUTE**:
`None (LANE_2)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 app.install_software 27.13
2 app.check_installed 24.73
3 app.get_location 24.50
4 windows.media_control 15.02
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`2`

**ENTITY RESOLUTION**:
`app:vlc`

**RESOURCE TYPE**:
`ApplicationResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`APP`

**ROOT CAUSE**:
`RANK_SUPPRESSED_BY_OTHER_CANDIDATE`

---

### Test ID: `para_146` (paraphrase)

**USER QUERY**:
`Make audio quieter by 10%`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_down']`

**ACTUAL ROUTE**:
`None (CLARIFY)`

**DID IT BYPASS RETRIEVER?**:
`NO`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`RETRIEVER_ZERO_RESULTS`

---

### Test ID: `para_147` (paraphrase)

**USER QUERY**:
`Make audio louder`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['system.volume_up']`

**ACTUAL ROUTE**:
`volume_up (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 [NONE] 0.00
2 [NONE] 0.00
3 [NONE] 0.00
4 [NONE] 0.00
5 [NONE] 0.00
6 [NONE] 0.00
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`None detected`

**RESOURCE TYPE**:
`GenericResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOWS`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

### Test ID: `para_148` (paraphrase)

**USER QUERY**:
`Minimize all windows to see desktop`

**EXPECTED CAPABILITY/CAPABILITIES**:
`['window.show_desktop']`

**ACTUAL ROUTE**:
`show_desktop (LANE_0)`

**DID IT BYPASS RETRIEVER?**:
`YES`

**TOP 10 RETRIEVED**:
```text
1 windows.show_desktop 37.97
2 windows.minimize_window 33.22
3 file.list_directory 9.57
4 file.delete 8.65
5 windows.desktop_ui_snapshot 7.76
6 windows.desktop_ui_click 6.88
7 [NONE] 0.00
8 [NONE] 0.00
9 [NONE] 0.00
10 [NONE] 0.00
```

**EXPECTED CAPABILITY RANK**:
`NOT_IN_TOP_10`

**ENTITY RESOLUTION**:
`folder:desktop`

**RESOURCE TYPE**:
`SystemResource`

**ACTIVE CONTEXT**:
`Session memory initialized; category=paraphrase`

**INTENT FAMILY**:
`WINDOW`

**ROOT CAUSE**:
`DETERMINISTIC_LANE0_BYPASS`

---

