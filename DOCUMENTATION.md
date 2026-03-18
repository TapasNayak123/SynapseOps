# SynapseOps — AI-Powered DevOps Agent

## Project Overview

SynapseOps is an intelligent DevOps agent that automates code review, pipeline failure analysis, application monitoring, and incident response using Amazon Bedrock LLMs. It acts as an always-on AI teammate that watches your GitHub repositories and production infrastructure, providing real-time analysis and automated remediation.

**Live URL:** http://a7da142a1e4ff48669cb977d182c0594-310346557.us-east-1.elb.amazonaws.com/

**Repository:** https://github.com/TapasNayak123/SynapseOps

---

## Problem Statement

Modern development teams face several operational challenges:

- Pull requests pile up waiting for review, slowing delivery velocity
- CI/CD pipeline failures require manual investigation and debugging
- Production errors go unnoticed until users report them
- Incident response is reactive rather than proactive
- Context switching between GitHub, CloudWatch, and communication tools wastes engineering time

SynapseOps solves these by deploying a multi-agent AI system that continuously monitors, analyzes, and acts on DevOps events — automatically.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Webhooks                          │
│              (pull_request + workflow_run events)                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SynapseOps (FastAPI)                          │
│                   Deployed on Amazon EKS                         │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │  PR Analysis  │  │   Pipeline   │  │  API Monitoring    │    │
│  │  Multi-Agent  │  │   Failure    │  │  & Alerting        │    │
│  │  Pipeline     │  │   Analyzer   │  │  Engine            │    │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────────┘    │
│         │                 │                    │                 │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌────────┴───────────┐    │
│  │ Diff Analyst  │  │ Auto-Healer  │  │ Anomaly Detector   │    │
│  │ Code Reviewer │  │ (generates   │  │ SLA Tracker        │    │
│  │ Summary Gen   │  │  fixes and   │  │ Error Analyzer     │    │
│  │ Priority      │  │  pushes to   │  │ Performance        │    │
│  │ Description   │  │  branch)     │  │ Incident Analyzer  │    │
│  │ Conflict Det  │  │              │  │ Deployment Tracker │    │
│  └──────────────┘  └──────────────┘  └────────────────────┘    │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │  Chat Engine  │  │  Auto-Fix    │  │  Retry with        │    │
│  │  (NL query    │  │  Engine      │  │  Exponential       │    │
│  │   interface)  │  │  (code PRs)  │  │  Backoff           │    │
│  └──────────────┘  └──────────────┘  └────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
         │                 │                    │
         ▼                 ▼                    ▼
┌──────────────┐  ┌──────────────┐  ┌────────────────────┐
│ Amazon       │  │  DynamoDB    │  │  Redis             │
│ Bedrock      │  │  (persistent │  │  (cache, rate      │
│ (LLM)       │  │   storage)   │  │   limiting)        │
└──────────────┘  └──────────────┘  └────────────────────┘
         │                                     │
         ▼                                     ▼
┌──────────────┐                    ┌────────────────────┐
│ CloudWatch   │                    │ Microsoft Teams    │
│ Logs Insights│                    │ (notifications)    │
└──────────────┘                    └────────────────────┘
```

---

## AWS Services Used

| Service | Purpose |
|---------|---------|
| **Amazon Bedrock** | LLM inference (Claude 3 Haiku) for code analysis, error diagnosis, fix generation, and chat |
| **Amazon EKS** | Container orchestration for the SynapseOps application |
| **Amazon ECR** | Docker image registry |
| **Amazon DynamoDB** | Persistent storage for PR records, pipeline records, alerts, metrics, and audit logs |
| **Amazon CloudWatch Logs Insights** | Querying application logs for error analysis, performance metrics, and anomaly detection |
| **Amazon ElastiCache (Redis)** | Caching layer, rate limiting, and alert cooldown tracking |
| **Elastic Load Balancer** | Public endpoint for the application and GitHub webhook receiver |
| **IAM (IRSA)** | Secure pod-level access to AWS services via service account role binding |

---

## Core Features

### 1. AI-Powered PR Analysis (Multi-Agent Pipeline)

When a pull request is opened or updated, GitHub sends a webhook to SynapseOps, which triggers a pipeline of 5 specialized AI agents:

| Agent | Responsibility |
|-------|---------------|
| **Diff Analysis Agent** | Categorizes changes (feature, bugfix, refactor, etc.), groups files by area, identifies key modifications |
| **Code Review Agent** | Analyzes code quality, security concerns, best practice violations, and highlights well-written code |
| **Summary Generator Agent** | Produces a human-readable PR summary with overview, changes breakdown, review highlights, risk level, and recommendation |
| **Priority Assessment Agent** | Classifies PR priority (Critical / High / Medium / Low) based on code changes and context |
| **Description Generator Agent** | Auto-generates a PR description when the author leaves it empty |

Additionally:
- **Conflict Detection Agent** compares the PR's changed files against all other open PRs and alerts on overlapping files
- Results are posted as a GitHub PR comment and sent as an interactive Microsoft Teams adaptive card with Approve/Reject actions

### 2. Pipeline Failure Analysis and Auto-Healing

When a GitHub Actions workflow fails, SynapseOps:

1. Receives the `workflow_run` webhook event
2. Fetches failed jobs and their logs via GitHub API
3. Sends logs to Bedrock for root cause analysis (categorizes as build error, test failure, lint error, dependency issue, config error, or infra issue)
4. **Auto-Healer Agent** generates a concrete code fix, pushes it directly to the failing branch, and comments on the associated PR
5. Optionally re-triggers the failed pipeline
6. Sends a detailed failure analysis and auto-heal status to Microsoft Teams

### 3. Real-Time Application Monitoring

Background scheduler jobs continuously monitor the target application via CloudWatch Logs Insights:

| Monitor | What It Does |
|---------|-------------|
| **Error Rate Monitor** | Checks error rates per API endpoint against configurable thresholds, alerts on breach |
| **Slow API Monitor** | Identifies APIs exceeding latency thresholds, generates LLM-powered optimization suggestions |
| **Anomaly Detector** | Uses linear regression for predictive threshold warnings and z-score analysis for traffic spike/drop detection |
| **SLA Tracker** | Checks compliance against configurable per-API SLA targets (error rate, p99 latency, uptime) |
| **Recurring Error Detector** | Fingerprints errors and identifies patterns recurring across multiple days |
| **Deployment Tracker** | Correlates GitHub Actions deployments with error spikes (within 30-minute windows) |
| **Hourly Rollup** | Aggregates metrics into DynamoDB for historical analysis |

### 4. AI Chat Interface

A natural language chat interface where engineers can query their infrastructure:

- "What are the top APIs by traffic in the last hour?"
- "Show me errors for /api/auth/login"
- "Trace correlation ID abc-123"
- "Compare error rates: last 24h vs previous 24h"
- "Build an incident timeline from 2am to 5am"
- "Check SLA compliance for /api/payments"
- "Are there any traffic anomalies on /api/orders?"
- "Show recent deployments and correlate with errors"

The chat engine uses intent classification to route queries to the appropriate service, fetches real data from CloudWatch/DynamoDB, and generates contextual responses via Bedrock.

### 5. Auto-Fix Engine (Production Error Remediation)

When triggered via API, the auto-fix engine:

1. Categorizes the error using pattern matching (syntax error, null reference, auth failure, etc.)
2. Parses the stack trace to identify the source file and line
3. Fetches the actual source code from GitHub
4. Sends the error + source code to Bedrock for analysis and fix generation
5. Creates a PR with the fix on a dedicated branch
6. Notifies the team via Microsoft Teams

### 6. Microsoft Teams Integration

All events produce rich adaptive cards in Microsoft Teams:

- PR summaries with inline Approve/Reject action buttons
- Pipeline failure analysis with links to the run
- Auto-heal status notifications
- Conflict detection warnings
- Error rate and SLA violation alerts
- Traffic anomaly notifications

---

## Event-Driven Architecture (Webhook-Based)

SynapseOps uses a webhook-driven architecture instead of polling:

- **`/webhook` endpoint** receives GitHub webhook events
- **`pull_request` events** (opened, synchronize, reopened) trigger the multi-agent PR analysis pipeline
- **`workflow_run` events** (completed with failure conclusion) trigger pipeline failure analysis and auto-healing
- This eliminates unnecessary API calls and provides instant response to events

---

## Resilience: Retry with Exponential Backoff

All external API calls are wrapped with a shared retry decorator (`app/services/retry.py`) that implements exponential backoff with jitter:

| Integration | Retryable Errors | Max Retries | Base Delay |
|-------------|-----------------|-------------|------------|
| Amazon Bedrock (LLM) | ClientError, ConnectionError, TimeoutError | 3 | 2s |
| GitHub API | ConnectionError, Timeout, HTTPError | 3 | 1s |
| Teams Webhook | ConnectError, ConnectTimeout, ReadTimeout, WriteTimeout | 3 | 1s |

---

## Persistent Storage (DynamoDB)

All operational data survives application restarts:

| Table | Content | Key Schema |
|-------|---------|------------|
| `synapse-ops-pr-records` | PR analysis results, agent outputs, risk levels, metrics | PK: repo, SK: pr_number#timestamp |
| `synapse-ops-pipeline-records` | Pipeline failure analyses, auto-heal status | PK: repo, SK: run_id |
| `synapse-ops-alerts` | Error rate alerts, anomaly alerts | PK: ALERT#api_path, SK: timestamp |
| `synapse-ops-metrics` | Metric snapshots, hourly rollups | PK: METRIC#api_path, SK: timestamp |
| `synapse-ops-audit` | Audit trail for all agent actions | PK: AUDIT#action, SK: timestamp |

Tables are auto-created on first access using PAY_PER_REQUEST billing.

---

## Web Dashboard

SynapseOps includes a full web dashboard with the following pages:

| Route | Page |
|-------|------|
| `/` | PR analysis dashboard — all processed PRs with stats |
| `/metrics` | Detailed metrics — charts for risk distribution, PR types, priorities, author activity, agent performance |
| `/pr/{repo}/{pr_number}` | Individual PR detail with full agent outputs |
| `/pipelines` | Pipeline failure dashboard |
| `/pipeline/{repo}/{run_id}` | Individual pipeline failure detail with analysis and auto-heal status |
| `/activity` | Real-time activity log of all agent actions |
| `/chat` | AI chat interface |
| `/test` | Manual PR analysis testing page |
| `/health` | Health check endpoint |
| `/health/ready` | Readiness probe (checks Redis + DynamoDB connectivity) |

---

## API Endpoints

### PR & Pipeline
- `POST /webhook` — GitHub webhook receiver (PR + pipeline events)
- `GET /api/stats` — PR analysis statistics
- `GET /api/pr-metrics` — Detailed PR metrics
- `GET /api/prs` — List all processed PRs
- `GET /api/activity` — Activity log with cursor-based pagination
- `POST /api/pr/approve` — Approve and merge a PR
- `POST /api/pr/reject` — Request changes on a PR

### Monitoring & Metrics
- `GET /api/metrics/top-apis` — Top APIs by traffic
- `GET /api/metrics/slowest-apis` — Slowest APIs with optimization suggestions
- `GET /api/metrics/health-score/{api_path}` — Composite health score
- `GET /api/metrics/errors/by-status` — Error breakdown by HTTP status
- `GET /api/metrics/errors/recurring` — Recurring error patterns
- `GET /api/metrics/predict/{api_path}` — Predictive error trend
- `GET /api/metrics/anomaly/{api_path}` — Traffic anomaly detection
- `GET /api/metrics/compare/{api_path}` — Period-over-period comparison
- `GET /api/metrics/timeline` — Incident timeline builder
- `GET /api/metrics/sla/{api_path}` — SLA compliance check
- `GET /api/metrics/deployments` — Recent deployments
- `GET /api/metrics/deployments/correlate/{api_path}` — Deployment-error correlation

### Alerts & Auto-Fix
- `GET /api/alerts/monitored-apis` — List monitored APIs
- `POST /api/alerts/monitored-apis` — Set monitored APIs
- `GET /api/alerts/check/{api_path}` — Check error rate for an API
- `GET /api/alerts/history/{api_path}` — Alert history
- `POST /api/alerts/auto-fix` — Trigger auto-fix for an error
- `POST /api/alerts/categorize` — Categorize an error
- `GET /api/alerts/auto-fix/history` — Auto-fix audit trail

### Chat
- `POST /api/chat/` — Natural language monitoring query

---

## Deployment

### Infrastructure
- **Container:** Docker image built with Python 3.11-slim, runs as non-root user
- **Orchestration:** Amazon EKS with Helm chart deployment
- **Image Registry:** Amazon ECR (`551494044780.dkr.ecr.us-east-1.amazonaws.com/synapse-ops`)
- **Service Type:** LoadBalancer (ELB) exposing port 80 → container port 5000
- **IAM:** IRSA (IAM Roles for Service Accounts) for secure AWS API access

### Helm Chart
```
helm/synapse-ops/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── deployment.yaml
    ├── service.yaml
    ├── secret.yaml
    └── serviceaccount.yaml
```

### Resource Allocation
- CPU: 256m request / 512m limit
- Memory: 512Mi request / 1Gi limit

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend Framework | FastAPI (Python) |
| LLM | Amazon Bedrock (Claude 3 Haiku) |
| Log Analysis | Amazon CloudWatch Logs Insights |
| Persistent Storage | Amazon DynamoDB |
| Cache & Rate Limiting | Redis |
| Container Runtime | Docker |
| Orchestration | Amazon EKS |
| CI/CD Integration | GitHub Webhooks + GitHub Actions API |
| Notifications | Microsoft Teams (Adaptive Cards via Power Automate) |
| Scheduling | APScheduler |
| Configuration | Pydantic Settings (environment variables) |

---

## Security Considerations

- GitHub webhook signature verification (HMAC SHA-256)
- Non-root container user
- IAM Roles for Service Accounts (no hardcoded AWS credentials)
- Input sanitization for CloudWatch queries (prevents injection)
- Chat rate limiting via Redis (configurable per-minute limit)
- Secrets managed via Kubernetes secrets (not in container image)
- PII-safe logging with structured log output (structlog + JSON)

---

## Team

**Repository:** TapasNayak123/SynapseOps
