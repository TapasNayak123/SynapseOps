# 🤖 AI-Powered PR Summary Agent

Multi-agent system that automatically summarizes GitHub Pull Requests using Amazon Bedrock.

Built for the **AWS Codeathon — TopGear Challenge 2026** (Theme 1: AI-Powered Developer Productivity Platform).

## Architecture

```
GitHub Webhook (PR opened/updated)
        │
        ▼
┌─────────────────────┐
│  Flask Server (API)  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────┐
│  Supervisor Agent        │  ← Orchestrates the workflow
└─────────┬───────────────┘
          │
    ┌─────┼──────────┐
    ▼     ▼          ▼
┌──────┐ ┌──────┐ ┌──────────┐
│Diff  │ │Code  │ │Summary   │
│Agent │ │Review│ │Generator │
│      │ │Agent │ │Agent     │
└──────┘ └──────┘ └──────────┘
```

### Agents

| Agent | Responsibility |
|-------|---------------|
| **Diff Analysis Agent** | Parses the PR diff, categorizes changes (feature/bugfix/refactor), groups files by area, assesses risk |
| **Code Review Agent** | Reviews code quality, security concerns, best practice violations, highlights good code |
| **Summary Generator Agent** | Combines outputs into a polished, human-readable PR summary |
| **Supervisor** | Orchestrates the three agents in sequence |

## Setup

### 1. Install dependencies

```bash
cd mr-summary-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your actual values
```

You need:
- **GITHUB_TOKEN** — a GitHub Personal Access Token with `repo` scope
- **GITHUB_WEBHOOK_SECRET** — the secret you set when creating the webhook
- **AWS credentials** — configured via env vars or `~/.aws/credentials`
- **BEDROCK_MODEL_ID** — the Bedrock model to use (default: Claude 3 Sonnet)

### 3. Run the server

```bash
python app.py
```

Server starts on `http://0.0.0.0:5000`.

### 4. Expose to the internet (for local dev)

Use ngrok or similar:

```bash
ngrok http 5000
```

### 5. Configure GitHub Webhook

1. Go to your repo → Settings → Webhooks → Add webhook
2. **Payload URL**: `https://your-ngrok-url/webhook`
3. **Content type**: `application/json`
4. **Secret**: same as `GITHUB_WEBHOOK_SECRET`
5. **Events**: select "Pull requests"

### 6. Test it

Open a PR on your repo — the agent will automatically post an AI-generated summary as a comment.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI — live feed of processed PRs |
| `/pr/<repo>/<number>` | GET | PR detail page — agent outputs + summary |
| `/health` | GET | Health check |
| `/api/stats` | GET | JSON stats (total PRs, avg duration, risk distribution) |
| `/api/prs` | GET | JSON list of all processed PRs |
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
