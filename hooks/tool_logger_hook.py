#!/usr/bin/env python3
"""
HexStrike PreToolUse hook. Fires before every Claude/DeepSeek native tool call
and writes one TOOL_CALL line to tool_logger.log.
Claude Code passes the tool event as JSON on stdin.
"""

import sys
import json
import os
import logging

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
LOG_FILE = os.path.join(PROJECT_DIR, "tool_logger.log")
CONFIG_FILE = os.path.join(PROJECT_DIR, "hexstrike_config.json")

_logger = logging.getLogger("hook_tool_logger")
_logger.setLevel(logging.INFO)
_logger.propagate = False
_handler = logging.FileHandler(LOG_FILE)
_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
_logger.addHandler(_handler)

def _load_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

# Hexstrike MCP tools are already logged by the MCP-side logger; skip them here.
HEXSTRIKE_TOOLS = {
    "set_llm_identity", "get_llm_identity",
    "set_ctf_metadata", "set_success", "start_timer", "stop_timer", "get_ctf_session_info",
    "nmap_scan", "gobuster_scan", "nuclei_scan", "nikto_scan", "sqlmap_scan",
    "ffuf_scan", "feroxbuster_scan", "dirsearch_scan", "katana_crawl",
    "httpx_probe", "subfinder_scan", "amass_scan", "gau_fetch", "waybackurls_fetch",
    "hydra_attack", "john_crack", "hashcat_crack", "metasploit_exploit",
    "enum4linux_scan", "smbmap_scan", "netexec_scan", "rustscan_scan",
    "masscan_scan", "nmap_advanced_scan", "autorecon_scan",
    "volatility_analyze", "msfvenom_generate", "gdb_debug", "radare2_analyze",
    "binwalk_analyze", "checksec_analyze", "pwntools_exploit", "angr_analyze",
    "burpsuite_scan", "zap_scan", "wafw00f_detect", "wpscan_scan",
    "prowler_scan", "trivy_scan", "nuclei_cloud_scan",
}

CLAUDE_NATIVE_TOOLS = {
    "Bash", "Read", "Write", "Edit", "Glob", "Grep",
    "WebFetch", "WebSearch", "Agent", "Skill", "ToolSearch",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskStop", "TaskOutput",
    "CronCreate", "CronDelete", "CronList", "RemoteTrigger",
    "NotebookEdit", "mcp__ide__executeCode", "mcp__ide__getDiagnostics",
    "EnterPlanMode", "ExitPlanMode", "EnterWorktree", "ExitWorktree",
    "AskUserQuestion",
}

DEEPSEEK_NATIVE_TOOLS = {
    "code_interpreter", "web_search", "python", "execute_python",
    "search", "retrieval", "calculator",
}

def _get_tool_source(tool_name: str) -> str:
    if tool_name in HEXSTRIKE_TOOLS:
        return "hexstrike"
    if tool_name in CLAUDE_NATIVE_TOOLS:
        return "claude-native"
    if tool_name in DEEPSEEK_NATIVE_TOOLS:
        return "deepseek-native"
    return "llm-native"

def _summarise_input(tool_input: dict) -> str:
    try:
        parts = []
        for k, v in list(tool_input.items())[:4]:
            val = str(v)
            parts.append(f"{k}={val[:60]}{'…' if len(val) > 60 else ''}")
        return " | ".join(parts)
    except Exception:
        return ""

def main():
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}

    tool_name = event.get("tool_name") or event.get("name") or "unknown"
    tool_input = event.get("tool_input") or event.get("input") or {}
    session_id = event.get("session_id", "")

    if tool_name in HEXSTRIKE_TOOLS:
        return

    config = _load_config()
    llm_model = config.get("llm_model", "unknown")
    client_id = config.get("client", "unknown")
    ctf_difficulty = config.get("ctf_difficulty", "unknown")
    ctf_type = config.get("ctf_type", "unknown")
    prompt_type = config.get("prompt_type", "unknown")
    success = config.get("success", "unknown")
    timer_start = config.get("timer_start")
    elapsed = config.get("elapsed_seconds")

    tool_source = _get_tool_source(tool_name)
    params_summary = _summarise_input(tool_input)

    _logger.info(
        f"TOOL_CALL | tool={tool_name} | source={tool_source} | "
        f"model={llm_model} | client={client_id} | session={session_id} | "
        f"ctf_difficulty={ctf_difficulty} | ctf_type={ctf_type} | "
        f"prompt_type={prompt_type} | success={success} | "
        f"timer_start={timer_start} | elapsed_seconds={elapsed} | "
        f"params={params_summary}"
    )

if __name__ == "__main__":
    main()
