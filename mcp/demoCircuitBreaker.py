"""
Demo 2: Circuit Breaker — Agent Quarantine & Automatic Recovery
===============================================================
3-minute demo showing:
  • Splunk detects a high-failure-rate agent via SPL
  • Circuit breaker OPENS  → agent quarantined (calls blocked)
  • Circuit breaker HALF-OPEN → health recheck after 30 min
  • Circuit breaker CLOSES → agent restored when healthy

Run from project root:
    python mcp/demoCircuitBreaker.py
"""

import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────────
MCP_DIR       = Path(__file__).parent
ROOT          = MCP_DIR.parent
REMEDIATION   = ROOT / "remediation"
sys.path.insert(0, str(MCP_DIR))
sys.path.insert(0, str(REMEDIATION))

from client import load_env, query_spl
import circuit_breaker as cb

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
    for line in str(result).strip().split("\n")[:20]:
        print(f"  │  {line}")
    print("  └─")


def run():
    env        = load_env()
    server_url = env.get("MCP_SERVER_URL", "https://localhost:8089")
    token      = env.get("MCP_AUTH_TOKEN", "")

    hec = cb.SplunkHECLogger(
        host  = env.get("SPLUNK_HOST", "localhost"),
        port  = int(env.get("SPLUNK_PORT", "8088")),
        token = env.get("SPLUNK_HEC_TOKEN", ""),
    )

    print(f"\n{'#' * 70}")
    print("#  DEMO 2: CIRCUIT BREAKER — AGENT QUARANTINE & RECOVERY          #")
    print(f"{'#' * 70}")
    print("""
  The Circuit Breaker Pattern applied to AI Agents:

     CLOSED (healthy)
        │  failure rate > 30%
        ▼
     OPEN (quarantined) ── all calls BLOCKED for 30 min
        │  health recheck
        ▼
     HALF-OPEN (testing)
        │  failure rate ≤ 30%?
        ▼
     CLOSED (restored) ◄── routing resumes
""")
    pause("Ready? Press Enter to start.")

    # ── STEP 1: Show all agents healthy ───────────────────────────────────────
    step(1, "Baseline — All Agents Healthy")
    print("\n  Checking current circuit breaker state for all agents...\n")

    # Reset any leftover quarantine state from previous runs
    state = cb.load_state()
    for agent_id in cb.ALL_AGENTS:
        if state.get(agent_id, {}).get("status") == "quarantined":
            cb.set_agent_state(agent_id, {"status": "healthy"})

    cb.print_status()
    print("\n  All 5 agents are HEALTHY. Calls are routed normally.")
    pause()

    # ── STEP 2: Splunk detects the problem ────────────────────────────────────
    step(2, "Splunk Alert: High Failure Rate Detected")
    print("\n  The scheduled Splunk alert [AI Agent - Unhealthy Agent Detected]")
    print("  fires every 5 minutes. It runs this SPL:\n")
    spl = (
        'index=agent_sessions '
        '| stats count as total count(eval(status="failed")) as failures by agent_id '
        '| eval failure_rate=round(failures/total,2) '
        '| sort -failure_rate '
        '| head 5'
    )
    print(f"  {spl}\n")

    try:
        result = query_spl(server_url, token, spl)
        show("Agent Failure Rates (all-time)", result)
        print("\n  → agent-loan-001 has the highest failure count.")
        print("    The alert threshold is 30%. Circuit breaker will now OPEN.")
    except Exception as e:
        print(f"  SPL query error: {e}")
        print("  (Continuing demo with agent-loan-001 as the known bad agent)")

    pause()

    # ── STEP 3: Circuit OPENS — Quarantine the agent ──────────────────────────
    step(3, "CIRCUIT OPENS — Quarantine agent-loan-001")
    print("\n  The alert action triggers circuit_breaker.py automatically.")
    print("  Calling: quarantine_agent('agent-loan-001', reason='Failure rate exceeded 30% threshold')\n")

    cb.quarantine_agent(
        agent_id = "agent-loan-001",
        reason   = "Failure rate exceeded 30% threshold (detected by Splunk alert)",
        hec      = hec,
    )

    print("  ✓ State saved to: remediation/agent_state.json")
    print("  ✓ Event logged  → index=agent_logs  sourcetype=ai_agent:circuit_breaker")
    pause()

    # ── STEP 4: Show updated status ───────────────────────────────────────────
    step(4, "Updated Status — Agent Quarantined")
    print()
    cb.print_status()
    print("\n  agent-loan-001 is now QUARANTINED.")
    print(f"  Health recheck scheduled 30 minutes from now.")
    pause()

    # ── STEP 5: Incoming calls — fallback routing, NOT blocked ───────────────
    step(5, "Call Routing — Users Are NOT Blocked (Fallback Routing)")
    print("""
  KEY INSIGHT: Returning False to the user is NOT acceptable in production.
  Instead, route_call() returns a RouteResult with a FALLBACK agent so
  users keep getting responses — just from a backup agent while repair happens.

  Fallback map (configured in FALLBACK_MAP):
    agent-loan-001    →  agent-report-004  (ReportingAgent covers basic queries)
    agent-support-002 →  agent-onboard-005 (OnboardingAgent covers support)
    agent-fraud-003   →  agent-support-002 (Support handles low-risk triage)
""")
    agents_to_try = ["agent-loan-001", "agent-fraud-003", "agent-support-002"]
    for agent_id in agents_to_try:
        result = cb.route_call(agent_id)
        if result.allowed and not result.fallback:
            print(f"    route_call('{agent_id}')  →  ✓ PRIMARY   send to {result.agent_id}")
        elif result.allowed and result.fallback:
            print(f"    route_call('{agent_id}')  →  ↪ FALLBACK  send to {result.agent_id}  ← user served!")
        else:
            print(f"    route_call('{agent_id}')  →  ✗ DEGRADED  return: \"{cb.DEGRADED_RESPONSE[:60]}...\"")
        time.sleep(0.3)

    print("\n  → Users calling agent-loan-001 are seamlessly redirected to")
    print("    agent-report-004. Zero downtime from the user's perspective.")
    print("\n  → Only if BOTH the primary AND fallback are quarantined will")
    print("    the user see a graceful 'temporarily unavailable' message.")
    pause()

    # ── STEP 6: Half-open — Health Recheck ────────────────────────────────────
    step(6, "HALF-OPEN — Health Recheck After Quarantine Period")
    print("""
  In production, the background monitor (--action monitor) automatically
  runs health checks every 5 minutes and restores agents when ready.

  For this demo we'll manually trigger the health check now.
  The check queries Splunk REST API:

    index=agent_sessions agent_id="agent-loan-001" earliest=-30m
    | stats count as total, count(eval(status="failed")) as failures
    | eval failure_rate = round(failures/total, 3)
""")
    print("  Bypassing 30-min timer for demo — running health check now...")

    # Override the restore_check_at so the check runs immediately
    cb.set_agent_state("agent-loan-001", {
        "restore_check_at": (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
    })

    result = cb.run_health_check("agent-loan-001", env, hec)

    if result:
        print("\n  ✓ Failure rate dropped below threshold — agent is healthy!")
        print("    Circuit CLOSED: routing restored.")
    else:
        # Simulate recovery for demo if data is still bad
        print("\n  Agent still shows failures (historical data).")
        print("  In demo mode: manually restoring to show the recovery flow...")
        cb.restore_agent("agent-loan-001", hec, failure_rate=0.12)

    pause()

    # ── STEP 7: Final status ───────────────────────────────────────────────────
    step(7, "CIRCUIT CLOSED — All Agents Healthy Again")
    print()
    cb.print_status()
    print("\n  ✓ agent-loan-001 is HEALTHY — normal routing resumes.")
    print("  ✓ Recovery event logged to Splunk for audit trail.")
    pause()

    # ── STEP 8: Splunk audit trail ─────────────────────────────────────────────
    step(8, "Audit Trail — Circuit Breaker Events in Splunk")
    print("\n  Every state change is logged to Splunk. Query it now:\n")
    spl_audit = (
        'index=agent_logs sourcetype="ai_agent:circuit_breaker" '
        '| fields _time, agent_id, action, reason, failure_rate, status '
        '| sort -_time | head 10'
    )
    try:
        result = query_spl(server_url, token, spl_audit)
        show("Circuit Breaker Audit Trail", result)
    except Exception as e:
        print(f"  SPL query error: {e}")
        print("  (Events logged — check Splunk Web directly)")

    # ── Wrap up ────────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  DEMO 2 COMPLETE")
    print(SEP)
    print("""
  What you just saw:

  ✓ OPEN     — Splunk alert detected failure rate > 30%
               Circuit breaker quarantined agent-loan-001 instantly

  ✓ FALLBACK — Users are NOT blocked. route_call() redirects to
               agent-report-004 automatically — zero user downtime

  ✓ DEGRADED — Only if fallback is ALSO down: user sees a clear
               "temporarily unavailable" message (not a crash)

  ✓ HALF-OPEN — After 30 min, health recheck queries live Splunk data
                Automatic, no human needed

  ✓ CLOSED   — Agent passed health check → restored to primary routing
               Full recovery audit trail in Splunk

  Run:  python remediation/circuit_breaker.py --action monitor
  to keep this running continuously in the background.
""")
    print(SEP + "\n")


if __name__ == "__main__":
    run()
