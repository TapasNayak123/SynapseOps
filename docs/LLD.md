# SynapseOps — Low-Level Design Document

**Version**: 1.0  
**Last Updated**: March 2026  
**Authors**: SynapseOps Engineering Team

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Technology Stack](#3-technology-stack)
4. [Module Breakdown](#4-module-breakdown)
5. [Data Flow Diagrams](#5-data-flow-diagrams)
6. [Database Design](#6-database-design)
7. [API Reference](#7-api-reference)
8. [Multi-Agent PR Analysis Pipeline](#8-multi-agent-pr-analysis-pipeline)
9. [Pipeline Monitoring & Auto-Healing](#9-pipeline-monitoring--auto-healing)
10. [API Monitoring Engine](#10-api-monitoring-engine)
11. [Chat Engine](#11-chat-engine)
12. [Deployment Gate](#12-deployment-gate)
13. [Auto-Fix Engine](#13-auto-fix-engine)
14. [Conflict Detection](#14-conflict-detection)
15. [Real-Time Communication (WebSocket)](#15-real-time-communication-websocket)
16. [Caching & Deduplication](#16-caching--deduplication)
17. [Error Handling & Resilience](#17-error-handling--resilience)
18. [Security](#18-security)
19. [Deployment Architecture](#19-deployment-architecture)
20. [Configuration Management](#20-configuration-management)
21. [Diagnostic Tool](#21-diagnostic-tool)
22. [File Structure Reference](#22-file-structure-reference)

---

## 1. System Overview

> **Why "SynapseOps"?** — In biology, a *synapse* is the junction between nerve cells where signals are transmitted, triggering rapid, intelligent responses. SynapseOps is the nervous system of your DevOps workflow — it connects GitHub, CloudWatch, Kubernetes, and Teams, processing signals and making autonomous decisions in real time.

SynapseOps is an AI-powered DevOps monitoring and observability platform that provides:

- Multi-agent PR code review with risk assessment and auto-description generation
- GitHub Actions pipeline failure detection, root cause analysis, and auto-healing
- Real-time API monitoring via CloudWatch Logs with predictive alerting
- AI-driven deployment gating based on live traffic health
- Natural language chat interface for infrastructure queries (18 intents)
- Anomaly detection (z-score), SLA tracking, and incident correlation
- Auto-fix engine with error categorization and automated PR generation
- PR conflict detection across open pull requests
- Real-time notifications via WebSocket and Microsoft Teams (Adaptive Cards)
- PR approve/reject actions from Teams cards

The platform monitors a target application's APIs (e.g., `/api/auth/login`, `/api/auth/register`, `/api/products`) by analyzing CloudWatch log streams, and manages the full CI/CD lifecycle through GitHub webhook integration.

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BROWSER (UI Layer)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │Dashboard │ │Pipelines │ │ Metrics  │ │ Activity │ │PR Detail │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│       │            │            │            │            │        │
│  ┌────┴────────────┴────────────┴────────────┴────────────┘        │
│  │  Chat Widget (all pages) ── WebSocket ── Notifications          │
│  └─────────────────────────────┬───────────────────────────────────│
└────────────────────────────────┼───────────────────────────────────┘
                                 │ HTTP / WebSocket
┌────────────────────────────────┼───────────────────────────────────┐
│                    FastAPI Application (Port 5000)                  │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  Routes     │  │  Services    │  │  Background  │               │
│  │  ─────────  │  │  ──────────  │  │  ──────────  │               │
│  │  /webhook   │  │  ChatEngine  │  │  APScheduler │               │
│  │  /api/chat  │  │  CloudWatch  │  │  (7 jobs)    │               │
│  │  /api/metr* │  │  LLM         │  │              │               │
│  │  /api/alert*│  │  ErrorAnalyz │  │  Webhook     │               │
│  │  /ws/*      │  │  Anomaly     │  │  Handlers    │               │
│  │  /dashboard │  │  SLA         │  │  (threads)   │               │
│  │  /metrics   │  │  DeployGate  │  │              │               │
│  │  /pipelines │  │  AutoFix     │  │              │               │
│  │  /activity  │  │  K8sClient   │  │              │               │
│  │  /action/*  │  │  CodeAnalyz  │  │              │               │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                │                 │                        │
│  ┌──────┴────────────────┴─────────────────┴───────────────────┐   │
│  │                    External Services                         │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │   │
│  │  │ Bedrock  │ │ DynamoDB │ │CloudWatch│ │  Redis   │       │   │
│  │  │(Multi-   │ │(5 tables)│ │  Logs    │ │ (cache)  │       │   │
│  │  │ model)   │ │          │ │ Insights │ │          │       │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │   │
│  │  │ GitHub   │ │  Teams   │ │Kubernetes│                    │   │
│  │  │   API    │ │ Webhook  │ │ (kubectl)│                    │   │
│  │  └──────────┘ └──────────┘ └──────────┘                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|----------|
| Runtime | Python 3.11 | Application language |
| Framework | FastAPI + Uvicorn | Async HTTP server with WebSocket support |
| LLM | Amazon Bedrock (multi-model) | AI inference — supports Anthropic Claude, Amazon Nova, Meta Llama |
| Database | Amazon DynamoDB | Persistent storage (PRs, pipelines, alerts, metrics, audit) |
| Log Analysis | Amazon CloudWatch Logs Insights | Production API log querying with stream-scan fallback |
| Cache | Redis (optional, graceful degradation) | Caching, rate limiting, deduplication, SLA targets |
| Container | Docker (python:3.11-slim, non-root) | Application packaging with health checks |
| Orchestration | Amazon EKS + Helm | Kubernetes deployment with liveness/readiness probes |
| CI/CD | GitHub Actions | Build, test, deploy pipeline |
| Notifications | Microsoft Teams (Adaptive Cards v1.4) | Alert and event notifications via Power Automate webhook |
| Templates | Jinja2 | Server-side HTML rendering |
| Logging | structlog (JSON) | Structured logging throughout |
| Kubernetes | kubectl (subprocess) | Pod, node, service, deployment status queries |
| HTTP Client | httpx (Teams), requests (GitHub) | Connection-pooled HTTP with retry |

---

## 4. Module Breakdown

### 4.1 Entry Point & Configuration

| File | Purpose |
|------|----------|
| `app.py` | Entry point — runs `uvicorn` on `app.main:app`, reads `PORT` env var (default 5000) |
| `app/main.py` | FastAPI app definition, lifespan management, route registration, webhook handlers, PR action endpoints, NoCacheHTMLMiddleware |
| `app/config.py` | Pydantic `BaseSettings` — all configuration via environment variables with validators |
| `config.py` | Root re-export of `app/config.py` settings for backward compatibility |
| `app/models/schemas.py` | Pydantic models: `ChatRequest`, `ChatResponse`, `HttpStatusCategory` enum |

### 4.2 Services Layer (`app/services/`)

| File | Class/Function | Responsibility |
|------|---------------|----------------|
| `llm.py` | `LLMService` | Bedrock multi-model invocation (Anthropic/Nova/Meta/Converse), retry, error analysis, chat |
| `cloudwatch.py` | `CloudWatchService` | CloudWatch Logs Insights queries + stream-scan fallback, API metrics, latency, top/slowest APIs |
| `chat_engine.py` | `ChatEngine` | Intent classification (keyword + LLM + hard override), 18 intent handlers, data fetching, LLM response |
| `error_analyzer.py` | `ErrorAnalyzer` | Error aggregation by status code, threshold alerting with cooldown, error breakdown |
| `log_analyzer.py` | `LogAnalyzer` | Log search, correlation ID tracing, top APIs, API history |
| `anomaly_detector.py` | `AnomalyDetector` | Traffic anomaly detection (z-score), predictive error trend (linear regression) |
| `performance.py` | `PerformanceAnalyzer` | Slowest APIs with LLM optimization suggestions, composite health score |
| `sla_tracker.py` | `SLATracker` | SLA compliance checking (availability, latency, error rate) with configurable per-API targets |
| `deployment_tracker.py` | `DeploymentTracker` | GitHub Actions deployment tracking, error-deployment correlation (30-min window) |
| `deployment_gate.py` | `DeploymentGate` | AI-driven hold/release decision, held deployment management, periodic recheck |
| `incident_analyzer.py` | `IncidentAnalyzer` | Incident timeline, period-over-period comparison, recurring error detection (fingerprinting) |
| `auto_fix.py` | `AutoFixService` | Error analysis with source code context, LLM fix generation, auto-fix PR creation |
| `code_analyzer.py` | `CodeAnalyzer` | Node.js error categorization (12 categories), stack trace parsing, GitHub source fetching |
| `k8s_client.py` | `K8sClient` | Kubernetes API via kubectl — pods, nodes, services, deployments, cluster info, resource usage |
| `cache.py` | `CacheService` | Redis connection with graceful degradation, rate limiting (Lua script), alert cooldown |
| `dynamodb.py` | `DynamoDBService` | DynamoDB operations — alerts, metrics, audit logs with Decimal handling |
| `websocket_manager.py` | `ConnectionManager` | WebSocket connection management — activity, chat, notifications with streaming |
| `notifier.py` | `NotifierService` | Teams Adaptive Card notifications with cooldown, httpx connection pooling |
| `retry.py` | `retry_with_backoff` | Decorator for exponential backoff retry with jitter |
| `dedup.py` | `is_duplicate()` | Redis-backed deduplication with in-memory fallback (bounded set, 10K cap) |

### 4.3 Root-Level Modules

| File | Purpose |
|------|----------|
| `agents.py` | Multi-agent PR analysis — 5 specialized agents + supervisor orchestrator + description generator |
| `bedrock_client.py` | Backward-compatible Bedrock API client (delegates to `LLMService`) |
| `github_client.py` | GitHub REST API wrapper with retry — PRs, diffs, files, comments, merges, file CRUD, workflow rerun |
| `pipeline_monitor.py` | GitHub Actions workflow run failure analysis, log fetching, LLM root cause analysis |
| `auto_healer.py` | Auto-fix PR generation for pipeline failures — fix generation, branch creation, PR opening |
| `conflict_detector.py` | Detects file-level conflicts between open PRs, posts comments, Teams notification |
| `teams_notifier.py` | PR summary Teams notification with approve/reject action buttons |
| `activity_log.py` | Centralized activity log — DynamoDB-persisted, in-memory cached (500 cap), WebSocket broadcast |
| `store.py` | DynamoDB-backed stores: `PRStore` (with stats/metrics) and `PipelineStore` |
| `diagnose.py` | CLI diagnostic tool — checks env, dependencies, server, AWS, Redis, GitHub token, Teams webhook |

### 4.4 Routes (`app/routes/`)

| File | Prefix | Endpoints |
|------|--------|-----------|
| `chat.py` | `/api/chat` | `POST /` — Chat message processing with rate limiting |
| `metrics.py` | `/api/metrics` | 13 endpoints — top APIs, slowest, history, health score, errors, recurring, correlation, predict, anomaly, compare, timeline, SLA, deployments |
| `alerts.py` | `/api/alerts` | 8 endpoints — monitored APIs CRUD, error check, alert history, auto-fix trigger, categorize, fix history, audit logs |
| `websockets.py` | — | `WS /ws/activity`, `WS /ws/chat`, `WS /ws/notifications`, `GET /ws/stats` |

### 4.5 Background Tasks (`app/tasks/scheduler.py`)

7 scheduled jobs via APScheduler:

| Job ID | Function | Interval | Purpose |
|--------|----------|----------|---------|
| `error_monitor` | `monitor_error_rates()` | configurable (default 60s) | Error rate threshold checking per API |
| `slow_monitor` | `monitor_slow_apis()` | 5 min | Slow API detection with Teams alerts |
| `anomaly` | `run_anomaly_detection()` | 5 min | Predictive trend + traffic anomaly per API |
| `recurring` | `run_recurring_error_check()` | 1 hour | Recurring error pattern detection (7-day window) |
| `sla` | `run_sla_check()` | 1 hour | SLA compliance checking per API |
| `rollup` | `hourly_rollup()` | 1 hour | Metric aggregation and caching |
| `deployment_gate_recheck` | `recheck_held_deployments()` | 120s | Re-evaluate held deployments against current conditions |

---

## 5. Data Flow Diagrams

### 5.1 PR Analysis Flow

```
GitHub (PR opened/synchronized/reopened)
        │
        ▼
  POST /webhook
  (HMAC SHA-256 signature verification)
        │
        ▼
  Delivery-level dedup (X-GitHub-Delivery header)
        │
        ▼
  PR-level dedup (repo + pr_number + head_sha)
  ──yes──▶ Return 202 (skip)
        │ no
        ▼
  Spawn background daemon thread
  (return 202 immediately)
        │
        ▼
  github_client.get_pr_details()
  github_client.get_pr_diff()
  github_client.get_pr_files()
        │
        ├──▶ check_and_generate_description()
        │     └─ Auto-generate PR description if body is empty/short
        │
        ├──▶ check_conflicts()
        │     └─ Compare files against all other open PRs
        │     └─ Post conflict comment + Teams notification
        │
        ▼
  ┌─────────────────────────────────────────┐
  │         Multi-Agent Pipeline            │
  │                                         │
  │  1. Diff Analyst Agent                  │
  │     → Analyzes code changes             │
  │                                         │
  │  2. Code Reviewer Agent                 │
  │     → Security, performance, style      │
  │                                         │
  │  3. Summary Generator Agent             │
  │     → Human-readable summary + risk     │
  │                                         │
  │  4. Priority Assessor Agent             │
  │     → Risk level + priority ranking     │
  │                                         │
  │  5. Supervisor Agent                    │
  │     → Consolidates all agent outputs    │
  └─────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────┐
  │  Post Results        │
  │  • PR comment        │
  │  • DynamoDB record   │
  │  • Activity log      │
  │  • Teams notification│
  │    (with approve/    │
  │     reject buttons)  │
  │  • WebSocket push    │
  └─────────────────────┘
```

### 5.2 Pipeline Monitoring & Auto-Heal Flow

```
GitHub (workflow_run completed, conclusion: failure)
        │
        ▼
  POST /webhook
  (delivery dedup + pipeline dedup)
        │
        ▼
  Spawn background daemon thread
        │
        ▼
  pipeline_monitor.process_failed_run()
        │
        ├──▶ Fetch workflow run jobs from GitHub
        ├──▶ Fetch job logs from GitHub
        ├──▶ LLM analysis of failure cause
        ├──▶ Store in DynamoDB (pipeline_store)
        ├──▶ Activity log entry
        ├──▶ Teams notification (Adaptive Card)
        │
        ▼
  auto_healer.attempt_auto_fix()
        │
        ├──▶ Generate fix via LLM (with job logs + file context)
        ├──▶ Create branch: synapse-ops/auto-fix/{category}-{timestamp}
        ├──▶ Commit fixed files via GitHub API
        ├──▶ Open auto-fix PR
        ├──▶ Teams notification
        └──▶ Activity log entry
```

### 5.3 API Monitoring Loop

```
APScheduler (runs on configured intervals)
        │
        ├──▶ error_monitor (60s default)
        │     └─ CloudWatch query → ErrorAnalyzer → Alert if server_error_rate ≥ threshold
        │
        ├──▶ slow_monitor (5 min)
        │     └─ CloudWatch query → PerformanceAnalyzer → LLM suggestions → Alert
        │
        ├──▶ anomaly (5 min)
        │     ├─ predict_error_trend() → Linear regression → Alert if breach in ≤20 min
        │     └─ detect_traffic_anomaly() → Z-score → Alert if |z| > 2.5
        │
        ├──▶ recurring (1 hour)
        │     └─ IncidentAnalyzer → MD5 fingerprinting → Alert top 3 recurring errors
        │
        ├──▶ sla (1 hour)
        │     └─ SLATracker → Check error_rate, p99_latency, uptime → Alert on violations
        │
        ├──▶ rollup (1 hour)
        │     └─ Aggregate metrics per API → Store in DynamoDB + cache
        │
        └──▶ deployment_gate_recheck (120s)
              └─ Re-evaluate held deployments → Auto-release if conditions improve

Each monitoring job:
  1. Queries CloudWatch Logs Insights (with stream-scan fallback)
  2. Analyzes results
  3. Stores metrics in DynamoDB
  4. If threshold breached → creates alert → Teams notification
  5. Pushes update via WebSocket
```

### 5.4 Chat Engine Flow

```
User types message in chat widget
        │
        ▼
  POST /api/chat/
  (rate limiting via Redis Lua script)
        │
        ▼
  ChatEngine._classify_intent(message)
        │
        ├──▶ Step 1: Keyword pre-classification (_KW_MAP)
        │     Checks for known keywords (pod, cluster, pipeline, etc.)
        │
        ├──▶ Step 2: LLM classification
        │     Sends message + intent guide to Bedrock
        │     Returns: { intent, params }
        │
        └──▶ Step 3: Hard override
              If LLM says general/service_info but keywords match → force correct intent
        │
        ▼
  Route to handler based on intent:
  ┌──────────────────────────────────────────────────────────┐
  │ Intent              │ Handler                            │
  │─────────────────────│────────────────────────────────────│
  │ top_apis            │ CloudWatch → top API usage          │
  │ error_analysis      │ ErrorAnalyzer → error breakdown     │
  │ slow_apis           │ PerformanceAnalyzer → latency       │
  │ recurring_errors    │ IncidentAnalyzer → recurring ptrns  │
  │ trace_request       │ CloudWatch → correlation ID search  │
  │ health_score        │ PerformanceAnalyzer → composite     │
  │ comparison          │ IncidentAnalyzer → period-over-prd  │
  │ sla_check           │ SLATracker → compliance report      │
  │ deployment_impact   │ DeploymentTracker → error correl.   │
  │ anomaly_detection   │ AnomalyDetector → z-score analysis  │
  │ pod_status          │ K8sClient → pods/nodes/services     │
  │ pipeline_status     │ GitHub API → recent workflow runs   │
  │ pr_summary          │ PRStore → recent PR reviews         │
  │ deployment_gate     │ DeploymentGate → gate status        │
  │ service_info        │ Static platform description         │
  │ general             │ LLM freeform response               │
  └──────────────────────────────────────────────────────────┘
        │
        ▼
  LLM generates human-readable response from data
  (system prompt enforces data-only answers, no fabrication)
        │
        ▼
  Return { response, data, intent }
```

### 5.5 Deployment Gate Flow

```
GitHub (workflow_run completed, conclusion: success, branch: main/master/production)
  — OR —
GitHub (deployment event)
        │
        ▼
  POST /webhook → deployment gate check
  (delivery dedup + deploy dedup)
        │
        ▼
  DeploymentGate.evaluate()
        │
        ├──▶ Fetch current CloudWatch metrics per monitored API
        │     • Error rate (server errors)
        │     • Average latency
        │     • Request volume
        │
        ├──▶ LLM evaluates deployment safety
        │     Input: metrics + deployment context
        │     Output: { decision: PROCEED|HOLD, confidence, reasons }
        │
        ├──▶ If HOLD → Store held deployment in DynamoDB
        │              → Teams notification with release info
        │
        └──▶ If PROCEED → Log approval
                        → Teams notification

  Periodic recheck (every 120s):
        │
        ├──▶ Load all pending held deployments
        ├──▶ Re-analyze current conditions
        ├──▶ If conditions improved → auto-release + notify
        └──▶ If still unhealthy → keep held
```

---

## 6. Database Design

All tables use the prefix from `DYNAMODB_TABLE_PREFIX` (default: `synapse-ops`).

### 6.1 DynamoDB Tables

#### `synapse-ops-prs` — PR Analysis Records

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `repo` | String | PK | Repository (owner/name) |
| `pr_number` | Number | SK | Pull request number |
| `title` | String | — | PR title |
| `author` | String | — | PR author |
| `status` | String | — | Analysis status |
| `risk_level` | String | — | Low / Medium / High |
| `summary` | String | — | AI-generated summary |
| `review` | String | — | Full review text |
| `diff_analysis` | String | — | Diff analysis output |
| `priority_assessment` | String | — | Priority assessment |
| `pr_type` | String | — | PR type (feature/bugfix/refactor/etc.) |
| `priority` | String | — | Priority level |
| `files_changed` | Number | — | Number of files changed |
| `additions` | Number | — | Lines added |
| `deletions` | Number | — | Lines deleted |
| `total_duration_ms` | Number | — | Analysis duration |
| `timestamp` | String | — | ISO 8601 timestamp |

#### `synapse-ops-pipelines` — Pipeline Run Records

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `repo` | String | PK | Repository (owner/name) |
| `run_id` | String | SK | GitHub Actions run ID |
| `workflow` | String | — | Workflow name |
| `status` | String | — | success / failure |
| `analysis` | String | — | AI failure analysis |
| `auto_fix_pr` | Number | — | Auto-fix PR number (if created) |
| `timestamp` | String | — | ISO 8601 timestamp |

#### `synapse-ops-alerts` — Monitoring Alerts

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `pk` | String | PK | `ALERT#{api_path}` |
| `sk` | String | SK | ISO timestamp |
| `api_path` | String | — | API path |
| `alert_type` | String | — | error_rate_exceeded / traffic_anomaly / sla_violation / etc. |
| `error_rate` | Decimal | — | Error rate at time of alert |
| `threshold` | Decimal | — | Threshold that was exceeded |
| `total_requests` | Number | — | Request count |
| `timestamp` | String | — | ISO 8601 timestamp |

#### `synapse-ops-metrics` — Time-Series Metrics

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `pk` | String | PK | `METRIC#{api_path}` |
| `sk` | String | SK | ISO timestamp |
| `api_path` | String | — | API path |
| `total_requests` | Number | — | Total request count |
| `error_count` | Number | — | Error count |
| `error_rate` | Decimal | — | Error rate percentage |
| `server_error_rate` | Decimal | — | 5xx error rate |
| `rollup_type` | String | — | "hourly" for rollup snapshots |

#### `synapse-ops-audit` — Activity & Audit Log

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `pk` | String | PK | `ACTIVITY#YYYY-MM-DD` or `AUDIT#{action}` |
| `sk` | String | SK | ISO timestamp |
| `agent` | String | — | Agent name (e.g., "PR Reviewer") |
| `event` | String | — | Event type (started/processing/completed/error) |
| `message` | String | — | Human-readable description (max 500 chars) |
| `action` | String | — | Audit action (e.g., "auto_fix_analysis", "sla_check") |
| `repo` | String | — | Repository context |
| `pr_number` | Number | — | PR number (if applicable) |
| `duration_ms` | Number | — | Operation duration |
| `timestamp` | Decimal | — | Unix timestamp |

#### `synapse-ops-deployment-gate` — Held Deployments

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `pk` | String | PK | `HELD#{repo}` |
| `sk` | String | SK | `{run_id}` |
| `repo` | String | — | Repository |
| `run_id` | Number | — | Workflow run ID |
| `workflow` | String | — | Workflow name |
| `branch` | String | — | Branch name |
| `commit_sha` | String | — | Short commit SHA |
| `sender` | String | — | User who triggered |
| `status` | String | — | held / released / deployed |
| `reasons` | List | — | Hold reasons from LLM |
| `conditions` | Map | — | Traffic conditions at hold time |
| `held_at` | String | — | ISO timestamp |

---

## 7. API Reference

### 7.1 Webhook Endpoint

```
POST /webhook
Headers:
  X-Hub-Signature-256: sha256=<HMAC>
  X-GitHub-Event: pull_request | workflow_run | deployment
  X-GitHub-Delivery: <delivery-id>

Handled Events:
  • pull_request (opened, synchronize, reopened) → PR analysis pipeline
  • workflow_run (completed, failure)             → Pipeline analysis + auto-heal
  • workflow_run (completed, success, main/master) → Deployment gate evaluation
  • deployment                                     → Deployment gate evaluation

Deduplication:
  • Delivery-level: X-GitHub-Delivery header
  • PR-level: repo + pr_number + head_sha
  • Pipeline-level: repo + run_id
  • Deploy-level: repo + run_id or deployment_id
```

### 7.2 Chat API

```
POST /api/chat/
Body: {
  "message": "show me error breakdown",
  "context": {
    "time_range": "24h",
    "last_intent": "error_analysis"
  }
}
Response: {
  "response": "Here's the error breakdown...",
  "data": { ... },
  "intent": { "intent": "error_analysis", "params": {} }
}

Rate Limit: Configurable (default 30 req/min) via Redis Lua script
```

### 7.3 Page Routes (Server-Side Rendered)

| Route | Method | Template | Description |
|-------|--------|----------|-------------|
| `/` | GET | `dashboard.html` | Main dashboard with PR stats cards |
| `/dashboard` | GET | `dashboard.html` | Alias for `/` |
| `/pipelines` | GET | `pipelines.html` | Pipeline runs table with stats |
| `/pipeline/{repo}/{run_id}` | GET | `pipeline_detail.html` | Pipeline run detail |
| `/metrics` | GET | `metrics.html` | API monitoring metrics |
| `/activity` | GET | `activity.html` | Real-time activity log |
| `/pr/{repo}/{pr_number}` | GET | `pr_detail.html` | PR analysis detail |
| `/test` | GET/POST | `test.html` | Manual PR analysis test page |
| `/action/approve/{repo}/{pr_number}` | GET/POST | `action.html` | PR approve & merge (Teams callback) |
| `/action/reject/{repo}/{pr_number}` | GET/POST | `action.html` | PR request changes (Teams callback) |

### 7.4 REST API Endpoints

#### Health

| Route | Method | Description |
|-------|--------|-------------|
| `/health` | GET | Basic health check |
| `/health/ready` | GET | Readiness check (Redis + DynamoDB connectivity) |

#### PR Data

| Route | Method | Description |
|-------|--------|-------------|
| `/api/stats` | GET | PR analysis statistics |
| `/api/pr-metrics` | GET | PR metrics (risk distribution, avg duration) |
| `/api/prs` | GET | All PR records |
| `/api/pr/approve` | POST | Approve and merge PR (JSON API) |
| `/api/pr/reject` | POST | Request changes on PR (JSON API) |

#### Activity & Pipelines

| Route | Method | Description |
|-------|--------|-------------|
| `/api/activity` | GET | Activity log entries (supports `since` cursor) |
| `/api/pipelines` | GET | Pipeline records with stats (limit 20) |

#### Deployment Gate

| Route | Method | Description |
|-------|--------|-------------|
| `/api/deployment-gate/status` | GET | Current conditions + held deployments |
| `/api/deployment-gate/held` | GET | List all held deployments |

#### Metrics (`/api/metrics/`)

| Route | Method | Description |
|-------|--------|-------------|
| `/api/metrics/top-apis` | GET | Top APIs by request count |
| `/api/metrics/slowest-apis` | GET | Slowest APIs with LLM suggestions |
| `/api/metrics/api-history/{api_path}` | GET | API request history |
| `/api/metrics/health-score/{api_path}` | GET | Composite health score (error + latency + throughput) |
| `/api/metrics/errors/by-status` | GET | Error breakdown by HTTP status code |
| `/api/metrics/errors/recurring` | GET | Recurring error patterns (7-day window) |
| `/api/metrics/correlation/{correlation_id}` | GET | Trace request by correlation ID |
| `/api/metrics/predict/{api_path}` | GET | Predictive error trend (linear regression) |
| `/api/metrics/anomaly/{api_path}` | GET | Traffic anomaly detection (z-score) |
| `/api/metrics/compare/{api_path}` | GET | Period-over-period comparison |
| `/api/metrics/timeline` | GET | Incident timeline (errors + slow requests) |
| `/api/metrics/sla/{api_path}` | GET | SLA compliance check |
| `/api/metrics/sla/{api_path}` | POST | Set custom SLA targets |
| `/api/metrics/deployments` | GET | Recent GitHub Actions deployments |
| `/api/metrics/deployments/correlate/{api_path}` | GET | Deployment-error correlation |

#### Alerts (`/api/alerts/`)

| Route | Method | Description |
|-------|--------|-------------|
| `/api/alerts/monitored-apis` | GET | List monitored APIs |
| `/api/alerts/monitored-apis` | POST | Set monitored APIs (bulk) |
| `/api/alerts/monitored-apis/add/{api_path}` | POST | Add single monitored API |
| `/api/alerts/monitored-apis/remove/{api_path}` | DELETE | Remove monitored API |
| `/api/alerts/check/{api_path}` | GET | Check API error rate against threshold |
| `/api/alerts/history/{api_path}` | GET | Alert history for an API |
| `/api/alerts/auto-fix` | POST | Trigger auto-fix analysis |
| `/api/alerts/categorize` | POST | Categorize error (without fix) |
| `/api/alerts/auto-fix/history` | GET | Auto-fix attempt history |
| `/api/alerts/audit` | GET | Audit logs (filterable by action) |

### 7.5 WebSocket Endpoints

| Route | Purpose | Message Format |
|-------|---------|----------------|
| `/ws/activity` | Real-time activity feed | `{ type: "activity", data: { agent, event, message, timestamp } }` |
| `/ws/chat` | Chat with streaming responses | `{ type: "chat_chunk", chunk, done }` |
| `/ws/notifications` | PR/pipeline/alert notifications | `{ type: "notification", data: { ... } }` |
| `/ws/stats` | GET — Connection statistics | `{ activity, chat, notifications, total }` |

---

## 8. Multi-Agent PR Analysis Pipeline

### 8.1 Agent Architecture

```
                    ┌──────────────┐
                    │  Supervisor  │
                    │    Agent     │
                    └──────┬───────┘
                           │ orchestrates
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
    │   Diff    │   │   Code    │   │  Summary  │
    │  Analyst  │   │ Reviewer  │   │ Generator │
    └───────────┘   └───────────┘   └───────────┘
          │                │
    ┌─────┴─────┐   ┌─────┴─────┐
    │ Priority  │   │Description│
    │ Assessor  │   │ Generator │
    └───────────┘   └───────────┘
```

### 8.2 Agent Details

| Agent | Input | Output | Key Logic |
|-------|-------|--------|-----------|
| Diff Analyst | PR diff + file list | Structured change analysis | Categorizes changes, identifies patterns |
| Code Reviewer | PR diff | Security, performance, style issues | Reviews code quality |
| Summary Generator | Diff analysis + review | Human-readable summary + risk level | Extracts risk level via regex |
| Priority Assessor | All previous outputs + PR metadata | Risk level (Low/Medium/High) + priority | Uses file count, additions, deletions, PR type |
| Description Generator | PR metadata + diff + files | Auto-generated PR description | Only runs if PR body is empty/short (<50 chars) |
| Supervisor | All agent outputs | Consolidated review comment | Formats final PR comment with all sections |

### 8.3 Execution Model

- Agents run sequentially (not parallel) to manage Bedrock rate limits
- Each agent call uses `bedrock_client.invoke_model()` with retry (3 attempts, exponential backoff)
- Total pipeline takes ~15-30 seconds depending on PR size
- Runs in a daemon thread to not block the webhook response (returns 202 immediately)
- Results posted as a single consolidated PR comment
- PR type extracted from diff analysis (feature/bugfix/refactor/docs/test/config/dependency)
- Risk level extracted via regex from summary output
- Priority extracted via regex from priority assessment

### 8.4 Additional PR Processing

- **Description Generation**: Auto-generates PR description if body is empty or < 50 chars, updates via GitHub API
- **Conflict Detection**: Compares changed files against all other open PRs, posts conflict comment, sends Teams notification
- **Teams Notification**: Sends Adaptive Card with approve/reject action buttons linking to `/action/approve` and `/action/reject`
- **DynamoDB Storage**: Full PR record stored in `synapse-ops-prs` table
- **Activity Log**: Events emitted at started/processing/completed stages

---

## 9. Pipeline Monitoring & Auto-Healing

### 9.1 Failure Detection (`pipeline_monitor.py`)

```python
def process_failed_run(repo, run):
    # 1. Fetch workflow run jobs from GitHub API
    # 2. Fetch job logs for failed jobs
    # 3. Send logs to LLM for root cause analysis
    # 4. Store analysis in DynamoDB (pipeline_store)
    # 5. Activity log entry
    # 6. Teams notification (Adaptive Card with failure details)
    # 7. Trigger auto-healer
```

### 9.2 Auto-Healing Process (`auto_healer.py`)

```python
def generate_fix(repo, run, failed_jobs, logs):
    # 1. Analyze failure logs with LLM
    # 2. Identify affected files
    # 3. Fetch current file contents from GitHub
    # 4. Generate fix via LLM

def apply_fix(repo, branch, fix, run_id):
    # 1. Find existing PR for branch (if any)
    # 2. Create new branch: synapse-ops/auto-fix/{category}-{timestamp}
    # 3. Commit fixed files via GitHub Contents API
    # 4. Open PR with fix description
    # 5. Teams notification
    # 6. Activity log entry
```

### 9.3 Conflict Detection (`conflict_detector.py`)

Triggered during PR analysis (not on push events):

```python
def check_conflicts(repo, pr_number, pr_files, pr_title, pr_author):
    # 1. Fetch all open PRs for the repo
    # 2. For each other open PR, fetch its files
    # 3. Compute file overlap (set intersection)
    # 4. If overlap found:
    #    - Post conflict comment on the PR
    #    - Send Teams notification
    #    - Log to activity log
    # 5. Return list of conflicts
```

---

## 10. API Monitoring Engine

### 10.1 CloudWatch Service (`app/services/cloudwatch.py`)

The CloudWatch service provides two query strategies:

1. **Logs Insights queries** — Preferred, uses CloudWatch Logs Insights for aggregation
2. **Stream-scan fallback** — When Insights returns empty, scans recent log events directly

Key methods:
- `get_api_metrics(api_path, period_minutes)` — Total requests, error count, error rate, server error rate
- `get_latency_metrics(api_path, period_minutes)` — avg, p50, p95, p99 latency
- `get_top_apis(hours_back, limit)` — Top APIs by request count
- `get_slowest_apis(hours_back, limit)` — Slowest APIs by average latency
- `get_error_logs(hours_back)` — Recent error log entries
- `get_logs_by_correlation_id(cid)` — Trace a request across log entries

API filtering: Uses configurable `monitored_apis` list to filter CloudWatch queries.

### 10.2 Error Analyzer

- Monitors server error rate (5xx only) against configurable threshold
- Alert cooldown via Redis (configurable, default 60 min)
- Error breakdown by HTTP status code category (2xx/3xx/4xx/5xx)
- Stores metric snapshots in DynamoDB for trend analysis

### 10.3 Anomaly Detector

Two detection algorithms:

1. **Predictive Error Trend** (linear regression):
   - Fits linear model to recent error rate history
   - Predicts time to threshold breach
   - Alerts if breach predicted within 20 minutes

2. **Traffic Anomaly Detection** (z-score):
   - Computes z-score of current traffic vs baseline
   - Alerts on spikes (z > 2.5) or drops (z < -2.5)
   - Severity: medium (|z| > 2.5), high (|z| > 3.5)

### 10.4 Performance Analyzer

- Identifies slowest APIs with LLM-generated optimization suggestions
- Composite health score: `error_rate_score * 0.4 + latency_score * 0.35 + throughput_score * 0.25`
- Results cached for 5 minutes

### 10.5 SLA Tracker

Configurable per-API SLA targets (stored in Redis, 24h TTL):
- `max_error_rate_pct` (default: 1.0%)
- `max_p99_latency_ms` (default: 3000ms)
- `min_uptime_pct` (default: 99.9%)

Violation severity: warning (exceeded) or critical (exceeded by 2x-5x).

### 10.6 Incident Analyzer

- **Timeline**: Builds chronological timeline of errors + slow requests in a time window
- **Period Comparison**: Compares current vs previous period metrics (error rate, latency, throughput)
- **Recurring Errors**: MD5 fingerprinting of error messages, groups by fingerprint, identifies patterns seen on 2+ unique days

---

## 11. Chat Engine

### 11.1 Intent Classification (3-stage)

1. **Keyword pre-classification**: Checks message against `_KW_MAP` dictionary for known keywords (pod, cluster, pipeline, deploy, sla, etc.)
2. **LLM classification**: Sends message + intent guide to Bedrock, returns `{ intent, params }`
3. **Hard override**: If LLM returns `general` or `service_info` but keywords match a specific intent, forces the correct intent

### 11.2 Supported Intents (18)

| Intent | Data Source | Description |
|--------|------------|-------------|
| `top_apis` | CloudWatch | Top APIs by request volume |
| `error_analysis` | ErrorAnalyzer | Error breakdown by status code |
| `slow_apis` | PerformanceAnalyzer | Slowest APIs with suggestions |
| `recurring_errors` | IncidentAnalyzer | Recurring error patterns |
| `trace_request` | CloudWatch | Correlation ID search |
| `health_score` | PerformanceAnalyzer | Composite health score |
| `comparison` | IncidentAnalyzer | Period-over-period comparison |
| `sla_check` | SLATracker | SLA compliance report |
| `deployment_impact` | DeploymentTracker | Deployment-error correlation |
| `anomaly_detection` | AnomalyDetector | Traffic anomaly + prediction |
| `pod_status` | K8sClient | Kubernetes pod/node/service status |
| `pipeline_status` | GitHub API | Recent workflow runs |
| `pr_summary` | PRStore | Recent PR reviews |
| `deployment_gate` | DeploymentGate | Gate status + held deployments |
| `service_info` | Static | Platform description |
| `general` | LLM | Freeform response |
| `incident_timeline` | IncidentAnalyzer | Error + slow request timeline |
| `predict_errors` | AnomalyDetector | Predictive error trend |

### 11.3 Response Generation

- For data queries: System prompt enforces data-only answers, no fabrication
- For service info: Dedicated prompt with platform context (capabilities, monitored APIs, infrastructure)
- Empty result detection: Returns "no data found" message instead of hallucinating

---

## 12. Deployment Gate

### 12.1 Evaluation Process

1. Triggered by successful workflow runs on main/master/production branches, or deployment events
2. Fetches current traffic conditions for all monitored APIs
3. LLM evaluates deployment safety with metrics context
4. Decision: `PROCEED` (deploy) or `HOLD` (wait for conditions to improve)

### 12.2 Held Deployment Management

- Held deployments stored in DynamoDB with full context
- Periodic recheck every 120 seconds via APScheduler
- Auto-release when conditions improve
- Teams notifications for hold, release, and proceed decisions

### 12.3 API Endpoints

- `GET /api/deployment-gate/status` — Current conditions + held deployments
- `GET /api/deployment-gate/held` — List all held deployments

---

## 13. Auto-Fix Engine

### 13.1 Error Categorization (`code_analyzer.py`)

12 bug categories with auto-fixable classification:

| Category | Auto-Fixable | Pattern |
|----------|-------------|---------|
| `null_reference` | Yes | Cannot read property of undefined/null |
| `type_error` | Yes | TypeError: is not a function |
| `missing_import` | Yes | Cannot find module / Module not found |
| `unhandled_promise` | Yes | UnhandledPromiseRejection |
| `syntax_error` | Yes | SyntaxError / JSON.parse |
| `env_config` | Yes | Missing env/config variable |
| `memory_leak` | No | heap / out of memory / ENOMEM |
| `db_connection` | No | ECONNREFUSED + database |
| `auth_failure` | No | 401/403 / Unauthorized / token expired |
| `timeout` | No | ECONNREFUSED / ETIMEDOUT |
| `infrastructure` | No | SIGTERM / OOMKilled / CrashLoopBackOff |
| `unknown` | No | No pattern match |

### 13.2 Fix Generation Pipeline

```
Error + Stack Trace
        │
        ▼
  CodeAnalyzer.categorize_error()
  CodeAnalyzer.parse_stack_trace()
        │
        ▼
  Fetch source file from GitHub (top stack frame)
        │
        ▼
  Get code context (±15 lines around error)
        │
        ▼
  LLM analysis with full file + error context
  → { root_cause, explanation, confidence, fixed_code, changes_summary }
        │
        ▼
  If auto_fixable AND confidence ≥ 0.8 AND fixed_code present:
        │
        ├──▶ Create branch: synapse-ops/auto-fix/{category}-{timestamp}
        ├──▶ Commit fixed file via GitHub Contents API
        ├──▶ Open PR with root cause + changes summary
        ├──▶ Teams notification
        └──▶ Audit log
```

---

## 14. Conflict Detection

### 14.1 Detection Logic

- Fetches all open PRs for the repository (up to 50)
- Compares changed file sets using set intersection
- Reports overlapping files per conflicting PR

### 14.2 Notification

- Posts a Markdown comment on the PR listing all conflicts
- Sends Teams Adaptive Card with conflict details and action buttons
- Logs to activity log

---

## 15. Real-Time Communication (WebSocket)

### 15.1 Connection Types

| Type | Endpoint | Purpose |
|------|----------|---------|
| `activity` | `/ws/activity` | Real-time activity feed from all agents |
| `chat` | `/ws/chat` | Chat with streaming responses (50-word chunks) |
| `notifications` | `/ws/notifications` | PR, pipeline, alert notifications |

### 15.2 Features

- Automatic dead connection cleanup on broadcast failure
- Ping/pong keepalive support
- Connection statistics endpoint (`/ws/stats`)
- Thread-safe broadcasting from background threads via stored event loop reference
- Chat response streaming with typing indicator and chunked delivery

---

## 16. Caching & Deduplication

### 16.1 Redis Cache (`app/services/cache.py`)

- Connection pooling (20 max connections, 3s timeout)
- Graceful degradation: all operations return None/True when Redis unavailable
- Rate limiting via atomic Lua script (INCR + EXPIRE)
- Alert cooldown tracking
- SLA target storage (24h TTL)
- Monitored API list (30-day TTL)
- Metric caching (various TTLs: 120s for latest, 300s for slow APIs, 7200s for rollups)

### 16.2 Deduplication (`app/services/dedup.py`)

- Redis-backed with 24h TTL using `SET NX`
- In-memory fallback with bounded set (10K cap, evicts oldest half)
- Dedup key types:
  - `dedup:pr:{repo}:{pr_number}:{head_sha}` — PR events
  - `dedup:pipe:{repo}:{run_id}` — Pipeline failures
  - `dedup:deploy:{repo}:{run_id}` — Deployment gate events
  - `dedup:delivery:{delivery_id}` — GitHub webhook delivery retries

---

## 17. Error Handling & Resilience

### 17.1 Retry Strategy (`app/services/retry.py`)

- Exponential backoff with jitter: `delay = min(base * 2^attempt + random(0,1), max_delay)`
- Default: 3 retries, 1s base delay, 30s max delay
- Configurable retryable exception types per use case:
  - GitHub API: `ConnectionError`, `Timeout`, `HTTPError`
  - Bedrock: `ClientError`, `ConnectionError`, `TimeoutError`
  - Teams webhook: `ConnectError`, `ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, `PoolTimeout`

### 17.2 Graceful Degradation

- Redis unavailable → in-memory fallback for dedup, rate limiting fails open
- DynamoDB unavailable → activity log operates in-memory only
- CloudWatch Insights empty → stream-scan fallback
- Bedrock failure → error logged, operation continues
- Teams webhook failure → logged, does not block main flow
- kubectl not found → returns empty results

### 17.3 Background Processing

- All webhook-triggered heavy processing runs in daemon threads
- Webhook returns 202 immediately
- Thread failures are caught and logged, never crash the server

---

## 18. Security

### 18.1 Webhook Verification

- HMAC SHA-256 signature verification using `X-Hub-Signature-256` header
- Constant-time comparison via `hmac.compare_digest()`
- Warning logged (but not blocked) when `GITHUB_WEBHOOK_SECRET` is not set

### 18.2 Container Security

- Non-root user (`appuser`) in Docker container
- No shell access in production image
- Health check via Python urllib (no curl dependency)

### 18.3 Input Validation

- Pydantic validators on all configuration values (thresholds, intervals, rate limits)
- Chat message length limit (2000 chars)
- Auto-fix error message limit (5000 chars)
- Monitored APIs limit (100 max)
- Query parameter validation with min/max bounds on all metric endpoints

### 18.4 Rate Limiting

- Chat endpoint: configurable rate limit (default 30 req/min) via Redis Lua script
- Fails open when Redis unavailable

### 18.5 Middleware

- `NoCacheHTMLMiddleware`: Sets `Cache-Control: no-cache, no-store, must-revalidate` on all HTML responses to prevent stale content

---

## 19. Deployment Architecture

### 19.1 Docker

```dockerfile
FROM python:3.11-slim
# Non-root user: appuser
# Health check: HTTP GET /health (30s interval, 5s timeout, 3 retries)
# Entrypoint: uvicorn app.main:app --host 0.0.0.0 --port 5000
```

### 19.2 Kubernetes (Helm)

```yaml
# helm/synapse-ops/
Chart: synapse-ops v0.1.0 (appVersion 1.0.0)

Deployment:
  replicas: 1
  image: 551494044780.dkr.ecr.us-east-1.amazonaws.com/synapse-ops:latest
  resources:
    requests: 256m CPU, 512Mi memory
    limits: 512m CPU, 1Gi memory
  probes:
    liveness: GET /health (30s period, 5s timeout, 5 failures)
    readiness: GET /health/ready (10s period, 5s timeout, 5 failures)

Service:
  type: LoadBalancer
  port: 80 → targetPort: 5000

ServiceAccount:
  name: synapse-ops-sa
  IAM Role: arn:aws:iam::551494044780:role/synapse-ops-role (IRSA)

Secrets:
  TEAMS_WEBHOOK_URL, GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET
  (stored in Kubernetes Secret, injected via secretKeyRef)
```

### 19.3 IAM Permissions Required

- `bedrock:InvokeModel` — LLM inference
- `dynamodb:PutItem`, `dynamodb:Query`, `dynamodb:Scan`, `dynamodb:CreateTable`, `dynamodb:DescribeTable` — Data storage
- `logs:StartQuery`, `logs:GetQueryResults`, `logs:FilterLogEvents`, `logs:DescribeLogStreams` — CloudWatch Logs

---

## 20. Configuration Management

### 20.1 Environment Variables (`app/config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_REGION` | `us-east-1` | AWS region for DynamoDB |
| `BEDROCK_MODEL_ID` | `anthropic.claude-3-haiku-20240307-v1:0` | Bedrock model (supports anthropic/nova/meta) |
| `BEDROCK_REGION` | `us-east-1` | AWS region for Bedrock |
| `GITHUB_TOKEN` | — | GitHub personal access token |
| `GITHUB_WEBHOOK_SECRET` | — | Webhook HMAC secret |
| `GITHUB_REPO` | — | Comma-separated repo list (owner/name) |
| `TEAMS_WEBHOOK_URL` | — | Microsoft Teams webhook URL |
| `CLOUDWATCH_LOG_GROUP` | `/your/service/log-group` | Target CloudWatch log group |
| `DYNAMODB_TABLE_PREFIX` | `synapse-ops` | DynamoDB table name prefix |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `ERROR_RATE_THRESHOLD` | `50.0` | Server error rate alert threshold (%) |
| `SLOW_API_THRESHOLD_MS` | `2000` | Slow API latency threshold (ms) |
| `MONITORING_INTERVAL_SECONDS` | `60` | Error monitoring job interval |
| `ALERT_COOLDOWN_MINUTES` | `60` | Minimum time between alerts for same API |
| `MONITORED_APIS` | — | Comma-separated API paths to monitor |
| `CHAT_RATE_LIMIT_PER_MINUTE` | `30` | Chat endpoint rate limit |
| `POLL_INTERVAL` | `60` | General polling interval |
| `APP_BASE_URL` | `http://localhost:5000` | Base URL for action links in Teams cards |

### 20.2 Startup Validation

`validate_settings_on_startup()` checks for:
- Placeholder CloudWatch log group
- Missing GitHub token
- Empty webhook secret (security warning)
- Missing GitHub repo
- Default Redis URL without explicit env var

### 20.3 Monitored API Seeding

On startup, `_seed_monitored_apis()` reads `MONITORED_APIS` env var and seeds the Redis cache if not already populated (30-day TTL).

---

## 21. Diagnostic Tool

### 21.1 `diagnose.py`

CLI diagnostic tool that validates the full SynapseOps setup:

| Check | What It Validates |
|-------|-------------------|
| Environment variables | `.env` file exists, required vars set, no placeholders |
| Python dependencies | All required packages installed (fastapi, boto3, redis, etc.) |
| Server running | HTTP GET to `/health` endpoint |
| AWS credentials | STS `GetCallerIdentity`, Bedrock client creation |
| Redis connection | Redis ping |
| GitHub token | GitHub API `/user` call, scope validation (needs `repo`) |
| Teams webhook | POST test message to webhook URL |

Run: `python diagnose.py`

---

## 22. File Structure Reference

```
SynapseOps/
├── app.py                          # Entry point (uvicorn launcher)
├── app/
│   ├── main.py                     # FastAPI app, lifespan, webhook, routes
│   ├── config.py                   # Pydantic settings
│   ├── __init__.py
│   ├── models/
│   │   ├── schemas.py              # Pydantic request/response models
│   │   └── __init__.py
│   ├── routes/
│   │   ├── alerts.py               # /api/alerts/* endpoints
│   │   ├── chat.py                 # /api/chat/ endpoint
│   │   ├── metrics.py              # /api/metrics/* endpoints
│   │   ├── websockets.py           # /ws/* endpoints
│   │   └── __init__.py
│   ├── services/
│   │   ├── anomaly_detector.py     # Z-score + linear regression
│   │   ├── auto_fix.py             # Auto-fix PR generation
│   │   ├── cache.py                # Redis with graceful degradation
│   │   ├── chat_engine.py          # Intent classification + handlers
│   │   ├── cloudwatch.py           # CloudWatch Logs Insights
│   │   ├── code_analyzer.py        # Error categorization + stack parsing
│   │   ├── dedup.py                # Webhook deduplication
│   │   ├── deployment_gate.py      # AI deployment gating
│   │   ├── deployment_tracker.py   # GitHub Actions tracking
│   │   ├── dynamodb.py             # DynamoDB operations
│   │   ├── error_analyzer.py       # Error rate monitoring
│   │   ├── incident_analyzer.py    # Timeline + comparison + recurring
│   │   ├── k8s_client.py           # Kubernetes via kubectl
│   │   ├── llm.py                  # Multi-model Bedrock LLM
│   │   ├── log_analyzer.py         # Log search + analysis
│   │   ├── notifier.py             # Teams notifications
│   │   ├── performance.py          # Latency analysis + health score
│   │   ├── retry.py                # Exponential backoff decorator
│   │   ├── sla_tracker.py          # SLA compliance
│   │   ├── websocket_manager.py    # WebSocket connection manager
│   │   └── __init__.py
│   ├── static/
│   │   ├── chat.html               # Chat widget
│   │   └── .gitkeep
│   └── tasks/
│       ├── scheduler.py            # APScheduler (7 jobs)
│       └── __init__.py
├── agents.py                       # Multi-agent PR analysis
├── auto_healer.py                  # Pipeline auto-fix
├── bedrock_client.py               # Bedrock client (backward compat)
├── config.py                       # Root config re-export
├── conflict_detector.py            # PR conflict detection
├── diagnose.py                     # Diagnostic CLI tool
├── github_client.py                # GitHub API wrapper
├── pipeline_monitor.py             # Pipeline failure analysis
├── store.py                        # DynamoDB PR + Pipeline stores
├── teams_notifier.py               # PR Teams notification
├── activity_log.py                 # Activity log singleton
├── templates/                      # Jinja2 HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── metrics.html
│   ├── pipelines.html
│   ├── pipeline_detail.html
│   ├── pr_detail.html
│   ├── activity.html
│   ├── action.html
│   └── test.html
├── helm/synapse-ops/               # Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── deployment.yaml
│       ├── service.yaml
│       ├── secret.yaml
│       └── serviceaccount.yaml
├── Dockerfile
├── requirements.txt
├── .env.example
└── docs/
    └── LLD.md                      # This document
```
