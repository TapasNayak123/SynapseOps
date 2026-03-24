# Application Components

## Architecture Overview

The application follows MVC (Model-View-Controller) pattern with additional layers for better separation of concerns:

```
Routes Layer (API Endpoints)
    |
    v
Middleware Layer (Validation, Auth, Rate Limiting)
    |
    v
Controllers Layer (Request/Response Handling)
    |
    v
Services Layer (Business Logic)
    |
    v
Models Layer (Data Access)
    |
    v
DynamoDB
```

---

## Layer 1: Routes

### Component: AuthRoutes
**File**: `src/routes/auth.routes.ts`

**Purpose**: Define API endpoints for authentication operations

**Responsibilities**:
- Map HTTP methods and paths to controller methods
- Apply middleware to routes (validation, rate limiting)
- Group related authentication endpoints

**Endpoints**:
- POST /api/auth/register
- POST /api/auth/login
- POST /api/auth/forgot-password
- POST /api/auth/reset-password

---

## Layer 2: Controllers

### Component: AuthController
**File**: `src/controllers/auth.controller.ts`

**Purpose**: Handle HTTP requests and responses for authentication operations

**Responsibilities**:
- Extract and validate request data
- Call appropriate service methods
- Format responses according to API standards
- Handle controller-level errors with try-catch
- Return appropriate HTTP status codes

**Dependencies**:
- UserService
- EmailService
- TokenService

---

## Layer 3: Services

### Component: UserService
**File**: `src/services/user.service.ts`

**Purpose**: Implement business logic for user operations

**Responsibilities**:
- User registration logic
- User authentication logic
- Password hashing and verification
- User data validation (business rules)
- Interact with UserModel for data persistence

**Dependencies**:
- UserModel
- bcrypt library

---

### Component: EmailService
**File**: `src/services/email.service.ts`

**Purpose**: Handle email sending operations

**Responsibilities**:
- Send password reset emails
- Format email content
- Configure Nodemailer with Gmail SMTP
- Handle email sending errors
- Log email operations

**Dependencies**:
- Nodemailer library
- Email configuration

---

### Component: TokenService
**File**: `src/services/token.service.ts`

**Purpose**: Manage JWT tokens and password reset tokens

**Responsibilities**:
- Generate JWT tokens for authentication
- Verify JWT tokens
- Generate password reset tokens
- Validate password reset tokens (expiration, usage)
- Store and retrieve reset tokens from database

**Dependencies**:
- jsonwebtoken library
- PasswordResetTokenModel
- crypto library (for reset tokens)

---

## Layer 4: Models

### Component: UserModel
**File**: `src/models/user.model.ts`

**Purpose**: Data access layer for user operations

**Responsibilities**:
- CRUD operations for users in DynamoDB
- Query users by email
- Check for duplicate emails
- Data mapping between application and database

**Dependencies**:
- AWS DynamoDB SDK
- Database configuration

**DynamoDB Table**: Users
- Primary Key: userId (String)
- GSI: email-index (for querying by email)

---

### Component: PasswordResetTokenModel
**File**: `src/models/password-reset-token.model.ts`

**Purpose**: Data access layer for password reset tokens

**Responsibilities**:
- CRUD operations for reset tokens in DynamoDB
- Query tokens by token value
- Mark tokens as used
- Leverage DynamoDB TTL for automatic expiration

**Dependencies**:
- AWS DynamoDB SDK
- Database configuration

**DynamoDB Table**: PasswordResetTokens
- Primary Key: tokenId (String)
- GSI: token-index (for querying by token value)
- TTL Attribute: expiresAt (automatic deletion after 1 hour)

---

## Layer 5: Middleware

### Component: ValidationMiddleware
**File**: `src/middleware/validation.middleware.ts`

**Purpose**: Validate incoming request data before reaching controllers

**Responsibilities**:
- Validate request body structure
- Validate email format
- Validate email domain (Gmail only)
- Validate password strength
- Validate date of birth (18+ years)
- Return 400 errors for invalid data

**Dependencies**:
- Validation library (e.g., Joi, express-validator)

---

### Component: AuthMiddleware
**File**: `src/middleware/auth.middleware.ts`

**Purpose**: Authenticate requests using JWT tokens

**Responsibilities**:
- Extract JWT token from request headers
- Verify JWT token validity
- Attach user information to request object
- Return 401 errors for invalid/missing tokens

**Dependencies**:
- TokenService
- jsonwebtoken library

---

### Component: RateLimitMiddleware
**File**: `src/middleware/rate-limit.middleware.ts`

**Purpose**: Prevent API abuse through rate limiting

**Responsibilities**:
- Track request counts per IP address
- Enforce rate limits (100 requests per 15 minutes)
- Return 429 errors when limit exceeded
- Add Retry-After header to responses

**Dependencies**:
- express-rate-limit library

---

### Component: ErrorHandlerMiddleware
**File**: `src/middleware/error-handler.middleware.ts`

**Purpose**: Centralized error handling for the application

**Responsibilities**:
- Catch all unhandled errors
- Format error responses consistently
- Log errors with appropriate detail
- Return appropriate HTTP status codes
- Handle different error types (validation, authentication, database, etc.)

**Dependencies**:
- Logger utility

---

## Layer 6: Utilities

### Component: Logger
**File**: `src/utils/logger.ts`

**Purpose**: Structured logging throughout the application

**Responsibilities**:
- Configure Winston logger
- Provide logging methods (error, warn, info, debug)
- Format log output (JSON for production)
- Log to console and/or files

**Dependencies**:
- Winston library

---

### Component: ResponseFormatter
**File**: `src/utils/response-formatter.ts`

**Purpose**: Standardize API response formats

**Responsibilities**:
- Format success responses
- Format error responses
- Ensure consistent response structure

**Response Format**:
```typescript
{
  status: "success" | "error",
  message: string,
  data: any | null
}
```

---

### Component: EmailValidator
**File**: `src/utils/email-validator.ts`

**Purpose**: Email validation logic with extensible design

**Responsibilities**:
- Validate email format using regex
- Check email domain against whitelist
- Provide easy configuration for adding new domains

**Dependencies**: None

---

### Component: PasswordValidator
**File**: `src/utils/password-validator.ts`

**Purpose**: Password strength validation

**Responsibilities**:
- Check password length (minimum 8 characters)
- Check for uppercase letters
- Check for lowercase letters
- Check for numbers
- Return detailed validation errors

**Dependencies**: None

---

### Component: DateValidator
**File**: `src/utils/date-validator.ts`

**Purpose**: Date of birth validation

**Responsibilities**:
- Validate date format
- Calculate age from date of birth
- Check minimum age requirement (18 years)

**Dependencies**: None

---

## Configuration

### Component: Config
**File**: `src/config/config.ts`

**Purpose**: Centralized application configuration

**Responsibilities**:
- Load environment variables
- Provide typed configuration object
- Validate required configuration
- Export configuration for use across application

**Configuration Sections**:
- Server configuration (port, environment)
- Database configuration (DynamoDB table names, region)
- JWT configuration (secret, expiration)
- Email configuration (SMTP settings)
- Rate limiting configuration

---

## Application Entry Point

### Component: App
**File**: `src/app.ts`

**Purpose**: Express application setup and configuration

**Responsibilities**:
- Initialize Express app
- Configure middleware (CORS, body parser, rate limiting)
- Register routes
- Configure error handling
- Export app for server

---

### Component: Server
**File**: `src/server.ts`

**Purpose**: HTTP server initialization

**Responsibilities**:
- Import and start Express app
- Listen on configured port
- Handle server startup errors
- Log server status

---

## Component Summary

### Total Components: 19

**By Layer**:
- Routes: 1 component
- Controllers: 1 component
- Services: 3 components
- Models: 2 components
- Middleware: 4 components
- Utilities: 6 components
- Configuration: 1 component
- Application: 2 components

**MVC Pattern Compliance**:
- ✅ Models: UserModel, PasswordResetTokenModel
- ✅ Views: API responses (JSON format via ResponseFormatter)
- ✅ Controllers: AuthController
- ✅ Additional layers for separation of concerns (Services, Middleware, Utils)
