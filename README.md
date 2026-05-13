# Agentic AI Observability for Splunk

> Built for the **Splunk AI Hackathon** — Observability Track

AI-powered observability platform for monitoring, analyzing, and auto-remediating AI agent behavior using Splunk MCP Server, AI Toolkit, and Splunk hosted models.

---

## The Problem

### A Real Story — Friday, 11:47 PM

A fintech company just deployed a new AI agent to handle customer loan application queries. The deployment went smoothly. Engineers signed off and went home.

By midnight, the agent started looping — asking customers the same clarifying question repeatedly. By 1 AM, it was returning loan eligibility responses with completely fabricated interest rates. By 2 AM, 400 customers had received wrong information. Support tickets were flooding in.

**Nobody knew.**

The on-call engineer got paged at 2:15 AM. She opened her laptop. Where does she even start?

- The AI agent framework logs? Scattered across 3 services, no central view.
- Token usage spiked — but which agent? Which session? Which user?
- The model started hallucinating at 12:43 AM — but what triggered it?
- Was it the prompt change deployed at 11:52 PM? The new data pipeline? A downstream API timeout?

She spent 90 minutes manually correlating logs across systems before finding the root cause — a single upstream API that started returning null values, which the agent had no guardrail for.

**The fix took 4 minutes. The investigation took 90.**

---

### The Gap

As AI agents become central to business operations, teams have **zero visibility** into what those agents are actually doing in production.

When an agent fails, hallucinates, spikes in cost, or behaves anomalously:
- There is no centralized place to look
- There is no alert that fires on *agent-level* anomalies
- There is no tool that explains *why* it happened in plain English
- There is no automated action to contain the damage

Traditional APM and monitoring tools were built for software systems — request/response, CPU, memory. They were not built for **agentic AI behavior** — multi-step reasoning, tool calls, model confidence, session context, and emergent failures.

**The gap is growing. The cost of that gap is growing faster.**

---

## The Solution

**Agentic AI Observability for Splunk** ingests AI agent telemetry (traces, logs, sessions, tool calls, model responses) into Splunk and provides:

- **Real-time monitoring** — session activity, token usage, latency, error rates
- **Anomaly detection** — hallucinations, unexpected tool calls, cost spikes, failure loops
- **AI-powered analysis** — natural language investigation of agent behavior using Splunk AI Assistant
- **Automated remediation** — alert, reroute, or quarantine misbehaving agents automatically

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. AI Agents  (loan bot, support bot, fraud detector, etc.)        │
│     Emit: session events, tool calls, model responses, costs        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  JSON telemetry
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. modular_input/collector.py  — Telemetry Ingestion               │
│     Reads agent logs → pushes to Splunk via HEC (port 8088)         │
│     sample_data/generate.py generates 500 synthetic agent sessions  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  stored in Splunk indexes
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. Splunk Enterprise  (localhost:8000)                             │
│     Indexes: agent_sessions · agent_traces · agent_logs            │
│     ┌─────────────────────┐   ┌──────────────────────────────────┐ │
│     │  3 Dashboards        │   │  7 Scheduled Alerts              │ │
│     │  · AI Agent Overview │   │  · High anomaly rate             │ │
│     │  · Anomaly Invest.   │   │  · Cost spike detected           │ │
│     │  · Agent Health      │   │  · Hallucination rate            │ │
│     └─────────────────────┘   │  · Failure loop · Timeout · etc. │ │
│                                └────────────────┬─────────────────┘ │
└────────────┬────────────────────────────────────┼────────────────────┘
             │                                    │ alert fires
             │                                    ▼
             │                ┌───────────────────────────────────────┐
             │                │  5. remediation/action_handler.py     │
             │                │     Auto-fixes 5 anomaly types:       │
             │                │     · hallucination → throttle model  │
             │                │     · failure loop → circuit break    │
             │                │     · cost spike → cap token budget   │
             │                │     · null cascade → fallback prompt  │
             │                │     · timeout → reroute agent         │
             │                │     Logs remediation back to Splunk   │
             │                └───────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. Splunk MCP Server  (installed Splunk app, port 8089)            │
│     Exposes 14 tools over Model Context Protocol:                   │
│     · splunk_run_query      → run any SPL search                    │
│     · saia_ask_splunk_question → plain English → Splunk answer      │
│     · saia_generate_spl     → question → SPL                        │
│     · saia_explain_spl      → explain what a query does             │
│     · splunk_run_saved_search → run named alerts/searches           │
│     · splunk_get_indexes, splunk_get_info, + 8 more                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  MCP protocol (HTTPS, port 8089)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  mcp/client.py  — Natural Language Observability Client             │
│  "Which agent had the most failures?" → live Splunk data in seconds │
│                                                                     │
│  python mcp/client.py --query "top failing agents"                  │
│  python mcp/client.py --ask  "why would an agent hallucinate?"      │
│  python mcp/client.py --spl  "index=agent_sessions | stats ..."     │
└─────────────────────────────────────────────────────────────────────┘
```

### How It All Connects — The Demo Story

| Step | What Happens | Which Component |
|------|-------------|-----------------|
| Agent misbehaves at midnight | Emits anomalous session events | AI Agent |
| Events land in Splunk | HEC ingestion in real time | `collector.py` |
| Alert fires at 12:05 AM | Hallucination rate > threshold | `savedsearches.conf` |
| Auto-remediation runs | Model throttled, team notified | `action_handler.py` |
| Engineer investigates at 8 AM | Types a question in plain English | `mcp/client.py` |
| Gets the answer instantly | MCP → SPL → Splunk → results | Splunk MCP Server |

---

## Key Features

| Feature | Description |
|---|---|
| Agent Session Monitoring | Track active sessions, duration, user interactions |
| Token & Cost Tracking | Monitor token usage and cost per agent/session |
| Error & Failure Detection | Detect loops, crashes, timeouts in real time |
| Hallucination Flagging | Score and flag low-confidence or inconsistent responses |
| Natural Language Investigation | Ask questions about agent behavior in plain English |
| Auto-Remediation | Close the loop — act on anomalies automatically |
| Circuit Breaker | Quarantine unhealthy agents; fallback routing keeps users served |
| Automatic Recovery | Health recheck via Splunk after 30 min; restores agent when healthy |

---

## Splunk AI Capabilities Used

- **Splunk MCP Server** — connects AI agents securely to Splunk data
- **Splunk AI Assistant** — natural language to SPL for investigation
- **Splunk AI Toolkit** — custom anomaly detection on agent telemetry
- **Splunk Hosted Models** — Foundation-Sec-1.1-8B for reasoning over failures
- **Splunk Python SDK** — modular input for telemetry ingestion + remediation actions

---

## Project Structure

```
Agentic-AI-Observability-for-Splunk/
├── app/                          # Splunk app (dashboards, searches, alerts)
│   └── default/
│       ├── app.conf              # App metadata
│       ├── indexes.conf          # Custom indexes: agent_sessions, traces, logs
│       ├── savedsearches.conf    # 8 scheduled alerts (incl. unhealthy agent CB)
│       └── data/ui/views/        # 3 Dashboard Studio JSON dashboards
├── mcp/                          # Splunk MCP Server integration
│   ├── client.py                 # MCP client — natural language → SPL → results
│   ├── demo.py                   # Full end-to-end observability demo (10 steps)
│   ├── demoHealthy.py            # Demo 1: MCP queries + auto-remediation (3 min)
│   └── demoCircuitBreaker.py     # Demo 2: circuit breaker quarantine + recovery (3 min)
├── modular_input/                # Python SDK telemetry collector (HEC)
│   └── collector.py              # Sends agent telemetry to Splunk indexes
├── remediation/                  # Auto-remediation scripts
│   ├── action_handler.py         # Alert-triggered remediation (5 anomaly types)
│   ├── circuit_breaker.py        # Circuit breaker: quarantine → fallback → restore
│   └── agent_state.json          # Persisted agent circuit-breaker state
├── sample_data/                  # Synthetic AI agent logs for demo
│   └── generate.py               # Generates 500 sessions with realistic anomalies
├── docs/                         # Documentation
│   ├── architecture.md           # Component diagram and data flow
│   └── mcp_setup.md              # MCP Server setup guide
├── .env.example                  # Environment variable template
└── README.md
```

---

## Quick Start

### 1. Configure environment
```powershell
copy .env.example .env
# Edit .env with your Splunk HEC token, credentials, and MCP server URL
```

### 2. Generate and load synthetic data
```powershell
python sample_data/generate.py       # generates 500 AI agent sessions
python modular_input/collector.py    # sends events to Splunk via HEC
```

### 3. View dashboards in Splunk
Open Splunk Web → Search & Reporting → Dashboards:
- **AI Agent Overview** — KPIs, trends, agent comparison
- **Anomaly Investigation** — hallucinations, failure loops, cost spikes
- **Agent Health** — per-agent health scoring and latency

### 4. Query via MCP (natural language)
```powershell
python mcp/client.py --query "top failing agents"
python mcp/client.py --query "anomaly summary"
python mcp/client.py --query "cost breakdown by agent"
python mcp/client.py --ask  "why would an agent hallucinate?"
python mcp/client.py --spl  "index=agent_sessions | stats count by status"
python mcp/client.py --list-tools    # see all 14 MCP tools
```

### 5. Run Demo 1 — MCP Queries + Auto-Remediation (3 min)
```powershell
python mcp/demoHealthy.py
```
Covers: MCP connection → agent health check → anomaly detection → cost analysis → auto-remediation firing → Splunk audit trail

### 6. Run Demo 2 — Circuit Breaker (3 min)
```powershell
python mcp/demoCircuitBreaker.py
```
Covers: detect unhealthy agent → quarantine → fallback routing (users kept served) → health recheck → automatic restore

### 7. Circuit Breaker — manual controls
```powershell
# Check status of all agents
python remediation/circuit_breaker.py --action status

# Quarantine an agent manually
python remediation/circuit_breaker.py --action quarantine --agent_id agent-loan-001

# Restore an agent manually
python remediation/circuit_breaker.py --action restore --agent_id agent-loan-001

# Run health recheck on all quarantined agents now
python remediation/circuit_breaker.py --action check

# Background monitor loop (checks every 5 min, auto-restores when healthy)
python remediation/circuit_breaker.py --action monitor
```

### 8. Test auto-remediation directly
```powershell
python remediation/action_handler.py --anomaly_type failure_loop --agent_id agent-loan-001 --session_id session-001
python remediation/action_handler.py --anomaly_type hallucination --agent_id agent-fraud-003 --session_id session-002
python remediation/action_handler.py --anomaly_type cost_spike --agent_id agent-support-002 --session_id session-003
```

---

## Circuit Breaker — How It Works

```
  Agent failure rate > 30%
         │
         ▼
  ┌─────────────┐   quarantine_agent()     ┌──────────────────────┐
  │   CLOSED    │ ──────────────────────►  │   OPEN (quarantined) │
  │  (healthy)  │                          │   calls BLOCKED 30min│
  └─────────────┘                          └──────────┬───────────┘
         ▲                                            │ fallback routing
         │                               users routed to backup agent
         │ failure_rate ≤ 30%                         │
         │                                            ▼
  restore_agent()          ◄──────────  ┌──────────────────────┐
                                         │  HALF-OPEN           │
                                         │  (health recheck)    │
                                         │  queries Splunk live │
                                         └──────────────────────┘
```

**Key behaviour:**
- While an agent is quarantined, `route_call()` transparently redirects calls to a **fallback agent** — users are never blocked
- If both primary and fallback are down, users receive a graceful **"temporarily unavailable"** message instead of a crash
- After 30 minutes, the health recheck queries **live Splunk data** — no manual intervention needed
- All state changes are logged to `index=agent_logs sourcetype=ai_agent:circuit_breaker` for full audit trail

---

## Hackathon Track

**Observability** — Splunk AI Hackathon 2026

---

## License

MIT License — see [LICENSE](LICENSE)

