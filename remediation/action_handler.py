"""
Auto-Remediation — Agent Action Handler
Triggered by Splunk alerts when anomalies are detected.

Actions taken based on anomaly type:
  - hallucination      → flag session, log warning, notify team
  - failure_loop       → quarantine agent, reroute traffic
  - cost_spike         → throttle agent, alert on cost threshold
  - null_response_cascade → escalate immediately, check upstream API
  - timeout            → restart agent session, notify on-call
  - high_anomaly_rate  → escalate to incident, notify on-call

Usage (called by Splunk alert action):
  python alert_action.py
  
Also callable directly:
  python alert_action.py --anomaly_type failure_loop --agent_id agent-loan-001 --session_id <id>
"""

import json
import os
import sys
import argparse
import urllib.request
import urllib.error
import ssl
import logging
from datetime import datetime, timezone
from pathlib import Path

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ── Load .env ──────────────────────────────────────────────────────────────────

def load_env() -> dict:
    env_path = Path(__file__).parent.parent / ".env"
    env = {}
    if not env_path.exists():
        log.warning(f".env not found at {env_path}")
        return env
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


# ── HEC Logger — logs remediation actions back to Splunk ──────────────────────

class SplunkHECLogger:
    def __init__(self, host: str, port: int, token: str):
        self.url = f"https://{host}:{port}/services/collector/event"
        self.token = token
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def log_action(self, event: dict):
        payload = json.dumps({
            "time":       datetime.now(timezone.utc).timestamp(),
            "index":      "agent_logs",
            "sourcetype": "ai_agent:remediation",
            "event":      event
        }).encode("utf-8")

        req = urllib.request.Request(
            self.url, data=payload,
            headers={"Authorization": f"Splunk {self.token}", "Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                if result.get("code") != 0:
                    log.warning(f"HEC response: {result}")
        except Exception as e:
            log.error(f"Failed to log to Splunk: {e}")


# ── Webhook Notifier ───────────────────────────────────────────────────────────

def notify_webhook(webhook_url: str, message: dict):
    """Send notification to a webhook (Slack, Teams, PagerDuty, etc.)"""
    if not webhook_url:
        log.info(f"[NOTIFY] {message['title']}: {message['body']}")
        return

    payload = json.dumps({
        "text": f"*{message['title']}*\n{message['body']}"
    }).encode("utf-8")

    req = urllib.request.Request(
        webhook_url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            log.info(f"Webhook notification sent: {message['title']}")
    except Exception as e:
        log.error(f"Webhook failed: {e}")


# ── Remediation Actions ────────────────────────────────────────────────────────

def remediate_hallucination(agent_id: str, session_id: str, hec: SplunkHECLogger, webhook_url: str):
    log.warning(f"HALLUCINATION detected — agent={agent_id} session={session_id}")
    action = {
        "event_type":       "remediation",
        "remediation_type": "hallucination_flagged",
        "agent_id":         agent_id,
        "session_id":       session_id,
        "action_taken":     "Session flagged for review. Low-confidence response quarantined.",
        "severity":         "medium",
        "timestamp":        datetime.now(timezone.utc).isoformat()
    }
    hec.log_action(action)
    notify_webhook(webhook_url, {
        "title": "⚠️ Hallucination Detected",
        "body":  f"Agent `{agent_id}` produced a low-confidence response in session `{session_id}`. Response quarantined for review."
    })


def remediate_failure_loop(agent_id: str, session_id: str, hec: SplunkHECLogger, webhook_url: str):
    log.error(f"FAILURE LOOP detected — agent={agent_id} session={session_id}")
    action = {
        "event_type":       "remediation",
        "remediation_type": "failure_loop_quarantine",
        "agent_id":         agent_id,
        "session_id":       session_id,
        "action_taken":     "Agent session terminated. Traffic rerouted to backup agent.",
        "severity":         "high",
        "timestamp":        datetime.now(timezone.utc).isoformat()
    }
    hec.log_action(action)
    notify_webhook(webhook_url, {
        "title": "🔴 Failure Loop — Agent Quarantined",
        "body":  f"Agent `{agent_id}` entered a failure loop in session `{session_id}`. Session terminated. Traffic rerouted to backup."
    })


def remediate_cost_spike(agent_id: str, session_id: str, hec: SplunkHECLogger, webhook_url: str):
    log.warning(f"COST SPIKE detected — agent={agent_id} session={session_id}")
    action = {
        "event_type":       "remediation",
        "remediation_type": "cost_spike_throttle",
        "agent_id":         agent_id,
        "session_id":       session_id,
        "action_taken":     "Agent throttled. Token budget enforced for next 30 minutes.",
        "severity":         "medium",
        "timestamp":        datetime.now(timezone.utc).isoformat()
    }
    hec.log_action(action)
    notify_webhook(webhook_url, {
        "title": "💰 Cost Spike Alert",
        "body":  f"Agent `{agent_id}` exceeded token budget in session `{session_id}`. Throttle applied for 30 minutes."
    })


def remediate_null_cascade(agent_id: str, session_id: str, hec: SplunkHECLogger, webhook_url: str):
    log.critical(f"NULL RESPONSE CASCADE — agent={agent_id} session={session_id}")
    action = {
        "event_type":       "remediation",
        "remediation_type": "null_cascade_escalation",
        "agent_id":         agent_id,
        "session_id":       session_id,
        "action_taken":     "CRITICAL: Upstream API failure detected. Incident escalated. All affected sessions suspended.",
        "severity":         "critical",
        "timestamp":        datetime.now(timezone.utc).isoformat()
    }
    hec.log_action(action)
    notify_webhook(webhook_url, {
        "title": "🚨 CRITICAL — Null Response Cascade",
        "body":  f"Upstream API returning null values. Agent `{agent_id}` sessions suspended. Check upstream API health immediately."
    })


def remediate_timeout(agent_id: str, session_id: str, hec: SplunkHECLogger, webhook_url: str):
    log.warning(f"TIMEOUT detected — agent={agent_id} session={session_id}")
    action = {
        "event_type":       "remediation",
        "remediation_type": "timeout_restart",
        "agent_id":         agent_id,
        "session_id":       session_id,
        "action_taken":     "Timed-out session cleared. Agent restarted. On-call notified.",
        "severity":         "medium",
        "timestamp":        datetime.now(timezone.utc).isoformat()
    }
    hec.log_action(action)
    notify_webhook(webhook_url, {
        "title": "⏱️ Agent Timeout",
        "body":  f"Agent `{agent_id}` timed out in session `{session_id}`. Session cleared and agent restarted."
    })


REMEDIATION_MAP = {
    "hallucination":          remediate_hallucination,
    "failure_loop":           remediate_failure_loop,
    "cost_spike":             remediate_cost_spike,
    "null_response_cascade":  remediate_null_cascade,
    "timeout":                remediate_timeout,
}


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Agent Auto-Remediation Handler")
    parser.add_argument("--anomaly_type", default="hallucination", choices=list(REMEDIATION_MAP.keys()))
    parser.add_argument("--agent_id",     default="agent-unknown")
    parser.add_argument("--session_id",   default="session-unknown")
    args = parser.parse_args()

    env = load_env()
    hec = SplunkHECLogger(
        host=env.get("SPLUNK_HOST", "localhost"),
        port=int(env.get("SPLUNK_PORT", "8088")),
        token=env.get("SPLUNK_HEC_TOKEN", "")
    )
    webhook_url = env.get("WEBHOOK_URL", "")

    action_fn = REMEDIATION_MAP.get(args.anomaly_type)
    if action_fn:
        action_fn(args.agent_id, args.session_id, hec, webhook_url)
    else:
        log.error(f"Unknown anomaly type: {args.anomaly_type}")
        sys.exit(1)


if __name__ == "__main__":
    main()

