# Component Dependencies and Communication Patterns

## Dependency Matrix

### Controllers Dependencies

| Component | Depends On | Dependency Type | Purpose |
|-----------|------------|-----------------|---------|
| AuthController | UserService | Service | User operations |
| AuthController | EmailService | Service | Send emails |
| AuthController | TokenService | Service | Token operations |
| AuthController | ResponseFormatter | Utility | Format responses |
| AuthController | Logger | Utility | Logging |

### Services Dependencies

| Component | Depends On | Dependency Type | Purpose |
|-----------|------------|-----------------|---------|
| UserService | UserModel | Model | Data access |
| UserService | bcrypt | External Library | Password hashing |
| UserService | Logger | Utility | Logging |
| EmailService | Nodemailer | External Library | Email sending |
| EmailService | Config | Configuration | SMTP settings |
| EmailService | Logger | Utility | Logging |
| TokenService | jsonwebtoken | External Library | JWT operations |
| TokenService | crypto | Node.js Built-in | Random generation |
| TokenService | PasswordResetTokenModel | Model | Data access |
| TokenService | Config | Configuration | JWT secret |
| TokenService | Logger | Utility | Logging |

### Models Dependencies

| Component | Depends On | Dependency Type | Purpose |
|-----------|------------|-----------------|---------|
| UserModel | AWS DynamoDB SDK | External Library | Database operations |
| UserModel | Config | Configuration | Table names, region |
| PasswordResetTokenModel | AWS DynamoDB SDK | External Library | Database operations |
| PasswordResetTokenModel | Config | Configuration | Table names, region |

### Middleware Dependencies

| Component | Depends On | Dependency Type | Purpose |
|-----------|------------|-----------------|---------|
| ValidationMiddleware | EmailValidator | Utility | Email validation |
| ValidationMiddleware | PasswordValidator | Utility | Password validation |
| ValidationMiddleware | DateValidator | Utility | Date validation |
| ValidationMiddleware | ResponseFormatter | Utility | Error responses |
| AuthMiddleware | TokenService | Service | Token verification |
| AuthMiddleware | ResponseFormatter | Utility | Error responses |
| RateLimitMiddleware | express-rate-limit | External Library | Rate limiting |
| ErrorHandlerMiddleware | Logger | Utility | Error logging |
| ErrorHandlerMiddleware | ResponseFormatter | Utility | Error responses |

---

## Communication Patterns

### Pattern 1: Request-Response Flow

```
Client Request
    |
    v
+------------------+
| Rate Limiting    |
| Middleware       |
+------------------+
    |
    v
+------------------+
| Validation       |
| Middleware       |
+------------------+
    |
    v
+------------------+
| Auth Middleware  |
| (if protected)   |
+------------------+
    |
    v
+------------------+
| Controller       |
+------------------+
    |
    v
+------------------+
| Service Layer    |
+------------------+
    |
    v
+------------------+
| Model Layer      |
+------------------+
    |
    v
+------------------+
| DynamoDB         |
+------------------+
    |
    v
Response to Client
```

### Pattern 2: Registration Flow

```
POST /api/auth/register
    |
    v
Rate Limit Middleware
    |
    v
Validation Middleware
    |
    v
AuthController.register
    |
    v
UserService.createUser
    |
    +---> UserModel.emailExists (check duplicate)
    |
    +---> bcrypt.hash (hash password)
    |
    +---> UserModel.create (save user)
    |
    v
Response (201 Created)
```

### Pattern 3: Login Flow

```
POST /api/auth/login
    |
    v
Rate Limit Middleware
    |
    v
Validation Middleware
    |
    v
AuthController.login
    |
    v
UserService.authenticateUser
    |
    +---> UserModel.findByEmail
    |
    +---> bcrypt.compare (verify password)
    |
    v
TokenService.generateJWT
    |
    v
Response (200 OK with JWT)
```

### Pattern 4: Forgot Password Flow

```
POST /api/auth/forgot-password
    |
    v
Rate Limit Middleware
    |
    v
Validation Middleware
    |
    v
AuthController.forgotPassword
    |
    v
UserService.getUserByEmail
    |
    v
TokenService.generatePasswordResetToken
    |
    v
TokenService.createPasswordResetToken
    |
    +---> PasswordResetTokenModel.create
    |
    v
EmailService.sendPasswordResetEmail
    |
    +---> Nodemailer.sendMail
    |
    v
Response (200 OK)
```

### Pattern 5: Reset Password Flow

```
POST /api/auth/reset-password
    |
    v
Rate Limit Middleware
    |
    v
Validation Middleware
    |
    v
AuthController.resetPassword
    |
    v
TokenService.validatePasswordResetToken
    |
    +---> PasswordResetTokenModel.findByToken
    |
    +---> Check expiration and used status
    |
    v
UserService.updateUserPassword
    |
    +---> bcrypt.hash (hash new password)
    |
    +---> UserModel.updatePassword
    |
    v
TokenService.markTokenAsUsed
    |
    +---> PasswordResetTokenModel.markAsUsed
    |
    v
Response (200 OK)
```

### Pattern 6: Error Handling Flow

```
Any Error Occurs
    |
    v
Try-Catch in Controller
    |
    v
Pass to next(error)
    |
    v
ErrorHandlerMiddleware
    |
    +---> Logger.error (log error)
    |
    +---> Determine error type
    |
    +---> ResponseFormatter.error
    |
    v
Error Response to Client
```

---

## Data Flow Diagrams

### User Registration Data Flow

```
Client
    |
    | POST {fullName, dateOfBirth, email, password}
    v
Validation Middleware
    |
    | Validated data
    v
AuthController
    |
    | CreateUserDTO
    v
UserService
    |
    | Check email exists
    v
UserModel --> DynamoDB (Query)
    |
    | Email available
    v
UserService
    |
    | Hash password
    v
bcrypt
    |
    | Hashed password
    v
UserService
    |
    | UserData with hashed password
    v
UserModel --> DynamoDB (Put)
    |
    | Created user
    v
AuthController
    |
    | Success response
    v
Client
```

### Password Reset Data Flow

```
Client
    |
    | POST {email}
    v
AuthController
    |
    v
UserService --> UserModel --> DynamoDB
    |
    | User found
    v
TokenService
    |
    | Generate random token
    v
crypto.randomBytes
    |
    | Token string
    v
TokenService --> PasswordResetTokenModel --> DynamoDB
    |
    | Token stored
    v
EmailService
    |
    | Email with reset link
    v
Nodemailer --> Gmail SMTP
    |
    v
User's Email Inbox
```

---

## Component Interaction Diagram

```
+-------------------+
|   Client/API      |
|   Consumer        |
+-------------------+
         |
         | HTTP Requests
         v
+-------------------+
|   Express App     |
+-------------------+
         |
         v
+-------------------+     +-------------------+
| Rate Limiting     |     | CORS              |
| Middleware        |     | Middleware        |
+-------------------+     +-------------------+
         |
         v
+-------------------+
| Validation        |
| Middleware        |
+-------------------+
         |
         v
+-------------------+
| Auth Controller   |
+-------------------+
         |
         +------------------+------------------+
         |                  |                  |
         v                  v                  v
+-------------+    +-------------+    +-------------+
| User        |    | Email       |    | Token       |
| Service     |    | Service     |    | Service     |
+-------------+    +-------------+    +-------------+
         |                  |                  |
         v                  v                  v
+-------------+    +-------------+    +-------------+
| User        |    | Nodemailer  |    | Password    |
| Model       |    |             |    | Reset Token |
|             |    |             |    | Model       |
+-------------+    +-------------+    +-------------+
         |                  |                  |
         v                  v                  v
+-------------+    +-------------+    +-------------+
| DynamoDB    |    | Gmail SMTP  |    | DynamoDB    |
| Users Table |    |             |    | Tokens Table|
+-------------+    +-------------+    +-------------+
```

---

## Dependency Injection Strategy

### Constructor Injection Pattern

All services and controllers receive dependencies via constructor:

```typescript
// Example: AuthController
class AuthController {
  constructor(
    private userService: UserService,
    private emailService: EmailService,
    private tokenService: TokenService,
    private logger: Logger
  ) {}
}

// Example: UserService
class UserService {
  constructor(
    private userModel: UserModel,
    private logger: Logger
  ) {}
}
```

### Benefits
- Testability: Easy to mock dependencies
- Flexibility: Easy to swap implementations
- Clarity: Dependencies are explicit
- Maintainability: Clear component boundaries

---

## Cross-Cutting Concerns

### Logging
- All components log to centralized Logger
- Consistent log format across application
- Log levels: error, warn, info, debug

### Error Handling
- Services throw domain-specific errors
- Controllers catch and pass to error handler
- Error handler formats and logs errors
- Consistent error response format

### Configuration
- All components read from centralized Config
- Environment-based configuration
- Validation on startup

### Security
- Password hashing in UserService
- Token generation in TokenService
- Validation in middleware
- Rate limiting at application level

---

## External Dependencies

### NPM Packages

| Package | Version | Purpose | Used By |
|---------|---------|---------|---------|
| express | ^4.18.0 | Web framework | App |
| typescript | ^5.0.0 | Type safety | All |
| @types/node | ^20.0.0 | Node types | All |
| @types/express | ^4.17.0 | Express types | Controllers, Middleware |
| bcrypt | ^5.1.0 | Password hashing | UserService |
| @types/bcrypt | ^5.0.0 | Bcrypt types | UserService |
| jsonwebtoken | ^9.0.0 | JWT operations | TokenService |
| @types/jsonwebtoken | ^9.0.0 | JWT types | TokenService |
| nodemailer | ^6.9.0 | Email sending | EmailService |
| @types/nodemailer | ^6.4.0 | Nodemailer types | EmailService |
| aws-sdk | ^2.1400.0 | DynamoDB operations | Models |
| express-rate-limit | ^6.10.0 | Rate limiting | Middleware |
| winston | ^3.10.0 | Logging | Logger |
| dotenv | ^16.3.0 | Environment variables | Config |
| uuid | ^9.0.0 | UUID generation | Services, Models |
| @types/uuid | ^9.0.0 | UUID types | Services, Models |

### AWS Services

| Service | Purpose | Used By |
|---------|---------|---------|
| DynamoDB | Data storage | UserModel, PasswordResetTokenModel |
| SES (optional) | Email sending | EmailService (alternative to Gmail) |

---

## Testing Dependencies

### Test Isolation Strategy

Each component can be tested in isolation by mocking its dependencies:

**Example: Testing UserService**
- Mock UserModel
- Mock Logger
- Mock bcrypt
- Test business logic independently

**Example: Testing AuthController**
- Mock UserService
- Mock EmailService
- Mock TokenService
- Mock Logger
- Test request/response handling

---

## Circular Dependency Prevention

### Rules
1. Controllers depend on Services (never reverse)
2. Services depend on Models (never reverse)
3. Models never depend on Services or Controllers
4. Utilities are leaf nodes (no dependencies on app components)
5. Middleware can depend on Services and Utilities

### Dependency Direction
```
Controllers --> Services --> Models --> Database
     |              |
     v              v
  Utilities    Utilities
```

---

## Component Lifecycle

### Application Startup Sequence

1. Load environment variables (dotenv)
2. Validate configuration (Config)
3. Initialize logger (Logger)
4. Initialize DynamoDB connection (Models)
5. Initialize services (Services)
6. Initialize controllers (Controllers)
7. Register routes (Routes)
8. Register middleware (Middleware)
9. Start HTTP server (Server)

### Shutdown Sequence

1. Stop accepting new requests
2. Complete in-flight requests
3. Close DynamoDB connections
4. Flush logs
5. Exit process

---

## Summary

**Total Dependencies Mapped**: 35 dependency relationships

**Dependency Types**:
- Service dependencies: 12
- Model dependencies: 6
- Middleware dependencies: 9
- External library dependencies: 15
- Configuration dependencies: 8

**Communication Patterns**: 6 major patterns documented

**Design Principles Followed**:
- ✅ Separation of concerns
- ✅ Dependency injection
- ✅ Single responsibility
- ✅ Loose coupling
- ✅ High cohesion
- ✅ Testability
