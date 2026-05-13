# Splunk MCP Server Setup Guide

This document explains how to configure the **Splunk MCP Server** app to enable
natural-language querying of AI agent observability data.

---

## Prerequisites

- Splunk Enterprise or Splunk Cloud (version 9.x+)
- [Splunk MCP Server app](https://splunkbase.splunk.com/app/7892) installed
- Python 3.10+ on the client machine
- This project's `.env` configured

---

## Step 1 — Install the Splunk MCP Server App

1. Log into Splunk Web → **Apps → Find More Apps**
2. Search for **"MCP Server"** or browse to Splunkbase app ID 7892
3. Click **Install** and restart Splunk if prompted

Or download from Splunkbase and install via:
```
Settings → Apps → Install app from file
```

---

## Step 2 — Configure the MCP Server

After installation, configure it at:
```
Settings → MCP Server → Configuration
```

Key settings:
| Setting | Value |
|---|---|
| Enable MCP Server | ✓ Enabled |
| Port | `8001` (default) |
| Authentication | Token or Basic Auth |
| Allowed Indexes | `agent_sessions, agent_traces, agent_logs` |
| Max search results | `1000` |

If using token auth, generate a token at:
```
Settings → Tokens → New Token
```

Then add it to your `.env`:
```
MCP_AUTH_TOKEN=<your-token>
MCP_SERVER_URL=http://localhost:8001
```

---

## Step 3 — Verify MCP Server is Running

Test with curl (from your machine):
```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"test","version":"1.0"},"capabilities":{}}}'
```

Expected response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "serverInfo": { "name": "Splunk MCP Server", "version": "..." }
  }
}
```

---

## Step 4 — List Available Tools

```bash
python mcp/client.py --list-tools
```

The Splunk MCP Server exposes tools such as:
- `run_search` — execute SPL queries
- `ask_question` — natural language → SPL translation using AI
- `list_indexes` — list available indexes
- `get_field_summary` — field statistics for an index
- `get_saved_searches` — list saved searches/alerts

---

## Step 5 — Run the MCP Client

**Interactive mode** (ask any question):
```bash
python mcp/client.py
```

**Single question:**
```bash
python mcp/client.py --query "Which agent had the most failures today?"
```

**Run a raw SPL query:**
```bash
python mcp/client.py --spl "index=agent_sessions | stats count by agent_id"
```

**Full observability demo:**
```bash
python mcp/demo.py
```

---

## Step 6 — How It Works

```
You (or an AI agent)
       │
       │  Natural language question
       ▼
 MCP Client (mcp/client.py)
       │
       │  JSON-RPC 2.0 POST /mcp
       ▼
 Splunk MCP Server
       │
       │  Translates NL → SPL via Splunk AI Toolkit
       ▼
 Splunk Search Head
       │
       │  Runs SPL against indexes
       ▼
 agent_sessions / agent_traces / agent_logs
       │
       │  Structured results
       ▼
 MCP Client → display / trigger remediation
```

---

## Available Observability Queries

The client has 6 built-in observability queries:

| Query | Description |
|---|---|
| `get_top_failing_agents()` | Which agents failed most in last 24h |
| `get_anomaly_summary()` | Count of each anomaly type (24h) |
| `get_cost_by_agent()` | Token cost per agent (24h) |
| `get_recent_critical_events()` | Critical/high severity events (1h) |
| `get_hallucination_events()` | Hallucination-flagged sessions (24h) |
| `get_agent_health_summary()` | Full health score per agent (7 days) |

Natural language phrases mapped automatically:
- `"most failures"` → `get_top_failing_agents()`
- `"anomaly types"` → `get_anomaly_summary()`
- `"cost breakdown"` → `get_cost_by_agent()`
- `"critical events"` → `get_recent_critical_events()`
- `"hallucination"` → `get_hallucination_events()`
- `"agent health"` → `get_agent_health_summary()`

---

## Troubleshooting

**"Cannot reach MCP server"**
- Confirm the MCP Server app is installed and enabled
- Check the port in `.env` matches the configured port
- If Splunk is on a remote host, update `MCP_SERVER_URL` accordingly

**"HTTP 401 Unauthorized"**
- Check `MCP_AUTH_TOKEN` or `SPLUNK_USERNAME`/`SPLUNK_PASSWORD` in `.env`
- Ensure the token hasn't expired (Settings → Tokens)

**"Tools list is empty"**
- MCP Server may need additional configuration in Splunk UI
- Check Splunk internal logs: `index=_internal source=*mcp*`

**Running `mcp/demo.py` with no MCP Server**
- The demo automatically switches to **simulation mode** showing expected outputs
- Useful for presentations when Splunk is not accessible
