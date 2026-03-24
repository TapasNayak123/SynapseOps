# Requirements Document

## Intent Analysis

### User Request Summary
Create a Node.js authentication application with user registration, login, and password reset functionality. The application must be built using TypeScript, Express, and follow MVC pattern with rate limiting. User data will be stored in DynamoDB with Gmail-only email validation (extensible design).

### Request Type
New Feature - Greenfield Project

### Scope Estimate
Multiple Components - Full authentication system with API endpoints, email integration, database layer, and comprehensive testing

### Complexity Estimate
Moderate - Standard authentication patterns with specific technology stack requirements and AWS integration

---

## Functional Requirements

### FR-1: User Registration
**Priority**: High  
**Description**: Users must be able to register with their personal information

**Acceptance Criteria**:
- Accept full name, date of birth, email, and password
- Validate email format (Gmail only initially, extensible for other providers)
- Validate date of birth (user must be 18+ years old)
- Enforce password policy: minimum 8 characters with at least one uppercase, one lowercase, and one number
- Store user data securely in DynamoDB
- Return appropriate success/error responses
- Prevent duplicate email registrations

**Data Fields**:
- Full Name (string, required)
- Date of Birth (date, required, must be 18+ years old)
- Email (string, required, must be @gmail.com, unique)
- Password (string, required, hashed before storage)

### FR-2: User Login
**Priority**: High  
**Description**: Registered users must be able to authenticate and receive access tokens

**Acceptance Criteria**:
- Accept email and password credentials
- Validate credentials against stored user data
- Generate JWT token upon successful authentication
- Return JWT token in response
- Return appropriate error messages for invalid credentials
- Implement rate limiting to prevent brute force attacks

**Authentication Flow**:
- User submits email and password
- System validates credentials
- System generates JWT token with user information
- System returns token to client

### FR-3: Forgot Password
**Priority**: High  
**Description**: Users must be able to request password reset via email

**Acceptance Criteria**:
- Accept email address as input
- Validate that email exists in the system
- Generate time-limited reset token (expires in 1 hour)
- Send password reset email with reset link using Nodemailer with Gmail SMTP
- Reset link must contain the token
- Token must be single-use and expire after 1 hour
- Provide endpoint to verify token and set new password

**Password Reset Flow**:
1. User requests password reset with email
2. System generates unique reset token
3. System sends email with reset link containing token
4. User clicks link and submits new password
5. System validates token (not expired, not used)
6. System updates password and invalidates token

### FR-4: Email Validation
**Priority**: High  
**Description**: System must validate email addresses and enforce Gmail-only policy with extensible design

**Acceptance Criteria**:
- Validate email format using standard email regex
- Check that email domain is @gmail.com
- Design validation logic to easily add other email providers in the future
- Return clear error messages for invalid email formats
- Return clear error messages for non-Gmail addresses

**Extensibility**:
- Email validation logic should be configurable
- Easy to add whitelist of allowed domains
- Centralized validation function

---

## Non-Functional Requirements

### NFR-1: Technology Stack
**Category**: Technology Constraints  
**Description**: Application must use specific technologies

**Requirements**:
- **Language**: TypeScript
- **Runtime**: Node.js (LTS version)
- **Framework**: Express.js
- **Database**: AWS DynamoDB
- **Email Service**: Nodemailer with Gmail SMTP
- **Architecture Pattern**: MVC (Model-View-Controller)
- **Rate Limiting**: express-rate-limit or similar

### NFR-2: Security
**Category**: Security  
**Description**: Application must implement security best practices

**Requirements**:
- Passwords must be hashed using bcrypt before storage
- JWT tokens for stateless authentication
- Rate limiting on all endpoints (100 requests per 15 minutes per IP)
- Input validation on all API endpoints
- Secure password reset token generation (cryptographically random)
- HTTPS enforcement (in production)
- CORS configuration (allow all origins for development)
- Environment variables for sensitive configuration

### NFR-3: Performance
**Category**: Performance  
**Description**: Application must meet performance standards

**Requirements**:
- API response time < 500ms for authentication operations
- Database queries optimized with proper indexing
- JWT token validation should be fast (< 50ms)
- Email sending should be asynchronous (non-blocking)

### NFR-4: Scalability
**Category**: Scalability  
**Description**: Application should be designed for AWS deployment

**Requirements**:
- Stateless authentication (JWT) for horizontal scaling
- DynamoDB for scalable data storage
- Deployment target: AWS (Lambda, ECS, or EC2)
- Environment-based configuration for different stages

### NFR-5: Logging and Monitoring
**Category**: Observability  
**Description**: Application must have comprehensive logging

**Requirements**:
- Structured logging using Winston
- Log levels: error, warn, info, debug
- Log all authentication attempts (success and failure)
- Log all password reset requests
- Log all errors with stack traces
- Production-ready logging format (JSON)

### NFR-6: Testing
**Category**: Quality Assurance  
**Description**: Application must have comprehensive test coverage

**Requirements**:
- Unit tests for business logic (controllers, services, validators)
- Integration tests for API endpoints
- End-to-end tests for complete user flows
- Test framework: Jest or Mocha
- Minimum 80% code coverage target

### NFR-7: API Documentation
**Category**: Documentation  
**Description**: APIs must be well-documented

**Requirements**:
- Swagger/OpenAPI specification
- Postman collection for API testing
- README with setup instructions
- Environment variable documentation

### NFR-8: Configuration Management
**Category**: Configuration  
**Description**: Application configuration must be externalized

**Requirements**:
- Use .env files with dotenv package
- Separate configurations for development, staging, production
- No hardcoded credentials or secrets
- Environment variables for:
  - Database connection details
  - JWT secret
  - Email service credentials
  - Rate limiting configuration
  - CORS origins

---

## API Endpoints

### POST /api/auth/register
**Description**: Register a new user  
**Request Body**:
```json
{
  "fullName": "string",
  "dateOfBirth": "YYYY-MM-DD",
  "email": "string",
  "password": "string"
}
```
**Response** (Success - 201):
```json
{
  "status": "success",
  "message": "User registered successfully",
  "data": {
    "userId": "string",
    "email": "string",
    "fullName": "string"
  }
}
```

### POST /api/auth/login
**Description**: Authenticate user and receive JWT token  
**Request Body**:
```json
{
  "email": "string",
  "password": "string"
}
```
**Response** (Success - 200):
```json
{
  "status": "success",
  "message": "Login successful",
  "data": {
    "token": "string",
    "user": {
      "userId": "string",
      "email": "string",
      "fullName": "string"
    }
  }
}
```

### POST /api/auth/forgot-password
**Description**: Request password reset email  
**Request Body**:
```json
{
  "email": "string"
}
```
**Response** (Success - 200):
```json
{
  "status": "success",
  "message": "Password reset email sent",
  "data": null
}
```

### POST /api/auth/reset-password
**Description**: Reset password using token  
**Request Body**:
```json
{
  "token": "string",
  "newPassword": "string"
}
```
**Response** (Success - 200):
```json
{
  "status": "success",
  "message": "Password reset successfully",
  "data": null
}
```

---

## Data Models

### User Model
```typescript
{
  userId: string (UUID, primary key)
  fullName: string
  dateOfBirth: string (ISO date)
  email: string (unique, indexed)
  password: string (bcrypt hashed)
  createdAt: string (ISO timestamp)
  updatedAt: string (ISO timestamp)
}
```

### Password Reset Token Model
```typescript
{
  tokenId: string (UUID, primary key)
  userId: string (foreign key to User)
  token: string (unique, indexed)
  expiresAt: number (Unix timestamp, TTL attribute)
  used: boolean
  createdAt: string (ISO timestamp)
}
```

**DynamoDB Design Decision**: Single users table with separate password reset tokens table. Reset tokens will use DynamoDB TTL feature to automatically expire after 1 hour.

---

## Technical Constraints

1. **MVC Pattern**: Code must be organized following Model-View-Controller architecture
   - Models: Data structures and database operations
   - Controllers: Request handling and response formatting
   - Services: Business logic layer
   - Routes: API endpoint definitions

2. **TypeScript**: All code must be written in TypeScript with proper type definitions

3. **Rate Limiting**: Must use express-rate-limit or similar middleware

4. **AWS Deployment**: Application designed for AWS infrastructure

5. **Gmail SMTP**: Email service must use Nodemailer with Gmail SMTP configuration

---

## Success Criteria

1. All four API endpoints functional and tested
2. User registration with validation working correctly
3. Login returns valid JWT tokens
4. Password reset email flow complete and functional
5. Gmail-only email validation enforced
6. Rate limiting active on all endpoints
7. Comprehensive test suite passing
8. API documentation (Swagger + Postman) complete
9. Application deployable to AWS
10. Code follows MVC pattern and TypeScript best practices

---

## Out of Scope

1. User profile management (update profile, delete account)
2. Email verification during registration
3. Two-factor authentication (2FA)
4. Social login integration
5. User roles and permissions
6. Account lockout after failed login attempts
7. Password history (prevent reuse of old passwords)
8. Frontend application
9. Admin panel or user management interface
10. Production deployment automation (CI/CD pipelines)
