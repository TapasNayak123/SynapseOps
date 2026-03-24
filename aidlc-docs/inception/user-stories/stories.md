# User Stories

## Registration Journey

### Story US-001: Successful User Registration
**Title**: Register with valid information

**As a** new user (Sarah)  
**I want** to register with my full name, date of birth, email, and password  
**So that** I can create an account and access the service

**Acceptance Criteria**:
- **Given** I am on the registration endpoint
- **When** I provide valid full name, date of birth (18+ years), Gmail address, and strong password
- **Then** my account is created successfully
- **And** my password is hashed before storage
- **And** I receive a 201 status code
- **And** I receive a success response with my user ID, email, and full name
- **And** my data is stored in DynamoDB

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-1

---

### Story US-002: Registration with Invalid Email Format
**Title**: Reject registration with malformed email

**As a** new user (Sarah)  
**I want** to receive clear feedback when my email format is invalid  
**So that** I can correct it and complete registration

**Acceptance Criteria**:
- **Given** I am attempting to register
- **When** I provide an email that doesn't match standard email format (e.g., "notanemail", "user@", "@domain.com")
- **Then** registration fails
- **And** I receive a 400 status code
- **And** I receive an error message: "Invalid email format"
- **And** no data is stored in DynamoDB

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-1, FR-4

---

### Story US-003: Registration with Non-Gmail Email
**Title**: Reject registration with non-Gmail email address

**As a** new user (Sarah)  
**I want** to understand that only Gmail addresses are currently accepted  
**So that** I can use an appropriate email address

**Acceptance Criteria**:
- **Given** I am attempting to register
- **When** I provide a valid email format but non-Gmail domain (e.g., "user@yahoo.com", "user@outlook.com")
- **Then** registration fails
- **And** I receive a 400 status code
- **And** I receive an error message: "Only Gmail addresses are currently supported"
- **And** no data is stored in DynamoDB

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-1, FR-4

---

### Story US-004: Registration with Weak Password
**Title**: Reject registration with password not meeting security requirements

**As a** new user (Sarah)  
**I want** to receive clear feedback about password requirements  
**So that** I can create a secure password

**Acceptance Criteria**:
- **Given** I am attempting to register
- **When** I provide a password that doesn't meet requirements (less than 8 characters, or missing uppercase, or missing lowercase, or missing number)
- **Then** registration fails
- **And** I receive a 400 status code
- **And** I receive an error message: "Password must be at least 8 characters and contain at least one uppercase letter, one lowercase letter, and one number"
- **And** no data is stored in DynamoDB

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-1, NFR-2

---

### Story US-005: Registration with Underage Date of Birth
**Title**: Reject registration for users under 18 years old

**As a** new user (Sarah)  
**I want** to understand age requirements  
**So that** I know if I'm eligible to register

**Acceptance Criteria**:
- **Given** I am attempting to register
- **When** I provide a date of birth that indicates I am under 18 years old
- **Then** registration fails
- **And** I receive a 400 status code
- **And** I receive an error message: "You must be at least 18 years old to register"
- **And** no data is stored in DynamoDB

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-1

---

### Story US-006: Registration with Duplicate Email
**Title**: Prevent duplicate account creation with same email

**As a** new user (Sarah)  
**I want** to be informed if my email is already registered  
**So that** I can log in instead or recover my password

**Acceptance Criteria**:
- **Given** I am attempting to register
- **When** I provide an email address that already exists in the system
- **Then** registration fails
- **And** I receive a 409 status code
- **And** I receive an error message: "An account with this email already exists"
- **And** no duplicate data is stored in DynamoDB

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-1

---

### Story US-007: Registration with Missing Required Fields
**Title**: Reject registration when required fields are missing

**As a** new user (Sarah)  
**I want** to know which fields are required  
**So that** I can provide all necessary information

**Acceptance Criteria**:
- **Given** I am attempting to register
- **When** I omit one or more required fields (fullName, dateOfBirth, email, or password)
- **Then** registration fails
- **And** I receive a 400 status code
- **And** I receive an error message listing the missing fields
- **And** no data is stored in DynamoDB

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-1

---

## Authentication Journey

### Story US-008: Successful User Login
**Title**: Login with correct credentials and receive JWT token

**As an** existing user (Michael)  
**I want** to log in with my email and password  
**So that** I can access my account and receive an authentication token

**Acceptance Criteria**:
- **Given** I have a registered account
- **When** I provide correct email and password
- **Then** authentication succeeds
- **And** I receive a 200 status code
- **And** I receive a JWT token in the response
- **And** I receive my user information (userId, email, fullName)
- **And** the JWT token contains my user ID and email

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-2

---

### Story US-009: Login with Incorrect Password
**Title**: Reject login attempt with wrong password

**As an** existing user (Michael)  
**I want** to receive clear feedback when my password is incorrect  
**So that** I can retry or reset my password

**Acceptance Criteria**:
- **Given** I have a registered account
- **When** I provide correct email but incorrect password
- **Then** authentication fails
- **And** I receive a 401 status code
- **And** I receive an error message: "Invalid email or password"
- **And** no JWT token is generated
- **And** the failed attempt is logged

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-2, NFR-5

---

### Story US-010: Login with Non-Existent Email
**Title**: Reject login attempt for unregistered email

**As an** existing user (Michael)  
**I want** to receive feedback when my email is not found  
**So that** I can register or use the correct email

**Acceptance Criteria**:
- **Given** I am attempting to log in
- **When** I provide an email that doesn't exist in the system
- **Then** authentication fails
- **And** I receive a 401 status code
- **And** I receive an error message: "Invalid email or password"
- **And** no JWT token is generated
- **And** the failed attempt is logged

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-2, NFR-5

---

### Story US-011: Login with Missing Credentials
**Title**: Reject login when email or password is missing

**As an** existing user (Michael)  
**I want** to know which credentials are required  
**So that** I can provide complete information

**Acceptance Criteria**:
- **Given** I am attempting to log in
- **When** I omit email or password
- **Then** authentication fails
- **And** I receive a 400 status code
- **And** I receive an error message indicating which field is missing
- **And** no JWT token is generated

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-2

---

## Password Recovery Journey

### Story US-012: Request Password Reset with Valid Email
**Title**: Initiate password reset for registered email

**As a** forgetful user (Jennifer)  
**I want** to request a password reset  
**So that** I can regain access to my account

**Acceptance Criteria**:
- **Given** I have a registered account
- **When** I provide my registered email address
- **Then** a password reset token is generated
- **And** the token is stored in DynamoDB with 1-hour expiration
- **And** a password reset email is sent to my email address
- **And** I receive a 200 status code
- **And** I receive a success message: "Password reset email sent"
- **And** the email contains a reset link with the token

**Priority**: High  
**Size**: Medium  
**Related Requirement**: FR-3

---

### Story US-013: Request Password Reset with Non-Existent Email
**Title**: Handle password reset request for unregistered email

**As a** forgetful user (Jennifer)  
**I want** to receive feedback when my email is not found  
**So that** I know to register or use the correct email

**Acceptance Criteria**:
- **Given** I am requesting a password reset
- **When** I provide an email that doesn't exist in the system
- **Then** I receive a 200 status code (security: don't reveal if email exists)
- **And** I receive a success message: "Password reset email sent"
- **And** no email is actually sent
- **And** no token is generated
- **And** the attempt is logged for security monitoring

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-3, NFR-2

---

### Story US-014: Receive Password Reset Email
**Title**: Receive email with password reset instructions

**As a** forgetful user (Jennifer)  
**I want** to receive a clear email with reset instructions  
**So that** I can easily reset my password

**Acceptance Criteria**:
- **Given** I requested a password reset with valid email
- **When** the system processes my request
- **Then** I receive an email within 1 minute
- **And** the email contains a reset link with embedded token
- **And** the email explains the link expires in 1 hour
- **And** the email is sent via Nodemailer with Gmail SMTP
- **And** the email has a clear subject line: "Password Reset Request"

**Priority**: High  
**Size**: Medium  
**Related Requirement**: FR-3, NFR-1

---

### Story US-018: Reset Password with Valid Token
**Title**: Successfully reset password using valid token

**As a** forgetful user (Jennifer)  
**I want** to reset my password using the emailed link  
**So that** I can regain access to my account

**Acceptance Criteria**:
- **Given** I have a valid, unexpired reset token
- **When** I provide the token and a new password meeting requirements
- **Then** my password is updated in DynamoDB
- **And** the new password is hashed before storage
- **And** the reset token is marked as used
- **And** I receive a 200 status code
- **And** I receive a success message: "Password reset successfully"
- **And** I can log in with the new password

**Priority**: High  
**Size**: Medium  
**Related Requirement**: FR-3, NFR-2

---

### Story US-019: Reset Password with Expired Token
**Title**: Reject password reset with expired token

**As a** forgetful user (Jennifer)  
**I want** to understand when my reset link has expired  
**So that** I can request a new one

**Acceptance Criteria**:
- **Given** I have a reset token that expired (more than 1 hour old)
- **When** I attempt to reset my password with the expired token
- **Then** the password reset fails
- **And** I receive a 400 status code
- **And** I receive an error message: "Password reset token has expired. Please request a new one"
- **And** my password is not changed
- **And** the token remains marked as expired in DynamoDB

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-3, NFR-2

---

### Story US-020: Reset Password with Already-Used Token
**Title**: Reject password reset with previously used token

**As a** forgetful user (Jennifer)  
**I want** to understand when a reset link has already been used  
**So that** I know my password was already changed

**Acceptance Criteria**:
- **Given** I have a reset token that was already used
- **When** I attempt to reset my password with the used token
- **Then** the password reset fails
- **And** I receive a 400 status code
- **And** I receive an error message: "Password reset token has already been used"
- **And** my password is not changed

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-3, NFR-2

---

### Story US-021: Reset Password with Invalid Token
**Title**: Reject password reset with non-existent or malformed token

**As a** forgetful user (Jennifer)  
**I want** to receive clear feedback when my reset link is invalid  
**So that** I can request a new one

**Acceptance Criteria**:
- **Given** I have an invalid token (doesn't exist in database or malformed)
- **When** I attempt to reset my password
- **Then** the password reset fails
- **And** I receive a 400 status code
- **And** I receive an error message: "Invalid password reset token"
- **And** my password is not changed

**Priority**: High  
**Size**: Small  
**Related Requirement**: FR-3, NFR-2

---

## Cross-Cutting Stories

### Story US-015: Rate Limiting Protection
**Title**: Prevent API abuse through rate limiting

**As an** API consumer (Alex) and existing user (Michael)  
**I want** the API to enforce rate limits  
**So that** my account is protected from brute force attacks

**Acceptance Criteria**:
- **Given** rate limiting is configured for 100 requests per 15 minutes per IP
- **When** a client exceeds the rate limit
- **Then** subsequent requests are rejected
- **And** the client receives a 429 status code
- **And** the client receives an error message: "Too many requests. Please try again later"
- **And** the response includes Retry-After header
- **And** rate limit applies to all endpoints (registration, login, password reset)

**Priority**: High  
**Size**: Medium  
**Related Requirement**: NFR-2

---

### Story US-016: Consistent Success Response Format
**Title**: Return standardized success responses

**As an** API consumer (Alex)  
**I want** all successful API responses to follow the same format  
**So that** I can handle responses consistently in my application

**Acceptance Criteria**:
- **Given** any API endpoint is called successfully
- **When** the operation completes successfully
- **Then** the response follows this structure:
  ```json
  {
    "status": "success",
    "message": "Descriptive success message",
    "data": { /* relevant data or null */ }
  }
  ```
- **And** appropriate HTTP status code is returned (200, 201)

**Priority**: Medium  
**Size**: Small  
**Related Requirement**: NFR-8

---

### Story US-017: Consistent Error Response Format
**Title**: Return standardized error responses

**As an** API consumer (Alex)  
**I want** all error API responses to follow the same format  
**So that** I can handle errors consistently in my application

**Acceptance Criteria**:
- **Given** any API endpoint encounters an error
- **When** the operation fails
- **Then** the response follows this structure:
  ```json
  {
    "status": "error",
    "message": "Descriptive error message",
    "data": null
  }
  ```
- **And** appropriate HTTP status code is returned (400, 401, 409, 429, 500)
- **And** error messages are clear and actionable

**Priority**: Medium  
**Size**: Small  
**Related Requirement**: NFR-8

---

## Story Summary

### Total Stories: 17

### By Priority:
- **High**: 15 stories
- **Medium**: 2 stories

### By Journey:
- **Registration Journey**: 7 stories (US-001 to US-007)
- **Authentication Journey**: 4 stories (US-008 to US-011)
- **Password Recovery Journey**: 6 stories (US-012 to US-014, US-018 to US-021)
- **Cross-Cutting**: 2 stories (US-015 to US-017)

### By Size:
- **Small**: 13 stories
- **Medium**: 4 stories

### INVEST Criteria Verification:
- ✅ **Independent**: Each story can be implemented independently
- ✅ **Negotiable**: Stories focus on outcomes, not implementation details
- ✅ **Valuable**: Each story delivers value to users or API consumers
- ✅ **Estimable**: Stories are clear enough to estimate effort
- ✅ **Small**: Stories are appropriately sized for implementation
- ✅ **Testable**: Each story has clear, testable acceptance criteria
