# NFR Design Patterns

## Overview
This document defines the NFR patterns and implementation strategies for the authentication application.

---

## Pattern Category 1: Resilience Patterns

### Pattern 1.1: Centralized Error Handling

**Purpose**: Consistent error handling across all endpoints

**Implementation Strategy**:
- Express error handling middleware
- Catch all errors in controllers
- Format errors consistently
- Log errors with context

**Error Response Format**:
```typescript
{
  status: "error",
  message: string,           // User-friendly message
  errorCode: string,         // Error code for support
  requestId: string,         // Request ID for correlation
  data: null
}
```

**Error Categories**:
- Validation errors (400)
- Authentication errors (401)
- Not found errors (404)
- Conflict errors (409)
- Rate limit errors (429)
- Server errors (500)

**Error Middleware Flow**:
```
Request --> Controller --> Error Thrown
                              |
                              v
                    Error Middleware
                              |
                              v
                    Log Error (Winston)
                              |
                              v
                    Format Error Response
                              |
                              v
                    Send to Client
```


### Pattern 1.2: Retry with Exponential Backoff

**Purpose**: Handle transient failures gracefully (email sending)

**Implementation Strategy**:
- Retry failed email operations
- 3 retry attempts maximum
- Exponential backoff: 1s, 2s, 4s
- Log each retry attempt
- Continue on final failure (don't block user)

**Retry Logic**:
```
Attempt 1 --> Fail --> Wait 1s --> Attempt 2
                                      |
                                   Fail --> Wait 2s --> Attempt 3
                                                           |
                                                        Fail --> Log Error, Continue
```

**Retry Configuration**:
- Max attempts: 3
- Initial delay: 1000ms
- Backoff multiplier: 2
- Max delay: 4000ms

**Error Handling**:
- Log each failure with attempt number
- On final failure: Log error, return success to user (security)
- Track retry metrics in CloudWatch

---

### Pattern 1.3: Graceful Degradation

**Purpose**: Continue operation when non-critical services fail

**Implementation Strategy**:
- Email service failure: Log error, return success (security)
- CloudWatch logging failure: Fall back to console logging
- Health check: Return degraded status if dependencies fail

**Degradation Scenarios**:
1. **Email Service Down**:
   - Log error with full context
   - Return success to user (don't reveal email service status)
   - Alert operations team via CloudWatch alarm

2. **CloudWatch Unavailable**:
   - Fall back to console logging
   - Continue normal operation
   - Retry CloudWatch connection periodically

3. **DynamoDB Throttling**:
   - Retry with exponential backoff (AWS SDK built-in)
   - Log throttling events
   - Alert if sustained throttling

---

## Pattern Category 2: Security Patterns

### Pattern 2.1: JWT Authentication Flow

**Purpose**: Stateless authentication with JWT tokens

**Implementation Strategy**:
- Generate JWT on successful login
- Include userId and email in payload
- Set 1-hour expiration
- Sign with HS256 algorithm
- Verify on every protected route

**JWT Flow**:
```
Login Request --> Verify Credentials --> Generate JWT
                                            |
                                            v
                                    Sign with Secret
                                            |
                                            v
                                    Return to Client
                                            |
                                            v
                            Client includes in Authorization header
                                            |
                                            v
                            Protected Route --> Verify JWT
                                                    |
                                                    v
                                            Extract User Info
                                                    |
                                                    v
                                            Process Request
```

**JWT Payload Structure**:
```typescript
{
  userId: string,
  email: string,
  iat: number,      // Issued at
  exp: number       // Expiration (iat + 3600)
}
```

**JWT Verification**:
- Verify signature with secret
- Check expiration time
- Extract user information
- Attach to request object


### Pattern 2.2: Password Hashing Strategy

**Purpose**: Secure password storage with bcrypt

**Implementation Strategy**:
- Hash passwords with bcrypt
- Cost factor: 12 rounds (~300ms)
- Salt generation automatic
- Async operations (non-blocking)

**Hashing Flow**:
```
Plain Password --> bcrypt.hash(password, 12) --> Hashed Password
                                                        |
                                                        v
                                                Store in Database
```

**Verification Flow**:
```
Login Attempt --> Retrieve Hashed Password from DB
                            |
                            v
                bcrypt.compare(plain, hashed)
                            |
                            v
                    Constant-time comparison
                            |
                            v
                    Return true/false
```

**Security Considerations**:
- Never log plain text passwords
- Never log hashed passwords
- Use async operations to prevent blocking
- Cost factor 12 provides good security/performance balance

---

### Pattern 2.3: Cryptographic Token Generation

**Purpose**: Secure password reset tokens

**Implementation Strategy**:
- Use crypto.randomBytes(32)
- Convert to hexadecimal (64 characters)
- 256 bits of entropy
- Store with expiration (1 hour)
- Mark as used after consumption

**Token Generation Flow**:
```
Reset Request --> crypto.randomBytes(32) --> Convert to Hex
                                                    |
                                                    v
                                            Generate Token ID (UUID)
                                                    |
                                                    v
                                            Store with Expiration
                                                    |
                                                    v
                                            Send in Email
```

**Token Validation Flow**:
```
Reset Attempt --> Find Token in DB --> Check Expiration
                                            |
                                            v
                                        Check Used Flag
                                            |
                                            v
                                        Validate Token
                                            |
                                            v
                                        Mark as Used
```

---

### Pattern 2.4: Rate Limiting Strategy

**Purpose**: Prevent brute force and abuse

**Implementation Strategy**:
- express-rate-limit middleware
- 100 requests per 15 minutes per IP
- In-memory storage (simple, sufficient for small scale)
- Applied globally to all endpoints
- Return 429 with Retry-After header

**Rate Limit Configuration**:
```typescript
{
  windowMs: 15 * 60 * 1000,  // 15 minutes
  max: 100,                   // 100 requests per window
  message: "Too many requests. Please try again later.",
  standardHeaders: true,      // Return RateLimit-* headers
  legacyHeaders: false        // Disable X-RateLimit-* headers
}
```

**Rate Limit Flow**:
```
Request --> Check IP in Store --> Count < Max?
                                      |
                                   Yes --> Process Request
                                      |
                                   No --> Return 429 + Retry-After
```

---

### Pattern 2.5: Security Headers

**Purpose**: Protect against common web vulnerabilities

**Implementation Strategy**:
- Helmet.js middleware
- Set multiple security headers
- Configure CORS appropriately
- Prevent XSS, clickjacking, MIME sniffing

**Headers Set by Helmet**:
- Content-Security-Policy
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security (HTTPS only)

**CORS Configuration**:
- Allow all origins (development-friendly)
- Allow credentials
- Expose necessary headers
- Can be restricted per environment

---

## Pattern Category 3: Performance Patterns

### Pattern 3.1: Database Connection Management

**Purpose**: Efficient DynamoDB client usage

**Implementation Strategy**:
- Single global DynamoDB client instance
- Initialize once at application startup
- Reuse across all requests
- AWS SDK handles connection pooling internally

**Client Initialization**:
```typescript
// Initialize once
const dynamoDBClient = new DynamoDBClient({
  region: process.env.AWS_REGION,
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
  }
});

// Reuse everywhere
export default dynamoDBClient;
```

**Benefits**:
- No connection overhead per request
- AWS SDK manages connection pooling
- Simple implementation
- Efficient for small scale

---

### Pattern 3.2: Asynchronous Email Sending

**Purpose**: Non-blocking email operations

**Implementation Strategy**:
- Send emails asynchronously
- Don't wait for email confirmation
- Log success/failure
- Return immediately to user

**Async Email Flow**:
```
Forgot Password Request --> Generate Token --> Store Token
                                                    |
                                                    v
                                            Send Email (async)
                                                    |
                                                    v
                                            Return Success Immediately
                                                    |
                                            (Email sends in background)
```

**Implementation**:
```typescript
// Fire and forget with error handling
sendEmail(options)
  .then(() => logger.info('Email sent successfully'))
  .catch(error => logger.error('Email failed', { error }));

// Return immediately
return res.status(200).json({ status: 'success', ... });
```

---

### Pattern 3.3: Query Optimization with Indexes

**Purpose**: Fast database queries

**Implementation Strategy**:
- Use Global Secondary Indexes (GSI) for email lookups
- Primary key for userId lookups
- Token index for reset token validation
- Avoid table scans

**Index Strategy**:
- Users table: email-index GSI (for login, uniqueness)
- PasswordResetTokens table: token-index GSI (for validation)
- All queries use indexed attributes

**Query Performance**:
- Primary key lookup: < 10ms
- GSI query: < 50ms
- No full table scans

---

## Pattern Category 4: Logging Patterns

### Pattern 4.1: Structured Logging

**Purpose**: Consistent, parseable log format

**Implementation Strategy**:
- Winston logging framework
- JSON format for production
- Pretty-print for development
- Include context in every log

**Log Structure**:
```typescript
{
  timestamp: string,        // ISO 8601
  level: string,           // error, warn, info, debug
  message: string,         // Log message
  requestId: string,       // Correlation ID
  userId?: string,         // If authenticated
  email?: string,          // If relevant
  ipAddress?: string,      // Client IP
  endpoint?: string,       // API endpoint
  duration?: number,       // Request duration
  error?: {                // If error
    message: string,
    stack: string,
    code: string
  }
}
```

**Log Levels**:
- error: Errors requiring attention
- warn: Warnings, degraded functionality
- info: Important events (login, registration)
- debug: Detailed debugging information


### Pattern 4.2: Request Correlation

**Purpose**: Track requests across logs

**Implementation Strategy**:
- Use X-Request-ID header
- Generate UUID if not provided
- Include in all logs for that request
- Return in response headers

**Correlation Flow**:
```
Request --> Check X-Request-ID header
                |
            Present? --> Use it
                |
            Missing? --> Generate UUID
                |
                v
        Attach to request object
                |
                v
        Include in all logs
                |
                v
        Return in response header
```

**Implementation**:
```typescript
// Middleware
app.use((req, res, next) => {
  req.requestId = req.headers['x-request-id'] || uuidv4();
  res.setHeader('X-Request-ID', req.requestId);
  next();
});

// Logging
logger.info('User login', { 
  requestId: req.requestId,
  ...otherContext 
});
```

---

### Pattern 4.3: Sensitive Data Filtering

**Purpose**: Never log sensitive information

**Implementation Strategy**:
- Filter passwords from logs
- Filter JWT tokens from logs
- Filter reset tokens from logs
- Filter password hashes from logs

**Prohibited in Logs**:
- Plain text passwords
- Password hashes
- JWT tokens
- Reset tokens
- Credit card numbers (if added later)
- Social security numbers (if added later)

**Allowed in Logs**:
- Email addresses
- User IDs
- IP addresses
- Timestamps
- Request/response status
- Error messages (sanitized)

**Log Sanitization**:
```typescript
// Before logging request body
const sanitized = {
  ...body,
  password: '[REDACTED]',
  token: '[REDACTED]'
};
logger.info('Request received', { body: sanitized });
```

---

## Pattern Category 5: Monitoring Patterns

### Pattern 5.1: Health Check Implementation

**Purpose**: Monitor application health

**Implementation Strategy**:
- Basic health check endpoint
- Return 200 OK if healthy
- Include uptime and timestamp
- No authentication required
- Fast response (< 50ms)

**Health Check Response**:
```typescript
{
  status: "healthy",
  timestamp: "2026-03-09T12:34:56.789Z",
  uptime: 3600  // seconds
}
```

**Health Check Endpoint**:
- Path: GET /health
- No database check (basic health check)
- No external service check
- Just application availability

---

### Pattern 5.2: Metrics Collection

**Purpose**: Track application performance

**Implementation Strategy**:
- CloudWatch custom metrics
- Track key performance indicators
- Aggregate metrics per minute
- Create dashboards for visualization

**Metrics to Track**:
- Request count by endpoint
- Response time percentiles (p50, p95, p99)
- Error rate by endpoint
- Authentication success/failure rate
- Rate limit violations
- Database query latency
- Email sending success rate

**Metric Dimensions**:
- Endpoint
- HTTP method
- Status code
- Environment

---

### Pattern 5.3: Error Tracking Integration

**Purpose**: Centralized error monitoring

**Implementation Strategy**:
- AWS CloudWatch Logs for error aggregation
- CloudWatch Metrics for error rates
- CloudWatch Alarms for critical errors
- Log all errors with full context

**Error Tracking Flow**:
```
Error Occurs --> Log to Winston --> CloudWatch Logs
                                          |
                                          v
                                  CloudWatch Metrics
                                          |
                                          v
                                  CloudWatch Alarms
                                          |
                                          v
                                  Alert if threshold exceeded
```

**Alarm Configuration**:
- Error rate > 5% for 5 minutes
- Response time p95 > 1000ms for 5 minutes
- Authentication failure rate > 20% for 5 minutes
- Database errors > 10 in 5 minutes

---

### Pattern 5.4: Performance Monitoring

**Purpose**: Track and optimize performance

**Implementation Strategy**:
- Log request duration
- Track slow queries
- Monitor bcrypt operations
- Alert on performance degradation

**Performance Metrics**:
- API response time by endpoint
- Database query time
- Bcrypt operation time
- Email sending time

**Performance Thresholds**:
- Registration: < 500ms (target)
- Login: < 500ms (target)
- Forgot password: < 200ms (target)
- Reset password: < 500ms (target)
- Health check: < 50ms (target)

---

## Pattern Summary

### Resilience Patterns (3)
1. Centralized Error Handling
2. Retry with Exponential Backoff
3. Graceful Degradation

### Security Patterns (5)
1. JWT Authentication Flow
2. Password Hashing Strategy
3. Cryptographic Token Generation
4. Rate Limiting Strategy
5. Security Headers

### Performance Patterns (3)
1. Database Connection Management
2. Asynchronous Email Sending
3. Query Optimization with Indexes

### Logging Patterns (3)
1. Structured Logging
2. Request Correlation
3. Sensitive Data Filtering

### Monitoring Patterns (4)
1. Health Check Implementation
2. Metrics Collection
3. Error Tracking Integration
4. Performance Monitoring

**Total Patterns**: 18 patterns across 5 categories

---

## Pattern Integration

All patterns work together to provide:
- **Resilience**: Graceful error handling and recovery
- **Security**: Defense in depth with multiple layers
- **Performance**: Optimized for < 200ms response times
- **Observability**: Comprehensive logging and monitoring
- **Maintainability**: Consistent patterns across codebase

