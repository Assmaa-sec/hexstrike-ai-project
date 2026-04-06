#!/usr/bin/env python3
"""
HexStrike LLM API Proxy
=======================
Sits between any OpenAI-compatible client (roo-code, 5ire, trae, cursor, etc.)
and the real LLM API (DeepSeek, OpenAI, etc.).

Intercepts tool_calls from LLM responses and logs them to tool_logger.log
in the same session-structured format as the MCP-side logger and hook.

Usage
-----
  python3 hooks/llm_proxy.py                                # DeepSeek, port 8889
  python3 hooks/llm_proxy.py --backend https://api.deepseek.com --port 8889
  python3 hooks/llm_proxy.py --backend https://api.openai.com --port 8890

Then in roo-code (or any client):
  Base URL : http://127.0.0.1:8889/v1
  API Key  : <your real key — passed through unchanged>

The proxy is fully transparent: responses are forwarded byte-for-byte.
Only tool_calls are observed and written to the log.
"""

import argparse
import json
import logging
import os
import sys

import requests
from flask import Flask, request, Response, stream_with_context

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(PROJECT_DIR, "tool_logger.log")
CONFIG_FILE = os.path.join(PROJECT_DIR, "hexstrike_config.json")

# Canonical hexstrike MCP tool names (exact function names registered with @mcp.tool()).
# Used as the reference set for cross-comparison.
HEXSTRIKE_TOOLS = frozenset({
    "advanced_payload_generation", "ai_generate_attack_suite", "ai_generate_payload",
    "ai_reconnaissance_workflow", "ai_test_payload", "ai_vulnerability_assessment",
    "amass_scan", "analyze_target_intelligence", "anew_data_processing",
    "angr_symbolic_execution", "api_fuzzer", "api_schema_analyzer",
    "arjun_parameter_discovery", "arjun_scan", "arp_scan_discovery",
    "autorecon_comprehensive", "autorecon_scan",
    "binwalk_analyze", "browser_agent_inspect",
    "bugbounty_authentication_bypass_testing", "bugbounty_business_logic_testing",
    "bugbounty_comprehensive_assessment", "bugbounty_file_upload_testing",
    "bugbounty_osint_gathering", "bugbounty_reconnaissance_workflow",
    "bugbounty_vulnerability_hunting",
    "burpsuite_alternative_scan", "burpsuite_scan",
    "checkov_iac_scan", "checksec_analyze", "clair_vulnerability_scan",
    "clear_cache", "cloudmapper_analysis", "comprehensive_api_audit",
    "correlate_threat_intelligence", "create_attack_chain_ai",
    "create_file", "create_scan_summary", "create_vulnerability_report",
    "dalfox_xss_scan", "delete_file", "detect_technologies_ai",
    "dirb_scan", "dirsearch_scan", "discover_attack_chains",
    "display_system_metrics", "dnsenum_scan", "docker_bench_security_scan",
    "dotdotpwn_scan", "enum4linux_ng_advanced", "enum4linux_scan",
    "error_handling_statistics", "execute_command", "execute_python_script",
    "exiftool_extract", "falco_runtime_monitoring", "feroxbuster_scan",
    "ffuf_scan", "fierce_scan", "foremost_carving", "format_tool_output_visual",
    "gau_discovery", "gdb_analyze", "gdb_peda_debug",
    "generate_exploit_from_cve", "generate_payload",
    "get_cache_stats", "get_ctf_session_info", "get_live_dashboard",
    "get_llm_identity", "get_process_dashboard", "get_process_status",
    "get_telemetry", "ghidra_analysis", "gobuster_scan", "graphql_scanner",
    "hakrawler_crawl", "hashcat_crack", "hashpump_attack",
    "http_framework_test", "http_intruder", "http_repeater",
    "http_set_rules", "http_set_scope", "httpx_probe", "hydra_attack",
    "install_python_package", "intelligent_smart_scan",
    "jaeles_vulnerability_scan", "john_crack", "jwt_analyzer",
    "katana_crawl", "kube_bench_cis", "kube_hunter_scan",
    "libc_database_lookup", "list_active_processes", "list_files",
    "masscan_high_speed", "metasploit_run", "modify_file",
    "monitor_cve_feeds", "msfvenom_generate",
    "nbtscan_netbios", "netexec_scan", "nikto_scan",
    "nmap_advanced_scan", "nmap_scan", "nuclei_scan",
    "objdump_analyze", "one_gadget_search", "optimize_tool_parameters_ai",
    "pacu_exploitation", "paramspider_discovery", "paramspider_mining",
    "pause_process", "prowler_scan", "pwninit_setup", "pwntools_exploit",
    "qsreplace_parameter_replacement", "radare2_analyze",
    "research_zero_day_opportunities", "responder_credential_harvest",
    "resume_process", "ropgadget_search", "ropper_gadget_search",
    "rpcclient_enumeration", "rustscan_fast_scan",
    "scout_suite_assessment", "select_optimal_tools_ai", "server_health",
    "set_ctf_metadata", "set_llm_identity", "set_success",
    "smbmap_scan", "sqlmap_scan", "start_timer", "steghide_analysis",
    "stop_timer", "strings_extract", "subfinder_scan",
    "terminate_process", "terrascan_iac_scan", "test_error_recovery",
    "threat_hunting_assistant", "trivy_scan", "uro_url_filtering",
    "volatility3_analyze", "volatility_analyze",
    "vulnerability_intelligence_dashboard",
    "wafw00f_scan", "waybackurls_discovery", "wfuzz_scan", "wpscan_analyze",
    "x8_parameter_discovery", "xsser_scan", "xxd_hexdump", "zap_scan",
})

# Aliases → canonical hexstrike name.
# LLMs calling via non-MCP paths often use short tool names (nmap, gobuster, etc.)
# or slight variations. Any alias hit is logged under the canonical name.
_ALIASES: dict[str, str] = {
    # nmap
    "nmap":                     "nmap_scan",
    "nmap_advanced":            "nmap_advanced_scan",
    # gobuster
    "gobuster":                 "gobuster_scan",
    "gobuster_dir":             "gobuster_scan",
    # nuclei
    "nuclei":                   "nuclei_scan",
    # nikto
    "nikto":                    "nikto_scan",
    # sqlmap
    "sqlmap":                   "sqlmap_scan",
    # ffuf
    "ffuf":                     "ffuf_scan",
    # feroxbuster
    "feroxbuster":              "feroxbuster_scan",
    # dirsearch
    "dirsearch":                "dirsearch_scan",
    # dirb
    "dirb":                     "dirb_scan",
    # wfuzz
    "wfuzz":                    "wfuzz_scan",
    # amass
    "amass":                    "amass_scan",
    # subfinder
    "subfinder":                "subfinder_scan",
    # httpx
    "httpx":                    "httpx_probe",
    # katana
    "katana":                   "katana_crawl",
    # gau
    "gau":                      "gau_discovery",
    "getallurls":               "gau_discovery",
    # waybackurls
    "waybackurls":              "waybackurls_discovery",
    "wayback":                  "waybackurls_discovery",
    # dnsenum
    "dnsenum":                  "dnsenum_scan",
    # fierce
    "fierce":                   "fierce_scan",
    # hakrawler
    "hakrawler":                "hakrawler_crawl",
    # arjun
    "arjun":                    "arjun_scan",
    # paramspider
    "paramspider":              "paramspider_discovery",
    # dalfox
    "dalfox":                   "dalfox_xss_scan",
    "dalfox_scan":              "dalfox_xss_scan",
    # xsser
    "xsser":                    "xsser_scan",
    # dotdotpwn
    "dotdotpwn":                "dotdotpwn_scan",
    # wpscan
    "wpscan":                   "wpscan_analyze",
    "wpscan_scan":              "wpscan_analyze",
    # burpsuite / burp
    "burpsuite":                "burpsuite_scan",
    "burp":                     "burpsuite_scan",
    "burp_scan":                "burpsuite_scan",
    "burpsuite_alt":            "burpsuite_alternative_scan",
    # zap / owasp-zap
    "zap":                      "zap_scan",
    "owasp_zap":                "zap_scan",
    # wafw00f
    "wafw00f":                  "wafw00f_scan",
    "wafw":                     "wafw00f_scan",
    "waf_detect":               "wafw00f_scan",
    # masscan
    "masscan":                  "masscan_high_speed",
    "masscan_scan":             "masscan_high_speed",
    # rustscan
    "rustscan":                 "rustscan_fast_scan",
    "rustscan_scan":            "rustscan_fast_scan",
    # autorecon
    "autorecon":                "autorecon_comprehensive",
    # enum4linux
    "enum4linux":               "enum4linux_scan",
    "enum4linux_ng":            "enum4linux_ng_advanced",
    "enum4linux_advanced":      "enum4linux_ng_advanced",
    # netexec / crackmapexec
    "netexec":                  "netexec_scan",
    "crackmapexec":             "netexec_scan",
    "cme":                      "netexec_scan",
    # smbmap
    "smbmap":                   "smbmap_scan",
    # rpcclient
    "rpcclient":                "rpcclient_enumeration",
    "rpc_enum":                 "rpcclient_enumeration",
    # nbtscan
    "nbtscan":                  "nbtscan_netbios",
    "netbios_scan":             "nbtscan_netbios",
    # arp-scan
    "arp_scan":                 "arp_scan_discovery",
    "arp-scan":                 "arp_scan_discovery",
    # responder
    "responder":                "responder_credential_harvest",
    # hydra
    "hydra":                    "hydra_attack",
    "hydra_brute":              "hydra_attack",
    # john
    "john":                     "john_crack",
    "john_the_ripper":          "john_crack",
    # hashcat
    "hashcat":                  "hashcat_crack",
    # hashpump
    "hashpump":                 "hashpump_attack",
    # metasploit
    "metasploit":               "metasploit_run",
    "msf":                      "metasploit_run",
    "msfconsole":               "metasploit_run",
    # msfvenom
    "msfvenom":                 "msfvenom_generate",
    # volatility
    "volatility":               "volatility_analyze",
    "volatility3":              "volatility3_analyze",
    # binwalk
    "binwalk":                  "binwalk_analyze",
    # checksec
    "checksec":                 "checksec_analyze",
    # gdb
    "gdb":                      "gdb_analyze",
    "gdb_peda":                 "gdb_peda_debug",
    "peda":                     "gdb_peda_debug",
    # radare2
    "radare2":                  "radare2_analyze",
    "r2":                       "radare2_analyze",
    "radare":                   "radare2_analyze",
    # ghidra
    "ghidra":                   "ghidra_analysis",
    # angr
    "angr":                     "angr_symbolic_execution",
    # pwntools
    "pwntools":                 "pwntools_exploit",
    "pwn":                      "pwntools_exploit",
    # ROPgadget
    "ropgadget":                "ropgadget_search",
    "ROPgadget":                "ropgadget_search",
    "rop_gadget":               "ropgadget_search",
    # ropper
    "ropper":                   "ropper_gadget_search",
    # one_gadget
    "one_gadget":               "one_gadget_search",
    # objdump
    "objdump":                  "objdump_analyze",
    # strings
    "strings":                  "strings_extract",
    # xxd / hexdump
    "xxd":                      "xxd_hexdump",
    "hexdump":                  "xxd_hexdump",
    # exiftool
    "exiftool":                 "exiftool_extract",
    # steghide
    "steghide":                 "steghide_analysis",
    # foremost
    "foremost":                 "foremost_carving",
    # anew
    "anew":                     "anew_data_processing",
    # uro
    "uro":                      "uro_url_filtering",
    # qsreplace
    "qsreplace":                "qsreplace_parameter_replacement",
    # jaeles
    "jaeles":                   "jaeles_vulnerability_scan",
    # graphql
    "graphql":                  "graphql_scanner",
    "graphql_scan":             "graphql_scanner",
    # jwt
    "jwt":                      "jwt_analyzer",
    "jwt_analyze":              "jwt_analyzer",
    # trivy
    "trivy":                    "trivy_scan",
    # prowler
    "prowler":                  "prowler_scan",
    # scout suite
    "scout_suite":              "scout_suite_assessment",
    "scoutsuite":               "scout_suite_assessment",
    # cloudmapper
    "cloudmapper":              "cloudmapper_analysis",
    # pacu
    "pacu":                     "pacu_exploitation",
    # kube-hunter
    "kube_hunter":              "kube_hunter_scan",
    "kubehunter":               "kube_hunter_scan",
    # kube-bench
    "kube_bench":               "kube_bench_cis",
    "kubebench":                "kube_bench_cis",
    # docker bench
    "docker_bench":             "docker_bench_security_scan",
    "docker_bench_security":    "docker_bench_security_scan",
    # clair
    "clair":                    "clair_vulnerability_scan",
    # falco
    "falco":                    "falco_runtime_monitoring",
    # checkov
    "checkov":                  "checkov_iac_scan",
    # terrascan
    "terrascan":                "terrascan_iac_scan",
    # x8
    "x8":                       "x8_parameter_discovery",
    # api_fuzzer
    "api_fuzz":                 "api_fuzzer",
    # pwninit
    "pwninit":                  "pwninit_setup",
    # libc
    "libc_db":                  "libc_database_lookup",
    "libc_lookup":              "libc_database_lookup",
    # execute_command variants
    "run_command":              "execute_command",
    "exec_command":             "execute_command",
    "shell":                    "execute_command",
    "bash":                     "execute_command",
    "terminal":                 "execute_command",
    # execute_python variants
    "python":                   "execute_python_script",
    "run_python":               "execute_python_script",
    "python_script":            "execute_python_script",
}

# Combined lookup: canonical names + all aliases. Used for filter + name resolution.
_ALL_KNOWN = HEXSTRIKE_TOOLS | frozenset(_ALIASES.keys())


def _resolve(tool_name: str) -> str | None:
    """Return the canonical hexstrike name for a tool call, or None if not hexstrike."""
    if tool_name in HEXSTRIKE_TOOLS:
        return tool_name
    return _ALIASES.get(tool_name) or _ALIASES.get(tool_name.lower())

_logger = logging.getLogger("llm_proxy")
_logger.setLevel(logging.INFO)
_logger.propagate = False
_fh = logging.FileHandler(LOG_FILE)
_fh.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
_logger.addHandler(_fh)

# Also print proxy activity to stdout so the terminal shows it's running
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(logging.Formatter("%(asctime)s [llm-proxy] %(message)s"))
_sh.setLevel(logging.INFO)
_logger.addHandler(_sh)

app = Flask(__name__)
BACKEND_URL = "https://api.deepseek.com"


# ---------------------------------------------------------------------------
# Config / session helpers
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _is_session_active(config: dict) -> bool:
    """True only between start_timer() and stop_timer()."""
    return bool(config.get("timer_start")) and config.get("elapsed_seconds") is None


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _log_tool_call(tool_name: str, tool_args: dict, source: str) -> None:
    # Resolve to canonical hexstrike name (handles aliases like nmap → nmap_scan).
    # Drop calls that don't correspond to any hexstrike tool.
    canonical = _resolve(tool_name)
    if canonical is None:
        return
    parts = []
    for k, v in list(tool_args.items())[:3]:
        val = str(v)
        parts.append(f"{k}={val[:60]}{'…' if len(val) > 60 else ''}")
    params_str = " | " + " | ".join(parts) if parts else ""
    # Log with canonical name; note alias if the LLM used a different name
    alias_note = f" (called as {tool_name})" if tool_name != canonical else ""
    _logger.info(f"TOOL_CALL | [{source}] {canonical}{alias_note}{params_str}")


def _source_from_model(model: str) -> str:
    """Map a model name string to a short source label."""
    m = model.lower()
    if "deepseek" in m:
        return "deepseek"
    if "gpt" in m or "o1" in m or "o3" in m:
        return "openai"
    if "claude" in m:
        return "claude"
    if "gemini" in m:
        return "gemini"
    if "llama" in m or "meta" in m:
        return "llama"
    if "mistral" in m or "mixtral" in m:
        return "mistral"
    if "qwen" in m:
        return "qwen"
    # fall back to first segment of the model id
    slug = m.replace("/", "-").split(":")[0][:20]
    return slug or "llm-native"


# ---------------------------------------------------------------------------
# Tool call extraction
# ---------------------------------------------------------------------------

def _log_from_complete_response(body: dict, source: str) -> None:
    """Extract and log tool_calls from a non-streaming response body."""
    try:
        for choice in body.get("choices", []):
            msg = choice.get("message", {})
            for tc in msg.get("tool_calls", []):
                name = tc.get("function", {}).get("name", "unknown")
                raw_args = tc.get("function", {}).get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {"_raw": str(raw_args)[:200]}
                _log_tool_call(name, args, source)
    except Exception:
        pass


def _log_from_stream_chunks(chunks: list, source: str) -> None:
    """Reassemble streamed delta chunks and log any tool_calls found."""
    try:
        # Accumulate per-index: {index: {name, arguments}}
        acc: dict = {}
        for chunk in chunks:
            for choice in chunk.get("choices", []):
                for tc in choice.get("delta", {}).get("tool_calls", []):
                    idx = tc.get("index", 0)
                    if idx not in acc:
                        acc[idx] = {"name": "", "arguments": ""}
                    fn = tc.get("function", {})
                    acc[idx]["name"] += fn.get("name") or ""
                    acc[idx]["arguments"] += fn.get("arguments") or ""
        for entry in acc.values():
            name = entry["name"] or "unknown"
            raw_args = entry["arguments"]
            try:
                args = json.loads(raw_args) if raw_args else {}
            except Exception:
                args = {"_raw": raw_args[:200]}
            _log_tool_call(name, args, source)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Proxy route — catches everything under /v1/
# ---------------------------------------------------------------------------

@app.route("/v1/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy(path: str):
    target = f"{BACKEND_URL}/v1/{path}"

    # Forward all headers except hop-by-hop ones
    fwd_headers = {
        k: v for k, v in request.headers
        if k.lower() not in ("host", "content-length", "transfer-encoding", "connection")
    }

    raw_body = request.get_data()

    # Parse request body to determine model / streaming
    try:
        body = json.loads(raw_body) if raw_body else {}
    except Exception:
        body = {}

    model = body.get("model", "")
    source = _source_from_model(model)
    is_streaming = bool(body.get("stream", False))

    upstream = requests.request(
        method=request.method,
        url=target,
        headers=fwd_headers,
        data=raw_body,
        stream=is_streaming,
        timeout=300,
    )

    # Strip hop-by-hop headers from upstream response before forwarding
    excluded = {"transfer-encoding", "connection", "content-encoding", "content-length"}
    resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in excluded}

    if is_streaming:
        def generate():
            chunks = []
            for raw_line in upstream.iter_lines(chunk_size=None):
                if not raw_line:
                    continue
                yield raw_line + b"\n\n"
                line = raw_line.decode("utf-8", errors="replace").strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        chunks.append(json.loads(line[6:]))
                    except Exception:
                        pass
            # All chunks received — extract and log tool calls
            _log_from_stream_chunks(chunks, source)

        return Response(
            stream_with_context(generate()),
            status=upstream.status_code,
            headers=resp_headers,
            content_type=upstream.headers.get("Content-Type", "text/event-stream"),
        )

    else:
        content = upstream.content
        try:
            _log_from_complete_response(json.loads(content), source)
        except Exception:
            pass
        return Response(content, status=upstream.status_code, headers=resp_headers)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="HexStrike LLM API proxy — logs tool calls from any LLM client"
    )
    parser.add_argument(
        "--backend", default="https://api.deepseek.com",
        help="Real LLM API base URL (default: https://api.deepseek.com)"
    )
    parser.add_argument(
        "--port", type=int, default=8889,
        help="Local port to listen on (default: 8889)"
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    args = parser.parse_args()

    global BACKEND_URL
    BACKEND_URL = args.backend.rstrip("/")

    print(f"[hexstrike-proxy] Listening on http://{args.host}:{args.port}/v1")
    print(f"[hexstrike-proxy] Forwarding to {BACKEND_URL}")
    print(f"[hexstrike-proxy] Logging tool calls to {LOG_FILE}")
    print(f"[hexstrike-proxy] Configure your client: Base URL = http://{args.host}:{args.port}/v1")

    # Suppress Flask's default request logging (keep our own)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
