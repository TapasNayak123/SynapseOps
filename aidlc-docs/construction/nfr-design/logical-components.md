# Logical Components

## Overview
This document identifies logical components needed to implement NFR patterns and support the application architecture.

---

## Component Category 1: Middleware Components

### Component 1.1: Request Correlation Middleware

**Purpose**: Generate and track request IDs across logs

**Responsibilities**:
- Check for X-Request-ID header
- Generate UUID if not present
- Attach requestId to request object
- Set X-Request-ID response header

**Dependencies**:
- uuid library

**Location**: `src/middleware/requestCorrelation.ts`

---

### Component 1.2: Request Logging Middleware

**Purpose**: Log all incoming requests

**Responsibilities**:
- Log request method, path, IP
- Log request headers (sanitized)
- Log request body (sanitized)
- Include requestId for correlation

**Dependencies**:
- Winston logger
- Request correlation middleware

**Location**: `src/middleware/requestLogger.ts`

---

### Component 1.3: Response Logging Middleware

**Purpose**: Log all outgoing responses

**Responsibilities**:
- Log response status code
- Log response time
- Log response body (sanitized)
- Include requestId for correlation

**Dependencies**:
- Winston logger
- Request correlation middleware

**Location**: `src/middleware/responseLogger.ts`

---

### Component 1.4: Error Handling Middleware

**Purpose**: Centralized error handling

**Responsibilities**:
- Catch all errors from controllers
- Format error responses consistently
- Log errors with full context
- Return appropriate HTTP status codes
- Include requestId in error response

**Dependencies**:
- Winston logger
- Request correlation middleware

**Location**: `src/middleware/errorHandler.ts`

**Error Response Format**:
```typescript
{
  status: "error",
  message: string,
  errorCode: string,
  requestId: string,
  data: null
}
```

---

### Component 1.5: Authentication Middleware

**Purpose**: Verify JWT tokens on protected routes

**Responsibilities**:
- Extract JWT from Authorization header
- Verify JWT signature
- Check JWT expiration
- Extract user information
- Attach user to request object
- Return 401 if invalid/expired

**Dependencies**:
- jsonwebtoken library
- JWT configuration

**Location**: `src/middleware/authenticate.ts`

---

### Component 1.6: Rate Limiting Middleware

**Purpose**: Prevent abuse and brute force attacks

**Responsibilities**:
- Track requests per IP address
- Enforce 100 requests per 15 minutes
- Return 429 when limit exceeded
- Set Retry-After header
- Log rate limit violations

**Dependencies**:
- express-rate-limit library

**Location**: `src/middleware/rateLimiter.ts`

---

### Component 1.7: Security Headers Middleware

**Purpose**: Set security headers on all responses

**Responsibilities**:
- Set Content-Security-Policy
- Set X-Content-Type-Options
- Set X-Frame-Options
- Set other security headers via Helmet

**Dependencies**:
- helmet library

**Location**: `src/middleware/securityHeaders.ts`

---

### Component 1.8: CORS Middleware

**Purpose**: Handle cross-origin requests

**Responsibilities**:
- Allow configured origins
- Set CORS headers
- Handle preflight requests

**Dependencies**:
- cors library

**Location**: `src/middleware/corsConfig.ts`

---

### Component 1.9: Body Parser Middleware

**Purpose**: Parse request bodies

**Responsibilities**:
- Parse JSON request bodies
- Set body size limit (1MB)
- Handle parsing errors

**Dependencies**:
- express.json()

**Location**: Built-in Express middleware

---

## Component Category 2: Service Components

### Component 2.1: Logger Service

**Purpose**: Centralized logging service

**Responsibilities**:
- Initialize Winston logger
- Configure transports (Console, CloudWatch)
- Provide logging methods (error, warn, info, debug)
- Format logs consistently
- Filter sensitive data

**Dependencies**:
- winston library
- winston-cloudwatch transport

**Location**: `src/services/logger.service.ts`

**Log Methods**:
- `logger.error(message, context)`
- `logger.warn(message, context)`
- `logger.info(message, context)`
- `logger.debug(message, context)`

---

### Component 2.2: Email Service

**Purpose**: Send emails via Nodemailer

**Responsibilities**:
- Initialize Nodemailer transport
- Send password reset emails
- Retry on failure (3 attempts with backoff)
- Log email sending attempts
- Handle email failures gracefully

**Dependencies**:
- nodemailer library
- Email configuration
- Logger service
- Retry utility

**Location**: `src/services/email.service.ts`

**Methods**:
- `sendPasswordResetEmail(email, token, resetUrl)`

---

### Component 2.3: Token Service

**Purpose**: Generate and validate tokens

**Responsibilities**:
- Generate JWT tokens
- Verify JWT tokens
- Generate password reset tokens
- Validate reset tokens

**Dependencies**:
- jsonwebtoken library
- crypto module
- JWT configuration

**Location**: `src/services/token.service.ts`

**Methods**:
- `generateJWT(userId, email)`
- `verifyJWT(token)`
- `generateResetToken()`
- `validateResetToken(token)`

---

### Component 2.4: Password Service

**Purpose**: Hash and verify passwords

**Responsibilities**:
- Hash passwords with bcrypt
- Verify passwords with bcrypt
- Use cost factor 12
- Async operations

**Dependencies**:
- bcryptjs library

**Location**: `src/services/password.service.ts`

**Methods**:
- `hashPassword(plainPassword)`
- `verifyPassword(plainPassword, hashedPassword)`

---

### Component 2.5: Metrics Service

**Purpose**: Track and publish metrics

**Responsibilities**:
- Track request counts
- Track response times
- Track error rates
- Publish to CloudWatch Metrics

**Dependencies**:
- AWS SDK CloudWatch
- Logger service

**Location**: `src/services/metrics.service.ts`

**Methods**:
- `trackRequest(endpoint, method, statusCode, duration)`
- `trackError(endpoint, errorType)`
- `publishMetrics()`

---

## Component Category 3: Utility Components

### Component 3.1: Retry Utility

**Purpose**: Retry failed operations with exponential backoff

**Responsibilities**:
- Execute operation with retries
- Implement exponential backoff
- Log retry attempts
- Return result or throw error

**Dependencies**:
- Logger service

**Location**: `src/utils/retry.util.ts`

**Configuration**:
- Max attempts: 3
- Initial delay: 1000ms
- Backoff multiplier: 2

**Method**:
- `retryWithBackoff(operation, maxAttempts, initialDelay)`

---

### Component 3.2: Validation Utility

**Purpose**: Common validation functions

**Responsibilities**:
- Validate email format
- Validate email domain (Gmail)
- Validate password strength
- Validate date format
- Calculate age from date of birth

**Dependencies**:
- None (pure functions)

**Location**: `src/utils/validation.util.ts`

**Methods**:
- `isValidEmail(email)`
- `isGmailDomain(email)`
- `isStrongPassword(password)`
- `isValidDate(dateString)`
- `calculateAge(dateOfBirth)`

---

### Component 3.3: Error Utility

**Purpose**: Create standardized error objects

**Responsibilities**:
- Create error objects with codes
- Format error messages
- Attach HTTP status codes

**Dependencies**:
- None

**Location**: `src/utils/error.util.ts`

**Error Classes**:
- `ValidationError` (400)
- `AuthenticationError` (401)
- `NotFoundError` (404)
- `ConflictError` (409)
- `RateLimitError` (429)
- `InternalError` (500)

---

### Component 3.4: Response Utility

**Purpose**: Format API responses consistently

**Responsibilities**:
- Format success responses
- Format error responses
- Include requestId

**Dependencies**:
- None

**Location**: `src/utils/response.util.ts`

**Methods**:
- `successResponse(message, data, requestId)`
- `errorResponse(message, errorCode, requestId)`

---

### Component 3.5: Sanitization Utility

**Purpose**: Sanitize data for logging

**Responsibilities**:
- Remove passwords from objects
- Remove tokens from objects
- Remove sensitive fields

**Dependencies**:
- None

**Location**: `src/utils/sanitize.util.ts`

**Methods**:
- `sanitizeForLogging(object)`
- `sanitizeRequestBody(body)`
- `sanitizeHeaders(headers)`

---

## Component Category 4: Configuration Components

### Component 4.1: Environment Configuration

**Purpose**: Load and validate environment variables

**Responsibilities**:
- Load .env file
- Validate required variables
- Provide typed configuration object
- Throw error if missing required vars

**Dependencies**:
- dotenv library

**Location**: `src/config/env.config.ts`

**Configuration Object**:
```typescript
{
  nodeEnv: string,
  port: number,
  aws: {
    region: string,
    accessKeyId: string,
    secretAccessKey: string
  },
  dynamodb: {
    usersTable: string,
    tokensTable: string
  },
  jwt: {
    secret: string,
    expiration: string
  },
  email: {
    host: string,
    port: number,
    user: string,
    password: string,
    from: string
  },
  rateLimit: {
    windowMs: number,
    maxRequests: number
  },
  logging: {
    level: string
  }
}
```

---

### Component 4.2: Database Configuration

**Purpose**: Initialize DynamoDB client

**Responsibilities**:
- Create DynamoDB client instance
- Configure AWS credentials
- Export client for reuse

**Dependencies**:
- AWS SDK DynamoDB
- Environment configuration

**Location**: `src/config/database.config.ts`

**Export**:
- `dynamoDBClient` (singleton instance)

---

### Component 4.3: Logger Configuration

**Purpose**: Configure Winston logger

**Responsibilities**:
- Create Winston logger instance
- Configure transports
- Set log levels
- Configure formats

**Dependencies**:
- winston library
- winston-cloudwatch transport
- Environment configuration

**Location**: `src/config/logger.config.ts`

**Export**:
- `logger` (singleton instance)

---

### Component 4.4: Email Configuration

**Purpose**: Configure Nodemailer transport

**Responsibilities**:
- Create Nodemailer transport
- Configure SMTP settings
- Export transport for reuse

**Dependencies**:
- nodemailer library
- Environment configuration

**Location**: `src/config/email.config.ts`

**Export**:
- `emailTransport` (singleton instance)

---

## Component Category 5: Health Check Components

### Component 5.1: Health Check Service

**Purpose**: Provide health check functionality

**Responsibilities**:
- Check application health
- Return health status
- Include uptime
- Include timestamp

**Dependencies**:
- None

**Location**: `src/services/health.service.ts`

**Methods**:
- `getHealthStatus()`

**Response**:
```typescript
{
  status: "healthy",
  timestamp: string,
  uptime: number
}
```

---

## Component Summary

### By Category

**Middleware Components**: 9 components
- Request Correlation
- Request Logging
- Response Logging
- Error Handling
- Authentication
- Rate Limiting
- Security Headers
- CORS
- Body Parser

**Service Components**: 5 components
- Logger Service
- Email Service
- Token Service
- Password Service
- Metrics Service

**Utility Components**: 5 components
- Retry Utility
- Validation Utility
- Error Utility
- Response Utility
- Sanitization Utility

**Configuration Components**: 4 components
- Environment Configuration
- Database Configuration
- Logger Configuration
- Email Configuration

**Health Check Components**: 1 component
- Health Check Service

**Total Logical Components**: 24 components

---

## Component Dependencies

### Dependency Graph

```
Environment Config
    |
    +---> Database Config --> DynamoDB Client
    |
    +---> Logger Config --> Logger Service
    |
    +---> Email Config --> Email Service
    |
    +---> JWT Config --> Token Service

Logger Service
    |
    +---> Request Logging Middleware
    +---> Response Logging Middleware
    +---> Error Handling Middleware
    +---> Email Service
    +---> Metrics Service

Token Service
    |
    +---> Authentication Middleware

Password Service
    |
    +---> Auth Controller (registration, login, reset)

Email Service
    |
    +---> Auth Controller (forgot password)

Validation Utility
    |
    +---> Validators (all endpoints)

Error Utility
    |
    +---> Controllers (all)
    +---> Services (all)

Response Utility
    |
    +---> Controllers (all)

Sanitization Utility
    |
    +---> Logger Service
    +---> Request Logging Middleware
```

---

## Component Integration

All components work together to provide:
- **Middleware Layer**: Request processing, authentication, logging, error handling
- **Service Layer**: Business logic, external integrations, utilities
- **Configuration Layer**: Environment setup, client initialization
- **Utility Layer**: Reusable functions, helpers

This architecture supports:
- Separation of concerns
- Testability (each component can be tested independently)
- Maintainability (clear responsibilities)
- Scalability (stateless components)
- Observability (comprehensive logging and monitoring)

