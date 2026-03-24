# Infrastructure Design

## Overview
This document maps logical components to Kubernetes infrastructure and AWS services.

---

## Kubernetes Infrastructure

### Deployment Configuration

**Resource**: Deployment  
**Name**: auth-api-deployment  
**Namespace**: default (or custom namespace)

**Specifications**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-api-deployment
  labels:
    app: auth-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: auth-api
  template:
    metadata:
      labels:
        app: auth-api
    spec:
      containers:
      - name: auth-api
        image: <docker-hub-username>/auth-api:latest
        ports:
        - containerPort: 3000
          name: http
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi
        env:
        - name: NODE_ENV
          valueFrom:
            configMapKeyRef:
              name: auth-api-config
              key: NODE_ENV
        - name: PORT
          valueFrom:
            configMapKeyRef:
              name: auth-api-config
              key: PORT
        envFrom:
        - secretRef:
            name: auth-api-secrets
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
```

**Resource Limits**:
- CPU Request: 100m (0.1 CPU)
- CPU Limit: 500m (0.5 CPU)
- Memory Request: 128Mi
- Memory Limit: 512Mi

**Health Checks**:
- Liveness Probe: /health endpoint, 30s initial delay, 10s period
- Readiness Probe: /health endpoint, 5s initial delay, 5s period

---

### Service Configuration

**Resource**: Service  
**Name**: auth-api-service  
**Type**: LoadBalancer

**Specifications**:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: auth-api-service
  labels:
    app: auth-api
spec:
  type: LoadBalancer
  selector:
    app: auth-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 3000
    name: http
```

**Service Details**:
- Type: LoadBalancer (cloud provider assigns external IP)
- External Port: 80 (HTTP)
- Target Port: 3000 (container port)
- Selector: app=auth-api (routes to deployment pods)

**Load Balancer Behavior**:
- Cloud provider creates external load balancer
- Assigns public IP address
- Routes traffic to healthy pods
- Distributes load across replicas

---

### ConfigMap Configuration

**Resource**: ConfigMap  
**Name**: auth-api-config

**Specifications**:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: auth-api-config
data:
  NODE_ENV: "production"
  PORT: "3000"
  AWS_REGION: "us-east-1"
  DYNAMODB_USERS_TABLE: "prod-Users"
  DYNAMODB_TOKENS_TABLE: "prod-PasswordResetTokens"
  JWT_EXPIRATION: "1h"
  EMAIL_HOST: "smtp.gmail.com"
  EMAIL_PORT: "587"
  EMAIL_FROM: "noreply@example.com"
  RESET_PASSWORD_URL: "https://example.com/reset-password"
  RATE_LIMIT_WINDOW_MS: "900000"
  RATE_LIMIT_MAX_REQUESTS: "100"
  LOG_LEVEL: "info"
```

**Non-Sensitive Configuration**:
- Environment settings
- Port configuration
- AWS region
- DynamoDB table names
- JWT expiration
- Email server settings (non-sensitive)
- Rate limit configuration
- Logging level

---

### Secret Configuration

**Resource**: Secret  
**Name**: auth-api-secrets

**Specifications**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: auth-api-secrets
type: Opaque
data:
  AWS_ACCESS_KEY_ID: <base64-encoded>
  AWS_SECRET_ACCESS_KEY: <base64-encoded>
  JWT_SECRET: <base64-encoded>
  EMAIL_USER: <base64-encoded>
  EMAIL_PASSWORD: <base64-encoded>
```

**Sensitive Configuration**:
- AWS credentials (access key ID and secret)
- JWT signing secret
- Email SMTP credentials

**Secret Management**:
- Create manually before deployment
- Base64 encode all values
- Never commit to version control
- Rotate periodically

---

### Horizontal Pod Autoscaler Configuration

**Resource**: HorizontalPodAutoscaler  
**Name**: auth-api-hpa

**Specifications**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: auth-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: auth-api-deployment
  minReplicas: 1
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**Autoscaling Behavior**:
- Minimum replicas: 1 (always at least one pod)
- Maximum replicas: 5 (scale up to 5 pods)
- Metric: CPU utilization
- Target: 70% average CPU utilization
- Scale up: When CPU > 70% for sustained period
- Scale down: When CPU < 70% for sustained period

**Scaling Triggers**:
- High traffic load
- CPU-intensive operations (bcrypt hashing)
- Sustained request volume

---

## AWS Infrastructure

### DynamoDB Tables

#### Users Table

**Table Name**: `prod-Users` (environment-prefixed)

**Primary Key**:
- Partition Key: `userId` (String) - UUID

**Global Secondary Index**:
- Index Name: `email-index`
- Partition Key: `email` (String)
- Projection: ALL

**Attributes**:
- `userId` (String) - UUID, primary key
- `fullName` (String)
- `dateOfBirth` (String) - YYYY-MM-DD format
- `email` (String) - Lowercase, unique
- `passwordHash` (String) - Bcrypt hash
- `createdAt` (String) - ISO 8601 timestamp
- `updatedAt` (String) - ISO 8601 timestamp

**Capacity Mode**: On-Demand (auto-scaling)

**Encryption**: AWS managed keys (default)

**Point-in-Time Recovery**: Enabled

**Access Patterns**:
- Get user by userId (primary key)
- Get user by email (GSI query)
- Create user (put item)
- Update user (update item)

---

#### PasswordResetTokens Table

**Table Name**: `prod-PasswordResetTokens` (environment-prefixed)

**Primary Key**:
- Partition Key: `tokenId` (String) - UUID

**Global Secondary Index**:
- Index Name: `token-index`
- Partition Key: `token` (String)
- Projection: ALL

**Attributes**:
- `tokenId` (String) - UUID, primary key
- `userId` (String) - UUID, foreign key to Users
- `token` (String) - 64-character hex string
- `expiresAt` (String) - ISO 8601 timestamp
- `used` (Boolean) - Token usage flag
- `createdAt` (String) - ISO 8601 timestamp

**Capacity Mode**: On-Demand (auto-scaling)

**Encryption**: AWS managed keys (default)

**Point-in-Time Recovery**: Enabled

**Access Patterns**:
- Get token by tokenId (primary key)
- Get token by token string (GSI query)
- Create token (put item)
- Mark token as used (update item)

**TTL Configuration**:
- TTL Attribute: `expiresAt`
- Automatic deletion of expired tokens

---

### CloudWatch Logs

**Log Group**: `/aws/kubernetes/auth-api`

**Configuration**:
- Retention: 30 days
- Encryption: AWS managed keys
- Log streams: One per pod instance

**Log Format**: JSON structured logs

**Log Levels**:
- ERROR: Application errors
- WARN: Warnings and degraded functionality
- INFO: Important events (login, registration)
- DEBUG: Detailed debugging (development only)

**Log Aggregation**:
- All pods write to same log group
- Separate log streams per pod
- CloudWatch Insights for querying

---

### CloudWatch Metrics

**Namespace**: `AuthAPI`

**Custom Metrics**:
- `RequestCount` (Count) - Dimensions: Endpoint, Method, StatusCode
- `ResponseTime` (Milliseconds) - Dimensions: Endpoint, Percentile
- `ErrorRate` (Percent) - Dimensions: Endpoint, ErrorType
- `AuthenticationSuccess` (Count) - Dimensions: Endpoint
- `AuthenticationFailure` (Count) - Dimensions: Endpoint, Reason
- `RateLimitViolations` (Count) - Dimensions: IPAddress
- `DatabaseQueryLatency` (Milliseconds) - Dimensions: Operation
- `EmailSendingSuccess` (Count)
- `EmailSendingFailure` (Count) - Dimensions: Reason

**Metric Publishing**:
- Publish every 60 seconds
- Aggregate metrics in application
- Batch publish to CloudWatch

---

### CloudWatch Alarms

**Alarm 1: High Error Rate**
- Metric: ErrorRate
- Threshold: > 5%
- Period: 5 minutes
- Action: SNS notification (optional)

**Alarm 2: High Response Time**
- Metric: ResponseTime (p95)
- Threshold: > 1000ms
- Period: 5 minutes
- Action: SNS notification (optional)

**Alarm 3: High Authentication Failure Rate**
- Metric: AuthenticationFailure
- Threshold: > 20% of total auth attempts
- Period: 5 minutes
- Action: SNS notification (optional)

**Alarm 4: Database Errors**
- Metric: DatabaseErrors
- Threshold: > 10 errors
- Period: 5 minutes
- Action: SNS notification (optional)

---

### IAM Permissions

**Required Permissions for Application**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:*:table/prod-Users",
        "arn:aws:dynamodb:us-east-1:*:table/prod-Users/index/*",
        "arn:aws:dynamodb:us-east-1:*:table/prod-PasswordResetTokens",
        "arn:aws:dynamodb:us-east-1:*:table/prod-PasswordResetTokens/index/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:*:log-group:/aws/kubernetes/auth-api:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "AuthAPI"
        }
      }
    }
  ]
}
```

**Permission Scope**:
- DynamoDB: Read and write to Users and PasswordResetTokens tables
- CloudWatch Logs: Create log groups, streams, and write logs
- CloudWatch Metrics: Publish custom metrics to AuthAPI namespace

---

## Container Infrastructure

### Dockerfile

**Multi-Stage Build**:

```dockerfile
# Stage 1: Build
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY src ./src

# Build TypeScript
RUN npm run build

# Stage 2: Production
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install production dependencies only
RUN npm ci --only=production

# Copy built application from builder
COPY --from=builder /app/dist ./dist

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

# Change ownership
RUN chown -R nodejs:nodejs /app

# Switch to non-root user
USER nodejs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Start application
CMD ["node", "dist/index.js"]
```

**Build Stages**:
1. **Builder Stage**: Install all dependencies, compile TypeScript
2. **Production Stage**: Install production dependencies only, copy compiled code

**Security Features**:
- Non-root user (nodejs:1001)
- Alpine base image (smaller attack surface)
- Production dependencies only
- Health check included

**Image Size Optimization**:
- Multi-stage build (removes dev dependencies)
- Alpine base image (~50MB vs ~900MB for full Node)
- .dockerignore file excludes unnecessary files

---

### Container Registry

**Registry**: Docker Hub

**Image Naming**:
- Repository: `<username>/auth-api`
- Tag format: `<version>` or `latest`
- Example: `johndoe/auth-api:1.0.0`

**Image Tagging Strategy**:
- `latest`: Most recent stable build
- `<version>`: Semantic versioning (1.0.0, 1.0.1, etc.)
- `<git-sha>`: Git commit SHA for traceability

**Image Push Workflow**:
```bash
# Build image
docker build -t <username>/auth-api:1.0.0 .

# Tag as latest
docker tag <username>/auth-api:1.0.0 <username>/auth-api:latest

# Push to Docker Hub
docker push <username>/auth-api:1.0.0
docker push <username>/auth-api:latest
```

---

## Networking

### Service Exposure

**Method**: LoadBalancer Service

**External Access**:
- Cloud provider assigns external IP
- Public internet access via external IP
- Port 80 (HTTP) exposed externally
- Routes to port 3000 internally

**DNS Configuration** (Optional):
- Create DNS A record pointing to external IP
- Example: api.example.com → <external-ip>

**HTTPS Configuration** (Future Enhancement):
- Use Ingress controller with TLS termination
- Or use cloud provider load balancer with SSL certificate

---

### Port Configuration

**Container Port**: 3000
- Application listens on port 3000
- Defined in Dockerfile EXPOSE
- Defined in Deployment containerPort

**Service Port**: 80
- External clients connect to port 80
- LoadBalancer routes to container port 3000

**Health Check Port**: 3000
- Liveness probe: GET /health on port 3000
- Readiness probe: GET /health on port 3000

---

### Network Security

**Kubernetes Network Policies** (Optional):
- Allow ingress from LoadBalancer only
- Allow egress to DynamoDB endpoints
- Allow egress to SMTP server
- Deny all other traffic

**AWS Security Groups** (If using EKS):
- Allow inbound on port 80 from 0.0.0.0/0
- Allow outbound to DynamoDB endpoints
- Allow outbound to SMTP server (port 587)
- Allow outbound to CloudWatch endpoints

---

## Configuration Management

### Environment Variables

**Source**: ConfigMap + Secrets

**ConfigMap Variables** (Non-Sensitive):
- NODE_ENV
- PORT
- AWS_REGION
- DYNAMODB_USERS_TABLE
- DYNAMODB_TOKENS_TABLE
- JWT_EXPIRATION
- EMAIL_HOST
- EMAIL_PORT
- EMAIL_FROM
- RESET_PASSWORD_URL
- RATE_LIMIT_WINDOW_MS
- RATE_LIMIT_MAX_REQUESTS
- LOG_LEVEL

**Secret Variables** (Sensitive):
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- JWT_SECRET
- EMAIL_USER
- EMAIL_PASSWORD

**Variable Injection**:
- ConfigMap: `envFrom.configMapRef`
- Secrets: `envFrom.secretRef`
- Both injected into container environment

---

### Configuration Updates

**ConfigMap Updates**:
1. Update ConfigMap YAML
2. Apply: `kubectl apply -f configmap.yaml`
3. Restart pods: `kubectl rollout restart deployment/auth-api-deployment`

**Secret Updates**:
1. Update Secret YAML (base64 encode values)
2. Apply: `kubectl apply -f secret.yaml`
3. Restart pods: `kubectl rollout restart deployment/auth-api-deployment`

**Note**: Pods don't automatically reload on ConfigMap/Secret changes

---

## Deployment Strategy

### Rolling Update

**Strategy**: RollingUpdate (default)

**Configuration**:
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

**Behavior**:
- Create 1 new pod before terminating old pod (maxSurge: 1)
- Never have 0 pods available (maxUnavailable: 0)
- Gradual rollout with zero downtime

**Rollout Process**:
1. Create new pod with updated image
2. Wait for new pod to be ready (readiness probe)
3. Terminate old pod
4. Repeat until all pods updated

---

### Deployment Commands

**Initial Deployment**:
```bash
# Create ConfigMap
kubectl apply -f k8s/configmap.yaml

# Create Secret
kubectl apply -f k8s/secret.yaml

# Create Deployment
kubectl apply -f k8s/deployment.yaml

# Create Service
kubectl apply -f k8s/service.yaml

# Create HPA
kubectl apply -f k8s/hpa.yaml
```

**Update Deployment**:
```bash
# Update image
kubectl set image deployment/auth-api-deployment auth-api=<username>/auth-api:1.1.0

# Or apply updated deployment YAML
kubectl apply -f k8s/deployment.yaml

# Check rollout status
kubectl rollout status deployment/auth-api-deployment
```

**Rollback Deployment**:
```bash
# Rollback to previous version
kubectl rollout undo deployment/auth-api-deployment

# Rollback to specific revision
kubectl rollout undo deployment/auth-api-deployment --to-revision=2
```

---

## Monitoring and Observability

### Kubernetes Monitoring

**Pod Status**:
```bash
# Check pod status
kubectl get pods -l app=auth-api

# Check pod logs
kubectl logs -l app=auth-api --tail=100 -f

# Check pod events
kubectl describe pod <pod-name>
```

**Service Status**:
```bash
# Check service
kubectl get service auth-api-service

# Get external IP
kubectl get service auth-api-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

**HPA Status**:
```bash
# Check HPA status
kubectl get hpa auth-api-hpa

# Check HPA details
kubectl describe hpa auth-api-hpa
```

---

### Application Monitoring

**CloudWatch Logs**:
- View logs in CloudWatch Logs console
- Use CloudWatch Insights for querying
- Set up log-based metrics

**CloudWatch Metrics**:
- View metrics in CloudWatch Metrics console
- Create custom dashboards
- Set up alarms for critical metrics

**CloudWatch Dashboard** (Recommended):
- Request count by endpoint
- Response time percentiles
- Error rate by endpoint
- Authentication success/failure rate
- HPA metrics (CPU, replica count)

---

## Infrastructure Summary

### Kubernetes Resources
- 1 Deployment (auth-api-deployment)
- 1 Service (auth-api-service, LoadBalancer)
- 1 ConfigMap (auth-api-config)
- 1 Secret (auth-api-secrets)
- 1 HorizontalPodAutoscaler (auth-api-hpa)

### AWS Resources
- 2 DynamoDB Tables (prod-Users, prod-PasswordResetTokens)
- 1 CloudWatch Log Group (/aws/kubernetes/auth-api)
- 1 CloudWatch Metrics Namespace (AuthAPI)
- 4 CloudWatch Alarms (error rate, response time, auth failures, DB errors)
- IAM permissions for DynamoDB, CloudWatch Logs, CloudWatch Metrics

### Container Infrastructure
- Multi-stage Dockerfile
- Docker Hub registry
- Non-root user for security
- Health check included

### Networking
- LoadBalancer service for external access
- Port 80 external, port 3000 internal
- Health check on /health endpoint

### Configuration
- ConfigMap for non-sensitive config
- Secret for sensitive credentials
- Environment variable injection

### Deployment
- Rolling update strategy
- Zero downtime deployments
- Easy rollback capability

### Monitoring
- Kubernetes pod/service monitoring
- CloudWatch Logs for application logs
- CloudWatch Metrics for performance metrics
- CloudWatch Alarms for critical issues

