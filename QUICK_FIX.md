# Quick Fix: Agent Not Detecting MRs

## Most Likely Issues

Based on your setup, here are the most common reasons your agent isn't detecting new MRs:

### 1. GitHub Webhook Not Configured ⚠️ MOST COMMON

Your system is **webhook-based**, not polling-based. GitHub must send events to your server.

**Fix:**
1. Go to your GitHub repo: https://github.com/TapasNayak123/aws_codethon_repo/settings/hooks
2. Click "Add webhook"
3. Set:
   - Payload URL: `http://your-server-ip:5000/webhook` (or your public URL)
   - Content type: `application/json`
   - Secret: `agentPolling` (from your .env)
   - Events: Select "Pull requests" and "Workflow runs"
4. Click "Add webhook"

**If your server is not publicly accessible:**
- Use ngrok: `ngrok http 5000` and use the ngrok URL
- Or deploy to a cloud service with a public IP

### 2. Server Not Running

**Check:**
```bash
curl http://localhost:5000/health
```

**If it fails, start the server:**
```bash
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

### 3. Environment Variables Not Set

Your `.env` has some placeholder values. Check these:

```bash
# Run diagnostic
python3 diagnose.py
```

**Critical variables:**
- `GITHUB_TOKEN` - Must be a valid GitHub personal access token
- `GITHUB_WEBHOOK_SECRET` - Must match GitHub webhook secret (currently: `agentPolling`)
- `TEAMS_WEBHOOK_URL` - Already set ✅
- `APP_BASE_URL` - Must be your public URL (currently: `http://localhost:5000`)

### 4. Server Not Accessible from GitHub

If your server is running locally or behind a firewall, GitHub can't reach it.

**Solutions:**
- **For testing:** Use ngrok
  ```bash
  ngrok http 5000
  # Use the HTTPS URL in GitHub webhook
  ```
- **For production:** Deploy to AWS/cloud with public IP
- **Check firewall:** Ensure port 5000 is open

## Quick Diagnostic Steps

Run these commands in order:

```bash
# 1. Check if server is running
curl http://localhost:5000/health

# 2. Run full diagnostic
python3 diagnose.py

# 3. Test manual PR analysis
# Go to: http://localhost:5000/test
# Enter: TapasNayak123/aws_codethon_repo
# Enter a PR number and click "Run Analysis"

# 4. Check if webhook is configured
# Go to: https://github.com/TapasNayak123/aws_codethon_repo/settings/hooks
# Look for a webhook pointing to your server
```

## How the System Works

1. **You create a PR** on GitHub
2. **GitHub sends webhook** to `http://your-server:5000/webhook`
3. **Your server receives** the webhook and processes in background
4. **Agent analyzes** the PR (diff, code review, summary)
5. **Teams notification** is sent with the analysis
6. **GitHub comment** is posted with the summary

## Verify It's Working

After fixing the webhook:

1. Create a test PR on your repo
2. Check GitHub webhook deliveries (Settings → Webhooks → Recent Deliveries)
3. Should see a green checkmark
4. Check your server logs for: `"Accepted PR #X on repo — processing in background"`
5. Check Teams channel for notification
6. Check GitHub PR for comment from your bot

## Still Not Working?

1. Check the detailed troubleshooting guide: `TROUBLESHOOTING.md`
2. Run the diagnostic: `python3 diagnose.py`
3. Check server logs for errors
4. Verify GitHub webhook shows successful deliveries (green checkmarks)

## Common Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| "Invalid webhook signature" | Secret mismatch | Ensure `.env` GITHUB_WEBHOOK_SECRET matches GitHub webhook secret |
| "TEAMS_WEBHOOK_URL not set" | Missing config | Set TEAMS_WEBHOOK_URL in .env |
| Connection refused | Server not running | Start server: `python3 app.py` |
| 404 in GitHub webhook | Wrong URL | Check webhook URL includes `/webhook` path |
| "Duplicate PR event" | Already processed | This is normal - prevents duplicate processing |

## Need Help?

1. Run: `python3 diagnose.py` and share the output
2. Check: `http://localhost:5000/activity` for agent activity logs
3. Check: GitHub webhook "Recent Deliveries" for errors
4. Share server logs from when you create a PR
