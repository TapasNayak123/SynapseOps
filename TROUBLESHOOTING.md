# Troubleshooting Guide

## Issue 1: PR Records Not Appearing on Dashboard

### Diagnosis Steps:

1. **Check if DynamoDB is working:**
   ```bash
   source venv/bin/activate
   python3 test_store.py
   ```
   You should see "✓ Record added" and "✓ Found 1 record(s)".

2. **Check the API endpoint directly:**
   ```bash
   curl http://localhost:5000/api/prs
   ```
   This returns the raw JSON of all PR records. If this is empty, records aren't being stored.

3. **Check the dashboard stats:**
   ```bash
   curl http://localhost:5000/api/stats
   ```
   Should show `{"total": N, ...}` where N > 0 if records exist.

4. **Run a test PR analysis and watch the logs:**
   - Keep the app running in one terminal
   - In another terminal, watch the logs for "Test PR:" messages
   - Go to http://localhost:5000/test
   - Enter a repo and PR number
   - Click "Run Analysis"
   - Check the terminal for log messages like:
     ```
     Test PR: Starting analysis for...
     Test PR: Fetched PR details
     Test PR: Supervisor complete...
     ```

5. **Check for errors in the logs:**
   Look for any exceptions or error messages during the analysis.

### Common Causes:

- **DynamoDB table doesn't exist yet:** The first time you run the app, it auto-creates tables. Check AWS Console → DynamoDB → Tables for `synapse-ops-pr-records`.
- **AWS credentials not configured:** Make sure your AWS credentials are set up (`aws configure` or environment variables).
- **Wrong AWS region:** Check that `AWS_REGION` in `.env` matches where your DynamoDB tables are.
- **Analysis is still running:** The test page takes 15-30 seconds. Wait for "✅ Analysis Complete" before refreshing the dashboard.

### Fix:

If DynamoDB tables don't exist, they'll be created automatically on first use. But if there's a permissions issue, you'll see errors in the logs.

To manually verify DynamoDB:
```bash
aws dynamodb list-tables --region us-east-1
# Should show: synapse-ops-pr-records, synapse-ops-pipeline-records, synapse-ops-held-deployments
```

---

## Issue 2: "Post Comment to PR" Checkbox Not Working

### Diagnosis Steps:

1. **Check the checkbox value in the form:**
   - Open browser DevTools (F12)
   - Go to http://localhost:5000/test
   - Check the "Post to GitHub" checkbox
   - Submit the form
   - In the Network tab, look at the POST request to `/test`
   - Check the Form Data — you should see `post_comment: on`

2. **Check the logs:**
   When you submit with the checkbox checked, you should see:
   ```
   Test PR: Posting comment to GitHub...
   Test PR: Comment posted successfully
   ```

3. **Verify GitHub token has write permissions:**
   ```bash
   curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
     https://api.github.com/repos/TapasNayak123/aws_codethon_repo/issues/1/comments \
     -X POST \
     -d '{"body":"Test comment from SynapseOps"}'
   ```
   If this fails with 403/404, your token doesn't have the right permissions.

### Common Causes:

- **GitHub token lacks permissions:** The token needs `repo` scope (full control of private repositories) or at least `public_repo` scope for public repos.
- **PR is in a different repo than expected:** Make sure you're testing on `TapasNayak123/aws_codethon_repo` or update `GITHUB_REPO` in `.env`.
- **Rate limiting:** GitHub API has rate limits. Check the response headers for `X-RateLimit-Remaining`.

### Fix:

1. **Regenerate GitHub token with correct scopes:**
   - Go to GitHub → Settings → Developer settings → Personal access tokens
   - Generate new token (classic)
   - Select scopes: `repo` (full control)
   - Copy the token and update `GITHUB_TOKEN` in `.env`
   - Restart the app

2. **Test the token manually:**
   ```bash
   # Check token scopes
   curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
   
   # Check rate limit
   curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit
   ```

---

## Quick Verification Commands

```bash
# 1. Check if app is running
curl http://localhost:5000/health

# 2. Check if DynamoDB is accessible
curl http://localhost:5000/health/ready

# 3. Check PR records
curl http://localhost:5000/api/prs | jq

# 4. Check stats
curl http://localhost:5000/api/stats | jq

# 5. Check activity log
curl http://localhost:5000/api/activity?since=0 | jq

# 6. Test GitHub API access
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/TapasNayak123/aws_codethon_repo/pulls/1
```

---

## Restart the App with Fresh Logs

```bash
# Stop the current app (Ctrl+C)

# Clear any cached data (optional)
# redis-cli FLUSHALL

# Restart with verbose logging
source venv/bin/activate
python3 app.py 2>&1 | tee app.log
```

Now run your test and check `app.log` for any errors.

---

## Still Not Working?

1. **Check the test_store.py output** — if that works, DynamoDB is fine
2. **Check the app logs** — look for exceptions during PR analysis
3. **Check AWS CloudWatch Logs** — if you have logging enabled
4. **Check GitHub webhook deliveries** — if using webhooks, check "Recent Deliveries" on the webhook settings page
5. **Verify .env file** — make sure all required variables are set:
   ```bash
   cat .env | grep -E "GITHUB_TOKEN|AWS_REGION|DYNAMODB_TABLE_PREFIX|BEDROCK_MODEL_ID"
   ```


---

## Issue 2: Agent Not Detecting New MRs/PRs

If your agent is not detecting new merge requests and sending Teams notifications, follow these steps:

### 1. Verify the Server is Running

```bash
# Check if the app is running
ps aux | grep "python.*app.py"

# Or if running in Docker/K8s
kubectl get pods -n your-namespace
kubectl logs -f pod-name -n your-namespace
```

The server should be listening on port 5000 and you should see:
```
Webhook mode active — listening on /webhook for PR and pipeline events.
```

### 2. Verify GitHub Webhook Configuration

Go to your GitHub repository:
- Navigate to: `Settings` → `Webhooks`
- Check if a webhook exists pointing to your SynapseOps server
- The webhook URL should be: `http://your-server:5000/webhook` or `https://your-domain/webhook`

**Required webhook settings:**
- Payload URL: `http://your-server-ip:5000/webhook` (or your public URL)
- Content type: `application/json`
- Secret: Must match your `GITHUB_WEBHOOK_SECRET` in `.env`
- Events: Select "Pull requests" and "Workflow runs"
- SSL verification: Enable if using HTTPS

**To add a webhook:**
1. Go to your repo → Settings → Webhooks → Add webhook
2. Set Payload URL to your server's `/webhook` endpoint
3. Set Content type to `application/json`
4. Set Secret to match `GITHUB_WEBHOOK_SECRET` in your `.env`
5. Select individual events: "Pull requests" and "Workflow runs"
6. Ensure "Active" is checked
7. Click "Add webhook"

### 3. Test Webhook Connectivity

```bash
# From your server, check if it's accessible
curl http://localhost:5000/health

# Check if webhook endpoint is responding
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -d '{"zen": "test"}'
```

**Check recent webhook deliveries in GitHub:**
- Go to: Settings → Webhooks → Click on your webhook → Recent Deliveries
- Look for any failed deliveries (red X) and check the error messages
- Green checkmarks mean GitHub successfully sent the webhook
- Click on a delivery to see request/response details

### 4. Verify Environment Variables

Check your `.env` file has these critical values set:

```bash
# Required for PR analysis
GITHUB_TOKEN=ghp_your_token_here              # Must have 'repo' scope
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here # Must match GitHub webhook
GITHUB_REPO=owner/repo                         # Your repository

# Required for Teams notifications
TEAMS_WEBHOOK_URL=https://your-teams-webhook-url
APP_BASE_URL=http://your-server-url:5000       # Your public URL

# Required for AWS services
AWS_REGION=us-east-1
BEDROCK_REGION=us-east-1
```

**Verify your current settings:**
```bash
source venv/bin/activate
python3 -c "from app.config import get_settings; s = get_settings(); print(f'GitHub Token: {\"SET\" if s.github_token else \"MISSING\"}'); print(f'Teams URL: {\"SET\" if s.teams_webhook_url else \"MISSING\"}'); print(f'Webhook Secret: {\"SET\" if s.github_webhook_secret else \"MISSING\"}')"
```

### 5. Check Application Logs

Look for these log messages when a PR is created:

```bash
# Successful webhook receipt
"Accepted PR #123 on owner/repo (action=opened) — processing in background"

# Background processing
"Background: analysing PR #123 on owner/repo"
"Background: finished PR #123 on owner/repo"

# Teams notification
"✅ Teams notification sent for PR #123"
```

**If you see:**
- `"Invalid webhook signature"` → Check `GITHUB_WEBHOOK_SECRET` matches GitHub
- `"TEAMS_WEBHOOK_URL not set"` → Set `TEAMS_WEBHOOK_URL` in `.env`
- `"Ignored PR action: ..."` → Only opened/synchronize/reopened trigger analysis
- `"Duplicate PR event"` → Already processed this PR at this commit

### 6. Test Manually

Use the built-in test page to verify the pipeline works:

1. Navigate to: `http://your-server:5000/test`
2. Enter your repo (e.g., `TapasNayak123/aws_codethon_repo`)
3. Enter a PR number
4. Check "Post comment to GitHub" if you want to test that too
5. Click "Run Analysis"
6. Wait 15-30 seconds for analysis to complete
7. Check if:
   - Analysis summary appears on the page
   - Teams notification was sent (check your Teams channel)
   - GitHub comment was posted (if checked)

### 7. Common Issues & Solutions

**Issue: "Invalid webhook signature"**
- **Cause:** `GITHUB_WEBHOOK_SECRET` mismatch
- **Solution:** Ensure `.env` value matches GitHub webhook secret exactly

**Issue: "TEAMS_WEBHOOK_URL not set — skipping Teams notification"**
- **Cause:** Missing Teams webhook URL
- **Solution:** Set `TEAMS_WEBHOOK_URL` in `.env` file

**Issue: Webhook shows 403/404 in GitHub deliveries**
- **Cause:** Server not accessible from internet
- **Solution:** 
  - Check firewall rules
  - Ensure port 5000 is open
  - If behind load balancer, verify routing
  - Consider using ngrok for local testing: `ngrok http 5000`

**Issue: "Background: failed processing PR"**
- **Cause:** AWS/Bedrock/GitHub API errors
- **Solution:** 
  - Verify AWS credentials: `aws sts get-caller-identity`
  - Check Bedrock model access in your region
  - Verify GitHub token has 'repo' scope

**Issue: PR created but no webhook received**
- **Cause:** Webhook not configured or inactive
- **Solution:** 
  - Check webhook exists in GitHub Settings → Webhooks
  - Ensure webhook is marked "Active"
  - Check "Recent Deliveries" for errors

**Issue: Webhook received but no Teams notification**
- **Cause:** Teams webhook URL invalid or expired
- **Solution:**
  - Test Teams webhook: `curl -X POST $TEAMS_WEBHOOK_URL -H "Content-Type: application/json" -d '{"text":"test"}'`
  - Regenerate Teams webhook if expired
  - Check Teams channel permissions

### 8. Enable Debug Logging

For more detailed logs:

```bash
# Set log level to DEBUG
export LOG_LEVEL=DEBUG
python3 app.py
```

Or modify the app startup in `app.py`:
```python
uvicorn.run("app.main:app", host="0.0.0.0", port=5000, log_level="debug")
```

### 9. Verify Dependencies

```bash
# Ensure all dependencies are installed
source venv/bin/activate
pip install -r requirements.txt

# Check specific packages
pip show uvicorn fastapi boto3 httpx
```

### 10. Quick Diagnostic Checklist

Run through this checklist:

- [ ] Server is running (`curl http://localhost:5000/health` returns `{"status":"healthy"}`)
- [ ] GitHub webhook is configured and active
- [ ] `GITHUB_TOKEN` is set and has 'repo' scope
- [ ] `GITHUB_WEBHOOK_SECRET` matches GitHub webhook secret
- [ ] `TEAMS_WEBHOOK_URL` is set and valid
- [ ] `APP_BASE_URL` is set to your public URL
- [ ] AWS credentials are configured
- [ ] Bedrock model access is enabled in your region
- [ ] Port 5000 is accessible from GitHub (or via load balancer)
- [ ] Recent webhook deliveries in GitHub show green checkmarks
- [ ] Manual test via `/test` page works

### 11. Test Webhook Locally with ngrok

If your server isn't publicly accessible:

```bash
# Install ngrok: https://ngrok.com/download
# Start ngrok tunnel
ngrok http 5000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Update GitHub webhook URL to: https://abc123.ngrok.io/webhook
# Update APP_BASE_URL in .env to: https://abc123.ngrok.io
# Restart your app

# Create a test PR and watch the ngrok console for incoming requests
```

### 12. Verify Webhook Signature Validation

Test if signature validation is working:

```bash
# This should fail with 403
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: sha256=invalid" \
  -d '{"action":"opened"}'

# Should return: {"detail":"Invalid signature"}
```

### 13. Check for Duplicate Detection

If PRs are being ignored due to duplicate detection:

```bash
# Check Redis for duplicate keys
redis-cli
> KEYS *pr:*
> KEYS *delivery:*

# Clear duplicate cache if needed (use with caution)
> FLUSHDB
```

### 14. Monitor Background Processing

The webhook returns 202 immediately and processes in background. To monitor:

```bash
# Watch logs in real-time
tail -f /path/to/app.log | grep "Background:"

# Or if using Docker/K8s
kubectl logs -f deployment/synapse-ops --tail=100 | grep "Background:"
```

### 15. Still Not Working?

If you've tried everything above:

1. **Check the activity log:** `http://localhost:5000/activity` - shows all agent activities
2. **Check PR records:** `http://localhost:5000/api/prs` - shows all analyzed PRs
3. **Enable verbose logging** and create a test PR
4. **Share the logs** with your team for debugging
5. **Verify GitHub webhook secret** is not empty and matches exactly

**Quick test command:**
```bash
# This tests the entire pipeline manually
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: sha256=$(echo -n '{"action":"opened","number":1,"pull_request":{"number":1,"title":"test","head":{"sha":"abc123"},"user":{"login":"test"},"base":{"ref":"main"},"head":{"ref":"feature"}},"repository":{"full_name":"'$GITHUB_REPO'"}}' | openssl dgst -sha256 -hmac "$GITHUB_WEBHOOK_SECRET" | cut -d' ' -f2)" \
  -d '{"action":"opened","number":1,"pull_request":{"number":1,"title":"test","head":{"sha":"abc123"},"user":{"login":"test"},"base":{"ref":"main"},"head":{"ref":"feature"}},"repository":{"full_name":"'$GITHUB_REPO'"}}'
```
