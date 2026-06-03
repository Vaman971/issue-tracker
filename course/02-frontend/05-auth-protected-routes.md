# Module 02-05 — Authentication, JWT Flow & Protected Routes

---

## Learning Objectives

After this module you will:
- Understand how JWT authentication works end-to-end
- Know the access token + refresh token pattern and why it exists
- See the complete login/logout flow in this project
- Understand how the frontend protects routes and enforces roles

---

## What Is Authentication vs Authorization?

```
Authentication: "Who are you?"
  → Proving identity (login with email + password)
  → Result: a JWT token proving you are who you say you are

Authorization: "What are you allowed to do?"
  → Checking permissions (can this user delete this project?)
  → Result: allow or deny the action based on user's role
```

---

## JSON Web Tokens (JWT)

A JWT (JSON Web Token) is a compact, self-contained way to transmit information securely.

### JWT Structure

A JWT looks like: `xxxxx.yyyyy.zzzzz`

It has three parts separated by dots:

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ
.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

Decode the middle part (payload):
```json
{
  "sub": "1",           // Subject: user ID
  "email": "alice@example.com",
  "role": "DEVELOPER",
  "exp": 1706123456,    // Expiry timestamp (15 minutes from issue)
  "iat": 1706122556     // Issued at timestamp
}
```

### How JWT Verification Works

```
Server issues JWT signed with secret key:
  payload = { sub: "1", exp: 1706123456 }
  signature = HMAC_SHA256(base64(header) + "." + base64(payload), SECRET_KEY)
  JWT = base64(header) + "." + base64(payload) + "." + base64(signature)

Client stores JWT and sends with every request:
  Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

Server verifies:
  1. Decode header and payload (anyone can do this)
  2. Recompute HMAC_SHA256 using own SECRET_KEY
  3. Compare to received signature
  4. If they match → token is authentic (only server could have made it)
  5. Check exp timestamp → not expired?
  → User is authenticated, no database query needed!
```

**Key insight**: JWT is **stateless** — the server doesn't need to query the database to verify who you are. Everything is encoded in the token.

### Why Two Tokens?

```
Access Token (short-lived, 15 minutes):
  + Fast to verify (no database query)
  - If stolen, attacker has access for 15 minutes

Refresh Token (long-lived, 7 days):
  + Allows getting new access tokens without re-login
  - Stored in database (revocable if stolen)
  - Only used at one endpoint (/auth/refresh)
```

The pattern:

```
Login → Server issues:
  Access Token (15 min) → stored in memory/localStorage
  Refresh Token (7 days) → stored in database + sent to client

Normal requests:
  Client sends Access Token
  Server verifies signature + expiry → no database query needed

Access Token expires:
  Client sends Refresh Token to /auth/refresh
  Server checks:
    1. Is refresh token in database? (not revoked)
    2. Is it expired?
    → Issues new Access Token
    → Client stores new Access Token, continues

Logout:
  Client deletes both tokens
  Server deletes Refresh Token from database
  → Can no longer get new Access Tokens
```

---

## The Authentication Flow in This Project

### Login

```
User submits email + password
        │
        ▼ POST /api/auth/login
Backend (auth.py):
  1. Find user by email in database
  2. bcrypt.verify(submitted_password, stored_hash)
  3. Check user.email_verified == True
  4. Check rate limit (max 5 attempts / 60 sec per IP)
        │
        ▼ Success
  5. Generate Access Token (JWT with user.id, email, role)
  6. Generate Refresh Token (JWT)
  7. Hash Refresh Token, store hash in refresh_tokens table
     (so we can revoke it if needed)
  8. Return: { user: {...}, access_token: "...", refresh_token: "..." }
        │
        ▼
Frontend (authSlice.js):
  dispatch(setCredentials({ user, accessToken }))
  localStorage.setItem('refreshToken', refresh_token)
  // Note: access token stays in Redux memory only
  // Refresh token persists to survive page reload
        │
        ▼
User is now logged in
```

### Staying Logged In Across Page Reloads

The access token lives in Redux memory — it's lost on page refresh. The refresh token persists in localStorage.

```javascript
// frontend/src/components/AuthInitializer/index.jsx
// This component runs when the app first loads

'use client'
import { useEffect } from 'react'
import { useDispatch } from 'react-redux'
import { setCredentials, setLoading } from '../../store/features/auth/authSlice'
import { useRefreshTokenMutation } from '../../store/features/auth/authApi'

export function AuthInitializer({ children }) {
  const dispatch = useDispatch()
  const [refreshToken] = useRefreshTokenMutation()
  
  useEffect(() => {
    // Check if we have a refresh token from a previous session
    const storedRefreshToken = localStorage.getItem('refreshToken')
    
    if (!storedRefreshToken) {
      // No previous session
      dispatch(setLoading(false))
      return
    }
    
    // Try to get a new access token
    refreshToken({ refresh_token: storedRefreshToken })
      .unwrap()
      .then(({ user, access_token }) => {
        dispatch(setCredentials({ user, accessToken: access_token }))
      })
      .catch(() => {
        // Refresh token invalid/expired
        localStorage.removeItem('refreshToken')
        dispatch(setLoading(false))
      })
  }, [])
  
  return children
}
```

This runs silently when the page loads — the user stays logged in without re-entering credentials.

### Token Refresh Mid-Request (Automatic)

When an access token expires mid-session, RTK Query handles it transparently:

```
Component calls useGetProjectsQuery()
        │
        ▼ GET /api/projects
        │ Authorization: Bearer <expired_access_token>
        │
        ▼ Server returns 401 Unauthorized
        │
        ▼ RTK Query baseQuery detects 401
        │
        ▼ POST /api/auth/refresh
        │ Body: { refresh_token: localStorage.getItem('refreshToken') }
        │
        ▼ Server verifies refresh token
        │ Issues new access token
        │
        ▼ RTK Query: dispatch(setCredentials(newTokenData))
        │
        ▼ Original request retried with new access token
        │ GET /api/projects
        │ Authorization: Bearer <new_access_token>
        │
        ▼ Server returns 200 with projects data
        │
        ▼ Component renders projects
        
User never notices the token expired — seamless experience
```

---

## Protected Routes

The `(protected)` route group in Next.js wraps all authenticated pages with a layout that checks authentication:

```javascript
// frontend/src/app/(protected)/layout.jsx

'use client'
import { useSelector } from 'react-redux'
import { useRouter, usePathname } from 'next/navigation'
import { useEffect } from 'react'

export default function ProtectedLayout({ children }) {
  const { isAuthenticated, isLoading } = useSelector(state => state.auth)
  const router = useRouter()
  const pathname = usePathname()
  
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      // Save where they were trying to go
      router.push(`/login?redirect=${encodeURIComponent(pathname)}`)
    }
  }, [isAuthenticated, isLoading, router, pathname])
  
  // Show loading while we check authentication status
  if (isLoading) {
    return <AppLoadingScreen />
  }
  
  // Don't render anything while redirecting
  if (!isAuthenticated) {
    return null
  }
  
  // User is authenticated — render the page with its layout
  return (
    <div className="app-layout">
      <Navbar />
      <main>{children}</main>
    </div>
  )
}
```

### Route Protection Flow

```
User visits /projects/42
        │
        ▼ Next.js: this is inside (protected)/ folder
        │ Run (protected)/layout.jsx FIRST
        │
        ▼ AuthInitializer has already run:
        │   isLoading=false, isAuthenticated=true
        │
        ▼ Layout: isAuthenticated=true → render children
        │
        ▼ /projects/[id]/page.jsx renders
        │
        ▼ User sees project detail page

OR: User visits /projects/42 but is NOT logged in:
        │
        ▼ (protected)/layout.jsx runs
        │ isAuthenticated=false
        │
        ▼ router.push('/login?redirect=/projects/42')
        │
        ▼ User sees login page
        │
        ▼ After login, redirect back to /projects/42
```

---

## Role-Based Access Control (RBAC) on the Frontend

The backend enforces real authorization. The frontend provides **UI-level hints** — hiding/showing elements based on role.

### User Roles in This Project

```
ADMIN           → Full access: manage all users, all projects, all issues
PROJECT_LEADER  → Manage their own projects, assign members
DEVELOPER       → Create and update issues in their projects
QA              → Create issues, add comments, change status
VIEWER          → Read-only access
```

### RoleGate Component

```javascript
// frontend/src/components/RoleGate/index.jsx

'use client'
import { useSelector } from 'react-redux'

export function RoleGate({ allowedRoles, children, fallback = null }) {
  const user = useSelector(state => state.auth.user)
  
  if (!user || !allowedRoles.includes(user.role)) {
    return fallback
  }
  
  return <>{children}</>
}

// Usage examples:

// Show delete button only to ADMIN
<RoleGate allowedRoles={['ADMIN']}>
  <DeleteProjectButton />
</RoleGate>

// Show project settings to ADMIN or PROJECT_LEADER
<RoleGate 
  allowedRoles={['ADMIN', 'PROJECT_LEADER']}
  fallback={<ReadOnlySettings />}
>
  <EditableSettings />
</RoleGate>
```

### Route-Level Role Protection

```javascript
// frontend/src/app/(protected)/admin/page.jsx

'use client'
import { RoleProtectedRoute } from '../../../components/RoleProtectedRoute'

export default function AdminPage() {
  return (
    <RoleProtectedRoute allowedRoles={['ADMIN']}>
      <AdminDashboard />
    </RoleProtectedRoute>
  )
}
```

```javascript
// frontend/src/components/RoleProtectedRoute/index.jsx

'use client'
import { useSelector } from 'react-redux'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export function RoleProtectedRoute({ allowedRoles, children }) {
  const { user } = useSelector(state => state.auth)
  const router = useRouter()
  
  useEffect(() => {
    if (user && !allowedRoles.includes(user.role)) {
      router.push('/projects')  // Redirect non-admins away
    }
  }, [user, allowedRoles])
  
  if (!user || !allowedRoles.includes(user.role)) {
    return <AccessDeniedPage />
  }
  
  return children
}
```

---

## Password Reset Flow

```
1. User clicks "Forgot Password"
   │
   ▼ POST /api/auth/forgot-password
   │ Body: { email: "alice@example.com" }
   │
   ▼ Backend:
   │   Generate reset token (random UUID)
   │   Hash and store in password_reset_tokens table
   │   Send email with reset link: /reset-password?token=xyz
   │
   ▼ (User checks email, clicks link)

2. User visits /reset-password?token=xyz
   │
   ▼ POST /api/auth/reset-password
   │ Body: { token: "xyz", new_password: "newpass123" }
   │
   ▼ Backend:
   │   Verify token exists and not expired (24h TTL)
   │   Hash new password with bcrypt
   │   Update user.hashed_password
   │   Delete all refresh tokens for this user (security)
   │   Delete used reset token
   │
   ▼ User can now log in with new password
```

---

## Email Verification Flow

```
1. User registers
   │
   ▼ POST /api/auth/register
   │
   ▼ Backend:
   │   Create user account (email_verified=False)
   │   Generate verification token
   │   Queue Celery task: send_verification_email
   │
   ▼ Celery worker:
   │   Send email with link: /verify-email?token=abc

2. User clicks email link
   │
   ▼ GET /api/auth/verify-email?token=abc
   │
   ▼ Backend:
   │   Verify token valid
   │   Set user.email_verified = True
   │   User can now log in
```

Users with `email_verified=False` get a 403 when attempting to login.

---

## Security Considerations

### Storing Tokens

```
Access Token storage:
  ✓ Redux store (in-memory)
  ✓ Lost on page refresh → refresh token handles re-issue
  ✗ Never in localStorage (XSS risk if using access token long-term)

Refresh Token storage:
  ✓ localStorage (for persistence across page refreshes)
  ✓ Only used at /auth/refresh endpoint
  ✓ HTTPOnly cookies would be more secure (mitigates XSS)
  (localStorage is pragmatic choice here)
```

### CSRF Protection

Since we use Authorization Bearer headers (not cookies for the auth token):
- CSRF attacks don't apply to our API endpoints
- Browser's same-origin policy prevents malicious sites from reading localStorage
- The Authorization header can only be set by JavaScript running on the same origin

### Rate Limiting on Auth Endpoints

```
Backend rate limiting (services/rate_limit.py):
  Login: 5 attempts per 60 seconds per IP
  Register: 3 attempts per 60 seconds per IP
  
After limit exceeded: 429 Too Many Requests
  "Too many login attempts. Try again in 60 seconds."
```

---

## Complete Authentication State Machine

```
                    App loads
                        │
                        ▼
                   isLoading=true
                        │
                        ▼
              AuthInitializer runs
                        │
              ┌─────────┴──────────┐
              │ refreshToken in    │ refreshToken NOT in
              │ localStorage?      │ localStorage?
              │ YES                │ NO
              ▼                    ▼
         POST /auth/refresh    isLoading=false
              │                isAuthenticated=false
              ├─Success          (show login page)
              │  setCredentials
              │  isAuthenticated=true
              │
              └─Failure
                 clear localStorage
                 isLoading=false
                 isAuthenticated=false
                 (show login page)

User logs in:
  POST /auth/login
  ├─ Success → setCredentials → isAuthenticated=true
  └─ Failure → show error, stay on login page

User logs out:
  POST /auth/logout (revoke refresh token on server)
  dispatch(logout())
  localStorage.removeItem('refreshToken')
  redirect to /login
```

---

## Further Reading & Videos

- **YouTube**: Search "JWT Authentication Tutorial" — Web Dev Simplified explains this clearly with diagrams
- **YouTube**: Search "Refresh Token Rotation" — Fireship covers the security implications
- **Official Docs**: [JWT.io introduction](https://jwt.io/introduction) — official JWT documentation with interactive decoder
- **Security reference**: [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

---

*Next: [Module 03-01 — FastAPI Fundamentals](../03-backend/01-fastapi-fundamentals.md)*
