# SynapseOps — 8-Minute Demo Speaker Notes
### AWS Codeathon 2026 | TopGear Challenge | Theme 1: AI-Powered Developer Productivity Platform

---

> **Timing Guide**
> | Section | Time | Cumulative |
> |---------|------|------------|
> | Opening Hook | 0:30 | 0:30 |
> | Section 1 — Application Functionality & Quality | 2:00 | 2:30 |
> | Section 2 — AWS Services Feature Utilization | 2:00 | 4:30 |
> | Section 3 — Productivity Demonstration | 1:30 | 6:00 |
> | Section 4 — Innovation & Creativity | 1:30 | 7:30 |
> | Closing | 0:30 | 8:00 |

---

## Opening Hook *(0:30)*

> *Stand in front of the live dashboard or architecture diagram.*

"Every engineering team I've spoken to has the same pain — developers spend more time firefighting pipelines, chasing failed builds, and triaging production alerts than writing code that actually ships.

**SynapseOps** is our answer to that. It's an AI-powered DevOps agent — an always-on, autonomous teammate that reviews your PRs, heals broken pipelines, monitors your production APIs, and answers infrastructure questions in plain English. All without anyone opening a terminal.

Let me show you exactly how it works."

---

## Section 1 — Application Functionality & Quality *(2:00)*

### Architecture *(~20s)*

> *Point to the architecture diagram on screen.*

"SynapseOps is a **FastAPI application deployed on AWS ECS Fargate**, fronted by an Application Load Balancer. It has four core pillars:

1. A **multi-agent PR analysis pipeline** — event-driven via GitHub webhooks
2. A **pipeline failure auto-healer** — spots CI/CD failures, generates fixes, and commits them
3. A **real-time monitoring engine** — continuously analyzing your API traffic in CloudWatch
4. A **natural-language chat interface** — so any engineer can query infrastructure without SQL or Logs Insights queries

All pillars share a common persistence layer — DynamoDB for durability and Redis for caching and rate-limiting."

### Functionality *(~30s)*

> *Switch to the live dashboard or demo the webhook flow.*

"Let me walk you through a real flow. When a developer opens a pull request:

- GitHub fires a webhook to our `/webhook` endpoint
- **Five specialized AI agents** run in sequence — a Diff Analyst, a Code Reviewer, a Summary Generator, a Priority Assessor, and a Description Generator
- Within seconds, an AI-generated review lands on the PR as a GitHub comment
- A rich **Microsoft Teams adaptive card** is delivered with inline Approve/Reject action buttons
- In parallel, our **Conflict Detector** scans every other open PR and flags if two developers are touching the same files

For pipeline failures, the flow is equally automated — we fetch failed job logs, send them to Bedrock for root cause analysis, generate a concrete code fix, push it to the branch, re-trigger the pipeline, and notify the team. Zero human intervention."

### Unit Test Coverage *(~20s)*

"The codebase follows a layered FastAPI architecture — routes, services, models — with full **Pydantic validation at every boundary**. Each route has field-level validators with explicit error messages. The retry decorator in `app/services/retry.py` is designed with exponential backoff and jitter, tested for Bedrock throttling, GitHub rate-limits, and Teams webhook timeouts separately. All external API calls are guarded with `try/except` blocks and logged via `structlog` with structured context."

### Deployment & Setup *(~20s)*

"Deployment is fully containerized. We have:

- A **Dockerfile** for the FastAPI application
- An **ECS task definition** with IRSA-style IAM roles for least-privilege AWS access
- A **Helm chart** for Kubernetes/EKS if teams prefer that route
- Environment-driven configuration — swap models, thresholds, and log groups with env vars, zero code changes

The live endpoint is running right now at our ECS ALB in `ap-south-1`."

### Testing & Validation Proof Points *(~15s)*

"Proof points:
- The monitoring engine runs on a **60-second APScheduler loop** — five independent job functions, each fault-isolated so one failure doesn't cascade
- Deduplication middleware (`app/services/dedup.py`) ensures duplicate webhook events don't spawn duplicate agent runs
- Alert cooldowns are enforced via Redis TTLs — no alert storms"

### Documentation *(~15s)*

"Documentation is comprehensive — we have a DOCUMENTATION.md, an ARCHITECTURE.md, a QUICK_FIX.md for operators, a TROUBLESHOOTING guide, and a setup_webhook guide. The `aidlc-docs` folder captures every design decision from requirements through infrastructure — fully traceable."

---

## Section 2 — AWS Services Feature Utilization *(2:00)*

### KIRO Usage *(~30s)*

> *Reference the `aidlc-docs/` directory structure on screen.*

"**KIRO** — Amazon's AI IDE — was central to how this solution was built. We used KIRO's **AI-Driven Development Lifecycle (AI-DLC)** feature end-to-end:

- KIRO guided us through 10 structured stages: requirements → user stories → application design → functional design → NFR requirements → NFR design → infrastructure design → code generation → build and test
- Every stage produced reviewable artifacts in `aidlc-docs/` before any code was written
- KIRO's spec-driven approach meant our architecture was deliberate, not accidental — 19 components, 47 methods, all designed before the first line of code was generated

This is KIRO doing what it's designed to do: making AI a full development partner, not just an autocomplete."

### Amazon Bedrock AgentCore Implementation *(~35s)*

"**Amazon Bedrock** is the intelligence backbone of SynapseOps. We use **Claude 3 Haiku** as our primary model — fast, cost-efficient, and accurate for code analysis tasks.

What makes our Bedrock integration production-grade is the **dual-backend architecture** in `app/services/llm.py`:

- In `runtime` mode — we invoke Bedrock directly via `bedrock-runtime`, building model-specific request bodies for Anthropic, Nova, and Meta models
- In `agentcore` mode — we switch to `bedrock-agent-runtime` and invoke a pre-deployed **Bedrock Agent** with a persistent session, enabling stateful, multi-turn reasoning

The backend is toggled with a single environment variable: `BEDROCK_BACKEND=agentcore`. All retry logic, timeout handling, and structured logging is shared across both modes.

We also use **Bedrock for four distinct workloads** simultaneously: PR code review, pipeline log analysis, production error fix generation, and natural-language chat response synthesis."

### Breadth of AWS Services Leveraged *(~55s)*

"We don't just use Bedrock — SynapseOps is a genuine multi-service AWS integration:

| Service | How We Use It |
|---------|--------------|
| **Amazon ECS Fargate** | Serverless container hosting for the FastAPI app |
| **Amazon ECR** | Private image registry (`127214194014.dkr.ecr.ap-south-1`) |
| **Amazon Bedrock** | LLM inference — Claude 3 Haiku — for all AI workloads |
| **Amazon DynamoDB** | Persistent storage for PR records, alerts, metrics, audit logs |
| **Amazon CloudWatch Logs Insights** | Primary data source for API error rates, latency, traffic analysis |
| **Amazon ElastiCache (Redis)** | Caching, rate limiting, alert cooldown TTLs |
| **Elastic Load Balancer (ALB)** | Public HTTPS endpoint, GitHub webhook receiver |
| **AWS IAM with IRSA** | Pod-level least-privilege access — task roles scoped per service |

Eight services working together, each with a distinct, justified purpose — not checkbox architecture."

---

## Section 3 — Productivity Demonstration *(1:30)*

### Solution Adoption Readiness *(~20s)*

"SynapseOps is **ready to wire into any existing GitHub repository in under 10 minutes**:

1. Set `GITHUB_REPO`, `GITHUB_TOKEN`, and `GITHUB_WEBHOOK_SECRET` as environment variables
2. Register the ALB URL as a GitHub webhook for `pull_request` and `workflow_run` events
3. Point `CLOUDWATCH_LOG_GROUP` at your application's log group
4. Optionally configure `TEAMS_WEBHOOK_URL` for notifications

No SDK changes. No code modifications in the target repo. No agent to install. It's purely event-driven from the outside."

### Quality of Solution *(~20s)*

"The solution is designed for operational reality:

- **Retry with exponential backoff and jitter** on all three external integrations — Bedrock, GitHub, and Teams — max 3 retries with adaptive delays up to 30 seconds
- **Redis-backed alert cooldowns** prevent notification floods — configurable per-API
- **Structured logging** via `structlog` throughout — every event has a `job_id`, `api_path`, and `error` key for easy filtering
- **Input validation** on every API endpoint using Pydantic validators with explicit, user-safe error messages"

### Measurement Methodology *(~25s)*

"We built the measurement capability into the product itself:

- **SLA Tracker** compares real-time CloudWatch error rates and p99 latency against per-API configurable targets
- **Deployment Tracker** correlates every GitHub Actions deployment with error spikes in a 30-minute window automatically
- **Anomaly Detector** uses **linear regression** to predict when an error rate will breach its threshold — and alerts proactively, before the breach happens
- **Z-score analysis** identifies traffic spikes and drops statistically — flags anything beyond 2.5 standard deviations"

### Quantified Results *(~25s)*

"Here's what SynapseOps eliminates from your team's workflow:

- **PR review time**: From hours-to-days of async review to **seconds** — every PR gets an AI review comment the moment it's opened
- **Pipeline triage time**: From 20-40 minutes of manual log digging to **automated root cause analysis and a code fix committed to the branch**
- **Alert fatigue**: Cooldown-based deduplication reduces notification volume by collapsing repeated alerts — one alert per API per hour maximum
- **War room resolution**: The NL chat interface gives any engineer access to 'Show me errors for `/api/payments` in the last 2 hours' — no CloudWatch console access required"

---

## Section 4 — Innovation & Creativity *(1:30)*

### Creative Idea / Architecture *(~20s)*

"The creative insight behind SynapseOps is **treating DevOps as an agent-coordination problem, not a tooling problem**.

Most DevOps platforms give you dashboards. SynapseOps gives you **autonomous agents with agency** — each one purpose-built for a single cognitive task. The Diff Analyst doesn't know about PR priority. The Priority Assessor doesn't write summaries. This separation means each agent can be fine-tuned, replaced, or upgraded independently.

The other insight is **predictive, not reactive, monitoring** — we alert before a threshold is breached using trend analysis, not just after. That's a fundamentally different operational posture."

### Community Impact Potential *(~25s)*

"The impact model here is significant:

- **Any team on GitHub + AWS** can adopt this — no proprietary toolchain required
- Small engineering teams gain the code review throughput of a much larger team
- Platform engineers get a pre-built observability brain without building CloudWatch dashboards from scratch
- The **AI-DLC methodology** — our KIRO-driven development approach documented in `aidlc-docs/` — is itself a reusable blueprint that any team could follow to build their own AI-native application

Think of SynapseOps as an open template for AI-driven DevOps that any organization can fork, configure, and deploy in a single afternoon."

### Technical Depth & Presentation *(~45s)*

"Let me leave you with the technical highlights that demonstrate real depth:

**Multi-model support** — `LLMService` auto-detects the model family from `model_id` and constructs the correct request body format. Switching from Claude to Nova to Llama is a config change.

**Statistical anomaly detection** — we implement both linear regression for trend prediction and z-score analysis for spike detection — two separate statistical methods, zero ML libraries, pure Python math.

**Dual-backend Bedrock** — the same service layer seamlessly routes between direct `bedrock-runtime` inference and `bedrock-agent-runtime`'s AgentCore, with full session management for stateful agents.

**Event-driven deduplication** — webhook delivery is at-least-once; our dedup layer ensures idempotency so a re-delivered event never triggers two PR reviews.

**KIRO-generated, production-hardened** — the entire application was designed through KIRO's AI-DLC, and then hardened with observability, retry logic, and rate limiting that any production team would expect.

This is what an AI-native application looks like when built with discipline."

---

## Closing *(0:30)*

"SynapseOps is live, it's deployed on AWS, and it's wired to a real GitHub repository right now.

We built it with KIRO. We run it on Bedrock. And it's already doing work that used to require an engineer.

That's developer productivity — quantified, automated, and delivered. Thank you."

---

> **Demo checkpoints to have ready:**
> - Live dashboard URL: `http://synapse-ops-alb-1042958172.ap-south-1.elb.amazonaws.com`
> - GitHub repo with a sample PR: `TapasNayak123/aws_codethon_repo`
> - Architecture diagram: `docs/AWS_Architecture.html`
> - Teams notification screenshot (if live webhook isn't feasible)
> - `aidlc-docs/` folder open in explorer to show KIRO AI-DLC artifacts
