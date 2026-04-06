#!/usr/bin/env python3

import sys
import json
import os
import logging

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
LOG_FILE = os.path.join(PROJECT_DIR, "tool_logger.log")
CONFIG_FILE = os.path.join(PROJECT_DIR, "hexstrike_config.json")

# The MCP server key as shown by `claude mcp list`.
# Hook receives hexstrike MCP tool calls as "mcp__hexstrike-ai__<tool_name>".
HEXSTRIKE_MCP_PREFIX = "mcp__hexstrike-ai__"

_logger = logging.getLogger("hook_tool_logger")
_logger.setLevel(logging.INFO)
_logger.propagate = False
_handler = logging.FileHandler(LOG_FILE)
_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
_logger.addHandler(_handler)

# Claude Code built-in tools
CLAUDE_NATIVE_TOOLS = {
    "Bash", "Read", "Write", "Edit", "MultiEdit", "Glob", "Grep",
    "WebFetch", "WebSearch",
    "Agent", "Skill", "ToolSearch", "SendMessage",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskStop", "TaskOutput",
    "CronCreate", "CronDelete", "CronList", "RemoteTrigger",
    "NotebookEdit", "NotebookRead",
    "EnterPlanMode", "ExitPlanMode",
    "EnterWorktree", "ExitWorktree",
    "AskUserQuestion",
    "mcp__ide__executeCode", "mcp__ide__getDiagnostics",
}


def _load_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _is_session_active(config: dict) -> bool:
    """Return True only between start_timer() and stop_timer() calls.

    start_timer sets timer_start and resets elapsed_seconds to None.
    stop_timer sets elapsed_seconds to a float.
    So an active session has timer_start set and elapsed_seconds absent/null.
    """
    return bool(config.get("timer_start")) and config.get("elapsed_seconds") is None


def _get_tool_source(tool_name: str) -> str:
    if tool_name in CLAUDE_NATIVE_TOOLS:
        return "claude"
    if tool_name.startswith("mcp__ide__"):
        return "ide"
    if tool_name.startswith("mcp__"):
        parts = tool_name.split("__", 2)
        return f"mcp-{parts[1]}" if len(parts) > 1 else "mcp"
    return "llm-native"


def _summarise_input(tool_input: dict) -> str:
    try:
        parts = []
        for k, v in list(tool_input.items())[:3]:
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

    # Hexstrike MCP tools are logged by the MCP-side logger in hexstrike_mcp.py.
    # Detect them by prefix so the list stays current as new tools are added to the server.
    if tool_name.startswith(HEXSTRIKE_MCP_PREFIX):
        return

    config = _load_config()

    # Only log within an active CTF session (after start_timer, before stop_timer).
    # This eliminates noise from the setup phase and any post-session activity.
    if not _is_session_active(config):
        return

    tool_source = _get_tool_source(tool_name)
    params_summary = _summarise_input(tool_input)
    params_str = f" | {params_summary}" if params_summary else ""

    _logger.info(f"TOOL_CALL | [{tool_source}] {tool_name}{params_str}")


if __name__ == "__main__":
    main()