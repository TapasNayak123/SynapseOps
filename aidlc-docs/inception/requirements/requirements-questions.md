# Requirements Clarification Questions

Please answer the following questions to help clarify the requirements for your Node.js authentication application.

## Question 1: Application Deployment Environment
Where will this application be deployed?

A) AWS (using AWS services like SES for email, DynamoDB)
B) Azure (using Azure services)
C) Google Cloud Platform
D) On-premises or self-hosted servers
E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2: Email Service for Password Reset
Which email service should be used for sending password reset emails?

A) AWS SES (Simple Email Service)
B) SendGrid
C) Nodemailer with Gmail SMTP
D) Mailgun
E) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 3: Password Reset Flow
How should the password reset process work?

A) Send a time-limited reset token link via email (expires in 1 hour)
B) Send a one-time password (OTP) via email
C) Send a reset link that expires after first use
D) Send a reset link with custom expiration time
E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4: Rate Limiting Strategy
What rate limiting rules should be applied?

A) Global rate limit (e.g., 100 requests per 15 minutes per IP)
B) Per-endpoint rate limits (stricter for login/registration)
C) Per-user rate limits (after authentication)
D) Combination of IP-based and user-based rate limits
E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5: Password Security Requirements
What password security rules should be enforced?

A) Minimum 8 characters, at least one uppercase, one lowercase, one number
B) Minimum 12 characters with complexity requirements
C) Minimum 8 characters, no specific complexity requirements
D) Custom password policy
E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6: Email Validation Scope
You mentioned "email validation to allow gmail only" - should this be:

A) Only @gmail.com addresses allowed (strict Gmail only)
B) Gmail and Google Workspace emails (@gmail.com and custom domains via Google)
C) Gmail for now, but designed to easily add other providers later
D) This was a mistake - allow all email providers
E) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 7: Session Management
How should user sessions be managed after login?

A) JWT tokens (stateless)
B) Session cookies with server-side storage
C) JWT with refresh tokens
D) OAuth 2.0 flow
E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8: DynamoDB Table Structure
How should the user data be organized in DynamoDB?

A) Single table design with user data and reset tokens
B) Separate tables for users and password reset tokens
C) Single users table, reset tokens stored temporarily (TTL)
D) Let AI decide based on best practices
E) Other (please describe after [Answer]: tag below)

[Answer]: D

## Question 9: API Response Format
What format should API responses follow?

A) Standard JSON with status, message, data structure
B) REST API standards with HTTP status codes only
C) Custom format
D) JSON API specification
E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10: Error Handling and Logging
What level of error handling and logging is needed?

A) Basic console logging for development
B) Structured logging with Winston or similar (production-ready)
C) Cloud-based logging (CloudWatch, etc.)
D) Comprehensive logging with error tracking service (Sentry, etc.)
E) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 11: Testing Requirements
What testing approach should be implemented?

A) Unit tests for business logic
B) Unit tests + integration tests for API endpoints
C) Unit tests + integration tests + end-to-end tests
D) No tests initially (add later)
E) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 12: Environment Configuration
How should environment-specific configuration be managed?

A) .env files with dotenv package
B) AWS Systems Manager Parameter Store
C) Environment variables only (no .env files)
D) Configuration service
E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 13: API Documentation
Should API documentation be generated?

A) Yes, using Swagger/OpenAPI
B) Yes, using Postman collection
C) Yes, using both Swagger and Postman
D) No, just README with examples
E) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 14: CORS Configuration
What CORS policy should be applied?

A) Allow all origins (for development)
B) Specific frontend origin(s) only
C) Configurable via environment variables
D) No CORS needed (same-origin only)
E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 15: Date of Birth Validation
What validation should be applied to the date of birth field?

A) Must be 18+ years old
B) Must be 13+ years old (COPPA compliance)
C) Must be a valid past date (no age restriction)
D) Custom age restriction
E) Other (please describe after [Answer]: tag below)

[Answer]: A
