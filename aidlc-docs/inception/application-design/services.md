# Service Layer Design

## Service Layer Purpose

The service layer sits between controllers and models, implementing business logic and orchestrating operations across multiple models and external services.

## Service Architecture Principles

1. **Single Responsibility**: Each service handles one domain area
2. **Business Logic Encapsulation**: All business rules in services, not controllers
3. **Transaction Management**: Services coordinate multi-step operations
4. **Error Handling**: Services throw domain-specific errors
5. **Testability**: Services are easily unit testable

---

## Service: UserService

### Responsibility
Manage all user-related business operations including registration, authentication, and password management.

### Dependencies
- UserModel (data access)
- bcrypt (password hashing)
- Logger (logging)

### Service Methods

#### createUser(userData: CreateUserDTO): Promise<User>

**Orchestration Flow**:
1. Check if email already exists (UserModel.emailExists)
2. If exists, throw ConflictError
3. Hash password using bcrypt (10 salt rounds)
4. Generate unique userId (UUID v4)
5. Create user record (UserModel.create)
6. Log successful registration
7. Return user object (without password)

**Business Rules**:
- Email must be unique
- Password must be hashed before storage
- Never return password in response
- Log all registration attempts

**Error Scenarios**:
- Email already exists → ConflictError (409)
- Database error → DatabaseError (500)

---

#### authenticateUser(email: string, password: string): Promise<User>

**Orchestration Flow**:
1. Find user by email (UserModel.findByEmail)
2. If not found, throw AuthenticationError
3. Compare password with stored hash (bcrypt.compare)
4. If password invalid, throw AuthenticationError
5. Log successful login
6. Return user object (without password)

**Business Rules**:
- Use constant-time comparison for security
- Log all authentication attempts (success and failure)
- Never reveal whether email exists or password is wrong
- Return generic "Invalid email or password" message

**Error Scenarios**:
- User not found → AuthenticationError (401)
- Password mismatch → AuthenticationError (401)
- Database error → DatabaseError (500)

---

#### getUserByEmail(email: string): Promise<User | null>

**Orchestration Flow**:
1. Query user by email (UserModel.findByEmail)
2. Return user or null

**Business Rules**:
- Return null if not found (don't throw error)
- Include password hash in result (for internal use only)

---

#### updateUserPassword(userId: string, newPassword: string): Promise<void>

**Orchestration Flow**:
1. Hash new password using bcrypt (10 salt rounds)
2. Update user password (UserModel.updatePassword)
3. Log password change
4. Return void

**Business Rules**:
- Always hash password before storage
- Log password changes for security audit
- Update updatedAt timestamp

**Error Scenarios**:
- User not found → NotFoundError (404)
- Database error → DatabaseError (500)

---

## Service: EmailService

### Responsibility
Handle all email sending operations, particularly password reset emails.

### Dependencies
- Nodemailer (email sending)
- Config (SMTP configuration)
- Logger (logging)

### Service Methods

#### sendPasswordResetEmail(email: string, resetToken: string): Promise<void>

**Orchestration Flow**:
1. Format email content (formatResetEmailContent)
2. Create reset link with token
3. Configure Nodemailer transporter (Gmail SMTP)
4. Send email using transporter
5. Log email sent
6. Return void

**Business Rules**:
- Use Gmail SMTP with app-specific password
- Include clear instructions in email
- Mention 1-hour expiration
- Use professional email template
- Handle email sending errors gracefully

**Error Scenarios**:
- SMTP connection error → EmailError (500)
- Invalid email address → EmailError (500)
- Rate limit exceeded → EmailError (429)

---

#### formatResetEmailContent(resetToken: string): EmailContent

**Orchestration Flow**:
1. Create reset URL with token
2. Format HTML email body
3. Format plain text email body
4. Return EmailContent object

**Business Rules**:
- Include both HTML and plain text versions
- Make reset link prominent
- Explain expiration clearly
- Include security notice
- Professional formatting

**Email Template Structure**:
```
Subject: Password Reset Request

Body:
- Greeting
- Reset link (prominent)
- Expiration notice (1 hour)
- Security notice (didn't request? ignore)
- Support contact
```

---

## Service: TokenService

### Responsibility
Manage JWT authentication tokens and password reset tokens.

### Dependencies
- jsonwebtoken (JWT operations)
- crypto (secure random generation)
- PasswordResetTokenModel (data access)
- Config (JWT secret, expiration)
- Logger (logging)

### Service Methods

#### generateJWT(userId: string, email: string): string

**Orchestration Flow**:
1. Create JWT payload with userId and email
2. Sign token with secret from config
3. Set expiration (from config, default 24 hours)
4. Return signed token

**Business Rules**:
- Include minimal data in payload (userId, email)
- Use strong secret from environment
- Set reasonable expiration
- Use HS256 algorithm

---

#### verifyJWT(token: string): JWTPayload

**Orchestration Flow**:
1. Verify token signature
2. Check expiration
3. Decode payload
4. Return payload

**Business Rules**:
- Throw error if signature invalid
- Throw error if token expired
- Validate payload structure

**Error Scenarios**:
- Invalid signature → AuthenticationError (401)
- Token expired → AuthenticationError (401)
- Malformed token → AuthenticationError (401)

---

#### generatePasswordResetToken(): string

**Orchestration Flow**:
1. Generate 32 random bytes using crypto
2. Convert to hex string
3. Return token

**Business Rules**:
- Use cryptographically secure random generation
- Generate sufficient entropy (32 bytes = 256 bits)
- Return URL-safe string

---

#### createPasswordResetToken(userId: string, token: string): Promise<PasswordResetToken>

**Orchestration Flow**:
1. Generate unique tokenId (UUID v4)
2. Calculate expiration time (current time + 1 hour)
3. Create token record (PasswordResetTokenModel.create)
4. Log token creation
5. Return token object

**Business Rules**:
- Set expiration to exactly 1 hour from creation
- Use DynamoDB TTL for automatic cleanup
- Initialize used flag to false
- Log token creation for security audit

---

#### validatePasswordResetToken(token: string): Promise<PasswordResetToken>

**Orchestration Flow**:
1. Find token by value (PasswordResetTokenModel.findByToken)
2. If not found, throw InvalidTokenError
3. Check if token expired (compare expiresAt with current time)
4. If expired, throw ExpiredTokenError
5. Check if token already used
6. If used, throw UsedTokenError
7. Return valid token object

**Business Rules**:
- Check expiration against current timestamp
- Prevent reuse of tokens
- Provide specific error messages
- Log validation attempts

**Error Scenarios**:
- Token not found → InvalidTokenError (400)
- Token expired → ExpiredTokenError (400)
- Token already used → UsedTokenError (400)

---

#### markTokenAsUsed(tokenId: string): Promise<void>

**Orchestration Flow**:
1. Update token used flag (PasswordResetTokenModel.markAsUsed)
2. Log token usage
3. Return void

**Business Rules**:
- Mark token as used immediately after password reset
- Prevent token reuse
- Log for security audit

---

## Service Interaction Patterns

### Registration Flow
```
Controller → UserService.createUser
                ↓
            UserModel.emailExists
                ↓
            bcrypt.hash
                ↓
            UserModel.create
                ↓
            Logger.info
```

### Login Flow
```
Controller → UserService.authenticateUser
                ↓
            UserModel.findByEmail
                ↓
            bcrypt.compare
                ↓
            TokenService.generateJWT
                ↓
            Logger.info
```

### Forgot Password Flow
```
Controller → UserService.getUserByEmail
                ↓
            TokenService.generatePasswordResetToken
                ↓
            TokenService.createPasswordResetToken
                ↓
            EmailService.sendPasswordResetEmail
                ↓
            Logger.info
```

### Reset Password Flow
```
Controller → TokenService.validatePasswordResetToken
                ↓
            UserService.updateUserPassword
                ↓
            TokenService.markTokenAsUsed
                ↓
            Logger.info
```

---

## Service Error Handling

### Error Types
Services throw domain-specific errors that controllers catch and convert to HTTP responses:

- **ConflictError**: Resource already exists (409)
- **AuthenticationError**: Invalid credentials (401)
- **NotFoundError**: Resource not found (404)
- **InvalidTokenError**: Token invalid (400)
- **ExpiredTokenError**: Token expired (400)
- **UsedTokenError**: Token already used (400)
- **EmailError**: Email sending failed (500)
- **DatabaseError**: Database operation failed (500)

### Error Handling Pattern
```typescript
try {
  // Service operation
} catch (error) {
  logger.error('Operation failed', { error, context });
  throw new DomainSpecificError('User-friendly message');
}
```

---

## Service Testing Strategy

### Unit Testing
- Mock all dependencies (models, external services)
- Test business logic in isolation
- Test error scenarios
- Test edge cases

### Integration Testing
- Test service interactions with real database
- Test email sending with test SMTP server
- Test token generation and validation
- Test complete workflows

---

## Service Performance Considerations

### Caching Opportunities
- User data (after authentication)
- JWT verification results
- Email templates

### Async Operations
- Email sending (non-blocking)
- Password hashing (CPU-intensive)
- Database queries (I/O-bound)

### Optimization Strategies
- Use bcrypt with appropriate cost factor (10 rounds)
- Implement connection pooling for DynamoDB
- Use batch operations where possible
- Implement retry logic for transient failures

---

## Service Security Considerations

### Password Security
- Use bcrypt with salt rounds ≥ 10
- Never log passwords (plain or hashed)
- Use constant-time comparison
- Enforce password complexity

### Token Security
- Use cryptographically secure random generation
- Set appropriate token expiration
- Validate tokens on every use
- Prevent token reuse

### Email Security
- Use app-specific passwords for Gmail
- Validate email addresses
- Rate limit email sending
- Log all email operations

### Logging Security
- Log authentication attempts
- Log password changes
- Log token operations
- Never log sensitive data (passwords, tokens)
