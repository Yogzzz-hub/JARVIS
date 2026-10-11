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
