# Stabilization and real acceptance

Status: **MORE_DEVELOPMENT_REQUIRED**. Generated WhatsApp auto-replies remain OFF during multilingual shadow. Tests expecting automatic sends cannot justify enabling them.

Baseline run executed both `tests` and `jarvis/tests`: 3,575 passed, 43 failed, 4 skipped, one collection error, 883.52 seconds. The failure inventory below is generated from the local JUnit artifact, with each inspected failure treated as development evidence.

Verified repairs include scoped negation, unread fallback/generation checks, OTP refusal and streamed-speech ownership. Status diagnostics previously exceeded the tool budget by loading optional libraries/probing vision models; these checks now report inventory without loading models. A follow-up run hit Windows WMI error 0x8007000e under low available memory; it is an environment failure, not a pass.

The Google test fixture previously wrote synthetic account metadata to owner configuration. Its file path is now isolated under pytest's temporary directory. A local private backup was retained and only exact known synthetic test records were considered for cleanup; owner records/tokens were not exported. No OAuth refresh was performed for acceptance.

The authoritative final automated result and individual baseline failure classification follow in the generated sections. Do not use this report to certify daily use until the remaining tests and owner checks pass.

## Baseline failure classification (all 43)

Each ID is a hash of the existing test identity. Parameter text and private payloads are omitted.

| ID | Test module/function | Classification and disposition |
|---|---|---|
| e628915eb0 | `tests.test_all_jarvis_actions::test_router_lane0_coverage` | STALE_EXPECTATION: typed text_op replaces older voice_edit route |
| 2a414aebf2 | `jarvis.tests.generalization.test_outcome_aggregation::test_stale_plan_prevention_on_meta_instruction` | REAL_ADMISSION_DEFECT: full prohibition confused with policy/excluded scope; repaired |
| e77c56fc54 | `jarvis.tests.test_away_message_and_install::test_rambled_meeting_request_turns_on_auto_reply_with_the_message` | STALE_EXPECTATION: away text preserves dictated wording without inventing a future promise |
| 4dbd7cb48c | `jarvis.tests.test_away_message_and_install::test_away_message_is_sent_once_per_person_without_the_model` | STALE_EXPECTATION: away text preserves dictated wording without inventing a future promise |
| 0cd51251d2 | `jarvis.tests.test_extras_generalization::test_extra_command_routes` | REAL_ISOLATION_DEFECT: shared runtime metadata affected default routing; registry ownership and WhatsApp domain guard repaired |
| cc64daabe4 | `jarvis.tests.test_extras_generalization::test_extra_command_routes` | REAL_ISOLATION_DEFECT: shared runtime metadata affected default routing; registry ownership and WhatsApp domain guard repaired |
| fcbdf900f8 | `jarvis.tests.test_extras_generalization::test_extra_command_routes` | REAL_ISOLATION_DEFECT: shared runtime metadata affected default routing; registry ownership and WhatsApp domain guard repaired |
| 04bb6cdae0 | `jarvis.tests.test_extras_generalization::test_extra_command_routes` | REAL_ISOLATION_DEFECT: shared runtime metadata affected default routing; registry ownership and WhatsApp domain guard repaired |
| 0079ddd4f0 | `jarvis.tests.test_extras_generalization::test_extra_command_routes` | REAL_ISOLATION_DEFECT: shared runtime metadata affected default routing; registry ownership and WhatsApp domain guard repaired |
| 5c0d5a5f96 | `jarvis.tests.test_extras_generalization::test_rules_refusals_and_approval_gates_end_to_end` | REAL_ADMISSION_DEFECT: full prohibition confused with policy/excluded scope; repaired |
| af8d890e76 | `jarvis.tests.test_phase1_introspection::test_end_to_end_no_model_no_web_no_unrelated_tool` | REAL_DEFECT: negation admission plus expensive status diagnostics; repaired, final regression required |
| 953692aa5a | `jarvis.tests.test_phase_suite_fixes::test_dictation_tool_stops_on_pause` | STALE_EXPECTATION: modern controller pause differs from legacy manager stop; owner pause behavior still needs acceptance |
| b59ecd73f3 | `jarvis.tests.test_phase_suite_fixes::test_google_tools_are_registered_actions` | STALE_EXPECTATION: registry contains expanded Google capabilities |
| bf20cfb911 | `jarvis.tests.test_scope_guard::test_payments_security_checks_and_lock_screens_are_refused` | REAL_ROUTING_DEFECT: OTP intent coverage or recognized Tanglish reinterpreted as typo; repaired |
| 85cd1b3513 | `jarvis.tests.test_scope_guard::test_pause_is_not_stop` | REAL_ROUTING_DEFECT: OTP intent coverage or recognized Tanglish reinterpreted as typo; repaired |
| 4ae7d93762 | `jarvis.tests.test_search::test_query_parser_temporal_hints` | REAL_METADATA_DEFECT: temporal activity qualifier lost; repaired |
| 4bd0bc0edc | `jarvis.tests.test_streaming_answers::test_pulse_speaks_streamed_sentences_once_and_skips_the_final_repeat` | REAL_SPEECH_DEFECT: final repeat or cancelled stream fallback; repaired, focused tests passed |
| 54510d8148 | `jarvis.tests.test_streaming_answers::test_barge_in_drops_the_rest_of_a_streamed_answer` | REAL_SPEECH_DEFECT: final repeat or cancelled stream fallback; repaired, focused tests passed |
| c6119c8d06 | `jarvis.tests.test_whatsapp_ai::test_planner_capability_gap_uses_the_whole_registry` | STALE_EXPECTATION: Google mail tools now registered |
| edad0329be | `jarvis.tests.test_whatsapp_bulk_reply::test_follow_up_reuses_the_earlier_message_and_ignores_constraints` | REAL_ADMISSION_DEFECT: full prohibition confused with policy/excluded scope; repaired |
| 9d444feb03 | `jarvis.tests.test_whatsapp_bulk_reply::test_plain_reply_never_lands_in_a_group` | REAL_REPORTING_DEFECT: unavailable grounded draft must wait for guidance, not claim SUCCESS; repaired |
| 1dd572f307 | `jarvis.tests.test_whatsapp_feed_and_style::test_greetings_get_the_owners_own_reply_instantly` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| a470748e5e | `jarvis.tests.test_whatsapp_personal_reply::test_auto_reply_sends_verifies_and_records_ledger` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| f8f9212045 | `jarvis.tests.test_whatsapp_personal_reply::test_stop_contact_and_emergency_stop` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 620a33fd0f | `jarvis.tests.test_whatsapp_personal_reply::test_stop_during_drafting_prevents_the_send` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 97aee7f2ad | `jarvis.tests.test_whatsapp_personal_reply::test_everyone_mode_uses_default_style_for_untrained_contacts_as_suggestions_only` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 075b5cfe90 | `jarvis.tests.test_whatsapp_personal_reply::test_duplicate_events_create_one_reply_even_across_restart` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 5f96dac35a | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_is_never_answered_and_real_body_is_answered_once` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 1afef5edc9 | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_is_never_answered_and_real_body_is_answered_once` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| f8cec76672 | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_is_never_answered_and_real_body_is_answered_once` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 4e365e26e4 | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_retry_uses_transport_fetch` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 7437cc3875 | `jarvis.tests.test_whatsapp_personal_reply::test_uncertain_send_is_never_resent` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| f6538dee00 | `jarvis.tests.test_whatsapp_personal_reply::test_disconnected_transport_is_a_clean_failure` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 0caa24fe07 | `jarvis.tests.test_whatsapp_personal_reply::test_copying_an_unrelated_past_reply_is_held` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 0ee6f2e398 | `jarvis.tests.test_whatsapp_personal_reply::test_owner_code_switching_decides_whether_tanglish_fits_an_english_turn` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 07906ef8ea | `jarvis.tests.test_whatsapp_personal_reply::test_autonomous_replies_are_not_training_data_but_owner_edits_are` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 39e534c04f | `jarvis.tests.test_whatsapp_personal_reply::test_coalescing_answers_a_burst_once` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 1359120e9f | `jarvis.tests.test_whatsapp_personal_reply::test_gateway_routes_direct_chats_to_the_agent_and_never_auto_replies_in_groups` | STALE_SAFETY_EXPECTATION: generated auto-replies intentionally OFF; no enablement to satisfy test |
| 5e5954c781 | `jarvis.tests.test_whatsapp_send_evidence::test_commandservice_contact_policy_and_confirmation` | SAFE_SEMANTIC_DIFFERENCE: explicit prohibition returns CANCELLED instead of SUCCESS; no send |
| 4957666e9b | `jarvis.tests.test_whatsapp_unread_state::test_without_a_full_chat_list_other_chats_use_the_inbox` | REAL_SYNC_DEFECT: partial fallback or generation completeness; repaired, focused tests passed |
| 28c29248e3 | `jarvis.tests.test_whatsapp_unread_state::test_stale_zero_badge_does_not_hide_newer_stored_message_during_partial_sync` | REAL_SYNC_DEFECT: partial fallback or generation completeness; repaired, focused tests passed |
| 8f35cb5f2a | `jarvis.tests.test_whatsapp_unread_state::test_ready_requires_snapshot_from_current_generation` | REAL_SYNC_DEFECT: partial fallback or generation completeness; repaired, focused tests passed |
| 409304036b | `jarvis.tests.test_whatsapp_unread_state::test_legacy_bridge_snapshot_cannot_claim_ready_after_connection` | REAL_SYNC_DEFECT: partial fallback or generation completeness; repaired, focused tests passed |

## Post-repair development run (before remote merge completed)

3,615 passed, 31 failed, 4 skipped; no collection errors. Duration 488.12 seconds. This run overlapped the remote merge and is not final combined-code evidence. All failures follow without private parameter payloads.

| ID | Test | Disposition |
|---|---|---|
| e628915eb0 | `tests.test_all_jarvis_actions::test_router_lane0_coverage` | STALE_ROUTE_NAME_EXPECTATION: existing typed action replaces legacy route name; semantic owner acceptance pending |
| eaf19dff0a | `jarvis.tests.test_agi_capabilities::test_capability_routes` | STALE_ROUTE_NAME_EXPECTATION: existing typed action replaces legacy route name; semantic owner acceptance pending |
| de6c00c380 | `jarvis.tests.test_ai_integration::test_offline_model_falls_back_to_web_answer` | REAL_DEFECT: web grounding check ran before offline fallback; order repaired for combined run |
| e77c56fc54 | `jarvis.tests.test_away_message_and_install::test_rambled_meeting_request_turns_on_auto_reply_with_the_message` | STALE_EXPECTATION: preserves dictated wording instead of adding an invented future promise |
| 4dbd7cb48c | `jarvis.tests.test_away_message_and_install::test_away_message_is_sent_once_per_person_without_the_model` | STALE_EXPECTATION: preserves dictated wording instead of adding an invented future promise |
| cf055c7728 | `jarvis.tests.test_computer_agent.TestPlaywrightBrowser::test_semantic_locator_immunity_to_coordinate_shift` | STALE_SAFETY_EXPECTATION: checkout control now pauses for owner interaction |
| 6708a0b030 | `jarvis.tests.test_computer_use::test_screen_click_scales_vision_coordinates_to_the_real_screen` | UNRESOLVED_ENVIRONMENT_OR_FIXTURE: real UI-point validation disagrees with synthetic screenshot/backend; no bypass added |
| 953692aa5a | `jarvis.tests.test_phase_suite_fixes::test_dictation_tool_stops_on_pause` | STALE_CONTROLLER_EXPECTATION: modern controller pause differs from legacy stop fixture; owner behavior pending |
| b59ecd73f3 | `jarvis.tests.test_phase_suite_fixes::test_google_tools_are_registered_actions` | STALE_EXPECTATION: expanded registry is larger than the historical three-tool exact set |
| c6119c8d06 | `jarvis.tests.test_whatsapp_ai::test_planner_capability_gap_uses_the_whole_registry` | STALE_CAPABILITY_EXPECTATION: email tools now registered |
| 9d444feb03 | `jarvis.tests.test_whatsapp_bulk_reply::test_plain_reply_never_lands_in_a_group` | UNRESOLVED: safe contextual-draft guidance/status or short response presentation; no synthetic send to satisfy assertion |
| 9008253c13 | `jarvis.tests.test_whatsapp_bulk_reply::test_nobody_waiting_is_reported_plainly` | UNRESOLVED: safe contextual-draft guidance/status or short response presentation; no synthetic send to satisfy assertion |
| 1dd572f307 | `jarvis.tests.test_whatsapp_feed_and_style::test_greetings_get_the_owners_own_reply_instantly` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| be53c1e72e | `jarvis.tests.test_whatsapp_intelligence_capabilities::test_capability_metadata_registers_after_late_tool_injection` | STALE_ISOLATION_EXPECTATION: runtime metadata no longer mutates global default catalog |
| a470748e5e | `jarvis.tests.test_whatsapp_personal_reply::test_auto_reply_sends_verifies_and_records_ledger` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| f8f9212045 | `jarvis.tests.test_whatsapp_personal_reply::test_stop_contact_and_emergency_stop` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 620a33fd0f | `jarvis.tests.test_whatsapp_personal_reply::test_stop_during_drafting_prevents_the_send` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 97aee7f2ad | `jarvis.tests.test_whatsapp_personal_reply::test_everyone_mode_uses_default_style_for_untrained_contacts_as_suggestions_only` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 075b5cfe90 | `jarvis.tests.test_whatsapp_personal_reply::test_duplicate_events_create_one_reply_even_across_restart` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 5f96dac35a | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_is_never_answered_and_real_body_is_answered_once` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 1afef5edc9 | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_is_never_answered_and_real_body_is_answered_once` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| f8cec76672 | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_is_never_answered_and_real_body_is_answered_once` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 4e365e26e4 | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_retry_uses_transport_fetch` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 7437cc3875 | `jarvis.tests.test_whatsapp_personal_reply::test_uncertain_send_is_never_resent` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| f6538dee00 | `jarvis.tests.test_whatsapp_personal_reply::test_disconnected_transport_is_a_clean_failure` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 0caa24fe07 | `jarvis.tests.test_whatsapp_personal_reply::test_copying_an_unrelated_past_reply_is_held` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 0ee6f2e398 | `jarvis.tests.test_whatsapp_personal_reply::test_owner_code_switching_decides_whether_tanglish_fits_an_english_turn` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 07906ef8ea | `jarvis.tests.test_whatsapp_personal_reply::test_autonomous_replies_are_not_training_data_but_owner_edits_are` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 39e534c04f | `jarvis.tests.test_whatsapp_personal_reply::test_coalescing_answers_a_burst_once` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 1359120e9f | `jarvis.tests.test_whatsapp_personal_reply::test_gateway_routes_direct_chats_to_the_agent_and_never_auto_replies_in_groups` | STALE_SAFETY_EXPECTATION: generated autonomous replies intentionally OFF; no enablement to satisfy assertions |
| 5e5954c781 | `jarvis.tests.test_whatsapp_send_evidence::test_commandservice_contact_policy_and_confirmation` | SAFE_SEMANTIC_DIFFERENCE: explicit prohibition returns CANCELLED; nothing sent |

## Combined-code automated result

After merging remote `58ecaa3`, the broad suite completed with **3,682 passed, 31 failed, 5 skipped**, no collection errors, in **312.85 seconds**. This includes 13/13 real-Chromium workflow fixtures and the optional-brain permission gate tests. The optional Claude SDK integration suite is skipped because that package is absent; it is not cloud acceptance. Bridge tests passed **24/24** again. All 868 tracked Python sources parsed.

After this run, inspection repaired loss of tool diagnostic data on failed verification. This also allows the offline web fallback to run and exposes NEEDS_GUIDANCE as WAITING_FOR_USER. Empty-recipient results preserve their useful group count without claiming a send. A focused final run covering these paths, consolidation/privacy, optional permissions, browser workflows and bookkeeping completed with **57 passed, 1 failed** in 47.95 seconds. The remaining assertion expects a generated whereabouts message to reach send confirmation; the implementation requests owner guidance instead. No fabricated whereabouts or send was allowed. The offline-fallback and empty-recipient regressions passed. This focused run does not replace a new full-suite run, and no all-green release claim is made.

Broad-run failure identities (parameters omitted) follow. Classification from the preceding table remains applicable; the offline-fallback and empty-recipient defects were repaired afterward, while contextual reply now safely waits for guidance.

| ID | Test |
|---|---|
| e628915eb0 | `tests.test_all_jarvis_actions::test_router_lane0_coverage` |
| eaf19dff0a | `jarvis.tests.test_agi_capabilities::test_capability_routes` |
| de6c00c380 | `jarvis.tests.test_ai_integration::test_offline_model_falls_back_to_web_answer` |
| e77c56fc54 | `jarvis.tests.test_away_message_and_install::test_rambled_meeting_request_turns_on_auto_reply_with_the_message` |
| 4dbd7cb48c | `jarvis.tests.test_away_message_and_install::test_away_message_is_sent_once_per_person_without_the_model` |
| cf055c7728 | `jarvis.tests.test_computer_agent.TestPlaywrightBrowser::test_semantic_locator_immunity_to_coordinate_shift` |
| 6708a0b030 | `jarvis.tests.test_computer_use::test_screen_click_scales_vision_coordinates_to_the_real_screen` |
| 953692aa5a | `jarvis.tests.test_phase_suite_fixes::test_dictation_tool_stops_on_pause` |
| b59ecd73f3 | `jarvis.tests.test_phase_suite_fixes::test_google_tools_are_registered_actions` |
| c6119c8d06 | `jarvis.tests.test_whatsapp_ai::test_planner_capability_gap_uses_the_whole_registry` |
| 9d444feb03 | `jarvis.tests.test_whatsapp_bulk_reply::test_plain_reply_never_lands_in_a_group` |
| 9008253c13 | `jarvis.tests.test_whatsapp_bulk_reply::test_nobody_waiting_is_reported_plainly` |
| 1dd572f307 | `jarvis.tests.test_whatsapp_feed_and_style::test_greetings_get_the_owners_own_reply_instantly` |
| be53c1e72e | `jarvis.tests.test_whatsapp_intelligence_capabilities::test_capability_metadata_registers_after_late_tool_injection` |
| a470748e5e | `jarvis.tests.test_whatsapp_personal_reply::test_auto_reply_sends_verifies_and_records_ledger` |
| f8f9212045 | `jarvis.tests.test_whatsapp_personal_reply::test_stop_contact_and_emergency_stop` |
| 620a33fd0f | `jarvis.tests.test_whatsapp_personal_reply::test_stop_during_drafting_prevents_the_send` |
| 97aee7f2ad | `jarvis.tests.test_whatsapp_personal_reply::test_everyone_mode_uses_default_style_for_untrained_contacts_as_suggestions_only` |
| 075b5cfe90 | `jarvis.tests.test_whatsapp_personal_reply::test_duplicate_events_create_one_reply_even_across_restart` |
| 5f96dac35a | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_is_never_answered_and_real_body_is_answered_once` |
| 1afef5edc9 | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_is_never_answered_and_real_body_is_answered_once` |
| f8cec76672 | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_is_never_answered_and_real_body_is_answered_once` |
| 4e365e26e4 | `jarvis.tests.test_whatsapp_personal_reply::test_pending_decryption_retry_uses_transport_fetch` |
| 7437cc3875 | `jarvis.tests.test_whatsapp_personal_reply::test_uncertain_send_is_never_resent` |
| f6538dee00 | `jarvis.tests.test_whatsapp_personal_reply::test_disconnected_transport_is_a_clean_failure` |
| 0caa24fe07 | `jarvis.tests.test_whatsapp_personal_reply::test_copying_an_unrelated_past_reply_is_held` |
| 0ee6f2e398 | `jarvis.tests.test_whatsapp_personal_reply::test_owner_code_switching_decides_whether_tanglish_fits_an_english_turn` |
| 07906ef8ea | `jarvis.tests.test_whatsapp_personal_reply::test_autonomous_replies_are_not_training_data_but_owner_edits_are` |
| 39e534c04f | `jarvis.tests.test_whatsapp_personal_reply::test_coalescing_answers_a_burst_once` |
| 1359120e9f | `jarvis.tests.test_whatsapp_personal_reply::test_gateway_routes_direct_chats_to_the_agent_and_never_auto_replies_in_groups` |
| 5e5954c781 | `jarvis.tests.test_whatsapp_send_evidence::test_commandservice_contact_policy_and_confirmation` |
