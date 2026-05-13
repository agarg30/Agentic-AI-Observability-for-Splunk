"""
Full Agentic Observability Demo
Demonstrates the complete loop:
  AI Agent misbehaves → Splunk detects → MCP queries → Auto-remediation fires

Run this script to show hackathon judges a live end-to-end demo.

Usage:
  python mcp/demo.py

Requirements:
  - Splunk Enterprise running with data loaded (run: python sample_data/generate.py
    then python modular_input/collector.py)
  - Splunk MCP Server app installed and running
  - .env configured with MCP_SERVER_URL and credentials
"""

import sys
import time
import json
import subprocess
import logging
from pathlib import Path

# Add mcp/ directory to path so we can import client.py directly
# (avoids naming conflict with the installed 'mcp' SDK package)
MCP_DIR = Path(__file__).parent
ROOT    = MCP_DIR.parent          # project root (one level up from mcp/)
sys.path.insert(0, str(MCP_DIR))

from client import load_env, list_tools, query_spl, natural_language_query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

SEPARATOR = "=" * 70
STEP_SEP  = "-" * 70


def pause(msg: str = ""):
    if msg:
        print(f"\n{msg}")
    input("  [Press Enter to continue...]\n")


def step(number: int, title: str):
    print(f"\n{SEPARATOR}")
    print(f"  STEP {number}: {title}")
    print(SEPARATOR)


def show_result(label: str, result):
    print(f"\n  ┌─ {label}")
    lines = str(result).strip().split("\n")
    for line in lines[:30]:
        print(f"  │  {line}")
    if len(lines) > 30:
        print(f"  │  ... ({len(lines) - 30} more lines)")
    print("  └─")


def run_demo():
    env = load_env()
    server_url = env.get("MCP_SERVER_URL", "https://localhost:8089")
    token      = env.get("MCP_AUTH_TOKEN", "")

    print(f"\n{'#' * 70}")
    print("#  AGENTIC AI OBSERVABILITY FOR SPLUNK — LIVE DEMO               #")
    print(f"{'#' * 70}")
    print("""
Scenario: It's Friday 11:47 PM. Your fintech AI agents are processing
end-of-month loan approvals and fraud checks. Suddenly, something is
very wrong — and you're asleep.

This demo shows how Splunk automatically detects, investigates, and
remediates AI agent failures WITHOUT human intervention.
""")
    pause("Ready to start?")

    # ── STEP 1: Connect to MCP Server ────────────────────────────────────────
    step(1, "Connect to Splunk via MCP Server")
    print(f"\n  Connecting to: {server_url}/services/mcp")
    print("  The Splunk MCP Server exposes all Splunk capabilities as AI tools.")
    print("  Any AI model or agent can now query Splunk in natural language.\n")

    if not token:
        print("  ✗ MCP_AUTH_TOKEN not set in .env")
        print("    Go to Splunk Web → Settings → Tokens → New Token")
        _run_simulation_mode()
        return

    try:
        tools = list_tools(server_url, token)
        print(f"  ✓ Connected to Splunk MCP Server")
        print(f"  ✓ {len(tools)} tools available")
    except Exception as e:
        print(f"\n  ✗ Could not connect: {e}")
        print("\n  Running in SIMULATION MODE (showing expected outputs)\n")
        _run_simulation_mode()
        return

    # ── STEP 2: List available tools ──────────────────────────────────────────
    step(2, "Discover Splunk MCP Tools")
    print("\n  Asking MCP: What can you do?\n")

    tools = list_tools(server_url, token)
    if tools:
        print(f"  ✓ {len(tools)} tools available:\n")
        for t in tools[:10]:
            desc = (t.description or "")[:60]
            print(f"    • {t.name}: {desc}")
        if len(tools) > 10:
            print(f"    ... and {len(tools) - 10} more")
    else:
        print("  (Tools list empty — MCP server may need configuration)")

    pause()

    # ── STEP 3: Natural language health check ─────────────────────────────────
    step(3, "Natural Language Query: Agent Health Check")
    question = "Give me the agent health summary for the week"
    print(f"\n  AI asks Splunk: \"{question}\"\n")

    try:
        _, result = natural_language_query(server_url, token, question)
        show_result("Agent Health Summary (7 days)", result)
    except Exception as e:
        print(f"  Query failed: {e}")

    pause()

    # ── STEP 4: Anomaly detection query ───────────────────────────────────────
    step(4, "AI Detects Anomalies via MCP")
    question = "Show me all anomaly types in the last 24 hours"
    print(f"\n  AI asks Splunk: \"{question}\"\n")
    print("  This is AI Agent Observability in action — an AI model")
    print("  interrogating Splunk about OTHER AI agents' behavior.\n")

    try:
        _, result = natural_language_query(server_url, token, question)
        show_result("Anomaly Breakdown (24h)", result)
    except Exception as e:
        print(f"  Query failed: {e}")

    pause()

    # ── STEP 5: Identify the failing agent ───────────────────────────────────
    step(5, "Identify the Worst Offender")
    question = "Which agent had the most failures today?"
    print(f"\n  AI asks Splunk: \"{question}\"\n")

    try:
        _, result = natural_language_query(server_url, token, question)
        show_result("Top Failing Agents (24h)", result)
        print("\n  → The MCP server translated this natural language question into SPL,")
        print("    ran it against Splunk indexes, and returned structured results.")
    except Exception as e:
        print(f"  Query failed: {e}")

    pause()

    # ── STEP 6: Hallucination deep-dive ──────────────────────────────────────
    step(6, "Deep Dive: Hallucination Events")
    print("\n  AI asks Splunk: \"List all hallucination events\"\n")

    try:
        _, result = natural_language_query(server_url, token, "List all hallucination events")
        show_result("Hallucination Events (24h)", result)
    except Exception as e:
        print(f"  Query failed: {e}")

    pause()

    # ── STEP 7: Trigger auto-remediation ─────────────────────────────────────
    step(7, "Auto-Remediation: Splunk Alert Fires Action Handler")
    print("""
  At this point, Splunk's scheduled alerts have already detected the
  anomaly surge. The alert triggers our remediation/action_handler.py
  automatically.

  Let's simulate what happens when the alert fires:
""")

    # Call the remediation handler for demonstration
    remediation_script = ROOT / "remediation" / "action_handler.py"
    test_cases = [
        ("failure_loop",          "LoanQueryAgent",       "session-demo-001"),
        ("hallucination",         "FraudDetectionAgent",  "session-demo-002"),
        ("cost_spike",            "CustomerSupportAgent", "session-demo-003"),
        ("null_response_cascade", "ReportingAgent",       "session-demo-004"),
    ]

    for anomaly_type, agent_id, session_id in test_cases:
        print(f"  → Firing remediation for: {anomaly_type} on {agent_id}")
        try:
            result = subprocess.run(
                [sys.executable, str(remediation_script),
                 "--anomaly_type", anomaly_type,
                 "--agent_id",     agent_id,
                 "--session_id",   session_id],
                capture_output=True,
                text=True,
                timeout=15
            )
            output = (result.stdout + result.stderr).strip()
            if output:
                for line in output.split("\n")[-3:]:
                    print(f"     {line}")
        except Exception as e:
            print(f"     [Error] {e}")
        time.sleep(0.3)

    print("\n  ✓ Remediation actions logged to Splunk index: agent_logs")
    print("    sourcetype: ai_agent:remediation")

    pause()

    # ── STEP 8: Verify remediation in Splunk ─────────────────────────────────
    step(8, "Verify: Remediation Events in Splunk")
    print("\n  Querying Splunk for remediation actions (via MCP)...\n")
    spl = (
        "index=agent_logs sourcetype=\"ai_agent:remediation\" "
        "| fields _time, agent_id, remediation_type, action_taken, severity "
        "| sort -_time | head 10"
    )
    try:
        result = query_spl(server_url, token, spl)
        show_result("Recent Remediation Actions", result)
    except Exception as e:
        print(f"  Query failed: {e}")
        print("  (Remediation events were logged — check Splunk directly if MCP query fails)")

    pause()

    # ── STEP 9: Cost analysis ─────────────────────────────────────────────────
    step(9, "Cost Intelligence: Token Budget Analysis")
    print("\n  AI asks Splunk: \"What is the cost breakdown by agent?\"\n")

    try:
        _, result = natural_language_query(server_url, token, "What is the cost breakdown by agent?")
        show_result("Cost by Agent (24h)", result)
    except Exception as e:
        print(f"  Query failed: {e}")

    pause()

    # ── STEP 10: Summary ──────────────────────────────────────────────────────
    step(10, "Demo Complete — What Just Happened")
    print("""
  In this demo, you saw:

  1. DATA PIPELINE
     500 synthetic AI agent sessions generated and loaded into Splunk
     3 custom indexes: agent_sessions, agent_traces, agent_logs
     Realistic anomaly distribution: hallucinations, failure loops,
     cost spikes, timeouts, null cascades

  2. INTELLIGENT DASHBOARDS
     Dashboard 1: AI Agent Overview (KPIs, trends, agent comparison)
     Dashboard 2: Anomaly Investigation (per-type deep dive)
     Dashboard 3: Agent Health (per-agent health scoring)

  3. SPLUNK AI CAPABILITIES USED
     • Splunk MCP Server — natural language → SPL translation
     • Splunk AI Toolkit — foundation model integration
     • Splunk AI Assistant — conversational SPL generation
     • Scheduled alerts (7 rules) — proactive anomaly detection

  4. AUTO-REMEDIATION
     Alert fires → action_handler.py executes →
     Agent quarantined / throttled / restarted →
     Remediation logged back to Splunk for audit trail

  5. CLOSED-LOOP OBSERVABILITY
     AI agents are monitored by AI (MCP + Splunk AI Toolkit)
     which triggers automated responses — no human needed.

  This is Agentic AI Observability for Splunk.
  Built for the Splunk AI Hackathon 2025.
""")

    print(f"{SEPARATOR}")
    print("  Thank you for watching!")
    print(SEPARATOR + "\n")


def _run_simulation_mode():
    """Show expected outputs when MCP server is not available."""
    print("""
  ╔══════════════════════════════════════════════════════════════════╗
  ║              SIMULATION MODE — Expected Demo Output              ║
  ╚══════════════════════════════════════════════════════════════════╝

  [Agent Health Summary — 7 days]
  agent_id               | total | success_rate | anomaly_rate | total_cost
  -----------------------+-------+--------------+--------------+-----------
  LoanQueryAgent         |   118 |        82.2% |        17.8% |    $5.84
  FraudDetectionAgent    |    96 |        84.4% |        15.6% |    $4.21
  CustomerSupportAgent   |   112 |        80.4% |        19.6% |    $5.50
  ReportingAgent         |    88 |        86.4% |        13.6% |    $3.91
  OnboardingAgent        |    86 |        83.7% |        16.3% |    $3.82

  [Anomaly Summary — 24h]
  anomaly_type           | count
  -----------------------+------
  hallucination          |    22
  failure_loop           |    19
  cost_spike             |    18
  timeout                |    20
  null_response_cascade  |    17

  [Top Failing Agents — 24h]
  agent_id               | failures
  -----------------------+---------
  CustomerSupportAgent   |       12
  LoanQueryAgent         |       11
  FraudDetectionAgent    |        9

  [Remediation Actions Fired]
  ✓ failure_loop         → LoanQueryAgent       quarantined, traffic rerouted
  ✓ hallucination        → FraudDetectionAgent  response flagged for review
  ✓ cost_spike           → CustomerSupportAgent token budget throttled 30min
  ✓ null_response_cascade→ ReportingAgent       CRITICAL — incident escalated

  All events logged to: index=agent_logs sourcetype=ai_agent:remediation
""")


if __name__ == "__main__":
    run_demo()
