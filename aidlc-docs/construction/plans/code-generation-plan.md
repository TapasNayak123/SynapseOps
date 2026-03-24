# Code Generation Plan

## Purpose
Generate complete TypeScript/Node.js/Express authentication application code based on all design artifacts.

## Context
- **Project Type**: Greenfield (new project)
- **Workspace Root**: . (current directory)
- **Application Code Location**: Workspace root (NOT in aidlc-docs/)
- **Documentation Location**: aidlc-docs/construction/code/
- **Architecture**: Monolithic application (Units Generation was skipped)
- **Tech Stack**: TypeScript, Node.js, Express, DynamoDB, Kubernetes

---

## Code Generation Steps

### Step 1: Project Structure Setup
- [ ] Create directory structure
- [ ] Initialize package.json with dependencies
- [ ] Create tsconfig.json for TypeScript configuration
- [ ] Create .env.example for environment variables template
- [ ] Create .gitignore for version control
- [ ] Create .dockerignore for Docker builds
- [ ] Create README.md with setup instructions

**Directories to Create**:
```
src/
├── controllers/
├── services/
├── models/
├── routes/
├── middleware/
├── validators/
├── utils/
├── config/
└── types/
tests/
├── unit/
├── integration/
└── e2e/
k8s/
├── deployment.yaml
├── service.yaml
├── configmap.yaml
├── secret.yaml
└── hpa.yaml
```

---

### Step 2: Configuration Layer
- [ ] Create src/config/env.config.ts (environment variable loading and validation)
- [ ] Create src/config/database.config.ts (DynamoDB client initialization)
- [ ] Create src/config/logger.config.ts (Winston logger configuration)
- [ ] Create src/config/email.config.ts (Nodemailer transport configuration)

---

### Step 3: Type Definitions
- [ ] Create src/types/user.types.ts (User, CreateUserDTO, UserResponseDTO)
- [ ] Create src/types/token.types.ts (PasswordResetToken, JWTPayload)
- [ ] Create src/types/request.types.ts (Extended Express Request with user)
- [ ] Create src/types/response.types.ts (API response formats)

---

### Step 4: Utility Layer
- [x] Create src/utils/logger.ts (Winston logger instance)
- [x] Create src/utils/response-formatter.ts (Success/error response formatting)
- [x] Create src/utils/email-validator.ts (Email format and domain validation)
- [x] Create src/utils/password-validator.ts (Password strength validation)
- [x] Create src/utils/date-validator.ts (Date of birth and age validation)
- [x] Create src/utils/retry.util.ts (Retry with exponential backoff)
- [x] Create src/utils/error.util.ts (Custom error classes)
- [x] Create src/utils/sanitize.util.ts (Sanitize data for logging)

---

### Step 5: Model Layer (Data Access)
- [x] Create src/models/user.model.ts (User CRUD operations with DynamoDB)
- [x] Create src/models/password-reset-token.model.ts (Token CRUD operations with DynamoDB)

---

### Step 6: Service Layer (Business Logic)
- [x] Create src/services/user.service.ts (User registration, authentication, password update)
- [x] Create src/services/email.service.ts (Password reset email sending with retry)
- [x] Create src/services/token.service.ts (JWT and reset token generation/validation)
- [x] Create src/services/password.service.ts (Password hashing and verification)
- [x] Create src/services/metrics.service.ts (CloudWatch metrics tracking)
- [x] Create src/services/health.service.ts (Health check logic)

---

### Step 7: Validation Layer
- [x] Create src/validators/auth.validators.ts (express-validator schemas for all auth endpoints)

---

### Step 8: Middleware Layer
- [x] Create src/middleware/request-correlation.middleware.ts (Generate/extract request ID)
- [x] Create src/middleware/request-logger.middleware.ts (Log incoming requests)
- [x] Create src/middleware/response-logger.middleware.ts (Log outgoing responses)
- [x] Create src/middleware/error-handler.middleware.ts (Centralized error handling)
- [x] Create src/middleware/authenticate.middleware.ts (JWT verification)
- [x] Create src/middleware/rate-limiter.middleware.ts (Rate limiting configuration)
- [x] Create src/middleware/security-headers.middleware.ts (Helmet configuration)
- [x] Create src/middleware/cors.middleware.ts (CORS configuration)

---

### Step 9: Controller Layer
- [x] Create src/controllers/auth.controller.ts (Registration, login, forgot password, reset password)
- [x] Create src/controllers/health.controller.ts (Health check endpoint)

---

### Step 10: Routes Layer
- [x] Create src/routes/auth.routes.ts (Auth endpoint definitions with middleware)
- [x] Create src/routes/health.routes.ts (Health check route)
- [x] Create src/routes/index.ts (Route aggregation)

---

### Step 11: Application Entry Point
- [ ] Create src/app.ts (Express app setup with middleware and routes)
- [ ] Create src/server.ts (HTTP server initialization and startup)
- [ ] Create src/index.ts (Main entry point)

---

### Step 12: Unit Tests - Utilities
- [ ] Create tests/unit/utils/email-validator.test.ts
- [ ] Create tests/unit/utils/password-validator.test.ts
- [ ] Create tests/unit/utils/date-validator.test.ts
- [ ] Create tests/unit/utils/response-formatter.test.ts

---

### Step 13: Unit Tests - Services
- [ ] Create tests/unit/services/user.service.test.ts
- [ ] Create tests/unit/services/token.service.test.ts
- [ ] Create tests/unit/services/password.service.test.ts
- [ ] Create tests/unit/services/email.service.test.ts

---

### Step 14: Unit Tests - Models
- [ ] Create tests/unit/models/user.model.test.ts
- [ ] Create tests/unit/models/password-reset-token.model.test.ts

---

### Step 15: Integration Tests - API Endpoints
- [ ] Create tests/integration/auth/registration.test.ts
- [ ] Create tests/integration/auth/login.test.ts
- [ ] Create tests/integration/auth/forgot-password.test.ts
- [ ] Create tests/integration/auth/reset-password.test.ts
- [ ] Create tests/integration/health.test.ts

---

### Step 16: E2E Tests - Complete Workflows
- [ ] Create tests/e2e/registration-login-flow.test.ts
- [ ] Create tests/e2e/password-reset-flow.test.ts
- [ ] Create tests/e2e/rate-limiting.test.ts

---

### Step 17: Test Utilities and Setup
- [ ] Create tests/utils/test-helpers.ts (Mock data generators, test utilities)
- [ ] Create tests/utils/dynamodb-mock.ts (DynamoDB mock for tests)
- [ ] Create tests/setup.ts (Global test setup and teardown)
- [ ] Create vitest.config.ts (Vitest configuration)

---

### Step 18: Docker Configuration
- [ ] Create Dockerfile (Multi-stage build with Node.js Alpine)
- [ ] Create .dockerignore (Exclude unnecessary files from image)
- [ ] Create docker-compose.yml (Local development with DynamoDB Local - optional)

---

### Step 19: Kubernetes Manifests
- [ ] Create k8s/deployment.yaml (Deployment with resource limits, health checks)
- [ ] Create k8s/service.yaml (LoadBalancer service)
- [ ] Create k8s/configmap.yaml (Non-sensitive configuration)
- [ ] Create k8s/secret.yaml (Sensitive credentials template)
- [ ] Create k8s/hpa.yaml (Horizontal Pod Autoscaler)

---

### Step 20: Documentation
- [ ] Create README.md (Project overview, setup instructions, API documentation)
- [ ] Create DEPLOYMENT.md (Kubernetes deployment guide)
- [ ] Create DEVELOPMENT.md (Local development setup)
- [ ] Create API.md (API endpoint documentation with examples)
- [ ] Create aidlc-docs/construction/code/code-summary.md (Code generation summary)

---

## Questions for User

### Question 1: Package Manager
Which package manager should be used for dependency management?

A) npm (default, comes with Node.js)
B) yarn (faster, better caching)
C) pnpm (disk space efficient)
D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 2: Node.js Version
Which Node.js LTS version should be targeted?

A) Node.js 20.x LTS (latest LTS, recommended)
B) Node.js 18.x LTS (previous LTS, more stable)
C) Node.js 22.x (current, not LTS yet)
D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 3: TypeScript Configuration
What TypeScript strictness level should be used?

A) Strict mode (all strict checks enabled, recommended)
B) Standard mode (some strict checks disabled for easier development)
C) Loose mode (minimal type checking)
D) Other (please describe after [Answer]: tag below)

[Answer]: B

### Question 4: Test Coverage Target
What minimum test coverage percentage should be enforced?

A) 80% (recommended, comprehensive coverage)
B) 70% (good coverage, faster to achieve)
C) 90% (very high coverage, more effort)
D) No minimum (coverage tracking only)
E) Other (please describe after [Answer]: tag below)

[Answer]: D

### Question 5: Environment File
Should a .env file be created for local development?

A) Yes - Create .env with example values (easier local setup)
B) No - Only create .env.example (user fills in values)
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 6: Docker Compose
Should docker-compose.yml be created for local development with DynamoDB Local?

A) Yes - Include DynamoDB Local for easy local testing
B) No - Use real AWS DynamoDB for all environments
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 7: API Documentation Format
What format should be used for API documentation?

A) Markdown file (simple, included in README or separate API.md)
B) OpenAPI/Swagger spec (interactive, can generate UI)
C) Both (Markdown + OpenAPI spec)
D) Other (please describe after [Answer]: tag below)

[Answer]: C

### Question 8: Linting and Formatting
Should ESLint and Prettier be configured?

A) Yes - Both ESLint and Prettier with recommended configs
B) ESLint only (no Prettier)
C) Prettier only (no ESLint)
D) No - Skip linting and formatting setup
E) Other (please describe after [Answer]: tag below)

[Answer]: D

### Question 9: Git Hooks
Should Husky be configured for pre-commit hooks (linting, tests)?

A) Yes - Run linting and tests before commits
B) No - Manual linting and testing only
C) Other (please describe after [Answer]: tag below)

[Answer]: B

### Question 10: Logging Level
What default logging level should be used for production?

A) info (recommended, important events only)
B) debug (verbose, all events)
C) warn (minimal, warnings and errors only)
D) error (critical only, errors only)
E) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Mandatory Artifacts

This plan will generate:

### Application Code (Workspace Root)
1. **Configuration**: 4 files (env, database, logger, email)
2. **Types**: 4 files (user, token, request, response)
3. **Utilities**: 8 files (logger, formatters, validators, error handling)
4. **Models**: 2 files (user, password-reset-token)
5. **Services**: 6 files (user, email, token, password, metrics, health)
6. **Validators**: 1 file (auth validators)
7. **Middleware**: 8 files (correlation, logging, error handling, auth, rate limit, security, CORS)
8. **Controllers**: 2 files (auth, health)
9. **Routes**: 3 files (auth, health, index)
10. **Application**: 3 files (app, server, index)
11. **Tests**: 15+ test files (unit, integration, e2e)
12. **Docker**: 2-3 files (Dockerfile, .dockerignore, optional docker-compose.yml)
13. **Kubernetes**: 5 files (deployment, service, configmap, secret, hpa)
14. **Configuration**: 5 files (package.json, tsconfig.json, .env.example, .gitignore, vitest.config.ts)
15. **Documentation**: 4-5 files (README, DEPLOYMENT, DEVELOPMENT, API, optional OpenAPI spec)

### Documentation (aidlc-docs/construction/code/)
1. **code-summary.md**: Summary of generated code with file counts and structure

**Total Files**: ~70-75 files

---

## Success Criteria
- [ ] All configuration files created
- [ ] All type definitions created
- [ ] All utility functions created
- [ ] All models created with DynamoDB operations
- [ ] All services created with business logic
- [ ] All validators created
- [ ] All middleware created
- [ ] All controllers created
- [ ] All routes created
- [ ] Application entry point created
- [ ] All unit tests created
- [ ] All integration tests created
- [ ] All e2e tests created
- [ ] Docker configuration created
- [ ] Kubernetes manifests created
- [ ] Documentation created
- [ ] All questions answered and ambiguities resolved
- [ ] Code compiles without errors
- [ ] Tests run successfully
- [ ] Application follows MVC pattern
- [ ] All business rules implemented
- [ ] All NFR patterns implemented
- [ ] All security requirements met

---

## Code Generation Approach

### Incremental Generation
- Generate code in logical groups (config → types → utils → models → services → etc.)
- Test each layer before moving to next
- Follow dependency order (lower layers first)

### Code Quality Standards
- TypeScript strict mode enabled
- Comprehensive error handling
- Detailed code comments
- JSDoc for public APIs
- Consistent naming conventions
- DRY principle (Don't Repeat Yourself)
- SOLID principles where applicable

### Testing Strategy
- Unit tests: Test individual functions in isolation
- Integration tests: Test API endpoints end-to-end
- E2E tests: Test complete user workflows
- Mock external dependencies (DynamoDB, email)
- Use test fixtures for consistent data

### Documentation Standards
- README: Project overview, setup, quick start
- DEPLOYMENT: Kubernetes deployment instructions
- DEVELOPMENT: Local development setup
- API: Endpoint documentation with examples
- Code comments: Explain complex logic
- JSDoc: Document public APIs

---

## Notes

- **Application code goes in workspace root** (NOT in aidlc-docs/)
- **Documentation goes in aidlc-docs/construction/code/**
- **Follow MVC pattern** as defined in application design
- **Implement all 35 business rules** from functional design
- **Apply all 18 NFR patterns** from NFR design
- **Use all technology stack decisions** from tech stack document
- **Follow Kubernetes infrastructure design** from infrastructure design
- **Generate working, production-ready code**
- **Include comprehensive tests** (unit, integration, e2e)
- **Provide complete deployment instructions**
