"""
Agent Circuit Breaker — Agentic AI Observability
=================================================
Implements the circuit breaker pattern for AI agents:

  CLOSED (healthy)  →  OPEN (quarantined)  →  HALF-OPEN (health check)  →  CLOSED

Flow:
  1. An agent exceeds failure threshold → quarantine_agent()
  2. All calls to that agent are blocked → route_call() returns False
  3. After 30 minutes → health_check() runs automatically
  4. If failure rate < threshold → agent restored → route_call() returns True

State is persisted to agent_state.json so it survives restarts.

Usage:
  # Quarantine an unhealthy agent
  python circuit_breaker.py --action quarantine --agent_id agent-loan-001

  # Check status of all agents
  python circuit_breaker.py --action status

  # Run the background health-recheck loop (checks every 5 minutes)
  python circuit_breaker.py --action monitor

  # Manually restore an agent
  python circuit_breaker.py --action restore --agent_id agent-loan-001
"""

import json
import os
import sys
import ssl
import time
import argparse
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, NamedTuple

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
STATE_FILE     = Path(__file__).parent / "agent_state.json"
QUARANTINE_MIN = 30          # minutes before health recheck
FAILURE_THRESHOLD = 0.30     # >30% failure rate = unhealthy
MONITOR_INTERVAL  = 300      # check every 5 minutes

# Known agents (used for status display)
ALL_AGENTS = [
    "agent-loan-001",
    "agent-onboard-005",
    "agent-report-004",
    "agent-support-002",
    "agent-fraud-003",
]

# Fallback routing: if agent X is quarantined, route to agent Y instead.
# In production this would be another instance of the same agent type.
# Here we map to the most similar healthy agent as a backup.
FALLBACK_MAP = {
    "agent-loan-001":    "agent-report-004",    # ReportingAgent handles basic loan queries
    "agent-support-002": "agent-onboard-005",   # OnboardingAgent handles basic support
    "agent-fraud-003":   "agent-support-002",   # Support handles low-risk fraud triage
    "agent-report-004":  "agent-loan-001",       # LoanAgent can cover basic reports
    "agent-onboard-005": "agent-support-002",   # Support handles onboarding queries
}

# What to tell users when NO fallback is available
DEGRADED_RESPONSE = (
    "This service is temporarily unavailable due to a system health event. "
    "Your request has been queued and will be processed automatically once "
    "the service recovers (typically within 30 minutes). "
    "For urgent matters please contact support."
)


class RouteResult(NamedTuple):
    """
    Returned by route_call().
    allowed   : True if original agent is healthy
    agent_id  : agent to actually send the request to (may be fallback)
    fallback  : True if a fallback agent is being used
    reason    : human-readable explanation
    """
    allowed:  bool
    agent_id: str
    fallback: bool
    reason:   str

# ── Load .env ──────────────────────────────────────────────────────────────────

def load_env() -> dict:
    env_path = Path(__file__).parent.parent / ".env"
    env = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    for key in list(env):
        env[key] = os.environ.get(key, env[key])
    return env


# ── State persistence ──────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load agent circuit-breaker state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict):
    """Persist state to disk."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_agent_state(agent_id: str) -> dict:
    state = load_state()
    return state.get(agent_id, {"status": "healthy"})


def set_agent_state(agent_id: str, updates: dict):
    state = load_state()
    current = state.get(agent_id, {"status": "healthy"})
    current.update(updates)
    state[agent_id] = current
    save_state(state)
    return current


# ── Splunk HEC Logger ──────────────────────────────────────────────────────────

class SplunkHECLogger:
    def __init__(self, host: str, port: int, token: str):
        self.url = f"https://{host}:{port}/services/collector/event"
        self.token = token
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def log_event(self, event: dict):
        payload = json.dumps({
            "time":       datetime.now(timezone.utc).timestamp(),
            "index":      "agent_logs",
            "sourcetype": "ai_agent:circuit_breaker",
            "event":      event
        }).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=payload,
            headers={"Authorization": f"Splunk {self.token}",
                     "Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=10):
                pass
        except Exception as e:
            log.warning(f"HEC log failed: {e}")


# ── Splunk health query via REST API ───────────────────────────────────────────

def query_agent_health(agent_id: str, env: dict) -> Optional[float]:
    """
    Query Splunk for the recent failure rate of an agent.
    Returns failure rate (0.0-1.0) or None on error.
    """
    import base64
    host     = env.get("SPLUNK_HOST", "localhost")
    api_port = env.get("SPLUNK_API_PORT", "8089")
    username = env.get("SPLUNK_USERNAME", "")
    password = env.get("SPLUNK_PASSWORD", "")

    spl = (
        f'search index=agent_sessions agent_id="{agent_id}" earliest=-30m '
        f'| stats count as total count(eval(status="failed")) as failures '
        f'| eval failure_rate=round(failures/total,3) '
        f'| fields failure_rate'
    )
    params = urllib.parse.urlencode({
        "search":       f"search {spl}",
        "output_mode":  "json",
        "count":        "1",
        "exec_mode":    "oneshot",
    }).encode("utf-8")

    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    ctx   = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE

    req = urllib.request.Request(
        f"https://{host}:{api_port}/services/search/jobs",
        data=params,
        headers={"Authorization": f"Basic {creds}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results", [])
            if results:
                return float(results[0].get("failure_rate", 0.0))
            return 0.0   # no events = no failures
    except Exception as e:
        log.error(f"Health query failed for {agent_id}: {e}")
        return None


# ── Circuit Breaker Actions ────────────────────────────────────────────────────

def quarantine_agent(agent_id: str, reason: str, hec: SplunkHECLogger):
    """
    Open the circuit: quarantine the agent.
    All routing calls will return False until restored.
    """
    now = datetime.now(timezone.utc)
    restore_at = (now + timedelta(minutes=QUARANTINE_MIN)).isoformat()

    agent_state = set_agent_state(agent_id, {
        "status":       "quarantined",
        "quarantined_at": now.isoformat(),
        "restore_check_at": restore_at,
        "reason":       reason,
    })

    log.warning(f"CIRCUIT OPEN — {agent_id} quarantined. Health recheck at {restore_at}")
    hec.log_event({
        "event_type":  "circuit_breaker",
        "action":      "quarantine",
        "agent_id":    agent_id,
        "reason":      reason,
        "status":      "quarantined",
        "restore_check_at": restore_at,
        "timestamp":   now.isoformat(),
    })
    print(f"\n  QUARANTINED: {agent_id}")
    print(f"  Reason:      {reason}")
    print(f"  Health check: {restore_at}\n")


def restore_agent(agent_id: str, hec: SplunkHECLogger, failure_rate: float = 0.0):
    """Close the circuit: restore the agent to healthy routing."""
    now = datetime.now(timezone.utc)
    set_agent_state(agent_id, {
        "status":       "healthy",
        "restored_at":  now.isoformat(),
        "failure_rate": failure_rate,
    })
    log.info(f"CIRCUIT CLOSED — {agent_id} restored (failure_rate={failure_rate:.1%})")
    hec.log_event({
        "event_type":   "circuit_breaker",
        "action":       "restore",
        "agent_id":     agent_id,
        "failure_rate": failure_rate,
        "status":       "healthy",
        "timestamp":    now.isoformat(),
    })
    print(f"\n  RESTORED: {agent_id} (failure rate: {failure_rate:.1%})\n")


def route_call(agent_id: str) -> RouteResult:
    """
    Decide where to route a call.

    Returns a RouteResult:
      • allowed=True,  agent_id=<original>  — original agent is healthy, use it
      • allowed=True,  agent_id=<fallback>,  fallback=True — original quarantined,
                                               use fallback agent so user is NOT blocked
      • allowed=False, agent_id=""           — quarantined AND no healthy fallback,
                                               return DEGRADED_RESPONSE to the user

    Usage:
        result = route_call("agent-loan-001")
        if not result.allowed:
            return DEGRADED_RESPONSE          # graceful degradation
        response = call_agent(result.agent_id) # works for both primary & fallback
    """
    state = get_agent_state(agent_id)
    if state.get("status") != "quarantined":
        return RouteResult(allowed=True, agent_id=agent_id, fallback=False,
                           reason="healthy")

    restore_check = state.get("restore_check_at", "unknown")
    log.warning(f"CIRCUIT OPEN: {agent_id} quarantined. Next health check: {restore_check}")

    # Try the fallback agent
    fallback_id = FALLBACK_MAP.get(agent_id)
    if fallback_id:
        fallback_state = get_agent_state(fallback_id)
        if fallback_state.get("status") != "quarantined":
            log.info(f"FALLBACK ROUTING: {agent_id} → {fallback_id} (user request served)")
            return RouteResult(allowed=True, agent_id=fallback_id, fallback=True,
                               reason=f"{agent_id} quarantined; routed to {fallback_id}")
        else:
            log.warning(f"FALLBACK also quarantined: {fallback_id}")

    # No healthy fallback — graceful degradation
    log.error(f"NO FALLBACK AVAILABLE for {agent_id} — returning degraded response")
    return RouteResult(allowed=False, agent_id="", fallback=False,
                       reason=f"{agent_id} quarantined and no healthy fallback available")


def run_health_check(agent_id: str, env: dict, hec: SplunkHECLogger) -> bool:
    """
    Half-open: check if a quarantined agent is healthy enough to restore.
    Returns True if restored, False if still unhealthy.
    """
    state = get_agent_state(agent_id)
    if state.get("status") != "quarantined":
        return True  # already healthy

    restore_check_at = state.get("restore_check_at", "")
    if restore_check_at:
        restore_time = datetime.fromisoformat(restore_check_at)
        if datetime.now(timezone.utc) < restore_time:
            remaining = (restore_time - datetime.now(timezone.utc)).seconds // 60
            log.info(f"HALF-OPEN PENDING: {agent_id} — {remaining} min until health check")
            return False

    # Time to check health
    log.info(f"HALF-OPEN: Checking health of {agent_id}...")
    failure_rate = query_agent_health(agent_id, env)

    if failure_rate is None:
        log.warning(f"Health check inconclusive for {agent_id} — staying quarantined 30 more min")
        # Extend quarantine
        set_agent_state(agent_id, {
            "restore_check_at": (
                datetime.now(timezone.utc) + timedelta(minutes=QUARANTINE_MIN)
            ).isoformat()
        })
        return False

    log.info(f"Health check result: {agent_id} failure_rate={failure_rate:.1%} (threshold={FAILURE_THRESHOLD:.0%})")

    if failure_rate <= FAILURE_THRESHOLD:
        restore_agent(agent_id, hec, failure_rate)
        return True
    else:
        log.warning(f"Still unhealthy: {agent_id} failure_rate={failure_rate:.1%} — extending quarantine 30 min")
        set_agent_state(agent_id, {
            "restore_check_at": (
                datetime.now(timezone.utc) + timedelta(minutes=QUARANTINE_MIN)
            ).isoformat(),
            "last_failure_rate": failure_rate,
        })
        hec.log_event({
            "event_type":   "circuit_breaker",
            "action":       "health_check_failed",
            "agent_id":     agent_id,
            "failure_rate": failure_rate,
            "status":       "quarantined",
            "timestamp":    datetime.now(timezone.utc).isoformat(),
        })
        return False


def print_status():
    """Print the current circuit breaker status of all agents."""
    state = load_state()
    print("\n" + "=" * 60)
    print("  Agent Circuit Breaker Status")
    print("=" * 60)
    for agent_id in ALL_AGENTS:
        s = state.get(agent_id, {"status": "healthy"})
        status = s.get("status", "healthy")
        icon   = "🟢" if status == "healthy" else "🔴"
        print(f"  {icon}  {agent_id:<25} {status.upper()}")
        if status == "quarantined":
            print(f"       Reason:       {s.get('reason', 'N/A')}")
            print(f"       Quarantined:  {s.get('quarantined_at', 'N/A')}")
            print(f"       Health check: {s.get('restore_check_at', 'N/A')}")
        elif status == "healthy" and s.get("restored_at"):
            print(f"       Restored at:  {s.get('restored_at')}")
    print("=" * 60 + "\n")


def run_monitor(env: dict, hec: SplunkHECLogger):
    """
    Background monitor loop.
    Checks all quarantined agents every MONITOR_INTERVAL seconds.
    """
    log.info(f"Circuit breaker monitor started (check interval: {MONITOR_INTERVAL}s)")
    print(f"\nMonitoring agent health. Press Ctrl+C to stop.\n")

    while True:
        state = load_state()
        quarantined = [
            agent_id for agent_id, s in state.items()
            if s.get("status") == "quarantined"
        ]
        if quarantined:
            log.info(f"Checking health of {len(quarantined)} quarantined agent(s): {quarantined}")
            for agent_id in quarantined:
                run_health_check(agent_id, env, hec)
        else:
            log.info("All agents healthy.")

        print_status()
        time.sleep(MONITOR_INTERVAL)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    import urllib.parse

    parser = argparse.ArgumentParser(description="Agent Circuit Breaker")
    parser.add_argument("--action", choices=["quarantine", "restore", "status", "monitor", "check"],
                        default="status")
    parser.add_argument("--agent_id", default="")
    parser.add_argument("--reason",   default="High failure rate detected by Splunk alert")
    args = parser.parse_args()

    env = load_env()
    hec = SplunkHECLogger(
        host=env.get("SPLUNK_HOST", "localhost"),
        port=int(env.get("SPLUNK_PORT", "8088")),
        token=env.get("SPLUNK_HEC_TOKEN", "")
    )

    if args.action == "status":
        print_status()

    elif args.action == "quarantine":
        if not args.agent_id:
            print("ERROR: --agent_id required for quarantine"); sys.exit(1)
        quarantine_agent(args.agent_id, args.reason, hec)

    elif args.action == "restore":
        if not args.agent_id:
            print("ERROR: --agent_id required for restore"); sys.exit(1)
        restore_agent(args.agent_id, hec)

    elif args.action == "check":
        agent_ids = [args.agent_id] if args.agent_id else ALL_AGENTS
        for aid in agent_ids:
            run_health_check(aid, env, hec)
        print_status()

    elif args.action == "monitor":
        run_monitor(env, hec)


if __name__ == "__main__":
    main()
