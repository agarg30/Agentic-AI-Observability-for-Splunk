"""
Splunk MCP Client — Agentic AI Observability
Connects to the Splunk MCP Server using the official MCP Python SDK
(SSE transport — as used by the Splunk MCP Server app v1.1.x).

Usage:
  python mcp/client.py                        # interactive mode
  python mcp/client.py --query "which agent had the most failures today?"
  python mcp/client.py --list-tools           # list all MCP tools
  python mcp/client.py --spl "index=agent_sessions | stats count by agent_id"

Configuration (via .env):
  MCP_SERVER_URL   https://localhost:8089
  MCP_AUTH_TOKEN   Splunk Bearer token (Settings → Tokens → New Token)
"""

import asyncio
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Any

import httpx
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)


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


# ── SPL queries ───────────────────────────────────────────────────────────────

def spl_top_failing() -> str:
    return ('index=agent_sessions status="failed" '
            '| stats count as failures by agent_id | sort -failures | head 5')

def spl_anomaly_summary() -> str:
    return ('index=agent_sessions anomaly_type!="none" '
            '| stats count by anomaly_type | sort -count')

def spl_cost_by_agent() -> str:
    return ('index=agent_sessions '
            '| stats sum(total_cost_usd) as total_cost avg(total_cost_usd) as avg_cost by agent_id '
            '| eval total_cost=round(total_cost,4), avg_cost=round(avg_cost,4) | sort -total_cost')

def spl_critical_events() -> str:
    return ('index=agent_logs severity IN ("critical","high") '
            '| fields _time,agent_id,message,severity,anomaly_type | sort -_time | head 20')

def spl_hallucinations() -> str:
    return ('index=agent_sessions anomaly_type=hallucination '
            '| fields _time,session_id,agent_id,model,confidence_score | sort -_time')

def spl_agent_health() -> str:
    return ('index=agent_sessions '
            '| stats count as total count(eval(status="success")) as successes '
            'count(eval(anomaly_type!="none")) as anomalies '
            'avg(duration_ms) as avg_latency sum(total_cost_usd) as cost by agent_id '
            '| eval success_rate=round(successes/total*100,1) '
            '| eval anomaly_rate=round(anomalies/total*100,1) '
            '| eval avg_latency=round(avg_latency,0) | eval cost=round(cost,4) '
            '| sort -success_rate')


# ── Async MCP session ─────────────────────────────────────────────────────────

async def run_with_session(server_url: str, token: str, action):
    """
    Opens a Streamable HTTP session to the Splunk MCP Server and runs `action(session)`.
    """
    mcp_url = f"{server_url.rstrip('/')}/services/mcp"
    auth_headers = {"Authorization": f"Bearer {token}"}

    # The SDK calls factory(headers=..., timeout=..., auth=...) — we add verify=False
    def make_client(headers=None, timeout=None, auth=None):
        merged = dict(headers or {})
        merged.update(auth_headers)
        return httpx.AsyncClient(verify=False, headers=merged, timeout=timeout or 30, auth=auth)

    async with streamablehttp_client(url=mcp_url, headers=auth_headers,
                                     httpx_client_factory=make_client) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await action(session)


async def list_tools_async(server_url: str, token: str) -> list:
    async def _action(session: ClientSession):
        result = await session.list_tools()
        return result.tools
    return await run_with_session(server_url, token, _action)


async def call_spl_async(server_url: str, token: str, spl: str,
                          earliest: str = "-7d", latest: str = "now") -> str:
    async def _action(session: ClientSession):
        # Splunk MCP Server v1.1 exposes 'splunk_run_query'
        result = await session.call_tool("splunk_run_query", {
            "query": spl,
            "earliest_time": earliest,
            "latest_time": latest,
        })
        texts = [c.text for c in result.content if hasattr(c, "text")]
        return "\n".join(texts) if texts else str(result)

    return await run_with_session(server_url, token, _action)


async def ask_splunk_async(server_url: str, token: str, question: str) -> str:
    """Use the Splunk AI Assistant (saia_ask_splunk_question) for natural language questions."""
    async def _action(session: ClientSession):
        result = await session.call_tool("saia_ask_splunk_question", {
            "question": question,
        })
        texts = [c.text for c in result.content if hasattr(c, "text")]
        return "\n".join(texts) if texts else str(result)

    return await run_with_session(server_url, token, _action)


async def generate_spl_async(server_url: str, token: str, question: str) -> str:
    """Use saia_generate_spl to convert natural language to SPL."""
    async def _action(session: ClientSession):
        result = await session.call_tool("saia_generate_spl", {
            "query": question,
        })
        texts = [c.text for c in result.content if hasattr(c, "text")]
        return "\n".join(texts) if texts else str(result)

    return await run_with_session(server_url, token, _action)


# ── Sync wrappers (for CLI use) ───────────────────────────────────────────────

def list_tools(server_url: str, token: str) -> list:
    return asyncio.run(list_tools_async(server_url, token))

def query_spl(server_url: str, token: str, spl: str,
              earliest: str = "-7d", latest: str = "now") -> str:
    return asyncio.run(call_spl_async(server_url, token, spl, earliest, latest))

def ask_splunk(server_url: str, token: str, question: str) -> str:
    return asyncio.run(ask_splunk_async(server_url, token, question))

def generate_spl(server_url: str, token: str, question: str) -> str:
    return asyncio.run(generate_spl_async(server_url, token, question))


# ── Natural language → SPL mapping ───────────────────────────────────────────

NL_MAP = {
    "top failing agents":  ("Top Failing Agents (7d)",       spl_top_failing),
    "failing agents":      ("Top Failing Agents (7d)",       spl_top_failing),
    "most failures":       ("Top Failing Agents (7d)",       spl_top_failing),
    "anomaly summary":     ("Anomaly Summary (7d)",          spl_anomaly_summary),
    "anomaly breakdown":   ("Anomaly Summary (7d)",          spl_anomaly_summary),
    "anomaly types":       ("Anomaly Summary (7d)",          spl_anomaly_summary),
    "cost by agent":       ("Cost by Agent (7d)",            spl_cost_by_agent),
    "cost breakdown":      ("Cost by Agent (7d)",            spl_cost_by_agent),
    "token cost":          ("Cost by Agent (7d)",            spl_cost_by_agent),
    "critical events":     ("Recent Critical Events",        spl_critical_events),
    "recent errors":       ("Recent Critical Events",        spl_critical_events),
    "high severity":       ("Recent Critical Events",        spl_critical_events),
    "hallucination":       ("Hallucination Events (7d)",     spl_hallucinations),
    "hallucinations":      ("Hallucination Events (7d)",     spl_hallucinations),
    "agent health":        ("Agent Health Summary (7d)",     spl_agent_health),
    "health summary":      ("Agent Health Summary (7d)",     spl_agent_health),
}


def natural_language_query(server_url: str, token: str, question: str) -> tuple[str, str]:
    q = question.lower()
    for phrase, (title, spl_fn) in NL_MAP.items():
        if phrase in q:
            return title, query_spl(server_url, token, spl_fn())
    # Unknown — use Splunk AI Assistant for true NL query
    log.info("No preset match found — using saia_ask_splunk_question")
    return f"AI Answer: {question}", ask_splunk(server_url, token, question)


# ── CLI ────────────────────────────────────────────────────────────────────────

PRESET_QUESTIONS = [
    "Which agent had the most failures today?",
    "Show me all anomaly types in the last 24 hours",
    "What is the cost breakdown by agent?",
    "Show recent critical and high severity events",
    "List all hallucination events",
    "Give me the agent health summary for the week",
]


def print_banner():
    print("\n" + "=" * 70)
    print("  Agentic AI Observability — Splunk MCP Client")
    print("  Natural language → SPL → Splunk data")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Splunk MCP Client")
    parser.add_argument("--query",        help="Natural language question (uses preset SPL or AI fallback)")
    parser.add_argument("--ask",          help="Ask Splunk AI Assistant directly (saia_ask_splunk_question)")
    parser.add_argument("--generate-spl", help="Generate SPL from natural language (saia_generate_spl)")
    parser.add_argument("--spl",          help="Run a raw SPL query")
    parser.add_argument("--list-tools",   action="store_true")
    parser.add_argument("--demo",         action="store_true")
    parser.add_argument("--server",       default="")
    args = parser.parse_args()

    env = load_env()
    server_url = args.server or env.get("MCP_SERVER_URL", "https://localhost:8089")
    token = env.get("MCP_AUTH_TOKEN", "")

    if not token:
        log.error("MCP_AUTH_TOKEN is not set in .env")
        log.error("Go to Splunk Web → Settings → Tokens → New Token")
        sys.exit(1)

    log.info(f"Connecting to Splunk MCP Server at {server_url}/services/mcp")

    if args.list_tools:
        tools = list_tools(server_url, token)
        print(f"\n{len(tools)} tools available:\n")
        for t in tools:
            desc = (t.description or "")[:72]
            print(f"  • {t.name}: {desc}")
        print()
        return

    if args.spl:
        print(query_spl(server_url, token, args.spl))
        return

    if args.ask:
        print(f"\n[Splunk AI Answer]\n{ask_splunk(server_url, token, args.ask)}\n")
        return

    if args.generate_spl:
        print(f"\n[Generated SPL]\n{generate_spl(server_url, token, args.generate_spl)}\n")
        return

    if args.query:
        title, result = natural_language_query(server_url, token, args.query)
        print(f"\n[{title}]\n{result}\n")
        return

    if args.demo:
        print_banner()
        for question in PRESET_QUESTIONS:
            print(f"▶ {question}")
            print("-" * 60)
            try:
                title, result = natural_language_query(server_url, token, question)
                print(result)
            except Exception as e:
                print(f"  [Error] {e}")
            print()
        return

    # Interactive mode
    print_banner()
    print("Type a question or 'exit' to quit. Examples:")
    for q in PRESET_QUESTIONS:
        print(f"  • {q}")
    print()
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if question.lower() in ("exit", "quit", "q"):
            break
        if not question:
            continue
        try:
            title, result = natural_language_query(server_url, token, question)
            print(f"\n[{title}]\n{result}\n")
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
