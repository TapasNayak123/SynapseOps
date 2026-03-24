# Business Logic Model

## Overview
This document defines the detailed business logic workflows and algorithms for the authentication application.

---

## Workflow 1: User Registration

### High-Level Flow
```
Client Request --> Validation --> Email Check --> Hash Password --> Create User --> Response
```

### Detailed Algorithm

**Step 1: Receive Registration Request**
- Input: fullName, dateOfBirth, email, password
- Validate all fields are present
- If any field missing → Return 400 "Missing required fields"

**Step 2: Validate Email Format**
- Check email matches regex: `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`
- If invalid format → Return 400 "Invalid email format"

**Step 3: Validate Email Domain**
- Extract domain from email
- Check domain against whitelist: ['gmail.com']
- If not in whitelist → Return 400 "Only Gmail addresses are currently supported"

**Step 4: Validate Password Strength**
- Check length >= 8 characters
- Check contains at least one uppercase letter (A-Z)
- Check contains at least one lowercase letter (a-z)
- Check contains at least one number (0-9)
- If any check fails → Return 400 with specific password requirement message

**Step 5: Validate Date of Birth**
- Parse dateOfBirth string to Date object
- If invalid date → Return 400 "Invalid date format"
- Calculate age: (today - dateOfBirth) / 365.25 days
- If age < 18 → Return 400 "You must be at least 18 years old to register"

**Step 6: Check Email Uniqueness**
- Query DynamoDB Users table using email-index GSI
- If email exists → Return 409 "An account with this email already exists"

**Step 7: Hash Password**
- Generate salt using bcrypt with cost factor 12
- Hash password with salt: `bcrypt.hash(password, 12)`
- Time complexity: ~300ms per hash

**Step 8: Generate User ID**
- Generate UUID v4: `uuid.v4()`
- Format: "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"

**Step 9: Create User Record**
- Prepare user object:
  ```typescript
  {
    userId: string (UUID),
    fullName: string,
    dateOfBirth: string (YYYY-MM-DD),
    email: string (lowercase),
    password: string (bcrypt hash),
    createdAt: string (ISO 8601),
    updatedAt: string (ISO 8601)
  }
  ```
- Insert into DynamoDB Users table
- If database error → Return 500 "Registration failed"

**Step 10: Log Registration**
- Log successful registration with userId and email
- Do not log password (plain or hashed)

**Step 11: Return Success Response**
- Return 201 Created
- Response body:
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
- Do not include password in response

### Error Handling
- Validation errors: 400 Bad Request
- Duplicate email: 409 Conflict
- Database errors: 500 Internal Server Error
- All errors logged with context

---

## Workflow 2: User Login

### High-Level Flow
```
Client Request --> Validation --> Find User --> Verify Password --> Generate JWT --> Response
```

### Detailed Algorithm

**Step 1: Receive Login Request**
- Input: email, password
- Validate both fields are present
- If any field missing → Return 400 "Email and password are required"

**Step 2: Validate Email Format**
- Check email matches basic format
- If invalid → Return 400 "Invalid email format"

**Step 3: Find User by Email**
- Query DynamoDB Users table using email-index GSI
- Convert email to lowercase before query
- If user not found → Go to Step 6 (security: don't reveal)

**Step 4: Verify Password**
- Use bcrypt.compare(plainPassword, hashedPassword)
- Constant-time comparison for security
- Time complexity: ~300ms per comparison
- If password invalid → Go to Step 6

**Step 5: Generate JWT Token**
- Create payload:
  ```typescript
  {
    userId: string,
    email: string,
    iat: number (issued at timestamp),
    exp: number (expiration timestamp)
  }
  ```
- Set expiration: current time + 1 hour (3600 seconds)
- Sign token with JWT secret using HS256 algorithm
- Token format: "header.payload.signature"

**Step 6: Handle Authentication Failure**
- Log failed attempt with:
  - Timestamp (ISO 8601)
  - Email attempted
  - IP address from request
  - Outcome: "failed"
- Return 401 Unauthorized
- Generic message: "Invalid email or password"
- Do not reveal whether email exists or password is wrong

**Step 7: Log Successful Login**
- Log with:
  - Timestamp
  - UserId
  - Email
  - IP address
  - Outcome: "success"

**Step 8: Return Success Response**
- Return 200 OK
- Response body:
  ```json
  {
    "status": "success",
    "message": "Login successful",
    "data": {
      "token": "JWT string",
      "user": {
        "userId": "string",
        "email": "string",
        "fullName": "string"
      }
    }
  }
  ```

### Security Considerations
- Use constant-time password comparison
- Generic error messages (don't reveal if email exists)
- Log all authentication attempts
- Rate limiting prevents brute force (100 req/15 min)

---

## Workflow 3: Forgot Password Request

### High-Level Flow
```
Client Request --> Find User --> Generate Token --> Store Token --> Send Email --> Response
```

### Detailed Algorithm

**Step 1: Receive Forgot Password Request**
- Input: email
- Validate email field is present
- If missing → Return 400 "Email is required"

**Step 2: Validate Email Format**
- Check email matches basic format
- If invalid → Return 400 "Invalid email format"

**Step 3: Find User by Email**
- Query DynamoDB Users table using email-index GSI
- If user not found → Go to Step 9 (security: don't reveal)

**Step 4: Generate Reset Token**
- Use crypto.randomBytes(32) for cryptographic randomness
- Convert to hexadecimal string
- Result: 64-character hex string
- Entropy: 256 bits

**Step 5: Calculate Expiration Time**
- Current timestamp + 1 hour (3600 seconds)
- Store as Unix timestamp (seconds since epoch)
- DynamoDB TTL will auto-delete after expiration

**Step 6: Generate Token ID**
- Generate UUID v4 for tokenId
- Ensures unique token records

**Step 7: Store Reset Token**
- Prepare token object:
  ```typescript
  {
    tokenId: string (UUID),
    userId: string,
    token: string (64 hex chars),
    expiresAt: number (Unix timestamp),
    used: boolean (false),
    createdAt: string (ISO 8601)
  }
  ```
- Insert into DynamoDB PasswordResetTokens table
- Set TTL attribute to expiresAt for auto-cleanup

**Step 8: Send Reset Email**
- Format reset URL: `${BASE_URL}/reset-password?token=${token}`
- Email subject: "Password Reset Request"
- Email body includes:
  - Reset link with token
  - Expiration notice (1 hour)
  - Security notice (ignore if didn't request)
- Send via Nodemailer with Gmail SMTP
- If email fails → Log error but still return success (security)

**Step 9: Log Password Reset Request**
- Log with:
  - Timestamp
  - Email (if found) or "unknown"
  - IP address
  - Outcome: "requested"

**Step 10: Return Success Response**
- Return 200 OK (even if email not found - security)
- Response body:
  ```json
  {
    "status": "success",
    "message": "Password reset email sent",
    "data": null
  }
  ```

### Security Considerations
- Always return success (don't reveal if email exists)
- Use cryptographically secure random tokens
- Tokens expire after 1 hour
- Log all reset requests
- Email sending is asynchronous (non-blocking)

---

## Workflow 4: Reset Password Execution

### High-Level Flow
```
Client Request --> Validate Token --> Check Expiration --> Check Used --> Update Password --> Mark Used --> Response
```

### Detailed Algorithm

**Step 1: Receive Reset Password Request**
- Input: token, newPassword
- Validate both fields are present
- If any missing → Return 400 "Token and new password are required"

**Step 2: Validate New Password Strength**
- Check length >= 8 characters
- Check contains uppercase, lowercase, number
- If invalid → Return 400 with password requirements

**Step 3: Find Token Record**
- Query DynamoDB PasswordResetTokens table using token-index GSI
- If token not found → Return 400 "Invalid password reset token"

**Step 4: Check Token Expiration**
- Get current Unix timestamp
- Compare with token.expiresAt
- If current time > expiresAt → Return 400 "Password reset token has expired. Please request a new one"

**Step 5: Check Token Used Status**
- Check token.used field
- If used === true → Return 400 "Password reset token has already been used"

**Step 6: Hash New Password**
- Generate salt using bcrypt with cost factor 12
- Hash new password: `bcrypt.hash(newPassword, 12)`
- Time complexity: ~300ms

**Step 7: Update User Password**
- Find user by userId from token
- Update password field with new hash
- Update updatedAt timestamp
- If user not found → Return 404 "User not found"

**Step 8: Mark Token as Used**
- Update token record: set used = true
- Prevents token reuse
- Token will still be auto-deleted by TTL

**Step 9: Log Password Reset**
- Log with:
  - Timestamp
  - UserId
  - IP address
  - Outcome: "password_reset"

**Step 10: Return Success Response**
- Return 200 OK
- Response body:
  ```json
  {
    "status": "success",
    "message": "Password reset successfully",
    "data": null
  }
  ```

### Security Considerations
- Validate token before any operations
- Check expiration and used status
- Hash new password with same strength as registration
- Mark token as used immediately
- Log all password resets for audit

---

## Algorithm: Age Calculation

### Purpose
Calculate age from date of birth to validate 18+ requirement

### Algorithm
```
Input: dateOfBirth (string in YYYY-MM-DD format)
Output: age (number in years)

1. Parse dateOfBirth to Date object
2. Get current date
3. Calculate difference in milliseconds: current - dateOfBirth
4. Convert to years: milliseconds / (1000 * 60 * 60 * 24 * 365.25)
5. Floor to integer: Math.floor(years)
6. Return age
```

### Edge Cases
- Leap years: Use 365.25 days per year
- Today is birthday: Age increments today
- Invalid dates: Throw error before calculation

---

## Algorithm: Email Domain Extraction

### Purpose
Extract domain from email for whitelist validation

### Algorithm
```
Input: email (string)
Output: domain (string)

1. Split email by '@' character
2. If split result length !== 2 → Invalid format
3. Take second part (after @)
4. Convert to lowercase
5. Return domain
```

### Examples
- "user@Gmail.com" → "gmail.com"
- "test@example.co.uk" → "example.co.uk"
- "invalid" → Error

---

## Algorithm: JWT Token Verification

### Purpose
Verify JWT token validity for protected routes

### Algorithm
```
Input: token (string)
Output: payload (object) or error

1. Extract token from Authorization header: "Bearer <token>"
2. If no token → Return 401 "No token provided"
3. Verify signature using JWT secret
4. If signature invalid → Return 401 "Invalid token"
5. Check expiration (exp claim)
6. If expired → Return 401 "Token expired"
7. Decode payload
8. Return payload with userId and email
```

### Token Structure
```
Header: { alg: "HS256", typ: "JWT" }
Payload: { userId, email, iat, exp }
Signature: HMACSHA256(base64(header) + "." + base64(payload), secret)
```

---

## Performance Considerations

### Password Hashing
- Bcrypt cost factor 12: ~300ms per operation
- Acceptable for authentication (not frequent)
- Prevents brute force attacks
- CPU-intensive, use async operations

### Database Queries
- Use GSI for email lookups (efficient)
- Primary key lookups for userId (fastest)
- Token lookups use GSI (efficient)
- DynamoDB auto-scales with load

### Email Sending
- Asynchronous operation (non-blocking)
- Timeout: 30 seconds
- Retry logic for transient failures
- Log failures but don't block user

---

## Transaction Boundaries

### Registration Transaction
- Atomic: User creation succeeds or fails completely
- No partial user records
- Rollback not needed (single DynamoDB Put operation)

### Password Reset Transaction
- Two operations: Update password + Mark token used
- Not atomic across operations
- Acceptable: If mark-used fails, token expires anyway
- Log any inconsistencies

---

## Concurrency Considerations

### Duplicate Email Registration
- Race condition: Two simultaneous registrations with same email
- Mitigation: DynamoDB conditional Put with email uniqueness
- One succeeds, one fails with 409 Conflict

### Token Reuse
- Race condition: Multiple password resets with same token
- Mitigation: Check used flag before update
- First succeeds, subsequent fail with "already used"

### Password Reset During Login
- Scenario: User logs in while password reset in progress
- Behavior: Old password works until reset completes
- Acceptable: Reset invalidates old password immediately
