# SynapseOps — Comprehensive Architecture Overview

**Version**: 1.0  
**Framework**: FastAPI (Python 3.11+)  
**Deployment**: AWS EKS + CloudWatch + DynamoDB + Bedrock  
**Built for**: AWS Codeathon 2026 (TopGear Challenge)

---

## Executive Summary

SynapseOps is an **AI-powered, event-driven DevOps platform** that orchestrates multiple autonomous agents to automate GitHub PR analysis, CI/CD pipeline healing, production monitoring, and incident response. The system couples **multi-agent LLM orchestration** with real-time infrastructure monitoring, creating a fully autonomous DevOps cognitive assistant.

**Core Value**: Real-time intelligence + automated remediation across the entire DevOps lifecycle.

---

## 1. High-Level Architecture

### Overall Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   EVENT SOURCES                             │
├─────────────────────────────────────────────────────────────┤
│  GitHub Webhooks   │  CloudWatch Logs  │  Scheduled Tasks   │
│  (PR, Workflow)    │  (API Activity)   │  (Monitoring Job)  │
└──────────────┬──────────────────┬──────────────────┬────────┘
               │                  │                  │
               ▼                  ▼                  ▼
        ┌──────────────────────────────────────────────┐
        │     FASTAPI APPLICATION (Unified Server)     │
        ├──────────────────────────────────────────────┤
        │  • Webhook Handler (/webhook)                │
        │  • Dashboard + Chat UI (HTML/WebSocket)      │
        │  • API Routes (alerts, metrics, chat)        │
        │  • APScheduler Background Jobs               │
        │  • Activity Log & Deduplication              │
        └──────────────┬────────────────────────┬──────┘
                       │                        │
      ┌────────────────┼────────────────────────┼──────────────────┐
      │                │                        │                  │
      ▼                ▼                        ▼                  ▼
┌─────────────┐ ┌──────────────┐ ┌──────────────────┐ ┌─────────────┐
│ AGENT       │ │ MONITORING   │ │ DEPLOYMENT GATE  │ │ SERVICES    │
│ SYSTEM      │ │ SERVICES     │ │ (AI-Driven)      │ │ (Analyzers) │
│ • Diff      │ │ • CloudWatch │ │                  │ │ • Error     │
│ • Review    │ │ • Anomaly    │ │ Traffic Safety   │ │ • Chat      │
│ • Summary   │ │ • Error Rate │ │ Analysis         │ │ • Code Fix  │
│ • Priority  │ │ • SLA Track  │ │                  │ │ • Auto-Fix  │
└─────────────┘ └──────────────┘ └──────────────────┘ └─────────────┘
      │                │                        │                  │
      └────────────────┼────────────────────────┼──────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │     PERSISTENCE LAYER       │
        └──────────────┬──────────────┘
               │       │
      ┌────────▼─┐  ┌──▼─────────┐  ┌─────────────┐
      │ DynamoDB │  │ Redis      │  │ GitHub API  │
      │ • Alerts │  │ • Cache    │  │ • PR Data   │
      │ • Metrics│  │ • Sessions │  │ • Workflow  │
      │ • Audit  │  │ • Rate     │  │ • Code Repo │
      │ • PRs    │  │   Limits   │  │             │
      └──────────┘  └────────────┘  └─────────────┘
                       │
      ┌────────────────┼────────────────┐
      │                │                │
      ▼                ▼                ▼
┌─────────────┐ ┌────────────────┐ ┌──────────────┐
│ Amazon      │ │ Microsoft      │ │ CloudWatch   │
│ Bedrock     │ │ Teams          │ │ Logs Insights│
│ (LLM)       │ │ (Notifications)│ │ (Log Source) │
└─────────────┘ └────────────────┘ └──────────────┘
```

---

## 2. Component Structure

### 2.1 Application Layout

```
app/
├── __init__.py
├── config.py                 # Settings from environment
├── main.py                   # FastAPI app, routes, middleware, lifespan
├── models/
│   ├── __init__.py
│   └── schemas.py            # Pydantic request/response models
├── routes/
│   ├── __init__.py
│   ├── alerts.py             # /api/alerts/* (error monitoring, auto-fix)
│   ├── chat.py               # /api/chat (NL query interface)
│   ├── metrics.py            # /api/metrics (dashboards, data feeds)
│   ├── websockets.py         # /ws/* (real-time activity, chat, notifications)
│   └── __init__.py
├── services/
│   ├── __init__.py
│   ├── llm.py                # Bedrock model invocation, multi-model support
│   ├── cloudwatch.py         # CloudWatch Logs Insights + stream scanning
│   ├── cache.py              # Redis connection pool, cache/rate limiting
│   ├── dynamodb.py           # DynamoDB resource, table operations
│   ├── retry.py              # Retry logic with exponential backoff
│   ├── notifier.py           # Teams adaptive cards via webhook
│   ├── chat_engine.py        # Intent classification, context building
│   ├── error_analyzer.py     # Error rate detection, thresholds
│   ├── performance.py        # Latency analysis, slowest APIs
│   ├── anomaly_detector.py   # Predictive trends, traffic spikes
│   ├── incident_analyzer.py  # Recurring errors, error fingerprinting
│   ├── sla_tracker.py        # SLA compliance per API
│   ├── deployment_tracker.py # Correlation: deploy → error spike
│   ├── deployment_gate.py    # AI-driven deploy safety analysis
│   ├── auto_fix.py           # Error categorization, code fix generation
│   ├── code_analyzer.py      # Stack trace parsing, repo integration
│   ├── k8s_client.py         # Kubernetes cluster introspection
│   ├── log_analyzer.py       # Request tracing, correlation ID search
│   └── websocket_manager.py  # WebSocket connections, broadcast
├── static/
│   └── chat.html             # Chat widget (injected in templates)
└── tasks/
    ├── __init__.py
    └── scheduler.py          # APScheduler background monitoring jobs
```

### 2.2 Root-Level Modules (Backward Compatibility)

```
Root level (dual interface pattern for legacy support):
├── agents.py                 # Multi-agent PR analysis (Supervisor pattern)
├── auto_healer.py            # Pipeline failure code fix generation
├── bedrock_client.py         # Wrapper → app.services.llm
├── github_client.py          # GitHub API client (REST, retries)
├── teams_notifier.py         # Teams card sender (PR summary, pipeline)
├── conflict_detector.py      # PR overlap detection
├── pipeline_monitor.py       # Workflow failure analysis → auto-heal
├── activity_log.py           # Activity log (DynamoDB + in-memory cache)
├── store.py                  # PR/Pipeline record storage (DynamoDB-backed)
├── config.py                 # Re-export from app.config (config delegation)
├── diagnose.py               # Diagnostics helper
└── dedup.py                  # Event deduplication (GitHub delivery IDs)
```

### 2.3 Configuration & Examples

```
├── .env.example              # Environment variable template
├── requirements.txt          # Python dependencies
├── Dockerfile                # Docker build image (EKS)
├── docker-compose.yml        # Local development (optional)
├── helm/
│   └── synapse-ops/
│       ├── Chart.yaml        # Helm chart metadata
│       ├── values.yaml       # Helm default values
│       └── templates/        # K8s manifests (Deployment, Service, etc.)
├── ecs/
│   └── task-definition.json  # AWS ECS task definition (alternative to K8s)
└── redeploy.sh              # Deployment automation script
```

---

## 3. Key Architectural Patterns & Design Decisions

### 3.1 Pattern: Event-Driven, Handler-Driven Orchestration

**Design**: Webhook events trigger background async handlers that orchestrate services without blocking the HTTP response.

```python
@app.post("/webhook", status_code=202)
async def webhook(request: Request):
    # Validate & deserialize (fast)
    # Check dedup (fast)
    # Enqueue handler in thread pool (non-blocking)
    _run_in_background(_process_pr, repo, pr_number)
    return {"message": "Accepted, processing in background"}  # Returns 202 immediately
```

**Rationale**:
- GitHub webhooks have strict timeout (10s); handlers can run for minutes
- 202 Accepted signals async processing without blocking
- Deduplication prevents duplicate work from GitHub retries
- Background threads maintain state for dashboard updates

### 3.2 Pattern: Multi-Agent Supervisor (Sequential Orchestration)

**Design**: Specialized agents execute in sequence; Supervisor collects results.

```
Diff Analyst (analyze what changed)
    ↓
Code Reviewer (assess quality/security)
    ↓
Summary Generator (synthesize final recommendation)
    ↓
Priority Assessor (classify urgency)
    ↓
[Supervisor] → Post comment + Teams notification
```

**Rationale**:
- Each agent focuses on one concern (separation of concerns)
- Sequential allows later agents to use earlier results
- Total latency: ~30-45s for 4 LLM calls (acceptable for async)
- Fallback: if any agent fails, partial results still useful

### 3.3 Pattern: Singleton Service Pattern with Thread Safety

**Design**: Services are lazy-initialized singletons with thread-safe locks.

```python
_client = None
_lock = threading.Lock()

def _get_client():
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = redis.Reddit(...)
    return _client
```

**Rationale**:
- Minimize resource creation (DB connections, HTTP pools)
- Thread pool workers share same instances → connection pooling
- Double-check locking pattern prevents initialization race
- Applied to: Redis, DynamoDB, Bedrock, HTTP clients

### 3.4 Pattern: Smart Caching with Automatic Fallback

**Design**: Try primary source; if unavailable, fall back transparently.

```
CloudWatch Logs Insights (indexed, 5-30min lag)
    ↓ [query fails or no results]
CloudWatch Log Stream Scanner (raw events, <1s lag)
    ↓ [both fail]
In-Memory Cache (300s TTL)
    ↓ [cache miss]
Return last known good or error
```

**Rationale**:
- Logs Insights has indexing delay; stream scan shows recent events
- Cache avoids repeated queries during high load
- Graceful degradation: partial data beats no data
- Monitoring never blocks due to unavailable storage

### 3.5 Pattern: Environment-Driven Configuration

**Design**: All secrets/settings via environment variables; Pydantic validation at startup.

```python
class Settings(BaseSettings):
    github_token: str = ""
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    error_rate_threshold: float = 50.0  # Validated in field_validator
    
    @field_validator("error_rate_threshold")
    def validate_threshold(cls, v):
        if not 0 < v <= 100:
            raise ValueError(...)
        return v

def validate_settings_on_startup() -> list[str]:
    """Returns list of warnings for missing critical settings."""
```

**Rationale**:
- No hardcoded secrets; safe for CI/CD
- Validation catches config errors at startup, not runtime
- Warnings logged for non-critical but recommended settings
- `get_settings()` singleton for entire app

### 3.6 Pattern: Differentiated Alerting with Cooldown

**Design**: Alert once per service per cooldown window to prevent alarm fatigue.

```python
def _maybe_alert(api_path, metrics):
    last_alert_time = cache.get(f"alert:last:{api_path}")
    if last_alert_time:
        cooldown = timedelta(minutes=settings.alert_cooldown_minutes)
        if now - last_alert_time < cooldown:
            return False  # Skip alert
    
    # Send alert, update last_alert_time
    notifier.send_teams_alert(alert)
    cache.set(f"alert:last:{api_path}", now.isoformat(), 3600)
    return True
```

**Rationale**:
- 1000 errors in 1 minute → 1 alert, not 1000
- Configurable cooldown (default 60min) balances response time vs. noise
- Redis TTL ensures cleanup even if Bedrock reset
- Teams notification only for genuine new incidents

### 3.7 Pattern: AI-Driven Deployment Gate (Safety Analysis)

**Design**: LLM analyzes current traffic/error conditions to block unsafe deployments.

```
Deployment webhook (main/master branch, success)
    ↓
Evaluation:
  - Is traffic at peak? (> baseline × 1.5)
  - Is error rate > 5%?
  - Is P99 latency > 3000ms?
    ↓ [Any yes] → HOLD deployment
    ↓ [All no] → ALLOW deployment
    
Background job (120s) rechecks held deployments, releases when safe
```

**Rationale**:
- Prevents deployments during customer-impacting issues
- Automated recheck avoids manual oversight
- Persisted to DynamoDB; survives restarts
- Prevents thundering herd (sequential recheck)

---

## 4. Integration Points

### 4.1 GitHub Integration

**Endpoints Used**:
- **REST API** (https://api.github.com)
  - `GET /repos/{owner}/{repo}/pulls/{pr}` → PR metadata
  - `GET /repos/{owner}/{repo}/pulls/{pr}.diff` → Diff
  - `GET /repos/{owner}/{repo}/pulls/{pr}/files` → File stats
  - `POST /repos/{owner}/{repo}/issues/{pr}/comments` → Post comment
  - `PUT /repos/{owner}/{repo}/pulls/{pr}/merge` → Merge PR
  - `GET /repos/{owner}/{repo}/actions/runs/{run}/jobs` → Job info
  - `GET /repos/{owner}/{repo}/actions/jobs/{job}/logs` → Job logs
  - `POST /repos/{owner}/{repo}/git/refs` → Create branch
  - `PUT /repos/{owner}/{repo}/contents/{path}` → Update file
  - `POST /repos/{owner}/{repo}/pulls` → Create PR

**Webhook Events Consumed**:
- `pull_request` (actions: opened, synchronize, reopened)
- `workflow_run` (action: completed, conclusions: success/failure)
- `deployment` (action: created)

**Auth**: Token authentication via `Authorization: token {GITHUB_TOKEN}`

**Retry Strategy**: 3 retries with exponential backoff (0.5s, 1s, 2s); handles 502/503/504

**Client**: `requests.Session` with connection pooling (10 max connections)

### 4.2 Amazon Bedrock LLM Integration

**Model Support**:
- Anthropic Claude (Claude 3 Haiku, Claude 3 Sonnet, etc.)
- Amazon Nova (Nova Micro, Nova Small, Nova Pro)
- Meta Llama (Llama 2, Llama 3)
- Generic Converse API models

**Request Format** (auto-detected from `model_id`):
```python
# Anthropic
{
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 4096,
    "messages": [{"role": "user", "content": prompt}],
    "system": "system_prompt (optional)"
}

# Nova
{
    "messages": [{"role": "user", "content": [{"text": prompt}]}],
    "inferenceConfig": {"max_new_tokens": 4096, "temperature": 0.3},
    "system": [{"text": "system_prompt (optional)"}]
}
```

**Invocations** (6 primary use cases):
1. **Diff Analysis** — categorize PR changes (feature/bugfix/refactor)
2. **Code Review** — assess quality/security concerns
3. **Summary Generation** — synthesize PR summary
4. **Priority Assessment** — classify PR urgency (Critical/High/Medium/Low)
5. **Pipeline Failure Analysis** — identify root cause from logs
6. **Auto-Fix Generation** — generate code patches for errors

**Retry Strategy**: 3 retries with exponential backoff (2s, 4s, 8s) for throttling/timeouts

**Request Timeout**: 60s total; Bedrock inference typically 10-20s

**Error Handling**: 
- Bedrock invocation failures → log, still post partial comment
- LLM latency included in total PR analysis time (~30-45s)

### 4.3 DynamoDB Persistence

**Tables Created On-Demand** (via `_ensure_table()`):

| Table Name | PK | SK | Purpose |
|---|---|---|---|
| `{prefix}-pr-records` | `REPO#{repo}` | `PR#{pr_number}` | PR analysis results |
| `{prefix}-pipeline-records` | `REPO#{repo}` | `RUN#{run_id}` | Pipeline run status |
| `{prefix}-alerts` | `ALERT#{api}` | `{timestamp}` | Error rate alerts |
| `{prefix}-metrics` | `METRIC#{api}` | `{timestamp}` | Hourly metric snapshots |
| `{prefix}-audit` | `AUDIT#{action}` | `{timestamp}` | Audit trail (fixes, actions) |
| `{prefix}-activity` | `ACTIVITY#{date}` | `{timestamp}` | Activity log entries |
| `{prefix}-held-deployments` | `{repo}` | `{run_id}` | Held deployments awaiting safety |

**Billing Mode**: `PAY_PER_REQUEST` (no provisioned capacity; scales automatically)

**Data Format**:
- Floats → Decimal (DynamoDB native type)
- DynamoDB Decimal → Python float via `_decimal_to_float()`
- TTL not used; manual cleanup via queries

**Write Patterns**:
- **Async writes** (monitoring) — don't block HTTP responses
- **Background cleanup** — hourly rollup aggregates metrics
- **Query patterns** — recent-first (`ScanIndexForward=False`)

### 4.4 Redis Caching

**Connection Pool**: 
```python
pool = redis.ConnectionPool.from_url(
    url,
    decode_responses=True,
    max_connections=20,
    socket_timeout=3,
    retry_on_timeout=True
)
```

**Use Cases**:
| Key Pattern | TTL | Purpose |
|---|---|---|
| `metrics:latest:{api}` | 2min | Most recent API metrics |
| `alert:last:{api}` | 1hr | Last alert timestamp (cooldown) |
| `rollup:hourly:{api}` | 2hrs | Hourly metric aggregation |
| `monitored_apis` | 30days | Cached list of monitored endpoints |
| `chat:rate:global` | 60sec | Rate limit counter (chat requests) |

**Fallback**: If Redis unavailable, `CacheService` returns `None` gracefully; no blocking errors

**Rate Limiting**: Sliding window (Redis SETEX); per-minute limits via cache key

### 4.5 Microsoft Teams Notifications

**Delivery Method**: Webhook via Power Automate (or Teams native connector)

**Payload Format**: Adaptive Card (JSON)

```json
{
    "type": "message",
    "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {"type": "TextBlock", "text": "Title", "weight": "Bolder"},
                {"type": "FactSet", "facts": [
                    {"title": "Key", "value": "Value"}
                ]},
                {"type": "TextBlock", "text": "Summary", "wrap": true}
            ]
        }
    }]
}
```

**Notification Types**:
1. **PR Summary** — AI review results + Approve/Reject actions
2. **Pipeline Failure** — Root cause analysis + auto-heal status
3. **Error Alerts** — Error rate exceeded, SLA breach, anomalies
4. **Deployment Gate** — Hold reason, recheck notification

**Retry Strategy**: 3 retries with exponential backoff (1s, 2s, 4s) for transient errors

### 4.6 CloudWatch Logs Integration

**Log Group**: Configured via `CLOUDWATCH_LOG_GROUP` (e.g., `/aws/lambda/my-service`)

**Query Strategy** (Two-tier):
1. **CloudWatch Logs Insights** (optimal)
   - SQL-like queries: `fields @timestamp, path, statusCode, duration`
   - Indexes last ~1M events
   - Latency: 5-30s (initial indexing delay)
   - Cost: $0.50 per GB scanned

2. **Log Stream Scanning** (fallback, <2s)
   - Scan raw events if Insights slow/unavailable
   - In-memory 300s cache
   - Handles recent data with indexing lag
   - No query cost

**Queries Used**:
- Error rate per API (5xx only vs. all 4xx/5xx)
- Latency percentiles (p50, p99)
- Top slow APIs
- Recurring error fingerprinting
- Request tracing via `correlationId`

**Example Query**:
```
fields @timestamp, statusCode, path, duration
| filter statusCode >= 500 and path like "/api/users"
| stats count(*) as error_count by statusCode
```

---

## 5. Agent System & Orchestration Flow

### 5.1 PR Analysis Multi-Agent Pipeline

**Trigger**: GitHub `pull_request` webhook (opened, synchronize, reopened)

**Flow**:
```
1. Webhook Handler
   ├─ Verify signature (HMAC-SHA256)
   ├─ Check dedup (delivery ID)
   └─ Enqueue _process_pr() in thread pool
   
2. _process_pr() handler
   ├─ Fetch PR details (title, author, branches)
   ├─ Fetch diff (raw unified format)
   ├─ Fetch file list (with +/- stats)
   └─ Enqueue supervisor in thread pool
   
3. Supervisor.run() [agents.py]
   ├─ Diff Analyst Agent
   │  ├─ Output: Change category, files grouped by area, risk assessment
   │  └─ Duration: ~4-6s (LLM invocation)
   │
   ├─ Code Reviewer Agent
   │  ├─ Input: Raw diff
   │  ├─ Output: Quality issues, security concerns, highlights
   │  └─ Duration: ~4-6s
   │
   ├─ Summary Generator Agent
   │  ├─ Input: PR details + diff analysis + code review
   │  ├─ Output: Polished Markdown summary (2-min read)
   │  └─ Duration: ~4-6s
   │
   ├─ Priority Assessor Agent
   │  ├─ Input: Summary output
   │  ├─ Output: Priority level (Critical/High/Medium/Low)
   │  └─ Duration: ~4-6s
   │
   └─ Conflict Detector [conflict_detector.py]
      ├─ Query: Find other open PRs
      ├─ Output: File overlaps, merge conflict risks
      └─ Duration: <1s (GitHub API query)

4. Store Results
   ├─ Save PR record to DynamoDB
   ├─ Store agent outputs + metrics
   └─ Duration: <1s

5. Notifications
   ├─ Post comment on GitHub PR
   ├─ Send adaptive card to Teams
   └─ Both include Approve/Reject action links

Total Latency: ~30-45 seconds (acceptable for async)
```

### 5.2 Agents Detailed

| Agent | Responsibility | Prompt Strategy | Confidence Factors |
|-------|---|---|---|
| **Diff Analyst** | Classify changes (feature/bugfix/refactor/docs/config); Group files by area; Identify risk | Change category must match patterns; Files grouped logically | File count, additions/deletions ratio |
| **Code Reviewer** | Identify quality, security, best practice issues; Highlight good patterns | Specific concerns (naming, complexity, hardcoded secrets) | Code patterns recognized; Stack language |
| **Summary Generator** | Create human-readable Markdown suitable for team review; Include metadata | Combine prior outputs; Executive summary format | LLM quality; clarity metrics |
| **Priority Assessor** | Assign PR urgency based on code impact and risk | Pattern matching from summary; Classify as Critical/High/Medium/Low | File areas touched (core vs. config); test coverage |
| **Conflict Detector** | Identify overlapping files with other open PRs | Query GitHub API per file in PR | Exact file path matches |
| **Description Generator** | Auto-fill empty PR body if description missing | Use summary output + PR type | Only runs if body.length < 10 |

### 5.3 Agent Output Structure

```python
@dataclass
class AgentResult:
    agent_name: str           # "diff_analyst", "code_reviewer", etc.
    status: str               # "completed" | "failed"
    output: str               # Agent response (Markdown/JSON)
    duration_ms: int          # Execution time
    error: Optional[str]      # Error message if failed
    confidence: float         # 0.0-1.0 for important results

@dataclass
class PRRecord:
    repo: str                 # "owner/repo"
    pr_number: int            # GitHub PR number
    title: str                # PR title
    author: str               # GitHub username
    risk_level: str           # "Low", "Medium", "High"
    pr_type: str              # "Feature", "Bugfix", "Refactor", etc.
    priority: str             # "Critical", "High", "Medium", "Low"
    summary: str              # Final summary comment
    agent_results: List[AgentResult]  # Per-agent outputs
    total_duration_ms: int    # Total pipeline time
    timestamp: str            # ISO8601 creation time
```

---

## 6. Event-Driven Workflow: Webhooks, Monitoring, Tasks

### 6.1 Event Types & Handlers

```python
@app.post("/webhook")
async def webhook(request):
    event_type = request.headers["X-GitHub-Event"]
    payload = await request.json()
    
    if event_type == "pull_request":
        # Trigger: PR opened, updated, reopened
        _run_in_background(_process_pr, repo, pr_number, pr_object)
        
    elif event_type == "workflow_run":
        # Trigger 1: Workflow completed successfully (deployment gate)
        if action == "completed" and conclusion == "success" and is_main_branch:
            _run_in_background(_process_deployment_gate, repo, run)
        
        # Trigger 2: Workflow failed (pipeline healing)
        elif action == "completed" and conclusion == "failure":
            _run_in_background(_process_pipeline, repo, run)
    
    elif event_type == "deployment":
        # Trigger: Deployment created
        _run_in_background(_process_deployment_event, repo, deployment, sender)
    
    return {"message": "Accepted"}  # 202 Async
```

### 6.2 Background Job Orchestration (APScheduler)

**Startup**: `start_scheduler()` in `lifespan` context

```python
jobs = [
    (monitor_error_rates,          "interval", {"seconds": 60},    "error_monitor"),
    (monitor_slow_apis,            "interval", {"minutes": 5},     "slow_monitor"),
    (run_anomaly_detection,        "interval", {"minutes": 5},     "anomaly"),
    (run_recurring_error_check,    "interval", {"hours": 1},       "recurring"),
    (run_sla_check,                "interval", {"hours": 1},       "sla"),
    (hourly_rollup,                "interval", {"hours": 1},       "rollup"),
    (recheck_held_deployments,     "interval", {"seconds": 120},   "deployment_gate_recheck"),
]

for func, trigger, kwargs, job_id in jobs:
    scheduler.add_job(func, trigger, **kwargs, id=job_id, replace_existing=True, 
                      max_instances=1, coalesce=True)
scheduler.start()
```

**Error Handling**: Global listener logs failures; jobs continue on exceptions

### 6.3 Monitoring Job Details

| Job | Trigger | Duration | Data Source | Action |
|---|---|---|---|---|
| **error_rates** | 60s | CloudWatch (1min window) | Per API → threshold → alert (with cooldown) | Teams alert |
| **slow_apis** | 5min | CloudWatch (1hr window) | Slowest 5 APIs → P99 latency | Teams alert + Bedrock suggestions |
| **anomaly_detection** | 5min | DynamoDB metrics history | Traffic z-score; error trend prediction | Teams alert if z>2.5 or slope>threshold |
| **recurring_errors** | 1hr | DynamoDB audit logs | Error fingerprinting (24h window) | Top 3 recurring → Teams alert |
| **sla_check** | 1hr | DynamoDB metrics | Per API SLA target vs. actuals | Teams alert if violated |
| **hourly_rollup** | 1hr | DynamoDB metrics (60 entries) | Aggregate metrics → rolling 1hr window | Store to DynamoDB + cache |
| **deployment_gate_recheck** | 2min | CloudWatch (live conditions) | Traffic/error/latency snapshot | Release held deployments if safe |

### 6.4 Activity Log (Centralized Events)

**File**: [activity_log.py](activity_log.py)

**Storage**:
- **In-Memory Cache**: Last 500 entries (fast polling, <100ms)
- **DynamoDB Persistence**: Survives restarts (audit trail)

**Event Types** (logged by handlers):
- `PR Analysis Started` → `PR Analysis Completed` (with duration)
- `Pipeline Failure Detected` → `Auto-Heal Applied` (with fix details)
- `Deployment Held` → `Deployment Released` (with reason)
- `Alert Triggered` (error rate, SLA, anomaly)

**API**: `/activity` dashboard and `/api/activity` (WebSocket support)

---

## 7. Data Flow & Persistence Layer

### 7.1 Write Patterns

**Immediate Writes** (HTTP response blocked):
- PR analysis results → DynamoDB `pr-records`
- Pipeline run status → DynamoDB `pipeline-records`
- Activity log entries → In-memory + async DynamoDB

**Fire-and-Forget Writes** (background tasks):
- Alerts → DynamoDB `alerts` table + Redis cache
- Metrics → DynamoDB `metrics` table + Redis cache
- Audit logs → DynamoDB `audit` table
- Teams notifications → HTTP webhook (retry enabled)

### 7.2 Query Patterns

**PR Dashboard** (recent PRs):
```sql
SELECT * FROM pr-records
WHERE repo = "owner/repo"
ORDER BY timestamp DESC
LIMIT 50
```

**Alert History** (last alerts for API):
```sql
SELECT * FROM alerts
WHERE pk = "ALERT#/api/users"
ORDER BY sk DESC
LIMIT 20
```

**Metrics Rollup** (hourly trend):
```sql
SELECT * FROM metrics
WHERE pk = "METRIC#/api/users"
ORDER BY sk DESC
LIMIT 60  -- Last 60 hours
```

### 7.3 Data Consistency Model

**Strong Consistency**:
- PR/Pipeline records (written once, read many)
- Alerts (per-API per-timestamp unique)
- No concurrent updates to same record

**Eventual Consistency** (acceptable):
- Metrics history (aggregation across intervals)
- Activity log (append-only, no updates)
- Cached data (Redis TTL auto-expires)

**Deduplication Strategy**:
- GitHub delivery ID → Exact duplicate detection
- PR commit SHA → Prevents re-analyzing same commit
- Pipeline run ID → Process once per failure

---

## 8. External Dependencies & APIs

### 8.1 Python Dependencies

```
boto3==1.36.0                      # AWS SDK (Bedrock, DynamoDB, CloudWatch, S3)
requests==2.32.0                   # HTTP client (GitHub API, Teams webhook)
fastapi==0.115.6                   # Web framework
uvicorn[standard]==0.34.0          # ASGI server
pydantic==2.10.0                   # Data validation
pydantic-settings==2.7.0           # Config from env
apscheduler==3.10.4                # Background job scheduler
redis==5.2.0                       # Redis client
httpx==0.28.0                      # Modern HTTP (async-capable)
jinja2==3.1.6                      # HTML templating
structlog==24.4.0                  # Structured logging (JSON)
python-dotenv==1.0.1               # Load .env files
python-multipart==0.0.20           # Form data parsing
```

### 8.2 AWS Services Required

| Service | Region | Purpose | IAM Permissions |
|---|---|---|---|
| **CloudWatch Logs** | Configured region | Application logs source | `logs:DescribeLogGroups`, `logs:StartQuery`, `logs:GetQueryResults`, `logs:GetLogEvents` |
| **CloudWatch Logs Insights** | Configured region | Metrics queries | Same as above |
| **Bedrock Runtime** | Configured region | LLM invocations | `bedrock:InvokeModel` |
| **DynamoDB** | Configured region | Data persistence | `dynamodb:GetItem`, `PutItem`, `Query`, `Scan`, `CreateTable`, `UpdateTable` |
| **EC2 (for K8s)** | Default VPC | EKS node instances | EC2 full access (or restricted via instance role) |
| **EKS** | Configured region | Kubernetes cluster | EKS cluster management (or admin role) |

### 8.3 Third-Party APIs

| Service | Authentication | Rate Limits | Retry Logic |
|---|---|---|---|
| **GitHub API** | Personal access token (header) | 5000 req/hr (authenticated) | 3 retries, 0.5-2s backoff |
| **Amazon Bedrock** | IAM role (AWS credentials) | Model-dependent (typically 100k tokens/min) | 3 retries, 2-30s backoff |
| **Microsoft Teams** | Webhook URL (no auth, secret in URL) | 100 req/min per webhook | 3 retries, 1-15s backoff |
| **CloudWatch Logs** | IAM role | 10k queries/sec per account | Built-in SDK retries |

### 8.4 Infrastructure Services

| Service | Purpose | Required | Optional |
|---|---|---|---|
| **Redis** | Caching, rate limiting, session storage | No* | Yes (graceful fallback) |
| **EC2/EKS** | Container orchestration | Yes | Can run on EC2/Fargate |
| **RDS/DynamoDB** | Data persistence | DynamoDB (yes) | RDS (no) |

*Redis assumed present in production; optional for local dev

---

## 9. Request-Response Lifecycle

### 9.1 GitHub Webhook → PR Analysis

```
┌──────────────────────────────────────────────────────────────┐
│ GitHub Webhook                                               │
│ POST /webhook (X-GitHub-Delivery: UUID, X-Hub-Signature-256) │
│ Body: { "action": "opened", "pull_request": {...}, ...}     │
└────┬──────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│ Webhook Handler (app/main.py)                                │
├──────────────────────────────────────────────────────────────┤
│ 1. Verify HMAC signature                                     │
│ 2. Check dedup (is_duplicate(delivery_key))                  │
│ 3. Extract repo, PR#, action                                 │
│ 4. Return 202 Accepted immediately                           │
│ 5. Enqueue _process_pr() in thread pool                      │
└────┬──────────────────────────────────────────────────────────┘
     │
     ▼ [Background Thread]
┌──────────────────────────────────────────────────────────────┐
│ _process_pr(repo, pr_number, pr_obj)                         │
├──────────────────────────────────────────────────────────────┤
│ 1. GitHub API: get_pr_details()                              │
│ 2. GitHub API: get_pr_diff()                                 │
│ 3. GitHub API: get_pr_files()                                │
│ 4. Enqueue supervisor.run(details, diff, files)              │
│    └─ Activity log: "PR Analysis Started"                    │
└────┬──────────────────────────────────────────────────────────┘
     │
     ▼ [Thread Pool]
┌──────────────────────────────────────────────────────────────┐
│ Supervisor (agents.py)                                       │
├──────────────────────────────────────────────────────────────┤
│ Sequential agent execution:                                  │
│                                                              │
│ 1. diff_analysis_agent(diff, files)                          │
│    └─ Bedrock invoke (~5s)                                   │
│    └─ Output: category, risk, files summary                  │
│                                                              │
│ 2. code_review_agent(diff)                                   │
│    └─ Bedrock invoke (~5s)                                   │
│    └─ Output: quality/security concerns                      │
│                                                              │
│ 3. summary_generator_agent(details, diff_out, review_out)    │
│    └─ Bedrock invoke (~5s)                                   │
│    └─ Output: polished Markdown summary                      │
│                                                              │
│ 4. priority_assessor_agent(summary)                          │
│    └─ Bedrock invoke (~5s)                                   │
│    └─ Output: priority classification                        │
│                                                              │
│ 5. conflict_detector.check_conflicts(repo, pr#, files)       │
│    └─ GitHub API query (~1s)                                 │
│    └─ Output: overlapping PRs                                │
│                                                              │
│ 6. check_and_generate_description(repo, pr#, details)        │
│    └─ Conditional: if PR body empty → generate               │
│    └─ GitHub API: update_pr_body()                           │
└────┬──────────────────────────────────────────────────────────┘
     │
     ▼ [Result Aggregation]
┌──────────────────────────────────────────────────────────────┐
│ Store & Notify                                               │
├──────────────────────────────────────────────────────────────┤
│ 1. pr_store.save(repo, pr#, {results})                       │
│    └─ DynamoDB: pk=REPO#{repo}, sk=PR#{pr#}                  │
│                                                              │
│ 2. activity_log.log("PR Analysis Completed", duration=45s)   │
│                                                              │
│ 3. post_pr_comment(repo, pr#, summary)                       │
│    └─ GitHub API: POST /issues/{pr}/comments                 │
│    └─ Comment body: "## 🤖 AI-Generated PR Summary\n..."     │
│                                                              │
│ 4. send_teams_notification(...)                              │
│    └─ Teams Webhook: Adaptive Card with Approve/Reject       │
│    └─ Includes: author, risk level, type, priority, files    │
│                                                              │
│ Total elapsed: ~30-45 seconds                                │
│ User sees: Teams notification + GitHub comment within 1min   │
└──────────────────────────────────────────────────────────────┘
```

### 9.2 Workflow Failure → Auto-Heal

```
GitHub workflow_run event (conclusion: failure)
│
├─ Extract: repo, run_id, branch, failed_jobs
│
├─ get_run_jobs() → list of job objects
│
├─ for each job: get_job_logs() → raw logs
│
├─ analyze_pipeline_failure(logs) 
│  └─ Bedrock LLM: "Why did this fail?" 
│  └─ Output: root cause, category, fix suggestion
│
├─ send_pipeline_failure_notification() 
│  └─ Teams Adaptive Card with analysis
│
├─ generate_fix(repo, logs, failed_jobs)
│  └─ Extract file paths from error messages
│  └─ Fetch source files from GitHub
│  └─ Bedrock: "Generate fixed code"
│  └─ Output: {fixable: bool, files: [{path, content, ...}]}
│
├─ [if fixable] apply_fix()
│  ├─ Create feature branch: synapse-ops/auto-fix/{category}-{timestamp}
│  ├─ Commit file changes
│  ├─ Push to GitHub
│  ├─ Create PR with fix
│  └─ Comment on original PR: "Auto-fix created: {PR_URL}"
│
└─ [optional] rerun_workflow()
   └─ GitHub API: POST /actions/runs/{run_id}/rerun
```

### 9.3 Monitoring Loop → Alert

```
APScheduler trigger [every 60 seconds]
│
├─ monitor_error_rates()
│  ├─ Get monitored APIs from cache
│  ├─ for each API:
│  │  ├─ CloudWatchService.get_api_metrics()
│  │  │  └─ Logs Insights query OR stream scan fallback
│  │  ├─ Extract: total_requests, error_count, error_rate (5xx only)
│  │  ├─ threshold = settings.error_rate_threshold (50%)
│  │  ├─ if error_rate >= threshold:
│  │  │  └─ _maybe_alert(api_path)
│  │  │     ├─ Check cooldown (last_alert_time in Redis)
│  │  │     ├─ if not in cooldown:
│  │  │     │  ├─ Teams alert + DynamoDB store
│  │  │     │  └─ Redis: update alert:last:{api} TTL 1hr
│  │  │     └─ else: skip (prevent spam)
│  │  └─ Cache metrics: metrics:latest:{api} TTL 2min
│  │
│  └─ Store metric snapshot: DynamoDB metrics table
│
└─ Dashboard polls /api/metrics → shows latest + history
```

---

## 10. Deployment Architecture

### 10.1 Kubernetes (EKS) Deployment

```yaml
# Helm Chart Structure: helm/synapse-ops/
apiVersion: apps/v1
kind: Deployment
metadata:
  name: synapse-ops
  namespace: default
spec:
  replicas: 2  # High availability
  selector:
    matchLabels:
      app: synapse-ops
  template:
    metadata:
      labels:
        app: synapse-ops
    spec:
      containers:
      - name: synapse-ops
        image: synapse-ops:latest
        ports:
        - containerPort: 5000
        env:
        - name: GITHUB_TOKEN
          valueFrom:
            secretKeyRef:
              name: synapse-ops-secrets
              key: github-token
        - name: BEDROCK_MODEL_ID
          value: "anthropic.claude-3-haiku-20240307-v1:0"
        - name: REDIS_URL
          value: "redis://redis-service:6379/0"
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 5000
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          periodSeconds: 30

---
apiVersion: v1
kind: Service
metadata:
  name: synapse-ops-service
spec:
  selector:
    app: synapse-ops
  ports:
  - protocol: TCP
    port: 80
    targetPort: 5000
  type: LoadBalancer
```

**AWS Resources**:
- **EKS Cluster**: Managed Kubernetes (2+ nodes)
- **Load Balancer**: ALB or NLB for external traffic
- **RDS/DynamoDB**: Database backend
- **CloudWatch Logs**: Log aggregation via ECS/EKS agent
- **IAM Role**: Pod execution role with Bedrock, DynamoDB, CloudWatch permissions

### 10.2 Environment Configuration

```bash
# .env (never commit to git)
GITHUB_TOKEN=ghp_xxxxx...
GITHUB_WEBHOOK_SECRET=whsec_xxxxx...
GITHUB_REPO=owner/repo
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_REGION=us-east-1
AWS_REGION=us-east-1
TEAMS_WEBHOOK_URL=https://outlook.webhook.office.com/...
APP_BASE_URL=https://synapse-ops.company.com
CLOUDWATCH_LOG_GROUP=/aws/ecs/synapse-ops
DYNAMODB_TABLE_PREFIX=synapse-ops
REDIS_URL=redis://localhost:6379/0
ERROR_RATE_THRESHOLD=50.0
SLOW_API_THRESHOLD_MS=2000
MONITORING_INTERVAL_SECONDS=60
ALERT_COOLDOWN_MINUTES=60
MONITORED_APIS=/api/users,/api/orders,/api/payments
CHAT_RATE_LIMIT_PER_MINUTE=30
MONITOR_BRANCH=main
```

---

## 11. Error Handling & Resilience

### 11.1 Retry Policies

**Standard Backoff**:
```python
@retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def some_operation():
    pass
# Delays: 1s, 2s, 4s (exponential)
```

**Service-Specific**:
- GitHub API: 3 retries, 0.5-2s backoff (handles 502/503/504)
- Bedrock: 3 retries, 2-30s backoff (handles throttling)
- CloudWatch: Built-in SDK retries (adaptive mode)
- Teams webhook: 3 retries, 1-15s backoff

### 11.2 Graceful Degradation

| Component | Failure | Fallback |
|---|---|---|
| Redis cache | Unavailable | In-process fallback; no caching |
| CloudWatch Logs Insights | Query timeout | Switch to log stream scanning |
| Bedrock LLM | Throttle/timeout | Retry with backoff; log error; partial result |
| Teams webhook | Network error | Retry; log failure; continue |
| DynamoDB | Unavailable | Log error; proceed with in-memory storage |
| GitHub API | Rate limit | Retry-After header respected |

### 11.3 Circuit Breaker Pattern

```python
class CacheService:
    def __init__(self):
        self.r = _get_redis()  # Returns None if unavailable
    
    def get(self, key):
        if self.r is None:
            return None  # Circuit open
        try:
            return self.r.get(key)
        except redis.ConnectionError:
            # Circuit opens automatically
            return None
```

---

## 12. Monitoring & Observability

### 12.1 Logging Strategy

**Structured Logging** (JSON to CloudWatch):
```python
logger = structlog.get_logger()
logger.info("bedrock_invoke_completed", 
    model=model_id, 
    duration_ms=elapsed,
    tokens_used=usage["input_tokens"],
    prompt_length=len(prompt)
)
# Output: {"event": "bedrock_invoke_completed", "model": "...", ...}
```

**Log Levels**:
- `ERROR`: Failures that block operations
- `WARNING`: Degraded service (retry ongoing, cache miss)
- `INFO`: Key events (PR analysis started, deployment held)
- `DEBUG`: Enable via env variable (noisy, not production)

### 12.2 Metrics Exported

**Application Metrics** (via CloudWatch):
```
pr_analysis_duration_ms        # Histogram
pr_analysis_count_total        # Counter
bedrock_invoke_duration_ms     # Histogram
github_api_call_duration_ms    # Histogram
error_rate_by_api_path         # Gauge
alert_sent_total_by_type       # Counter
```

**System Metrics** (via Kubernetes):
- CPU usage (500m request, 1000m limit)
- Memory usage (512Mi request, 1Gi limit)
- Pod restart count (should be 0)
- Request latency (p50, p99)

### 12.3 Health Checks

```
GET /health              → 200 OK (lightweight)
GET /health/ready        → 200 OK (dependencies check)
  ├─ Redis: PING
  ├─ DynamoDB: DescribeTable
  └─ Return: {"status": "ready|degraded"}
```

---

## 13. Security Considerations

### 13.1 Authentication & Authorization

**GitHub Webhook Verification**:
```python
def _verify_signature(body, signature):
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

**AWS IAM**:
- Pod execution role scoped to: Bedrock, DynamoDB, CloudWatch
- Least privilege principle
- No long-lived AWS keys (use STS)

**GitHub Token**:
- Stored in AWS Secrets Manager (mounted as env var)
- Personal access token with `repo`, `workflow` scopes only
- Rotated quarterly

**Teams Webhook**:
- Secret embedded in URL by Microsoft Teams
- Not exposed in logs or metrics
- HTTPS only

### 13.2 Secret Management

**Where Secrets Live**:
- Environment variables (AWS Secrets Manager → container)
- `.env` file (local dev only, .gitignored)
- GitHub Secrets (CI/CD only)

**Where Secrets Do NOT Go**:
- Logs (sanitized before logging)
- Metrics (redacted)
- DynamoDB (no PII, only metadata)
- Redis (only cache keys, no secrets)

### 13.3 Rate Limiting

**API Endpoints**:
```python
# Chat endpoint: 30 req/min per client
if not cache.check_rate_limit("chat:rate:global", 30, 60):
    raise HTTPException(429, "Rate limit exceeded")
```

**GitHub API**: Automatic 5000 req/hr; retries respect `X-RateLimit-Reset`

**Teams Webhook**: 100 req/min per webhook; built-in backoff

---

## 14. Future Extensibility

### 14.1 Pluggable LLM Models

Current: Bedrock with multi-model support (Anthropic, Nova, Llama)

Future options:
- OpenAI GPT-4 (via HTTP API)
- Azure OpenAI (enterprise)
- Self-hosted LLMs (VLLM, Ollama)
- Fine-tuned models (domain-specific)

**Extension Point**: `LLMService.invoke()` → swap implementation

### 14.2 Additional Alert Channels

Current: Microsoft Teams only

Future options:
- Slack (webhook API)
- PagerDuty (incident management)
- Datadog (observability platform)
- Email (SES)
- SMS (SNS)

**Extension Point**: `NotifierService.send_team_alert()` → multi-channel dispatcher

### 14.3 Customizable Monitoring

Current: CloudWatch logs only

Future options:
- Datadog integration
- New Relic APM
- Prometheus metrics
- Custom metric sources

**Extension Point**: `CloudWatchService` → pluggable log source adapter

---

## Appendix: Key Files Reference

| File | Purpose | Key Classes/Functions |
|---|---|---|
| `app/main.py` | FastAPI app, webhook handler, lifespan | `app`, `webhook()`, `lifespan()` |
| `agents.py` | Multi-agent PR analysis supervisor | `supervisor.run()`, agent functions |
| `app/services/llm.py` | Bedrock LLM invocation | `LLMService.invoke()` |
| `app/services/cloudwatch.py` | CloudWatch queries with fallback | `CloudWatchService.get_api_metrics()` |
| `app/services/error_analyzer.py` | Error rate detection & alerting | `ErrorAnalyzer.analyze_api_errors()` |
| `app/services/deployment_gate.py` | AI-driven deploy safety | `DeploymentGate.evaluate_deployment()` |
| `app/services/chat_engine.py` | Intent classification + context | `ChatEngine.process_message()` |
| `app/tasks/scheduler.py` | APScheduler job definitions | `start_scheduler()`, monitoring jobs |
| `pipeline_monitor.py` | Workflow failure handling | `process_failed_run()` |
| `auto_healer.py` | Code fix generation | `generate_fix()`, `apply_fix()` |
| `store.py` | PR/Pipeline record persistence | `pr_store`, `pipeline_store` |
| `activity_log.py` | Centralized activity logging | `ActivityLog`, `LogEntry` |

---

## Conclusion

SynapseOps combines **intelligent multi-agent orchestration** (Bedrock LLMs) with **real-time infrastructure observability** (CloudWatch, DynamoDB) to create a fully autonomous DevOps cognitive assistant. The event-driven architecture ensures scalability, while the layered services design provides extensibility for future integrations.

Key strengths:
- **Decoupled agents** → Easy to add/modify analysis logic
- **Graceful degradation** → Works even with partial dependencies
- **Cloud-native** → Scales horizontally on EKS
- **Audit trail** → Complete DynamoDB history for compliance
- **Team-centric** → Rich Teams notifications, web dashboard
