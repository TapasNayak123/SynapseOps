#!/bin/bash
# Redeploy SynapseOps to Kubernetes with updated configuration

set -e

echo "🚀 Redeploying SynapseOps to Kubernetes..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if kubectl is accessible
echo -e "${YELLOW}Checking cluster access...${NC}"
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"
    echo "Please ensure:"
    echo "  1. You're connected to VPN (if required)"
    echo "  2. kubectl is configured: aws eks update-kubeconfig --name your-cluster --region us-east-1"
    exit 1
fi
echo -e "${GREEN}✅ Cluster access confirmed${NC}"

# Check if helm is installed
if ! command -v helm &> /dev/null; then
    echo -e "${RED}❌ Helm is not installed${NC}"
    echo "Install helm: brew install helm"
    exit 1
fi
echo -e "${GREEN}✅ Helm is installed${NC}"

# Load secrets from .env
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found${NC}"
    exit 1
fi

source .env

# Validate required secrets
if [ -z "$GITHUB_TOKEN" ] || [ -z "$GITHUB_WEBHOOK_SECRET" ] || [ -z "$TEAMS_WEBHOOK_URL" ]; then
    echo -e "${RED}❌ Missing required secrets in .env${NC}"
    echo "Required: GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET, TEAMS_WEBHOOK_URL"
    exit 1
fi
echo -e "${GREEN}✅ Secrets loaded from .env${NC}"

# Check if release exists
echo -e "${YELLOW}Checking if synapse-ops release exists...${NC}"
if helm list | grep -q synapse-ops; then
    echo -e "${GREEN}✅ Release exists, will upgrade${NC}"
    ACTION="upgrade"
else
    echo -e "${YELLOW}⚠️  Release doesn't exist, will install${NC}"
    ACTION="install"
fi

# Deploy/Upgrade
echo -e "${YELLOW}Running helm ${ACTION}...${NC}"
helm ${ACTION} synapse-ops ./helm/synapse-ops \
  --set secrets.GITHUB_TOKEN="${GITHUB_TOKEN}" \
  --set secrets.GITHUB_WEBHOOK_SECRET="${GITHUB_WEBHOOK_SECRET}" \
  --set secrets.TEAMS_WEBHOOK_URL="${TEAMS_WEBHOOK_URL}" \
  --wait \
  --timeout 5m

echo -e "${GREEN}✅ Helm ${ACTION} completed${NC}"

# Wait for rollout
echo -e "${YELLOW}Waiting for deployment to be ready...${NC}"
kubectl rollout status deployment/synapse-ops --timeout=5m

# Get pod status
echo -e "${YELLOW}Checking pod status...${NC}"
kubectl get pods -l app=synapse-ops

# Get service info
echo -e "${YELLOW}Getting service information...${NC}"
kubectl get svc synapse-ops

# Get LoadBalancer URL
LB_URL=$(kubectl get svc synapse-ops -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
if [ -n "$LB_URL" ]; then
    echo -e "${GREEN}✅ LoadBalancer URL: http://${LB_URL}${NC}"
    
    # Test health endpoint
    echo -e "${YELLOW}Testing health endpoint...${NC}"
    sleep 10  # Wait for LB to be ready
    if curl -s -f "http://${LB_URL}/health" > /dev/null; then
        echo -e "${GREEN}✅ Health check passed${NC}"
        curl -s "http://${LB_URL}/health" | jq .
    else
        echo -e "${RED}⚠️  Health check failed (may need more time)${NC}"
    fi
else
    echo -e "${RED}⚠️  LoadBalancer URL not available yet${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Verify webhook URL in GitHub matches: http://${LB_URL}/webhook"
echo "  2. Create a test PR to verify end-to-end flow"
echo "  3. Check logs: kubectl logs -f deployment/synapse-ops"
echo "  4. View dashboard: http://${LB_URL}/"
