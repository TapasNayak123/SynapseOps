# Business Rules

## Overview
This document defines all business rules and validation logic for the authentication application.

---

## BR-001: Email Validation Rules

### BR-001.1: Email Format
**Rule**: Email must match standard email format

**Validation**:
- Regex: `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`
- Must contain exactly one @ symbol
- Must have characters before and after @
- Must have domain with at least one dot

**Error Message**: "Invalid email format"

**Examples**:
- ✅ Valid: "user@gmail.com", "test.user@example.co.uk"
- ❌ Invalid: "notanemail", "user@", "@domain.com", "user @gmail.com"

---

### BR-001.2: Email Domain Whitelist
**Rule**: Email domain must be in approved whitelist

**Whitelist**: ['gmail.com']

**Validation**:
- Extract domain from email (part after @)
- Convert domain to lowercase
- Check if domain exists in whitelist array

**Error Message**: "Only Gmail addresses are currently supported"

**Extensibility**: Whitelist is hardcoded array for easy modification

**Examples**:
- ✅ Valid: "user@gmail.com", "USER@Gmail.com" (case-insensitive)
- ❌ Invalid: "user@yahoo.com", "user@outlook.com", "user@example.com"

---

### BR-001.3: Email Uniqueness
**Rule**: Email must be unique across all users

**Validation**:
- Query Users table using email-index GSI
- Email comparison is case-insensitive (store lowercase)

**Error Message**: "An account with this email already exists"

**HTTP Status**: 409 Conflict

---

## BR-002: Password Validation Rules

### BR-002.1: Password Length
**Rule**: Password must be at least 8 characters long

**Validation**: `password.length >= 8`

**Error Message**: "Password must be at least 8 characters"

---

### BR-002.2: Password Uppercase Requirement
**Rule**: Password must contain at least one uppercase letter

**Validation**: `/[A-Z]/.test(password)`

**Error Message**: "Password must contain at least one uppercase letter"

---

### BR-002.3: Password Lowercase Requirement
**Rule**: Password must contain at least one lowercase letter

**Validation**: `/[a-z]/.test(password)`

**Error Message**: "Password must contain at least one lowercase letter"

---

### BR-002.4: Password Number Requirement
**Rule**: Password must contain at least one number

**Validation**: `/[0-9]/.test(password)`

**Error Message**: "Password must contain at least one number"

---

### BR-002.5: Combined Password Error Message
**Rule**: When password fails validation, provide complete requirements

**Error Message**: "Password must be at least 8 characters and contain at least one uppercase letter, one lowercase letter, and one number"

**Examples**:
- ✅ Valid: "Password1", "MyP@ssw0rd", "Secure123"
- ❌ Invalid: "pass" (too short), "password" (no uppercase/number), "PASSWORD1" (no lowercase)

---

## BR-003: Date of Birth Validation Rules

### BR-003.1: Date Format
**Rule**: Date of birth must be valid date in YYYY-MM-DD format

**Validation**:
- Parse string to Date object
- Check if valid date (not NaN)
- Check format matches YYYY-MM-DD

**Error Message**: "Invalid date format. Use YYYY-MM-DD"

---

### BR-003.2: Minimum Age Requirement
**Rule**: User must be at least 18 years old

**Validation**:
- Calculate age: (current date - date of birth) / 365.25 days
- Floor to integer
- Check age >= 18

**Error Message**: "You must be at least 18 years old to register"

**Examples**:
- ✅ Valid: Born on or before 2008-03-09 (as of 2026-03-09)
- ❌ Invalid: Born after 2008-03-09

---

### BR-003.3: Future Date Restriction
**Rule**: Date of birth cannot be in the future

**Validation**: `dateOfBirth <= currentDate`

**Error Message**: "Date of birth cannot be in the future"

---

## BR-004: Full Name Validation Rules

### BR-004.1: Full Name Required
**Rule**: Full name must be provided

**Validation**: `fullName !== null && fullName !== undefined && fullName.trim() !== ""`

**Error Message**: "Full name is required"

---

### BR-004.2: Full Name Minimum Length
**Rule**: Full name must be at least 2 characters

**Validation**: `fullName.trim().length >= 2`

**Error Message**: "Full name must be at least 2 characters"

**Rationale**: Accommodate short names while preventing single-character entries

---

## BR-005: Authentication Rules

### BR-005.1: Credential Verification
**Rule**: Both email and password must match stored credentials

**Validation**:
- Find user by email (case-insensitive)
- Compare password using bcrypt.compare()
- Both must succeed for authentication

**Error Message**: "Invalid email or password" (generic for security)

**Security**: Never reveal whether email exists or password is wrong

---

### BR-005.2: JWT Token Expiration
**Rule**: JWT tokens expire after 1 hour

**Validation**:
- Set exp claim: current timestamp + 3600 seconds
- Verify exp claim on every request
- Reject expired tokens

**Error Message**: "Token expired"

**Rationale**: High security with frequent re-authentication

---

### BR-005.3: JWT Token Structure
**Rule**: JWT must contain required claims

**Required Claims**:
- userId: string
- email: string
- iat: number (issued at)
- exp: number (expiration)

**Validation**: Verify all claims present when decoding token

---

## BR-006: Password Reset Token Rules

### BR-006.1: Token Generation
**Rule**: Reset tokens must be cryptographically secure

**Implementation**:
- Use crypto.randomBytes(32)
- Convert to hexadecimal
- Result: 64-character string
- Entropy: 256 bits

**Rationale**: Prevent token guessing attacks

---

### BR-006.2: Token Expiration
**Rule**: Reset tokens expire after 1 hour

**Validation**:
- Store expiresAt as Unix timestamp
- Check current time <= expiresAt
- Reject expired tokens

**Error Message**: "Password reset token has expired. Please request a new one"

---

### BR-006.3: Single-Use Token
**Rule**: Reset tokens can only be used once

**Validation**:
- Check used flag before allowing reset
- Set used = true after successful reset
- Reject already-used tokens

**Error Message**: "Password reset token has already been used"

---

### BR-006.4: Token Validity
**Rule**: Token must exist in database

**Validation**: Query PasswordResetTokens table by token value

**Error Message**: "Invalid password reset token"

---

## BR-007: Rate Limiting Rules

### BR-007.1: Global Rate Limit
**Rule**: Maximum 100 requests per 15 minutes per IP address

**Scope**: All API endpoints

**Implementation**: express-rate-limit middleware

**Response**: 429 Too Many Requests

**Error Message**: "Too many requests. Please try again later"

**Headers**: Include Retry-After header with seconds until reset

---

## BR-008: Response Format Rules

### BR-008.1: Success Response Format
**Rule**: All successful responses follow standard format

**Structure**:
```json
{
  "status": "success",
  "message": "Descriptive success message",
  "data": { /* relevant data or null */ }
}
```

**HTTP Status Codes**:
- 200: Success (login, password reset)
- 201: Created (registration)

---

### BR-008.2: Error Response Format
**Rule**: All error responses follow standard format

**Structure**:
```json
{
  "status": "error",
  "message": "Descriptive error message",
  "data": null
}
```

**HTTP Status Codes**:
- 400: Bad Request (validation errors)
- 401: Unauthorized (authentication failures)
- 404: Not Found (resource not found)
- 409: Conflict (duplicate email)
- 429: Too Many Requests (rate limit)
- 500: Internal Server Error (unexpected errors)

---

## BR-009: Security Rules

### BR-009.1: Password Storage
**Rule**: Passwords must never be stored in plain text

**Implementation**:
- Hash with bcrypt
- Cost factor: 12 rounds
- Salt automatically generated by bcrypt

**Validation**: Never store or log plain text passwords

---

### BR-009.2: Password Comparison
**Rule**: Password verification must use constant-time comparison

**Implementation**: Use bcrypt.compare() (built-in constant-time)

**Rationale**: Prevent timing attacks

---

### BR-009.3: Error Message Security
**Rule**: Error messages must not reveal sensitive information

**Examples**:
- ✅ "Invalid email or password" (generic)
- ❌ "Email not found" (reveals email existence)
- ❌ "Password incorrect" (reveals email exists)

**Rationale**: Prevent user enumeration attacks

---

### BR-009.4: Logging Security
**Rule**: Never log sensitive data

**Prohibited**:
- Plain text passwords
- Password hashes
- JWT tokens
- Reset tokens

**Allowed**:
- Email addresses
- User IDs
- IP addresses
- Timestamps
- Outcomes (success/failure)

---

## BR-010: Data Integrity Rules

### BR-010.1: Email Normalization
**Rule**: Store emails in lowercase for consistency

**Implementation**: Convert to lowercase before storage and queries

**Rationale**: Ensure case-insensitive email matching

---

### BR-010.2: Timestamp Format
**Rule**: All timestamps stored in ISO 8601 format

**Format**: "YYYY-MM-DDTHH:mm:ss.sssZ"

**Fields**: createdAt, updatedAt

**Example**: "2026-03-09T12:34:56.789Z"

---

### BR-010.3: UUID Format
**Rule**: All IDs use UUID v4 format

**Format**: "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"

**Fields**: userId, tokenId

**Rationale**: Globally unique, non-sequential, secure

---

## BR-011: Email Content Rules

### BR-011.1: Password Reset Email Subject
**Rule**: Subject line must be clear and consistent

**Subject**: "Password Reset Request"

---

### BR-011.2: Password Reset Email Content
**Rule**: Email must include required information

**Required Elements**:
- Reset link with token
- Expiration notice (1 hour)
- Security notice (ignore if didn't request)
- Clear call-to-action button/link

**Format**: Both HTML and plain text versions

---

### BR-011.3: Email Sending Behavior
**Rule**: Always return success for forgot password, even if email not found

**Rationale**: Security - don't reveal if email exists

**Implementation**: Send email only if user found, but always return 200 OK

---

## BR-012: Validation Order Rules

### BR-012.1: Registration Validation Sequence
**Rule**: Validate in this order to provide best user experience

**Sequence**:
1. Required fields present
2. Email format
3. Email domain
4. Password strength
5. Date of birth format
6. Age requirement
7. Email uniqueness (last, as it requires database query)

**Rationale**: Fast validations first, expensive operations last

---

### BR-012.2: Login Validation Sequence
**Rule**: Validate in this order

**Sequence**:
1. Required fields present
2. Email format
3. User exists (database query)
4. Password matches (expensive bcrypt operation)

---

## BR-013: Concurrency Rules

### BR-013.1: Duplicate Registration Prevention
**Rule**: Prevent simultaneous registrations with same email

**Implementation**: Use DynamoDB conditional Put with email uniqueness constraint

**Behavior**: First request succeeds, second fails with 409 Conflict

---

### BR-013.2: Token Reuse Prevention
**Rule**: Prevent simultaneous use of same reset token

**Implementation**: Check and set used flag atomically

**Behavior**: First request succeeds, subsequent fail with "already used"

---

## Business Rule Summary

**Total Rules**: 35 business rules across 13 categories

**By Category**:
- Email Validation: 3 rules
- Password Validation: 5 rules
- Date of Birth Validation: 3 rules
- Full Name Validation: 2 rules
- Authentication: 3 rules
- Password Reset Tokens: 4 rules
- Rate Limiting: 1 rule
- Response Format: 2 rules
- Security: 4 rules
- Data Integrity: 3 rules
- Email Content: 3 rules
- Validation Order: 2 rules
- Concurrency: 2 rules

**Compliance**:
- ✅ All functional requirements covered
- ✅ All security requirements addressed
- ✅ All user stories supported
- ✅ All error scenarios handled
