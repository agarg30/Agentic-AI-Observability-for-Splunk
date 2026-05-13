# Architecture

## Component Diagram

```
AI Agents (any framework: LangChain, CrewAI, AutoGen, custom)
        │
        ▼
  modular_input/collector.py  ←── reads telemetry via HEC
        │
        ▼
  Splunk Indexes
  ├── agent_traces    (step-by-step agent reasoning + tool calls)
  ├── agent_logs      (errors, warnings, info)
  └── agent_sessions  (session metadata, user, duration, cost)
        │
        ├── Splunk MCP Server       → AI agents query Splunk in natural language
        ├── Splunk AI Assistant     → Human analysts investigate via natural language
        ├── Splunk AI Toolkit       → Anomaly detection models
        └── Foundation-Sec-1.1-8B  → Reasoning over failures
                │
                ▼
        remediation/action_handler.py
        ├── Alert ops team
        ├── Reroute agent traffic
        └── Quarantine bad session
```

## Indexes

| Index | Data | Key Fields |
|---|---|---|
| agent_traces | Step traces, tool calls, model responses | agent_id, session_id, step, tool, confidence |
| agent_logs | Error/warning/info logs | agent_id, level, message, error_type |
| agent_sessions | Session summary | session_id, user, agent_id, tokens, cost, duration |

## Anomaly Types Detected

| Anomaly | Detection Method |
|---|---|
| Hallucination | Low confidence score + inconsistent responses |
| Failure loop | Same step repeating > N times |
| Cost spike | Token usage > 3x baseline in rolling window |
| Tool call anomaly | Unexpected tool called outside normal pattern |
| Timeout | Step duration > threshold |
| Null response cascade | Upstream API returning null propagating through agent |
