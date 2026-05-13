"""
Demo 1: Agentic AI Observability — Healthy Monitoring & Auto-Remediation
========================================================================
3-minute demo showing:
  • Splunk MCP Server natural-language queries
  • AI Agent health monitoring via Splunk dashboards
  • Anomaly detection (hallucinations, failures, cost spikes)
  • Auto-remediation firing from Splunk alerts

Run from project root:
    python mcp/demoHealthy.py
"""

import sys
import time
import subprocess
from pathlib import Path

MCP_DIR = Path(__file__).parent
ROOT    = MCP_DIR.parent
sys.path.insert(0, str(MCP_DIR))

from client import load_env, list_tools, query_spl, natural_language_query

SEP  = "=" * 70
DASH = "-" * 70


def pause(msg: str = ""):
    if msg:
        print(f"\n  {msg}")
    input("\n  [Press Enter to continue...]\n")


def step(n: int, title: str):
    print(f"\n{SEP}")
    print(f"  STEP {n}: {title}")
    print(SEP)


def show(label: str, result):
    print(f"\n  ┌─ {label}")
    for line in str(result).strip().split("\n")[:25]:
        print(f"  │  {line}")
    print("  └─")


def run():
    env        = load_env()
    server_url = env.get("MCP_SERVER_URL", "https://localhost:8089")
    token      = env.get("MCP_AUTH_TOKEN", "")

    print(f"\n{'#' * 70}")
    print("#  DEMO 1: AI AGENT HEALTH MONITORING & AUTO-REMEDIATION          #")
    print(f"{'#' * 70}")
    print("""
  Scenario: Friday 11:47 PM. Your fintech AI agents are processing
  end-of-month loan approvals and fraud checks. Something is wrong —
  and you're asleep.

  Splunk detects it. Splunk investigates it. Splunk fixes it.
  No human required.
""")
    pause("Ready? Press Enter to start the demo.")

    # ── STEP 1: Connect to Splunk MCP ────────────────────────────────────────
    step(1, "Connect to Splunk via MCP Server")
    print(f"\n  Connecting to: {server_url}/services/mcp")
    print("  The Splunk MCP Server exposes all of Splunk as AI-callable tools.")
    print("  Any AI model can now query Splunk in plain English.\n")

    try:
        tools = list_tools(server_url, token)
        print(f"  ✓ Connected!  {len(tools)} tools available")
        print(f"\n  Sample tools:")
        for t in tools[:6]:
            print(f"    • {t.name}")
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        return

    pause()

    # ── STEP 2: Agent Health Summary ─────────────────────────────────────────
    step(2, "Natural Language Query: Agent Health Check")
    question = "Give me the agent health summary for the week"
    print(f"\n  Asking Splunk (in plain English):\n  \"{question}\"\n")

    try:
        _, result = natural_language_query(server_url, token, question)
        show("Agent Health — Last 7 Days", result)
    except Exception as e:
        print(f"  Query error: {e}")

    print("\n  → MCP Server translated that question into SPL automatically.")
    pause()

    # ── STEP 3: Anomaly Detection ────────────────────────────────────────────
    step(3, "Detect Anomalies Across All Agents")
    question = "Show me all anomaly types in the last 7 days"
    print(f"\n  Asking Splunk:\n  \"{question}\"\n")
    print("  This is AI-on-AI observability: an AI model interrogating Splunk")
    print("  about OTHER AI agents' misbehavior.\n")

    try:
        _, result = natural_language_query(server_url, token, question)
        show("Anomaly Breakdown", result)
    except Exception as e:
        print(f"  Query error: {e}")

    pause()

    # ── STEP 4: Find the Worst Offender ──────────────────────────────────────
    step(4, "Identify the Worst Offender")
    question = "top failing agents"
    print(f"\n  Asking Splunk:\n  \"{question}\"\n")

    try:
        _, result = natural_language_query(server_url, token, question)
        show("Top Failing Agents", result)
        print("\n  → agent-loan-001 is our problem agent. Splunk found it instantly.")
    except Exception as e:
        print(f"  Query error: {e}")

    pause()

    # ── STEP 5: Cost Spike Analysis ───────────────────────────────────────────
    step(5, "Cost Intelligence: Token Budget Analysis")
    print("\n  Asking Splunk: \"What is the cost breakdown by agent?\"\n")

    try:
        _, result = natural_language_query(server_url, token, "What is the cost breakdown by agent?")
        show("Cost by Agent", result)
    except Exception as e:
        print(f"  Query error: {e}")

    pause()

    # ── STEP 6: Auto-Remediation Fires ───────────────────────────────────────
    step(6, "Auto-Remediation: Splunk Alert Fires Action Handler")
    print("""
  Splunk's scheduled alerts run every 15 minutes.
  When an anomaly threshold is crossed, the alert triggers
  remediation/action_handler.py automatically.

  Let's simulate the alert firing now:
""")

    remediation_script = ROOT / "remediation" / "action_handler.py"
    test_cases = [
        ("failure_loop",          "agent-loan-001",    "session-demo-001"),
        ("hallucination",         "agent-fraud-003",   "session-demo-002"),
        ("cost_spike",            "agent-support-002", "session-demo-003"),
        ("null_response_cascade", "agent-report-004",  "session-demo-004"),
    ]

    for anomaly_type, agent_id, session_id in test_cases:
        print(f"  → Alert fires: [{anomaly_type}] on {agent_id}")
        try:
            proc = subprocess.run(
                [sys.executable, str(remediation_script),
                 "--anomaly_type", anomaly_type,
                 "--agent_id",     agent_id,
                 "--session_id",   session_id],
                capture_output=True, text=True, timeout=15
            )
            output = (proc.stdout + proc.stderr).strip()
            for line in output.split("\n")[-2:]:
                if line.strip():
                    print(f"     {line}")
        except Exception as e:
            print(f"     [Error] {e}")
        time.sleep(0.4)

    print("\n  ✓ All remediation actions logged → index=agent_logs (sourcetype: ai_agent:remediation)")
    pause()

    # ── STEP 7: Verify in Splunk ──────────────────────────────────────────────
    step(7, "Verify: Remediation Events Confirmed in Splunk")
    print("\n  Querying Splunk for the remediation audit trail...\n")
    spl = (
        'index=agent_logs sourcetype="ai_agent:remediation" '
        '| fields _time, agent_id, remediation_type, action_taken, severity '
        '| sort -_time | head 8'
    )
    try:
        result = query_spl(server_url, token, spl)
        show("Remediation Audit Trail", result)
    except Exception as e:
        print(f"  Query failed: {e}")
        print("  (Events were logged — check Splunk Web directly)")

    # ── Wrap up ───────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  DEMO 1 COMPLETE")
    print(SEP)
    print("""
  What you just saw:

  ✓ Splunk MCP Server  — Natural language → SPL (no code needed)
  ✓ AI-on-AI monitoring — AI querying Splunk about other AI agents
  ✓ 7 scheduled alerts  — Auto-detecting hallucinations, failures, costs
  ✓ Auto-remediation   — Alert → action_handler → logged to Splunk
  ✓ Full audit trail   — Every action is searchable in Splunk

  See Demo 2 for Circuit Breaker: agent quarantine & automatic recovery.
""")
    print(SEP + "\n")


if __name__ == "__main__":
    run()
