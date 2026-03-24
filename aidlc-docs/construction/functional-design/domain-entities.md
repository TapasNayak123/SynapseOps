# Domain Entities

## Overview
This document defines the domain entities, their structure, relationships, and constraints.

---

## Entity 1: User

### Purpose
Represents a registered user in the system with authentication credentials.

### Attributes

| Attribute | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| userId | String (UUID) | Yes | Primary Key, Unique | Unique identifier for user |
| fullName | String | Yes | Min 2 chars | User's full name |
| dateOfBirth | String | Yes | YYYY-MM-DD, 18+ years | User's date of birth |
| email | String | Yes | Unique, Gmail only, Lowercase | User's email address |
| password | String | Yes | Bcrypt hash | Hashed password |
| createdAt | String | Yes | ISO 8601 | Account creation timestamp |
| updatedAt | String | Yes | ISO 8601 | Last update timestamp |

### Constraints

**Primary Key**: userId

**Global Secondary Index**: email-index
- Partition Key: email
- Purpose: Efficient email lookups for login and uniqueness checks

**Uniqueness Constraints**:
- userId: Globally unique (UUID v4)
- email: Unique across all users (enforced by GSI)

**Data Validation**:
- fullName: Not empty, min 2 characters
- dateOfBirth: Valid date, user must be 18+
- email: Valid format, @gmail.com domain, lowercase
- password: Bcrypt hash (never plain text)
- createdAt/updatedAt: ISO 8601 format

### Example

```json
{
  "userId": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  "fullName": "John Doe",
  "dateOfBirth": "1990-05-15",
  "email": "john.doe@gmail.com",
  "password": "$2b$12$KIXxLVq8YhZ9J0YvZ8X9XeN7Q8Z9X0YvZ8X9XeN7Q8Z9X0YvZ8X9Xe",
  "createdAt": "2026-03-09T10:30:00.000Z",
  "updatedAt": "2026-03-09T10:30:00.000Z"
}
```

### DynamoDB Table Configuration

**Table Name**: Users

**Billing Mode**: On-Demand (auto-scaling)

**Indexes**:
- Primary: userId (String)
- GSI: email-index
  - Partition Key: email (String)
  - Projection: ALL

**Estimated Size**: ~500 bytes per item

---

## Entity 2: PasswordResetToken

### Purpose
Represents a password reset token with expiration and usage tracking.

### Attributes

| Attribute | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| tokenId | String (UUID) | Yes | Primary Key, Unique | Unique identifier for token |
| userId | String (UUID) | Yes | Foreign Key to User | User requesting reset |
| token | String | Yes | Unique, 64 hex chars | Reset token value |
| expiresAt | Number | Yes | Unix timestamp, TTL | Token expiration time |
| used | Boolean | Yes | Default: false | Whether token has been used |
| createdAt | String | Yes | ISO 8601 | Token creation timestamp |

### Constraints

**Primary Key**: tokenId

**Global Secondary Index**: token-index
- Partition Key: token
- Purpose: Efficient token lookups during password reset

**Uniqueness Constraints**:
- tokenId: Globally unique (UUID v4)
- token: Unique (cryptographically random)

**Data Validation**:
- userId: Must reference existing User
- token: 64 hexadecimal characters
- expiresAt: Unix timestamp, must be future time
- used: Boolean (true/false)
- createdAt: ISO 8601 format

**TTL Configuration**:
- TTL Attribute: expiresAt
- Auto-deletion: DynamoDB automatically deletes expired tokens
- Grace Period: Tokens deleted shortly after expiration

### Example

```json
{
  "tokenId": "f1e2d3c4-b5a6-4978-8c9d-0e1f2a3b4c5d",
  "userId": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  "token": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
  "expiresAt": 1709985600,
  "used": false,
  "createdAt": "2026-03-09T10:30:00.000Z"
}
```

### DynamoDB Table Configuration

**Table Name**: PasswordResetTokens

**Billing Mode**: On-Demand (auto-scaling)

**Indexes**:
- Primary: tokenId (String)
- GSI: token-index
  - Partition Key: token (String)
  - Projection: ALL

**TTL**: Enabled on expiresAt attribute

**Estimated Size**: ~300 bytes per item

---

## Entity Relationships

### User ← PasswordResetToken

**Relationship Type**: One-to-Many

**Description**: One user can have multiple password reset tokens (historical)

**Foreign Key**: PasswordResetToken.userId → User.userId

**Cardinality**:
- User: 1
- PasswordResetToken: 0..N

**Referential Integrity**:
- Tokens reference users via userId
- No cascade delete (tokens expire via TTL)
- Orphaned tokens acceptable (will be cleaned up by TTL)

**Business Rules**:
- User can request multiple resets
- Only one active (unused, unexpired) token should exist at a time
- Previous tokens remain in database until TTL cleanup

### Relationship Diagram

```
+------------------+
|      User        |
|------------------|
| userId (PK)      |
| fullName         |
| dateOfBirth      |
| email (Unique)   |
| password         |
| createdAt        |
| updatedAt        |
+------------------+
         |
         | 1
         |
         | has
         |
         | 0..N
         v
+------------------+
| PasswordReset    |
| Token            |
|------------------|
| tokenId (PK)     |
| userId (FK)      |
| token (Unique)   |
| expiresAt (TTL)  |
| used             |
| createdAt        |
+------------------+
```

---

## Data Transfer Objects (DTOs)

### CreateUserDTO

**Purpose**: Data structure for user registration requests

**Attributes**:
```typescript
{
  fullName: string
  dateOfBirth: string (YYYY-MM-DD)
  email: string
  password: string (plain text)
}
```

**Validation**: All business rules applied before creating User entity

**Transformation**: password hashed, email lowercased, userId generated

---

### LoginRequestDTO

**Purpose**: Data structure for login requests

**Attributes**:
```typescript
{
  email: string
  password: string (plain text)
}
```

**Validation**: Format validation only (authentication happens in service)

---

### ForgotPasswordRequestDTO

**Purpose**: Data structure for password reset requests

**Attributes**:
```typescript
{
  email: string
}
```

**Validation**: Email format validation

---

### ResetPasswordRequestDTO

**Purpose**: Data structure for password reset execution

**Attributes**:
```typescript
{
  token: string
  newPassword: string (plain text)
}
```

**Validation**: Token format, password strength

---

### UserResponseDTO

**Purpose**: Data structure for user information in responses

**Attributes**:
```typescript
{
  userId: string
  email: string
  fullName: string
}
```

**Note**: Password never included in responses

---

## Entity Lifecycle

### User Entity Lifecycle

```
Registration Request
    |
    v
[Validation]
    |
    v
[Create User Entity]
    |
    v
[Store in DynamoDB]
    |
    v
[Active User]
    |
    | (Login, Password Reset)
    v
[Updated User]
    |
    | (Manual deletion - out of scope)
    v
[Deleted User]
```

**States**:
- **New**: User just registered
- **Active**: User can login and use system
- **Updated**: Password changed via reset
- **Deleted**: User removed (out of scope for this project)

---

### PasswordResetToken Entity Lifecycle

```
Forgot Password Request
    |
    v
[Generate Token]
    |
    v
[Create Token Entity]
    |
    v
[Store in DynamoDB]
    |
    v
[Active Token]
    |
    +---> [Used] (password reset successful)
    |
    +---> [Expired] (1 hour passed)
    |
    v
[Auto-Deleted by TTL]
```

**States**:
- **Active**: Token created, not used, not expired
- **Used**: Token used for password reset
- **Expired**: Token passed expiration time
- **Deleted**: Token removed by DynamoDB TTL

---

## Data Integrity Rules

### Rule 1: Email Uniqueness
- Enforced by DynamoDB GSI
- Case-insensitive (store lowercase)
- Prevents duplicate accounts

### Rule 2: Password Security
- Never store plain text passwords
- Always use bcrypt with cost factor 12
- Never log or expose password hashes

### Rule 3: Token Security
- Cryptographically random tokens
- Single-use enforcement via used flag
- Automatic expiration via TTL

### Rule 4: Timestamp Consistency
- All timestamps in ISO 8601 format
- UTC timezone
- Millisecond precision

### Rule 5: UUID Format
- All IDs use UUID v4
- Globally unique
- Non-sequential (security)

---

## Data Migration Considerations

### Initial Setup
- Create DynamoDB tables with indexes
- Configure TTL on PasswordResetTokens.expiresAt
- Set billing mode to On-Demand
- Enable point-in-time recovery (optional)

### Schema Evolution
- Add new attributes without breaking existing data
- Use sparse indexes for optional attributes
- Version entities if major changes needed

---

## Data Access Patterns

### Pattern 1: User Registration
- **Operation**: Put Item
- **Table**: Users
- **Key**: userId (generated)
- **Condition**: email does not exist (check via GSI)

### Pattern 2: User Login
- **Operation**: Query
- **Table**: Users
- **Index**: email-index
- **Key**: email
- **Result**: Single user or none

### Pattern 3: Password Reset Token Creation
- **Operation**: Put Item
- **Table**: PasswordResetTokens
- **Key**: tokenId (generated)
- **TTL**: expiresAt

### Pattern 4: Password Reset Token Validation
- **Operation**: Query
- **Table**: PasswordResetTokens
- **Index**: token-index
- **Key**: token
- **Result**: Single token or none

### Pattern 5: Password Update
- **Operation**: Update Item
- **Table**: Users
- **Key**: userId
- **Attributes**: password, updatedAt

### Pattern 6: Token Invalidation
- **Operation**: Update Item
- **Table**: PasswordResetTokens
- **Key**: tokenId
- **Attributes**: used = true

---

## Entity Summary

**Total Entities**: 2 core entities + 5 DTOs

**Core Entities**:
- User: 7 attributes
- PasswordResetToken: 6 attributes

**Relationships**: 1 (User ← PasswordResetToken)

**Indexes**: 2 GSIs (email-index, token-index)

**Constraints**: 35 business rules enforced

**Data Access Patterns**: 6 primary patterns
