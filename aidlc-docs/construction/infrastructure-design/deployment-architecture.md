# Deployment Architecture

## Overview
This document provides architectural diagrams and deployment topology for the authentication application.

---

## High-Level Architecture

```
                                Internet
                                   |
                                   v
                        +----------------------+
                        |   LoadBalancer       |
                        |   (Port 80)          |
                        +----------------------+
                                   |
                                   v
                        +----------------------+
                        |   Kubernetes         |
                        |   Service            |
                        +----------------------+
                                   |
                    +--------------+---------------+
                    |              |               |
                    v              v               v
            +----------+    +----------+    +----------+
            |  Pod 1   |    |  Pod 2   |    |  Pod N   |
            | (3000)   |    | (3000)   |    | (3000)   |
            +----------+    +----------+    +----------+
                    |              |               |
                    +------+-------+-------+-------+
                           |
                           v
                    +-------------+
                    |   AWS       |
                    |   Services  |
                    +-------------+
                           |
            +--------------+--------------+
            |              |              |
            v              v              v
      +----------+   +----------+   +----------+
      | DynamoDB |   | CloudWatch|  |  SMTP    |
      |  Tables  |   |  Logs     |  |  Server  |
      +----------+   +----------+   +----------+
```

---

## Kubernetes Deployment Topology

```
+---------------------------------------------------------------+
|                    Kubernetes Cluster                         |
|                                                               |
|  +----------------------------------------------------------+ |
|  |                    Namespace: default                    | |
|  |                                                          | |
|  |  +----------------------------------------------------+  | |
|  |  |  Service: auth-api-service (LoadBalancer)          |  | |
|  |  |  External IP: <assigned-by-cloud-provider>         |  | |
|  |  |  Port: 80 -> 3000                                  |  | |
|  |  +----------------------------------------------------+  | |
|  |                           |                              | |
|  |                           v                              | |
|  |  +----------------------------------------------------+  | |
|  |  |  Deployment: auth-api-deployment                   |  | |
|  |  |  Replicas: 1-5 (HPA controlled)                    |  | |
|  |  |                                                    |  | |
|  |  |  +------------------------------------------+      |  | |
|  |  |  |  Pod: auth-api-<random-id>              |      |  | |
|  |  |  |                                          |      |  | |
|  |  |  |  Container: auth-api                    |      |  | |
|  |  |  |  Image: <username>/auth-api:latest      |      |  | |
|  |  |  |  Port: 3000                             |      |  | |
|  |  |  |  Resources:                             |      |  | |
|  |  |  |    CPU: 100m-500m                       |      |  | |
|  |  |  |    Memory: 128Mi-512Mi                  |      |  | |
|  |  |  |                                          |      |  | |
|  |  |  |  Environment:                           |      |  | |
|  |  |  |    - ConfigMap: auth-api-config         |      |  | |
|  |  |  |    - Secret: auth-api-secrets           |      |  | |
|  |  |  |                                          |      |  | |
|  |  |  |  Health Checks:                         |      |  | |
|  |  |  |    - Liveness: /health (30s delay)      |      |  | |
|  |  |  |    - Readiness: /health (5s delay)      |      |  | |
|  |  |  +------------------------------------------+      |  | |
|  |  +----------------------------------------------------+  | |
|  |                                                          | |
|  |  +----------------------------------------------------+  | |
|  |  |  HPA: auth-api-hpa                                 |  | |
|  |  |  Min Replicas: 1                                   |  | |
|  |  |  Max Replicas: 5                                   |  | |
|  |  |  Target CPU: 70%                                   |  | |
|  |  +----------------------------------------------------+  | |
|  |                                                          | |
|  |  +----------------------------------------------------+  | |
|  |  |  ConfigMap: auth-api-config                        |  | |
|  |  |  - NODE_ENV, PORT, AWS_REGION, etc.                |  | |
|  |  +----------------------------------------------------+  | |
|  |                                                          | |
|  |  +----------------------------------------------------+  | |
|  |  |  Secret: auth-api-secrets                          |  | |
|  |  |  - AWS_ACCESS_KEY_ID, JWT_SECRET, etc.             |  | |
|  |  +----------------------------------------------------+  | |
|  +----------------------------------------------------------+ |
+---------------------------------------------------------------+
```

---

## AWS Services Integration

```
+---------------------------------------------------------------+
|                    Kubernetes Cluster                         |
|                                                               |
|                    +----------+                               |
|                    |   Pod    |                               |
|                    | (App)    |                               |
|                    +----------+                               |
|                         |                                     |
|         +---------------+---------------+                     |
|         |               |               |                     |
|         v               v               v                     |
+---------------------------------------------------------------+
         |               |               |
         |               |               |
         v               v               v
+---------------------------------------------------------------+
|                       AWS Services                            |
|                                                               |
|  +------------------+  +------------------+  +--------------+ |
|  |   DynamoDB       |  |   CloudWatch     |  |   SMTP       | |
|  |                  |  |                  |  |   Server     | |
|  |  +------------+  |  |  +------------+  |  |              | |
|  |  | prod-Users |  |  |  | Logs       |  |  | Gmail SMTP   | |
|  |  +------------+  |  |  +------------+  |  | Port 587     | |
|  |                  |  |                  |  |              | |
|  |  +------------+  |  |  +------------+  |  |              | |
|  |  | prod-      |  |  |  | Metrics    |  |  |              | |
|  |  | Password   |  |  |  +------------+  |  |              | |
|  |  | ResetTokens|  |  |                  |  |              | |
|  |  +------------+  |  |  +------------+  |  |              | |
|  |                  |  |  | Alarms     |  |  |              | |
|  |                  |  |  +------------+  |  |              | |
|  +------------------+  +------------------+  +--------------+ |
+---------------------------------------------------------------+
```

---

## Request Flow Diagram

```
User Request Flow:

1. User --> Internet --> LoadBalancer (Port 80)
                              |
                              v
2. LoadBalancer --> Kubernetes Service (auth-api-service)
                              |
                              v
3. Service --> Pod (Port 3000)
                              |
                              v
4. Pod --> Middleware Chain:
           - Request Correlation (generate request ID)
           - Request Logging (log incoming request)
           - Rate Limiting (check rate limit)
           - Security Headers (set headers)
           - CORS (handle cross-origin)
           - Body Parser (parse JSON)
           - Authentication (verify JWT if protected route)
                              |
                              v
5. Middleware --> Controller (handle request)
                              |
                              v
6. Controller --> Service Layer (business logic)
                              |
                              v
7. Service --> External Services:
               - DynamoDB (read/write data)
               - Email Service (send emails)
               - Token Service (generate/verify tokens)
               - Password Service (hash/verify passwords)
                              |
                              v
8. Service --> Controller (return result)
                              |
                              v
9. Controller --> Response Middleware:
                  - Response Logging (log response)
                  - Error Handling (if error occurred)
                              |
                              v
10. Response --> User (JSON response)

Parallel Activities:
- Logger Service --> CloudWatch Logs (async)
- Metrics Service --> CloudWatch Metrics (async, batched)
```

---

## Authentication Flow

```
Registration Flow:

User --> POST /api/auth/register
           |
           v
    Validation Middleware
           |
           v
    Auth Controller
           |
           v
    Check Email Uniqueness (DynamoDB query)
           |
           v
    Hash Password (bcrypt, ~300ms)
           |
           v
    Create User (DynamoDB put)
           |
           v
    Generate JWT Token
           |
           v
    Return Success + Token


Login Flow:

User --> POST /api/auth/login
           |
           v
    Validation Middleware
           |
           v
    Auth Controller
           |
           v
    Find User by Email (DynamoDB query via GSI)
           |
           v
    Verify Password (bcrypt compare, ~300ms)
           |
           v
    Generate JWT Token
           |
           v
    Return Success + Token


Forgot Password Flow:

User --> POST /api/auth/forgot-password
           |
           v
    Validation Middleware
           |
           v
    Auth Controller
           |
           v
    Find User by Email (DynamoDB query via GSI)
           |
           v
    Generate Reset Token (crypto.randomBytes)
           |
           v
    Store Token (DynamoDB put)
           |
           v
    Send Email (async, non-blocking)
           |
           v
    Return Success (immediately)


Reset Password Flow:

User --> POST /api/auth/reset-password
           |
           v
    Validation Middleware
           |
           v
    Auth Controller
           |
           v
    Find Token (DynamoDB query via GSI)
           |
           v
    Validate Token (expiration, used flag)
           |
           v
    Hash New Password (bcrypt, ~300ms)
           |
           v
    Update User Password (DynamoDB update)
           |
           v
    Mark Token as Used (DynamoDB update)
           |
           v
    Return Success
```

---

## Scaling Behavior

```
Horizontal Pod Autoscaling:

Normal Load (CPU < 70%):
+----------+
|  Pod 1   |  CPU: 50%
+----------+
Replicas: 1


Increased Load (CPU > 70%):
+----------+    +----------+
|  Pod 1   |    |  Pod 2   |  CPU: 60% each
+----------+    +----------+
Replicas: 2
HPA scales up


High Load (CPU > 70%):
+----------+    +----------+    +----------+
|  Pod 1   |    |  Pod 2   |    |  Pod 3   |  CPU: 55% each
+----------+    +----------+    +----------+
Replicas: 3
HPA scales up


Peak Load (CPU > 70%):
+----------+    +----------+    +----------+    +----------+    +----------+
|  Pod 1   |    |  Pod 2   |    |  Pod 3   |    |  Pod 4   |    |  Pod 5   |
+----------+    +----------+    +----------+    +----------+    +----------+
Replicas: 5 (max)
HPA at maximum


Load Decreases (CPU < 70%):
+----------+    +----------+
|  Pod 1   |    |  Pod 2   |  CPU: 40% each
+----------+    +----------+
Replicas: 2
HPA scales down


Normal Load Restored (CPU < 70%):
+----------+
|  Pod 1   |  CPU: 30%
+----------+
Replicas: 1 (min)
HPA scales down to minimum
```

---

## Deployment Process

```
Deployment Workflow:

1. Developer pushes code to Git
           |
           v
2. Build Docker image locally
   docker build -t <username>/auth-api:1.0.0 .
           |
           v
3. Push image to Docker Hub
   docker push <username>/auth-api:1.0.0
           |
           v
4. Update Kubernetes deployment
   kubectl set image deployment/auth-api-deployment auth-api=<username>/auth-api:1.0.0
           |
           v
5. Kubernetes Rolling Update:
   
   Initial State:
   +----------+
   |  Pod 1   |  (old version)
   +----------+
   
   Step 1: Create new pod
   +----------+    +----------+
   |  Pod 1   |    |  Pod 2   |  (new version, starting)
   +----------+    +----------+
   
   Step 2: Wait for readiness
   +----------+    +----------+
   |  Pod 1   |    |  Pod 2   |  (new version, ready)
   +----------+    +----------+
   
   Step 3: Terminate old pod
                   +----------+
                   |  Pod 2   |  (new version)
                   +----------+
   
   Final State:
   +----------+
   |  Pod 2   |  (new version)
   +----------+
           |
           v
6. Deployment complete
   Zero downtime achieved
```

---

## Monitoring Architecture

```
Application Monitoring:

+---------------------------------------------------------------+
|                    Kubernetes Pods                            |
|                                                               |
|  +----------+    +----------+    +----------+                 |
|  |  Pod 1   |    |  Pod 2   |    |  Pod N   |                 |
|  |          |    |          |    |          |                 |
|  | Winston  |    | Winston  |    | Winston  |                 |
|  | Logger   |    | Logger   |    | Logger   |                 |
|  +----------+    +----------+    +----------+                 |
|       |               |               |                       |
+---------------------------------------------------------------+
        |               |               |
        +---------------+---------------+
                        |
                        v
+---------------------------------------------------------------+
|                    AWS CloudWatch                             |
|                                                               |
|  +----------------------------------------------------------+ |
|  |  CloudWatch Logs                                         | |
|  |  Log Group: /aws/kubernetes/auth-api                     | |
|  |                                                          | |
|  |  Log Streams:                                            | |
|  |  - pod-1-<id>                                            | |
|  |  - pod-2-<id>                                            | |
|  |  - pod-n-<id>                                            | |
|  |                                                          | |
|  |  Retention: 30 days                                      | |
|  +----------------------------------------------------------+ |
|                                                               |
|  +----------------------------------------------------------+ |
|  |  CloudWatch Metrics                                      | |
|  |  Namespace: AuthAPI                                      | |
|  |                                                          | |
|  |  Metrics:                                                | |
|  |  - RequestCount (by endpoint, method, status)            | |
|  |  - ResponseTime (by endpoint, percentile)                | |
|  |  - ErrorRate (by endpoint, error type)                   | |
|  |  - AuthenticationSuccess/Failure                         | |
|  |  - RateLimitViolations                                   | |
|  |  - DatabaseQueryLatency                                  | |
|  |  - EmailSendingSuccess/Failure                           | |
|  +----------------------------------------------------------+ |
|                                                               |
|  +----------------------------------------------------------+ |
|  |  CloudWatch Alarms                                       | |
|  |                                                          | |
|  |  - High Error Rate (> 5% for 5 min)                      | |
|  |  - High Response Time (p95 > 1000ms for 5 min)           | |
|  |  - High Auth Failure Rate (> 20% for 5 min)              | |
|  |  - Database Errors (> 10 in 5 min)                       | |
|  +----------------------------------------------------------+ |
|                                                               |
|  +----------------------------------------------------------+ |
|  |  CloudWatch Dashboard                                    | |
|  |                                                          | |
|  |  Widgets:                                                | |
|  |  - Request count graph                                   | |
|  |  - Response time graph (p50, p95, p99)                   | |
|  |  - Error rate graph                                      | |
|  |  - Authentication metrics                                | |
|  |  - HPA metrics (CPU, replica count)                      | |
|  +----------------------------------------------------------+ |
+---------------------------------------------------------------+
```

---

## Security Architecture

```
Security Layers:

1. Network Layer:
   - LoadBalancer (external access control)
   - Kubernetes Service (internal routing)
   - Network policies (optional, restrict pod communication)

2. Application Layer:
   - Rate Limiting (100 req/15 min per IP)
   - Security Headers (Helmet.js)
   - CORS (cross-origin control)
   - Input Validation (express-validator)

3. Authentication Layer:
   - JWT tokens (1-hour expiration)
   - Password hashing (bcrypt, cost 12)
   - Reset tokens (cryptographic random, 1-hour expiration)

4. Data Layer:
   - DynamoDB encryption at rest (AWS managed keys)
   - TLS in transit (HTTPS, SMTP TLS)
   - No sensitive data in logs

5. Infrastructure Layer:
   - Non-root container user
   - Resource limits (prevent resource exhaustion)
   - Health checks (detect unhealthy pods)
   - IAM permissions (least privilege)
```

---

## Disaster Recovery

```
Backup and Recovery:

DynamoDB Tables:
- Point-in-time recovery enabled
- Continuous backups (35 days)
- Recovery to any point in time

Application Logs:
- CloudWatch Logs retention: 30 days
- Logs cannot be deleted by application
- Logs encrypted at rest

Configuration:
- Kubernetes manifests in Git
- ConfigMap and Secret definitions in Git (secrets encrypted)
- Infrastructure as Code

Recovery Scenarios:

1. Pod Failure:
   - Kubernetes automatically restarts pod
   - Health checks detect failure
   - New pod created from same image
   - RTO: < 1 minute

2. Node Failure:
   - Kubernetes reschedules pods to healthy nodes
   - LoadBalancer routes to healthy pods
   - RTO: < 5 minutes

3. Data Loss:
   - Restore DynamoDB from point-in-time backup
   - RPO: < 15 minutes (continuous backups)
   - RTO: < 1 hour (manual restore process)

4. Complete Cluster Failure:
   - Redeploy to new cluster
   - Apply Kubernetes manifests
   - Restore DynamoDB if needed
   - RTO: < 1 hour (manual process)
```

---

## Cost Optimization

```
Resource Costs:

Kubernetes:
- Pods: 1-5 replicas (HPA controlled)
- CPU: 100m-500m per pod
- Memory: 128Mi-512Mi per pod
- Cost: Depends on cloud provider

DynamoDB:
- On-demand capacity mode
- Pay per request
- No idle capacity costs
- Cost: ~$1.25 per million read requests, ~$6.25 per million write requests

CloudWatch:
- Logs: $0.50 per GB ingested
- Metrics: $0.30 per custom metric per month
- Alarms: $0.10 per alarm per month
- Cost: ~$10-20 per month for small scale

Docker Hub:
- Free tier: Unlimited public repositories
- Cost: $0 for public images

Email (Gmail SMTP):
- Free tier: 500 emails per day
- Cost: $0 for small scale

Total Estimated Cost:
- Small scale (< 1,000 users, < 10 req/sec): ~$50-100 per month
- Includes Kubernetes cluster, DynamoDB, CloudWatch, email
```

---

## Architecture Summary

### Deployment Model
- Kubernetes deployment with LoadBalancer service
- 1-5 pod replicas (HPA controlled)
- Rolling update strategy (zero downtime)
- Docker Hub for container registry

### AWS Integration
- DynamoDB for data storage (2 tables)
- CloudWatch Logs for application logs
- CloudWatch Metrics for performance metrics
- CloudWatch Alarms for critical issues

### Networking
- LoadBalancer service (external access)
- Port 80 external, port 3000 internal
- Health checks on /health endpoint

### Scaling
- Horizontal Pod Autoscaler (CPU-based)
- Min 1 replica, max 5 replicas
- Target 70% CPU utilization

### Security
- Multi-layer security (network, application, authentication, data, infrastructure)
- JWT authentication, bcrypt password hashing
- Rate limiting, security headers, input validation
- Encryption at rest and in transit

### Monitoring
- Comprehensive logging (Winston + CloudWatch)
- Custom metrics (request count, response time, error rate)
- Alarms for critical issues
- Dashboard for visualization

### Disaster Recovery
- DynamoDB point-in-time recovery
- CloudWatch Logs retention (30 days)
- Configuration in Git
- Automated pod recovery, manual data recovery

### Cost
- Small scale: ~$50-100 per month
- On-demand pricing (no idle costs)
- Free tiers utilized where possible
