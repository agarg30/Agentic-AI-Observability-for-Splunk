"""
Modular Input — AI Agent Telemetry Collector
Reads AI agent telemetry JSON files and sends them to Splunk via HEC.

Usage:
  python collector.py                      # send all three files
  python collector.py --file sessions      # send only sessions
  python collector.py --dry-run            # validate without sending

Indexes:
  sessions → agent_sessions
  traces   → agent_traces
  logs     → agent_logs
"""

import json
import os
import sys
import argparse
import urllib.request
import urllib.error
import ssl
from pathlib import Path

# ── Load .env manually (no external deps needed) ──────────────────────────────

def load_env(env_path: Path) -> dict:
    env = {}
    if not env_path.exists():
        print(f"[ERROR] .env file not found at {env_path}")
        sys.exit(1)
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


# ── HEC Sender ─────────────────────────────────────────────────────────────────

class SplunkHECSender:
    def __init__(self, host: str, port: int, token: str, verify_ssl: bool = False):
        self.url = f"https://{host}:{port}/services/collector/event"
        self.token = token
        self.verify_ssl = verify_ssl

    def send_batch(self, events: list, index: str, sourcetype: str) -> tuple[int, int]:
        """Send a list of events to Splunk HEC. Returns (success_count, fail_count)."""
        success = 0
        fail = 0

        # Build batch payload — Splunk HEC accepts newline-delimited JSON
        batch = ""
        for event in events:
            payload = {
                "time":       event.get("_time"),
                "index":      index,
                "sourcetype": sourcetype,
                "event":      event,
            }
            batch += json.dumps(payload) + "\n"

        data = batch.encode("utf-8")
        headers = {
            "Authorization": f"Splunk {self.token}",
            "Content-Type":  "application/json",
        }

        ctx = ssl.create_default_context()
        if not self.verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                if result.get("code") == 0:
                    success = len(events)
                else:
                    print(f"[WARN] HEC response: {result}")
                    fail = len(events)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"[ERROR] HTTP {e.code}: {body}")
            fail = len(events)
        except Exception as e:
            print(f"[ERROR] {e}")
            fail = len(events)

        return success, fail


# ── File Loader ────────────────────────────────────────────────────────────────

def load_json(path: Path) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Main ───────────────────────────────────────────────────────────────────────

FILES_CONFIG = {
    "sessions": {
        "file":       "sessions.json",
        "index":      "agent_sessions",
        "sourcetype": "ai_agent:session",
    },
    "traces": {
        "file":       "traces.json",
        "index":      "agent_traces",
        "sourcetype": "ai_agent:trace",
    },
    "logs": {
        "file":       "logs.json",
        "index":      "agent_logs",
        "sourcetype": "ai_agent:log",
    },
}

BATCH_SIZE = 100  # events per HEC request


def main():
    parser = argparse.ArgumentParser(description="Send AI agent telemetry to Splunk HEC")
    parser.add_argument("--file", choices=["sessions", "traces", "logs"],
                        help="Send only this file type (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Load and validate files without sending to Splunk")
    args = parser.parse_args()

    # Paths
    repo_root   = Path(__file__).parent.parent
    env_path    = repo_root / ".env"
    output_dir  = repo_root / "sample_data" / "output"

    # Load config
    env = load_env(env_path)
    host       = env.get("SPLUNK_HOST", "localhost")
    port       = int(env.get("SPLUNK_PORT", "8088"))
    token      = env.get("SPLUNK_HEC_TOKEN", "")
    verify_ssl = env.get("SPLUNK_VERIFY_SSL", "false").lower() == "true"

    if not token or token == "your-hec-token-here":
        print("[ERROR] SPLUNK_HEC_TOKEN not set in .env")
        sys.exit(1)

    sender = SplunkHECSender(host, port, token, verify_ssl)

    # Decide which files to send
    targets = [args.file] if args.file else list(FILES_CONFIG.keys())

    total_success = 0
    total_fail    = 0

    for target in targets:
        cfg      = FILES_CONFIG[target]
        filepath = output_dir / cfg["file"]

        if not filepath.exists():
            print(f"[SKIP] {filepath} not found — run sample_data/generate.py first")
            continue

        events = load_json(filepath)
        print(f"\n[{target.upper()}] {len(events)} events → index={cfg['index']} sourcetype={cfg['sourcetype']}")

        if args.dry_run:
            print(f"  [DRY RUN] Would send {len(events)} events in {len(events)//BATCH_SIZE + 1} batches")
            continue

        # Send in batches
        for i in range(0, len(events), BATCH_SIZE):
            batch = events[i:i + BATCH_SIZE]
            s, f  = sender.send_batch(batch, cfg["index"], cfg["sourcetype"])
            total_success += s
            total_fail    += f
            print(f"  Batch {i//BATCH_SIZE + 1}: sent {s}, failed {f}")

    if not args.dry_run:
        print(f"\nDone. Total sent: {total_success} | Failed: {total_fail}")


if __name__ == "__main__":
    main()

