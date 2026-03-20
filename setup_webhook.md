# GitHub Webhook Setup Guide

## Your Configuration

Based on your `.env` file:
- **Repository:** TapasNayak123/aws_codethon_repo
- **Webhook Secret:** `agentPolling`
- **Server URL:** You need to determine this (see below)

## Step 1: Determine Your Server URL

### Option A: Local Testing with ngrok (Recommended for testing)

```bash
# Install ngrok from https://ngrok.com/download
# Then run:
ngrok http 5000

# Copy the HTTPS URL (e.g., https://abc123.ngrok-free.app)
# This is your webhook URL
```

### Option B: Cloud Deployment (For production)

If you've deployed to AWS/cloud:
- Use your load balancer URL or public IP
- Example: `http://your-load-balancer.elb.amazonaws.com:5000`
- Or: `http://your-ec2-ip:5000`

### Option C: Local Network (Not recommended - GitHub can't reach it)

- `http://localhost:5000` - Only works if GitHub can reach your machine
- This typically won't work unless you have a public IP

## Step 2: Configure GitHub Webhook

1. **Go to your repository:**
   https://github.com/TapasNayak123/aws_codethon_repo/settings/hooks

2. **Click "Add webhook"**

3. **Fill in the form:**
   - **Payload URL:** `https://your-ngrok-url.ngrok-free.app/webhook`
     - Replace with your actual URL from Step 1
     - MUST include `/webhook` at the end
   
   - **Content type:** `application/json`
   
   - **Secret:** `agentPolling`
     - This MUST match GITHUB_WEBHOOK_SECRET in your .env
   
   - **Which events would you like to trigger this webhook?**
     - Select "Let me select individual events"
     - Check: ✅ Pull requests
     - Check: ✅ Workflow runs
     - Uncheck everything else
   
   - **Active:** ✅ Checked

4. **Click "Add webhook"**

5. **Verify it was created:**
   - You should see a green checkmark after GitHub sends a ping
   - If you see a red X, click on it to see the error

## Step 3: Update APP_BASE_URL

Update your `.env` file with the same URL:

```bash
# If using ngrok:
APP_BASE_URL=https://your-ngrok-url.ngrok-free.app

# If using cloud deployment:
APP_BASE_URL=http://your-load-balancer.elb.amazonaws.com:5000
```

This URL is used for the action buttons in Teams notifications.

## Step 4: Start Your Server

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies (if not already done)
pip install -r requirements.txt

# Start the server
python3 app.py
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:5000
```

## Step 5: Test the Webhook

### Method 1: Create a Test PR

1. Create a new branch in your repo
2. Make a small change
3. Create a pull request
4. Watch your server logs for activity
5. Check your Teams channel for notification

### Method 2: Use the Test Page

1. Go to: http://localhost:5000/test
2. Enter: `TapasNayak123/aws_codethon_repo`
3. Enter an existing PR number
4. Click "Run Analysis"
5. Wait for results

### Method 3: Check Webhook Deliveries

1. Go to: https://github.com/TapasNayak123/aws_codethon_repo/settings/hooks
2. Click on your webhook
3. Click "Recent Deliveries"
4. You should see deliveries with green checkmarks
5. Click on a delivery to see request/response details

## Troubleshooting

### Webhook shows red X in GitHub

**Check the error message:**
- "Connection refused" → Server not running
- "Connection timed out" → Server not accessible from internet
- "404 Not Found" → Wrong URL (missing `/webhook`?)
- "403 Forbidden" → Signature verification failed (wrong secret)

**Solutions:**
- Ensure server is running: `curl http://localhost:5000/health`
- If using ngrok, ensure it's running and URL is correct
- Check GITHUB_WEBHOOK_SECRET matches exactly

### No Teams notification

**Check:**
1. Server logs show: `"✅ Teams notification sent for PR #X"`
2. TEAMS_WEBHOOK_URL is set correctly in .env
3. Test Teams webhook:
   ```bash
   curl -X POST "$TEAMS_WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -d '{"text":"Test from SynapseOps"}'
   ```

### PR created but no webhook received

**Check:**
1. Webhook is marked "Active" in GitHub
2. Webhook events include "Pull requests"
3. Recent Deliveries shows attempts (even if failed)
4. Server is accessible from internet

## Using ngrok (Detailed)

ngrok creates a secure tunnel to your local server:

```bash
# 1. Download and install ngrok
# Visit: https://ngrok.com/download

# 2. Start ngrok
ngrok http 5000

# 3. You'll see output like:
# Forwarding  https://abc123.ngrok-free.app -> http://localhost:5000

# 4. Use the HTTPS URL in GitHub webhook:
# https://abc123.ngrok-free.app/webhook

# 5. Update .env:
# APP_BASE_URL=https://abc123.ngrok-free.app

# 6. Restart your server
# python3 app.py

# 7. Keep ngrok running while testing
```

**Note:** ngrok URLs change each time you restart (unless you have a paid account).

## Production Deployment

For production, deploy to a cloud service:

1. **AWS EKS/ECS:**
   - Deploy using the Helm chart in `helm/synapse-ops/`
   - Use LoadBalancer service to get public URL
   - Update webhook URL to LoadBalancer URL

2. **AWS EC2:**
   - Deploy on EC2 instance with public IP
   - Open port 5000 in security group
   - Use public IP or domain name in webhook

3. **Other Cloud:**
   - Ensure service has public IP/URL
   - Configure firewall to allow inbound on port 5000
   - Use HTTPS if possible (recommended)

## Verification Checklist

- [ ] Server is running (`curl http://localhost:5000/health`)
- [ ] Webhook is configured in GitHub
- [ ] Webhook secret matches `.env` file
- [ ] Webhook URL includes `/webhook` path
- [ ] Webhook events include "Pull requests"
- [ ] APP_BASE_URL is set in `.env`
- [ ] TEAMS_WEBHOOK_URL is set in `.env`
- [ ] Recent Deliveries shows green checkmarks
- [ ] Test PR triggers notification

## Next Steps

After webhook is working:

1. Monitor activity: http://localhost:5000/activity
2. View analyzed PRs: http://localhost:5000/
3. Check metrics: http://localhost:5000/metrics
4. Test chat: http://localhost:5000/chat

## Need Help?

Run the diagnostic tool:
```bash
python3 diagnose.py
```

This will check all your configuration and identify issues.
