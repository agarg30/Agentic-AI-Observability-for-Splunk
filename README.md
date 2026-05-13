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
AI Agents (any framework)
        │
        ▼
  Telemetry Collector (Python SDK modular input)
        │
        ▼
  Splunk Enterprise (indexes: agent_traces, agent_logs, agent_sessions)
        │
        ├── Splunk MCP Server ──► AI Agent queries Splunk data via natural language
        │
        ├── Splunk AI Assistant ──► SPL generation for ad-hoc investigation
        │
        ├── Splunk AI Toolkit ──► Anomaly detection models on agent behavior
        │
        └── Foundation-Sec-1.1-8B (Hosted Model) ──► Reasoning over agent failures
                │
                ▼
        Automated Remediation Actions (Python SDK)
        - Trigger alerts
        - Reroute agent traffic
        - Quarantine misbehaving agents
```

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
├── app/                        # Splunk app (dashboards, searches, alerts)
├── modular_input/              # Python SDK telemetry collector
├── remediation/                # Auto-remediation scripts
├── sample_data/                # Synthetic AI agent logs for demo
├── docs/                       # Architecture diagrams and documentation
└── README.md
```

---

## Hackathon Track

**Observability** — Splunk AI Hackathon 2026

---

## License

MIT License — see [LICENSE](LICENSE)

