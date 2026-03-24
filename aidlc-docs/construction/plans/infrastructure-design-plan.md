# Infrastructure Design Plan

## Purpose
Map logical components to actual Kubernetes infrastructure and AWS services.

## Context
Based on:
- Kubernetes deployment target
- AWS DynamoDB for data storage
- AWS CloudWatch for logging and monitoring
- Small-scale deployment (< 1,000 users, < 10 req/sec)
- Single global DynamoDB client
- Winston logging with CloudWatch transport

---

## Infrastructure Design Steps

### Step 1: Analyze Design Artifacts
- [x] Review functional design
- [x] Review NFR requirements
- [x] Review NFR design patterns
- [x] Review logical components

### Step 2: Design Kubernetes Resources
- [x] Deployment configuration
- [x] Service configuration
- [x] ConfigMap for non-sensitive config
- [x] Secret for sensitive data
- [x] Resource limits and requests

### Step 3: Design AWS Service Integration
- [x] DynamoDB tables design
- [x] CloudWatch Logs configuration
- [x] CloudWatch Metrics configuration
- [x] IAM roles and policies

### Step 4: Design Container Strategy
- [x] Dockerfile design
- [x] Multi-stage build
- [x] Base image selection
- [x] Health check configuration

### Step 5: Design Configuration Management
- [x] Environment variables mapping
- [x] Secrets management strategy
- [x] ConfigMap structure

### Step 6: Design Networking
- [x] Service exposure (LoadBalancer/NodePort/Ingress)
- [x] Port configuration
- [x] Health check endpoints

### Step 7: Document Infrastructure Design
- [x] Create infrastructure-design.md
- [x] Create deployment-architecture.md

---

## Questions for User

### Question 1: Kubernetes Service Type
How should the application be exposed in Kubernetes?

A) LoadBalancer (cloud provider load balancer, external IP)
B) NodePort (expose on node IP:port, manual load balancing)
C) Ingress (HTTP/HTTPS routing, requires ingress controller)
D) ClusterIP (internal only, not externally accessible)
E) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 2: DynamoDB Table Names
What naming convention should be used for DynamoDB tables?

A) Simple names (Users, PasswordResetTokens)
B) Prefixed with environment (dev-Users, prod-Users)
C) Prefixed with app name (auth-Users, auth-PasswordResetTokens)
D) Both environment and app (dev-auth-Users, prod-auth-Users)
E) Other (please describe after [Answer]: tag below)

[Answer]: B

### Question 3: AWS Credentials Management
How should AWS credentials be provided to the application?

A) Kubernetes Secrets (manual secret creation)
B) IAM Roles for Service Accounts (IRSA, recommended for EKS)
C) Environment variables in deployment
D) AWS credentials file mounted as volume
E) Other (please describe after [Answer]: tag below)

[Answer]: C

### Question 4: Container Registry
Where should the Docker image be stored?

A) Docker Hub (public or private repository)
B) AWS ECR (Elastic Container Registry)
C) GitHub Container Registry
D) Private registry
E) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 5: Horizontal Pod Autoscaling
Should the application use Horizontal Pod Autoscaler (HPA)?

A) Yes - Scale based on CPU utilization (70% threshold)
B) Yes - Scale based on memory utilization (80% threshold)
C) Yes - Scale based on custom metrics (request rate)
D) No - Fixed replica count (1 replica for small scale)
E) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Mandatory Artifacts

This plan will generate:
1. **infrastructure-design.md**: Complete infrastructure specifications
2. **deployment-architecture.md**: Kubernetes and AWS architecture diagrams

---

## Success Criteria
- [x] Kubernetes resources defined
- [x] AWS services mapped
- [x] Container strategy documented
- [x] Configuration management designed
- [x] Networking configured
- [x] All questions answered and ambiguities resolved
