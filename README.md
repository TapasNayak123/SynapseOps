# 🤖 SynapseOps — AI-Powered DevOps Agent

An intelligent, multi-agent DevOps platform that automatically analyzes GitHub pull requests, fixes pipeline failures, monitors production infrastructure, and responds to incidents using Amazon Bedrock LLMs.

**Built for the AWS Codeathon — TopGear Challenge 2026** (Theme 1: AI-Powered Developer Productivity Platform)

---

## Overview

SynapseOps deploys always-on AI agents that watch your GitHub repositories and production infrastructure, providing real-time analysis and automated remediation. It eliminates manual context switching between GitHub, CloudWatch, and communication tools by acting as an intelligent AI teammate.

### Key Capabilities

- **Multi-Agent PR Analysis** — Automatically summarize, review, and assess priority for pull requests
- **Pipeline Failure Auto-Healing** — Detect CI/CD failures, analyze root causes, generate fixes, and push directly to branches
- **Real-Time Monitoring** — Continuously monitor APIs for errors, latency, anomalies, and SLA compliance
- **AI Chat Interface** — Query infrastructure via natural language (errors, metrics, deployments, etc.)
- **Auto-Fix Engine** — Categorize production errors and generate code fixes via Bedrock
- **Microsoft Teams Integration** — Rich adaptive cards for PRs, failures, alerts, and incidents

---

## Architecture

```
GitHub Webhooks (PR + workflow events)
        │
        ▼
┌──────────────────────────────────────┐
│  SynapseOps (FastAPI on EKS)         │
├──────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐    │
│  │ PR Analysis │  │  Pipeline   │    │
│  │ Multi-Agent │  │  Failure    │    │
│  │ Pipeline    │  │  Auto-Heal  │    │
│  └─────────────┘  └─────────────┘    │
│                                       │
│  ┌─────────────┐  ┌─────────────┐    │
│  │ Monitoring  │  │ Chat Engine │    │
│  │ & Alerting  │  │ (NL Query)  │    │
│  └─────────────┘  └─────────────┘    │
└──────────────────────────────────────┘
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Amazon       │ │ DynamoDB     │ │ Redis        │
│ Bedrock      │ │ (storage)    │ │ (cache)      │
│ (LLM)        │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│ Microsoft Teams / CloudWatch / GitHub│
│ (notifications & data sources)       │
└──────────────────────────────────────┘
```

---

## Core Features

### 1. **Multi-Agent PR Analysis Pipeline**

Triggered on pull request events (`opened`, `synchronize`, `reopened`):

| Agent | Responsibility |
|-------|---------------|
| **Diff Analyst** | Categorizes changes (feature/bugfix/refactor), groups files by area, identifies key modifications |
| **Code Reviewer** | Analyzes code quality, security concerns, best practices, highlights well-written code |
| **Summary Generator** | Produces polished PR summary with overview, changes breakdown, risk level, and recommendation |
| **Priority Assessor** | Classifies PR priority (Critical/High/Medium/Low) based on code impact |
| **Description Generator** | Auto-fills empty PR descriptions |
| **Conflict Detector** | Identifies file overlaps with other open PRs and alerts |

**Output:** AI-generated comment on GitHub PR + adaptive card in Microsoft Teams with Approve/Reject actions

### 2. **Pipeline Failure Analysis & Auto-Healing**

Triggered on GitHub Actions workflow failures:

1. Fetches failed job logs via GitHub API
2. Sends logs to Bedrock for root cause analysis (categorizes as build error, test failure, lint error, dependency issue, config error, or infrastructure issue)
3. **Auto-Healer** generates concrete code fix, commits to branch, and comments on PR
4. Optionally re-triggers the failed pipeline
5. Sends detailed analysis to Microsoft Teams

### 3. **Real-Time Application Monitoring**

Background scheduler jobs continuously monitor APIs via CloudWatch Logs Insights:

| Monitor | Capability |
|---------|-----------|
| **Error Rate Monitor** | Checks per-API error rates against thresholds, alerts on breach |
| **Latency Monitor** | Identifies slow APIs, generates optimization suggestions via Bedrock |
| **Anomaly Detector** | Uses linear regression + z-score analysis for traffic anomalies |
| **SLA Tracker** | Checks compliance against configurable per-API targets |
| **Recurring Error Detector** | Fingerprints and correlates errors across multiple days |
| **Deployment Tracker** | Correlates deployments with error spikes (30-minute window) |
| **Hourly Rollup** | Aggregates metrics into DynamoDB for historical analysis |

### 4. **Natural Language Chat Interface**

Engineers query infrastructure via `/api/chat`:

```
"What are the top APIs by traffic in the last hour?"
"Show errors for /api/auth/login in the last 2 hours"
"Compare error rates: last 24h vs previous 24h"
"Are there traffic anomalies on /api/orders?"
"Check SLA compliance for /api/payments"
```

Chat engine routes queries via intent classification, fetches data from CloudWatch/DynamoDB, and generates responses via Bedrock.

### 5. **Auto-Fix Engine**

API endpoint `/api/alerts/auto-fix` to remediate production errors:

1. Categorizes error via pattern matching (syntax, null reference, auth failure, etc.)
2. Parses stack trace to identify source file and line
3. Fetches source code from GitHub
4. Sends error + source to Bedrock for fix generation
5. Creates PR with fix on dedicated branch
6. Notifies team via Microsoft Teams

### 6. **Microsoft Teams Integration**

All events produce rich adaptive cards:
- PR summaries with inline action buttons
- Pipeline failure analysis with links
- Auto-heal status and generated fixes
- Conflict detection warnings
- Error rate & SLA violation alerts
- Traffic anomaly notifications

---

## Setup

### Prerequisites

- Python 3.10+
- GitHub Personal Access Token (with `repo` scope)
- AWS Account with Bedrock access (Claude 3 Haiku)
- Microsoft Teams webhook URL (optional)
- Redis instance (for caching)
- DynamoDB tables (created automatically or via CloudFormation)

### Installation

```bash
# Clone and navigate to project
cd SynapseOps

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create `.env` file in the root directory:

```env
# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxx
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# Bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_BACKEND=runtime  # runtime | agentcore
BEDROCK_AGENT_ID=
BEDROCK_AGENT_ALIAS_ID=
BEDROCK_AGENT_SESSION_PREFIX=synapseops

# Teams (optional)
TEAMS_WEBHOOK_URL=https://outlook.webhook.office.com/webhookb2/...

# Application
APP_BASE_URL=https://your-domain.com
PORT=5000

# Monitoring
MONITORED_APIS=/api/users,/api/payments,/api/auth

# Redis
REDIS_URL=redis://localhost:6379

# DynamoDB
DYNAMODB_REGION=us-east-1
```

### Run Locally

```bash
python app.py
```

Server starts on `http://0.0.0.0:5000`

For webhook testing locally, use ngrok:

```bash
ngrok http 5000
```

### GitHub Webhook Configuration

1. Go to repository → Settings → Webhooks → Add webhook
2. **Payload URL**: `https://your-domain.com/webhook` (or ngrok URL for local)
3. **Content type**: `application/json`
4. **Secret**: `GITHUB_WEBHOOK_SECRET` value
5. **Events**: Select "Pull requests" and "Workflow runs"
6. **Active**: Checked

---

## API Endpoints

### Dashboard & UI
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard with live PR feed |
| `/metrics` | GET | Real-time metrics and monitoring dashboard |
| `/pipelines` | GET | Pipeline runs and failure history |
| `/chat` | GET | Chat interface UI |

### REST APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Overall statistics (total PRs, failures, metrics) |
| `/api/prs` | GET | List all processed PRs |
| `/api/pipelines` | GET | List pipeline records |
| `/api/metrics` | GET | Aggregated metrics by time range |
| `/api/alerts` | GET/POST | Manage monitored APIs and alerts |
| `/api/alerts/auto-fix` | POST | Trigger auto-fix for error |
| `/api/alerts/categorize` | POST | Categorize error type |
| `/api/chat` | POST | Natural language query interface |
| `/health` | GET | Health check |

### WebSocket
| Endpoint | Protocol | Description |
|----------|----------|-------------|
| `/ws` | WebSocket | Real-time activity feed |

---

## AWS Services

| Service | Purpose |
|---------|---------|
| **Amazon Bedrock** | LLM inference (Claude 3 Haiku) for code analysis, diagnostics, and fix generation |
| **Amazon EKS** | Container orchestration for deployment |
| **Amazon ECR** | Docker image registry |
| **Amazon DynamoDB** | Persistent storage (PRs, pipelines, alerts, metrics, audit logs) |
| **Amazon CloudWatch** | Application logs and metrics collection |
| **Amazon CloudWatch Logs Insights** | Querying application logs for error analysis and anomaly detection |
| **Amazon ElastiCache (Redis)** | Caching layer, rate limiting, alert cooldown |
| **Elastic Load Balancer** | Public endpoint for application and webhooks |
| **IAM** | Pod-level access via IRSA (service account role binding) |

---

## File Structure

```
SynapseOps/
├── app/                          # FastAPI application
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Configuration management
│   ├── models/
│   │   └── schemas.py            # Pydantic request/response models
│   ├── routes/
│   │   ├── alerts.py             # Alert & auto-fix endpoints
│   │   ├── chat.py               # Chat interface
│   │   ├── metrics.py            # Metrics endpoints
│   │   └── websockets.py         # WebSocket for live feed
│   ├── services/
│   │   ├── llm.py                # Bedrock LLM integration
│   │   ├── chat_engine.py        # NL intent classification & response
│   │   ├── error_analyzer.py     # Error analysis & categorization
│   │   ├── auto_fix.py           # Auto-fix generation
│   │   ├── code_analyzer.py      # Stack trace parsing
│   │   ├── anomaly_detector.py   # Anomaly detection algorithms
│   │   ├── deployment_tracker.py # Deployment correlation
│   │   ├── sla_tracker.py        # SLA compliance checks
│   │   ├── cloudwatch.py         # CloudWatch Logs Insights queries
│   │   ├── dynamodb.py           # DynamoDB operations
│   │   ├── cache.py              # Redis caching
│   │   ├── retry.py              # Retry with exponential backoff
│   │   └── notifier.py           # Teams notifications
│   └── tasks/
│       └── scheduler.py          # APScheduler for monitoring jobs
├── agents.py                     # Multi-agent PR analysis pipeline
├── auto_healer.py                # Pipeline failure analysis & fix
├── conflict_detector.py          # PR conflict detection
├── github_client.py              # GitHub API wrapper
├── bedrock_client.py             # Bedrock LLM wrapper
├── store.py                      # In-memory storage + DynamoDB
├── app.py                        # Entry point (runs uvicorn)
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container image
├── helm/                         # Kubernetes Helm chart
└── README.md                     # This file
```

---

## Resilience & Error Handling

All external API calls (Bedrock, GitHub, Teams) implement **retry with exponential backoff**:

| Integration | Max Retries | Base Delay | Backoff Strategy |
|-------------|------------|-----------|-----------------|
| Amazon Bedrock | 3 | 2s | Exponential + jitter |
| GitHub API | 3 | 1s | Exponential + jitter |
| Teams Webhook | 3 | 1s | Exponential + jitter |

Rate limiting is enforced via Redis for chat API (configurable per minute).

---

## Deployment

### Docker

```bash
docker build -t synapse-ops:latest .
docker run -p 5000:5000 --env-file .env synapse-ops:latest
```

### Kubernetes (Helm)

```bash
helm install synapse-ops ./helm/synapse-ops/ -f values.yaml
```

See `helm/synapse-ops/values.yaml` for configuration options.

---

## Monitoring & Logging

- **Structured logs** via `structlog` (JSON format)
- **CloudWatch integration** for log aggregation
- **Dashboard** at `GET /metrics` for real-time metrics
- **Audit logs** stored in DynamoDB for compliance

---

## Usage Examples

### Example 1: PR Analysis Comment

When you open a PR, SynapseOps posts:

```
# AI-Powered PR Summary

## Overview
Adds payment retry logic to the checkout service

## Changes
- Feature: Payment service improvements
- Risk: Medium

## Highlights
✓ Good error handling
✓ Proper logging
⚠ Consider adding rate limiting

## Recommendation
Approve
```

### Example 2: Pipeline Auto-Heal

When tests fail:

```
# Pipeline Fix Generated

**Root Cause:** Missing import in utils.py

**Fix Applied:**
- Branch: fix/test-import-error
- Commit: Add missing import statement
- Status: ✓ Tests passed on retry
```

### Example 3: Chat Query

```
POST /api/chat
{
  "message": "Show me errors for /api/orders in the last hour"
}

Response:
{
  "response": "Found 3 errors in /api/orders over the last hour...",
  "intent": "api_error_analysis",
  "data": {
    "api": "/api/orders",
    "error_count": 3,
    "errors": [...]
  }
}
```

---

## Troubleshooting

**Q: Webhook not triggering?**
- Verify `GITHUB_WEBHOOK_SECRET` matches GitHub repo settings
- Check firewall/security group allows inbound HTTPS to public endpoint
- Review CloudWatch logs for request details

**Q: Bedrock calls failing?**
- Ensure AWS credentials have `bedrock:InvokeModel` permissions
- Verify model ID is available in region
- Check rate limits on Bedrock

**Q: Teams notifications not appearing?**
- Verify `TEAMS_WEBHOOK_URL` is correct and not expired
- Check network connectivity to `outlook.webhook.office.com`
- Review application logs for webhook errors

**Q: Chat responses are slow?**
- Increase Bedrock timeout in `app/services/llm.py`
- Optimize CloudWatch Logs Insights queries
- Add Redis caching for frequently accessed data

---

## Contributing

Pull requests welcome! Please:
- Add tests for new features
- Update documentation
- Follow PEP 8 style guide
- Reference issue numbers in commit messages

---

## License

MIT
| `/webhook` | POST | GitHub webhook receiver |

## AWS Services Used

- **Amazon Bedrock** — Foundation model invocation (Claude 3 Sonnet)
- **Bedrock AgentCore pattern** — Supervisor + worker agent orchestration
- **IAM** — Secure access to Bedrock APIs

## Evaluation Alignment

| Criteria | How This Project Addresses It |
|----------|------------------------------|
| Application Quality (30pts) | Clean architecture, error handling, webhook signature verification |
| Amazon Q Utilization (30pts) | Built using Kiro IDE with specs and steering |
| Productivity Demo (20pts) | Automates PR review — saves 10-15 min per PR |
| Innovation (20pts) | Multi-agent orchestration, risk assessment, actionable code review |
