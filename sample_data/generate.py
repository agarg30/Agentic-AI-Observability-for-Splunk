"""
Synthetic Data Generator — AI Agent Telemetry
Generates realistic AI agent logs, traces, and session data for Splunk demo.

Scenarios included:
  - Normal agent behavior (baseline)
  - Hallucination (low confidence, inconsistent responses)
  - Failure loop (same step repeating)
  - Cost spike (token usage 3x baseline)
  - Null response cascade (upstream API returning null)
  - Timeout (step duration exceeds threshold)

Output: JSON files in sample_data/output/
  - sessions.json
  - traces.json
  - logs.json

Usage:
  python generate.py
"""

import json
import random
import uuid
import os
from datetime import datetime, timedelta

# ── Configuration ──────────────────────────────────────────────────────────────

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

AGENTS = [
    {"id": "agent-loan-001",    "name": "LoanQueryAgent",      "model": "gpt-4o",               "app": "fintech-portal"},
    {"id": "agent-support-002", "name": "CustomerSupportAgent","model": "gpt-4o-mini",           "app": "support-desk"},
    {"id": "agent-fraud-003",   "name": "FraudDetectionAgent", "model": "foundation-sec-1.1-8b", "app": "risk-platform"},
    {"id": "agent-report-004",  "name": "ReportingAgent",      "model": "gpt-4o",               "app": "analytics-hub"},
    {"id": "agent-onboard-005", "name": "OnboardingAgent",     "model": "gpt-4o-mini",           "app": "customer-onboarding"},
]

TOOLS = [
    "search_knowledge_base",
    "query_customer_db",
    "call_credit_api",
    "send_notification",
    "fetch_policy_doc",
    "validate_input",
    "generate_report",
    "check_fraud_score",
]

ANOMALY_TYPES = [
    "hallucination",
    "failure_loop",
    "cost_spike",
    "null_response_cascade",
    "timeout",
    "none",  # normal
]

# Weights: mostly normal, some anomalies
ANOMALY_WEIGHTS = [0.05, 0.05, 0.05, 0.05, 0.05, 0.75]

USERS = [f"user_{i:04d}" for i in range(1, 51)]

# ── Helpers ────────────────────────────────────────────────────────────────────

def random_time(base: datetime, jitter_minutes: int = 60) -> datetime:
    return base + timedelta(minutes=random.uniform(0, jitter_minutes))


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def epoch(dt: datetime) -> float:
    return dt.timestamp()


# ── Session Generator ──────────────────────────────────────────────────────────

def generate_session(base_time: datetime, anomaly: str) -> dict:
    agent = random.choice(AGENTS)
    session_id = str(uuid.uuid4())
    user = random.choice(USERS)

    if anomaly == "cost_spike":
        tokens_in  = random.randint(8000, 15000)
        tokens_out = random.randint(4000, 8000)
        cost_usd   = round((tokens_in + tokens_out) * 0.00004, 4)
        duration_s = random.uniform(12, 30)
        status     = "completed"
        error      = None
    elif anomaly == "timeout":
        tokens_in  = random.randint(200, 600)
        tokens_out = 0
        cost_usd   = round(tokens_in * 0.000015, 4)
        duration_s = random.uniform(60, 120)
        status     = "timeout"
        error      = "Session exceeded max duration threshold"
    elif anomaly == "failure_loop":
        tokens_in  = random.randint(3000, 6000)
        tokens_out = random.randint(1000, 2000)
        cost_usd   = round((tokens_in + tokens_out) * 0.00002, 4)
        duration_s = random.uniform(25, 45)
        status     = "failed"
        error      = "Agent entered recursive loop — step repeated 8 times"
    elif anomaly == "null_response_cascade":
        tokens_in  = random.randint(400, 800)
        tokens_out = random.randint(50, 150)
        cost_usd   = round((tokens_in + tokens_out) * 0.000015, 4)
        duration_s = random.uniform(5, 12)
        status     = "failed"
        error      = "Upstream API returned null — cascade failure across 3 steps"
    elif anomaly == "hallucination":
        tokens_in  = random.randint(1000, 3000)
        tokens_out = random.randint(500, 1500)
        cost_usd   = round((tokens_in + tokens_out) * 0.00002, 4)
        duration_s = random.uniform(8, 20)
        status     = "completed"
        error      = None
    else:  # normal
        tokens_in  = random.randint(300, 1500)
        tokens_out = random.randint(100, 600)
        cost_usd   = round((tokens_in + tokens_out) * 0.000015, 4)
        duration_s = random.uniform(2, 12)
        status     = "completed"
        error      = None

    start_time = random_time(base_time)
    end_time   = start_time + timedelta(seconds=duration_s)

    return {
        "timestamp":       iso(start_time),
        "_time":           epoch(start_time),
        "event_type":      "session",
        "session_id":      session_id,
        "agent_id":        agent["id"],
        "agent_name":      agent["name"],
        "model":           agent["model"],
        "app":             agent["app"],
        "user_id":         user,
        "status":          status,
        "anomaly_type":    anomaly if anomaly != "none" else "normal",
        "tokens_in":       tokens_in,
        "tokens_out":      tokens_out,
        "tokens_total":    tokens_in + tokens_out,
        "cost_usd":        cost_usd,
        "duration_s":      round(duration_s, 2),
        "start_time":      iso(start_time),
        "end_time":        iso(end_time),
        "error":           error,
    }, session_id, agent, start_time, anomaly


# ── Trace Generator ────────────────────────────────────────────────────────────

def generate_traces(session_id: str, agent: dict, start_time: datetime, anomaly: str) -> list:
    traces = []
    steps = random.randint(3, 6)
    current_time = start_time

    if anomaly == "failure_loop":
        # repeat same step 8 times
        looping_step = "validate_input"
        for i in range(8):
            current_time += timedelta(seconds=random.uniform(2, 5))
            traces.append({
                "timestamp":    iso(current_time),
                "_time":        epoch(current_time),
                "event_type":   "trace",
                "session_id":   session_id,
                "agent_id":     agent["id"],
                "agent_name":   agent["name"],
                "app":          agent["app"],
                "step":         i + 1,
                "step_name":    looping_step,
                "tool_called":  looping_step,
                "input_tokens": random.randint(100, 300),
                "output_tokens":random.randint(50, 150),
                "duration_ms":  random.randint(800, 2000),
                "confidence":   round(random.uniform(0.3, 0.5), 3),
                "status":       "loop_detected" if i > 2 else "ok",
                "anomaly_flag": True if i > 2 else False,
                "anomaly_type": "failure_loop" if i > 2 else "normal",
            })
        return traces

    for i in range(steps):
        tool = random.choice(TOOLS)
        current_time += timedelta(seconds=random.uniform(1, 6))
        step_anomaly = "normal"
        confidence = round(random.uniform(0.75, 0.98), 3)
        status = "ok"
        duration_ms = random.randint(200, 1500)

        if anomaly == "hallucination" and i == steps - 1:
            confidence = round(random.uniform(0.18, 0.35), 3)
            step_anomaly = "hallucination"
            status = "low_confidence"
        elif anomaly == "cost_spike":
            duration_ms = random.randint(3000, 8000)
        elif anomaly == "null_response_cascade" and i >= 1:
            status = "null_response"
            step_anomaly = "null_response_cascade"
            confidence = 0.0
        elif anomaly == "timeout" and i == 1:
            duration_ms = random.randint(60000, 90000)
            status = "timeout"
            step_anomaly = "timeout"

        traces.append({
            "timestamp":    iso(current_time),
            "_time":        epoch(current_time),
            "event_type":   "trace",
            "session_id":   session_id,
            "agent_id":     agent["id"],
            "agent_name":   agent["name"],
            "app":          agent["app"],
            "step":         i + 1,
            "step_name":    f"step_{i+1}_{tool}",
            "tool_called":  tool,
            "input_tokens": random.randint(100, 500),
            "output_tokens":random.randint(50, 300),
            "duration_ms":  duration_ms,
            "confidence":   confidence,
            "status":       status,
            "anomaly_flag": step_anomaly != "normal",
            "anomaly_type": step_anomaly,
        })

    return traces


# ── Log Generator ──────────────────────────────────────────────────────────────

def generate_logs(session_id: str, agent: dict, start_time: datetime, anomaly: str) -> list:
    logs = []
    current_time = start_time

    def log(level, message, error_type=None):
        nonlocal current_time
        current_time += timedelta(seconds=random.uniform(0.5, 3))
        entry = {
            "timestamp":  iso(current_time),
            "_time":      epoch(current_time),
            "event_type": "log",
            "session_id": session_id,
            "agent_id":   agent["id"],
            "agent_name": agent["name"],
            "app":        agent["app"],
            "level":      level,
            "message":    message,
            "error_type": error_type,
        }
        logs.append(entry)

    log("INFO", f"Session started for agent {agent['name']}")
    log("INFO", f"Model loaded: {agent['model']}")

    if anomaly == "hallucination":
        log("INFO", "Processing user query")
        log("INFO", "Tool call: fetch_policy_doc — success")
        log("WARN", "Low confidence score detected: 0.24 — response may be unreliable", "low_confidence")
        log("ERROR", "Hallucination risk flagged: response contradicts source document", "hallucination")

    elif anomaly == "failure_loop":
        log("INFO", "Processing user query")
        for i in range(8):
            log("WARN" if i > 2 else "INFO",
                f"Step validate_input executing (attempt {i+1})",
                "loop_detected" if i > 2 else None)
        log("ERROR", "Max retry limit reached — agent terminated", "failure_loop")

    elif anomaly == "cost_spike":
        log("INFO", "Processing complex multi-step query")
        log("WARN", "Token usage exceeded 5000 — approaching cost threshold", "cost_spike")
        log("ERROR", "Token usage 12,450 — 3x above session baseline", "cost_spike")

    elif anomaly == "null_response_cascade":
        log("INFO", "Calling upstream credit API")
        log("ERROR", "Upstream API returned null response", "null_response")
        log("ERROR", "Cascade failure: 3 downstream steps received null input", "null_response_cascade")

    elif anomaly == "timeout":
        log("INFO", "Processing user query")
        log("WARN", "Step duration exceeding 30s threshold", "slow_response")
        log("ERROR", "Session timeout after 90s — no response from model", "timeout")

    else:  # normal
        log("INFO", "Processing user query")
        log("INFO", "Tool call: search_knowledge_base — success")
        log("INFO", "Response generated — confidence: 0.91")
        log("INFO", "Session completed successfully")

    return logs


# ── Main ───────────────────────────────────────────────────────────────────────

def generate_all(num_sessions: int = 500, days_back: int = 7):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_sessions = []
    all_traces   = []
    all_logs     = []

    base = datetime.utcnow() - timedelta(days=days_back)

    for _ in range(num_sessions):
        anomaly = random.choices(ANOMALY_TYPES, weights=ANOMALY_WEIGHTS, k=1)[0]
        session, session_id, agent, start_time, anomaly = generate_session(base, anomaly)
        traces = generate_traces(session_id, agent, start_time, anomaly)
        logs   = generate_logs(session_id, agent, start_time, anomaly)

        all_sessions.append(session)
        all_traces.extend(traces)
        all_logs.extend(logs)

    # Write output files
    for filename, data in [
        ("sessions.json", all_sessions),
        ("traces.json",   all_traces),
        ("logs.json",     all_logs),
    ]:
        path = os.path.join(OUTPUT_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Generated {len(data):>6} records → {path}")

    print(f"\nDone. {num_sessions} sessions across {days_back} days.")
    print(f"Anomaly breakdown:")
    counts = {}
    for s in all_sessions:
        t = s["anomaly_type"]
        counts[t] = counts.get(t, 0) + 1
    for k, v in sorted(counts.items()):
        print(f"  {k:<30} {v}")


if __name__ == "__main__":
    generate_all(num_sessions=500, days_back=7)

