"""Deterministic Verifier Mappings for Capabilities."""

from typing import Any, Dict

VERIFIER_STRATEGIES: Dict[str, str] = {
    "open_app": "process_running_probe",
    "close_app": "process_terminated_probe",
    "close_window": "active_window_changed_probe",
    "minimize_window": "window_state_minimized_probe",
    "maximize_window": "window_state_maximized_probe",
    "volume_set": "pycaw_volume_match_probe",
    "brightness_set": "brightness_match_probe",
    "brightness_get": "brightness_read_probe",
    "top_memory_processes": "process_list_probe",
    "take_screenshot": "png_file_valid_probe",
    "create_folder": "path_is_dir_probe",
    "copy_file": "destination_file_exists_probe",
    "move_file": "dest_exists_source_absent_probe",
    "delete_file": "source_absent_in_recycle_bin_probe",
    "rename_file": "new_name_exists_old_absent_probe",
    "install_software": "app_catalog_resolved_probe",
    "browser_navigate": "browser_url_match_probe",
    "browser_type": "browser_dom_value_probe",
    "browser_click": "browser_dom_mutation_probe",
    "android_open_app": "adb_focused_window_probe",
    "send_whatsapp_message": "whatsapp_transport_ack_probe",
    "powershell_command": "process_exit_code_zero_probe",
}

def get_verifier_for_tool(tool_name: str) -> str:
    return VERIFIER_STRATEGIES.get(tool_name, "default_exit_code_verifier")
