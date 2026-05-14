# Architecture Diagram — Agentic AI Observability for Splunk

## How the Solution Works

### Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        AGENTIC AI OBSERVABILITY FOR SPLUNK                   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  1. AI Agents in Production                                         │   │
│   │     (loan bot · support bot · fraud detector · any LLM agent)      │   │
│   │     Emit: session events · tool calls · model responses · costs     │   │
│   └─────────────────────────────┬───────────────────────────────────────┘   │
│                                 │  JSON telemetry (traces, logs, sessions)   │
│                                 ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  2. Telemetry Ingestion  [modular_input/collector.py]               │   │
│   │     Reads agent log files → pushes to Splunk via HEC (port 8088)   │   │
│   │     sample_data/generate.py  →  500 synthetic agent sessions        │   │
│   └─────────────────────────────┬───────────────────────────────────────┘   │
│                                 │  HTTP POST to Splunk HEC                   │
│                                 ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  3. Splunk Enterprise  (localhost:8000 / 8089)                      │   │
│   │                                                                     │   │
│   │   Indexes:                    Dashboards:                           │   │
│   │   ├── agent_sessions          ├── AI Agent Overview (KPIs, trends)  │   │
│   │   ├── agent_traces            ├── Anomaly Investigation             │   │
│   │   └── agent_logs              └── Agent Health (scores, latency)    │   │
│   │                                                                     │   │
│   │   Scheduled Alerts (8):                                             │   │
│   │   ├── High anomaly rate       ├── Timeout storm                     │   │
│   │   ├── Cost spike detected     ├── Null response cascade             │   │
│   │   ├── Hallucination surge     ├── Agent silent (no events)          │   │
│   │   ├── Failure loop storm      └── Unhealthy agent → circuit breaker │   │
│   └──────────────┬──────────────────────────┬───────────────────────────┘   │
│                  │  alert fires              │  SPL query interface          │
│                  ▼                           ▼                               │
│   ┌─────────────────────────┐   ┌──────────────────────────────────────┐   │
│   │  4. Auto-Remediation    │   │  5. Splunk MCP Server  (port 8089)   │   │
│   │  [remediation/]         │   │     Exposes 14 tools over MCP:       │   │
│   │                         │   │     · splunk_run_query (SPL)         │   │
│   │  action_handler.py:     │   │     · saia_ask_splunk_question        │   │
│   │  · hallucination →      │   │     · saia_generate_spl              │   │
│   │    throttle model        │   │     · saia_explain_spl               │   │
│   │  · failure loop →        │   │     · splunk_run_saved_search        │   │
│   │    circuit break         │   │     · splunk_get_indexes + 9 more    │   │
│   │  · cost spike →          │   └─────────────────┬────────────────────┘   │
│   │    cap token budget       │                     │  MCP protocol (HTTPS)  │
│   │  · null cascade →         │                     ▼                        │
│   │    fallback prompt        │   ┌──────────────────────────────────────┐   │
│   │  · timeout →              │   │  6. MCP Client  [mcp/client.py]      │   │
│   │    reroute agent          │   │     Natural language → SPL → results  │   │
│   │                           │   │                                      │   │
│   │  circuit_breaker.py:      │   │  "Which agent had most failures?"    │   │
│   │  CLOSED → OPEN →          │   │  → live Splunk answer in seconds     │   │
│   │  HALF-OPEN → CLOSED       │   └──────────────────────────────────────┘   │
│   └─────────────────────────┘                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## How the Application Interacts with Splunk

| Integration Point | Mechanism | Component |
|---|---|---|
| Telemetry ingestion | Splunk HEC (HTTP Event Collector, port 8088) | `modular_input/collector.py` |
| Dashboards & alerts | Splunk app (app/default/) installed on Splunk instance | `app/` |
| Scheduled alerts | `savedsearches.conf` — 8 alert definitions with SPL searches | `app/default/savedsearches.conf` |
| Custom indexes | `indexes.conf` — agent_sessions, agent_traces, agent_logs | `app/default/indexes.conf` |
| Remediation feedback | HEC write-back — logs remediation events to `index=agent_logs` | `remediation/action_handler.py` |
| Natural language queries | Splunk MCP Server over HTTPS (port 8089) | `mcp/client.py` |
| SPL queries via SDK | Splunk REST API via `urllib` (no extra SDK dependency) | `remediation/circuit_breaker.py` |

---

## How AI Models and Agents Are Integrated

| AI Capability | Role in Solution | Where Used |
|---|---|---|
| **Splunk MCP Server** | Connects AI clients to Splunk data via Model Context Protocol; exposes 14 tools | `mcp/client.py` |
| **Splunk AI Assistant** (`saia_ask_splunk_question`) | Natural language questions → Splunk answers for human investigation | `mcp/client.py --ask` |
| **Splunk AI Assistant** (`saia_generate_spl`) | Natural language → generated SPL query | `mcp/client.py --query` |
| **Splunk AI Toolkit** | Anomaly detection models running over agent telemetry indexes | `app/default/savedsearches.conf` |
| **Foundation-Sec-1.1-8B** (Splunk hosted model) | Reasoning over agent failure patterns, root cause analysis | Alert-triggered analysis |

---

## Data Flow

```
AI Agent Telemetry
        │
        │  (JSON: session_id, agent_id, tokens, cost,
        │   tool_calls, confidence_score, error_type, ...)
        │
        ▼
collector.py  ──[HEC POST]──►  Splunk Index
                                    │
                    ┌───────────────┼────────────────┐
                    ▼               ▼                ▼
             agent_sessions   agent_traces      agent_logs
                    │               │                │
                    └───────────────┼────────────────┘
                                    │
                          ┌─────────┴────────┐
                          ▼                  ▼
                   Scheduled Alerts     Dashboards
                   (SPL searches)       (JSON views)
                          │
                     alert fires
                          │
                          ▼
                  action_handler.py
                  circuit_breaker.py
                          │
                  ┌───────┴──────────┐
                  ▼                  ▼
          Remediation action   Write-back to
          (throttle/reroute/   index=agent_logs
           quarantine/restore)  (audit trail)


Natural Language Investigation Path:
  Engineer → mcp/client.py → Splunk MCP Server (port 8089)
           → saia_ask_splunk_question / saia_generate_spl
           → Splunk index query
           → Plain-English answer
```

---

## Component Summary

| Component | File(s) | Purpose |
|---|---|---|
| Splunk App | `app/` | Dashboards, indexes, scheduled alerts |
| Telemetry Collector | `modular_input/collector.py` | Push agent events to Splunk via HEC |
| Sample Data Generator | `sample_data/generate.py` | Generate 500 synthetic agent sessions for demo |
| MCP Client | `mcp/client.py` | Natural language observability queries via MCP |
| Demo Scripts | `mcp/demoHealthy.py`, `mcp/demoCircuitBreaker.py` | End-to-end 3-minute demos |
| Auto-Remediation | `remediation/action_handler.py` | Alert-triggered anomaly response (5 types) |
| Circuit Breaker | `remediation/circuit_breaker.py` | Quarantine unhealthy agents; auto-restore |
| Agent State | `remediation/agent_state.json` | Persisted circuit breaker state |
| Environment Config | `.env.example` | Template for Splunk credentials and URLs |
