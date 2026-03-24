# Component Methods

## Controllers

### AuthController

#### register(req: Request, res: Response, next: NextFunction): Promise<void>
**Purpose**: Handle user registration requests

**Parameters**:
- req.body.fullName: string
- req.body.dateOfBirth: string (YYYY-MM-DD)
- req.body.email: string
- req.body.password: string

**Returns**: HTTP 201 with user data or HTTP 400/409 with error

**Business Rules**: Detailed in Functional Design stage

---

#### login(req: Request, res: Response, next: NextFunction): Promise<void>
**Purpose**: Handle user login requests

**Parameters**:
- req.body.email: string
- req.body.password: string

**Returns**: HTTP 200 with JWT token and user data or HTTP 401 with error

**Business Rules**: Detailed in Functional Design stage

---

#### forgotPassword(req: Request, res: Response, next: NextFunction): Promise<void>
**Purpose**: Handle password reset requests

**Parameters**:
- req.body.email: string

**Returns**: HTTP 200 with success message

**Business Rules**: Detailed in Functional Design stage

---

#### resetPassword(req: Request, res: Response, next: NextFunction): Promise<void>
**Purpose**: Handle password reset with token

**Parameters**:
- req.body.token: string
- req.body.newPassword: string

**Returns**: HTTP 200 with success message or HTTP 400 with error

**Business Rules**: Detailed in Functional Design stage

---

## Services

### UserService

#### createUser(userData: CreateUserDTO): Promise<User>
**Purpose**: Create a new user account

**Parameters**:
- userData.fullName: string
- userData.dateOfBirth: string
- userData.email: string
- userData.password: string (plain text)

**Returns**: Created user object (without password)

**Business Rules**: Hash password, generate userId, validate uniqueness

---

#### authenticateUser(email: string, password: string): Promise<User>
**Purpose**: Authenticate user credentials

**Parameters**:
- email: string
- password: string (plain text)

**Returns**: User object if credentials valid

**Throws**: Error if credentials invalid

**Business Rules**: Verify password hash, return user data

---

#### getUserByEmail(email: string): Promise<User | null>
**Purpose**: Retrieve user by email address

**Parameters**:
- email: string

**Returns**: User object or null if not found

---

#### updateUserPassword(userId: string, newPassword: string): Promise<void>
**Purpose**: Update user's password

**Parameters**:
- userId: string
- newPassword: string (plain text)

**Returns**: void

**Business Rules**: Hash new password before storage

---

### EmailService

#### sendPasswordResetEmail(email: string, resetToken: string): Promise<void>
**Purpose**: Send password reset email to user

**Parameters**:
- email: string
- resetToken: string

**Returns**: void

**Throws**: Error if email sending fails

**Business Rules**: Format email with reset link, use Nodemailer with Gmail SMTP

---

#### formatResetEmailContent(resetToken: string): EmailContent
**Purpose**: Format password reset email content

**Parameters**:
- resetToken: string

**Returns**: EmailContent object with subject, html, and text

**Business Rules**: Include reset link with token, explain expiration

---

### TokenService

#### generateJWT(userId: string, email: string): string
**Purpose**: Generate JWT token for authenticated user

**Parameters**:
- userId: string
- email: string

**Returns**: JWT token string

**Business Rules**: Include userId and email in payload, set expiration

---

#### verifyJWT(token: string): JWTPayload
**Purpose**: Verify and decode JWT token

**Parameters**:
- token: string

**Returns**: Decoded JWT payload

**Throws**: Error if token invalid or expired

---

#### generatePasswordResetToken(): string
**Purpose**: Generate cryptographically secure reset token

**Parameters**: None

**Returns**: Random token string

**Business Rules**: Use crypto.randomBytes for security

---

#### createPasswordResetToken(userId: string, token: string): Promise<PasswordResetToken>
**Purpose**: Store password reset token in database

**Parameters**:
- userId: string
- token: string

**Returns**: Created token object

**Business Rules**: Set expiration to 1 hour from creation

---

#### validatePasswordResetToken(token: string): Promise<PasswordResetToken>
**Purpose**: Validate password reset token

**Parameters**:
- token: string

**Returns**: Token object if valid

**Throws**: Error if token invalid, expired, or already used

**Business Rules**: Check expiration, check used status

---

#### markTokenAsUsed(tokenId: string): Promise<void>
**Purpose**: Mark password reset token as used

**Parameters**:
- tokenId: string

**Returns**: void

**Business Rules**: Update used flag in database

---

## Models

### UserModel

#### create(user: UserData): Promise<User>
**Purpose**: Insert new user into DynamoDB

**Parameters**:
- user: UserData object

**Returns**: Created user object

**Business Rules**: Generate userId, set timestamps

---

#### findByEmail(email: string): Promise<User | null>
**Purpose**: Query user by email using GSI

**Parameters**:
- email: string

**Returns**: User object or null

**Business Rules**: Use email-index GSI for efficient lookup

---

#### findById(userId: string): Promise<User | null>
**Purpose**: Get user by primary key

**Parameters**:
- userId: string

**Returns**: User object or null

---

#### updatePassword(userId: string, hashedPassword: string): Promise<void>
**Purpose**: Update user's password in database

**Parameters**:
- userId: string
- hashedPassword: string

**Returns**: void

**Business Rules**: Update password and updatedAt timestamp

---

#### emailExists(email: string): Promise<boolean>
**Purpose**: Check if email already registered

**Parameters**:
- email: string

**Returns**: true if email exists, false otherwise

**Business Rules**: Use GSI query for efficient check

---

### PasswordResetTokenModel

#### create(tokenData: TokenData): Promise<PasswordResetToken>
**Purpose**: Insert password reset token into DynamoDB

**Parameters**:
- tokenData: TokenData object

**Returns**: Created token object

**Business Rules**: Generate tokenId, set TTL attribute

---

#### findByToken(token: string): Promise<PasswordResetToken | null>
**Purpose**: Query token by token value using GSI

**Parameters**:
- token: string

**Returns**: Token object or null

**Business Rules**: Use token-index GSI for efficient lookup

---

#### markAsUsed(tokenId: string): Promise<void>
**Purpose**: Update token used status

**Parameters**:
- tokenId: string

**Returns**: void

**Business Rules**: Set used flag to true

---

## Middleware

### ValidationMiddleware

#### validateRegistration(req: Request, res: Response, next: NextFunction): void
**Purpose**: Validate registration request data

**Validates**:
- fullName: required, string, min 2 characters
- dateOfBirth: required, valid date, 18+ years old
- email: required, valid format, Gmail domain
- password: required, min 8 chars, complexity requirements

**Returns**: Calls next() if valid, sends 400 error if invalid

---

#### validateLogin(req: Request, res: Response, next: NextFunction): void
**Purpose**: Validate login request data

**Validates**:
- email: required, valid format
- password: required

**Returns**: Calls next() if valid, sends 400 error if invalid

---

#### validateForgotPassword(req: Request, res: Response, next: NextFunction): void
**Purpose**: Validate forgot password request data

**Validates**:
- email: required, valid format

**Returns**: Calls next() if valid, sends 400 error if invalid

---

#### validateResetPassword(req: Request, res: Response, next: NextFunction): void
**Purpose**: Validate reset password request data

**Validates**:
- token: required, string
- newPassword: required, min 8 chars, complexity requirements

**Returns**: Calls next() if valid, sends 400 error if invalid

---

### AuthMiddleware

#### authenticate(req: Request, res: Response, next: NextFunction): void
**Purpose**: Verify JWT token and attach user to request

**Process**:
1. Extract token from Authorization header
2. Verify token using TokenService
3. Attach user data to req.user
4. Call next()

**Returns**: Calls next() if authenticated, sends 401 error if not

---

### RateLimitMiddleware

#### rateLimiter: RateLimitRequestHandler
**Purpose**: Express-rate-limit middleware instance

**Configuration**:
- windowMs: 15 minutes
- max: 100 requests
- message: "Too many requests. Please try again later"
- standardHeaders: true
- legacyHeaders: false

---

### ErrorHandlerMiddleware

#### errorHandler(err: Error, req: Request, res: Response, next: NextFunction): void
**Purpose**: Centralized error handling

**Process**:
1. Log error with stack trace
2. Determine error type and status code
3. Format error response
4. Send response to client

**Error Types Handled**:
- ValidationError: 400
- AuthenticationError: 401
- NotFoundError: 404
- ConflictError: 409
- RateLimitError: 429
- DatabaseError: 500
- Generic Error: 500

---

## Utilities

### Logger

#### error(message: string, meta?: any): void
**Purpose**: Log error level messages

---

#### warn(message: string, meta?: any): void
**Purpose**: Log warning level messages

---

#### info(message: string, meta?: any): void
**Purpose**: Log info level messages

---

#### debug(message: string, meta?: any): void
**Purpose**: Log debug level messages

---

### ResponseFormatter

#### success(message: string, data?: any): ResponseObject
**Purpose**: Format success response

**Returns**:
```typescript
{
  status: "success",
  message: string,
  data: any | null
}
```

---

#### error(message: string): ResponseObject
**Purpose**: Format error response

**Returns**:
```typescript
{
  status: "error",
  message: string,
  data: null
}
```

---

### EmailValidator

#### isValidEmail(email: string): boolean
**Purpose**: Validate email format

**Returns**: true if valid format, false otherwise

---

#### isGmailAddress(email: string): boolean
**Purpose**: Check if email is Gmail address

**Returns**: true if @gmail.com, false otherwise

---

#### validateEmailDomain(email: string, allowedDomains: string[]): boolean
**Purpose**: Check email against whitelist of domains

**Returns**: true if domain allowed, false otherwise

**Note**: Extensible design for adding more domains

---

### PasswordValidator

#### validatePassword(password: string): ValidationResult
**Purpose**: Validate password strength

**Returns**: 
```typescript
{
  isValid: boolean,
  errors: string[]
}
```

**Checks**:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number

---

### DateValidator

#### isValidDate(dateString: string): boolean
**Purpose**: Validate date format

**Returns**: true if valid date, false otherwise

---

#### calculateAge(dateOfBirth: string): number
**Purpose**: Calculate age from date of birth

**Returns**: Age in years

---

#### isMinimumAge(dateOfBirth: string, minimumAge: number): boolean
**Purpose**: Check if date of birth meets minimum age

**Returns**: true if meets minimum age, false otherwise

---

## Configuration

### Config

#### getConfig(): ConfigObject
**Purpose**: Get application configuration

**Returns**: Configuration object with all settings

---

#### validateConfig(): void
**Purpose**: Validate required configuration exists

**Throws**: Error if required config missing

---

## Type Definitions

### User
```typescript
{
  userId: string
  fullName: string
  dateOfBirth: string
  email: string
  password: string (hashed)
  createdAt: string
  updatedAt: string
}
```

### CreateUserDTO
```typescript
{
  fullName: string
  dateOfBirth: string
  email: string
  password: string (plain text)
}
```

### PasswordResetToken
```typescript
{
  tokenId: string
  userId: string
  token: string
  expiresAt: number (Unix timestamp)
  used: boolean
  createdAt: string
}
```

### JWTPayload
```typescript
{
  userId: string
  email: string
  iat: number
  exp: number
}
```

---

## Method Summary

**Total Methods**: 47

**By Component Type**:
- Controllers: 4 methods
- Services: 13 methods
- Models: 9 methods
- Middleware: 6 methods
- Utilities: 13 methods
- Configuration: 2 methods
