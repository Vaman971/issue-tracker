# Module 02-01 — Next.js: App Router, SSR, SSG & Hydration

---

## Learning Objectives

After this module you will:
- Understand what Next.js is and why we use it over plain React
- Know the difference between Server-Side Rendering, Static Generation, and Client rendering
- Understand the App Router file system and how routing works
- See how this project's pages and layouts are structured
- Understand hydration and why it matters

---

## What Is Next.js?

React is a **UI library** — it gives you tools to build components, but it doesn't tell you:
- How to structure your files
- How to handle routing (URLs)
- How to render HTML on the server for fast initial loads
- How to build and deploy your app

**Next.js** is a **framework built on top of React** that solves all these problems. Think of React as the engine and Next.js as the complete car.

```
Next.js = React + Router + Build System + Server + Conventions
```

---

## How a Web Browser Loads a Page

Before understanding Next.js, understand the problem it solves:

### The Traditional Approach (Client-Side Rendering)
```
Browser requests https://yourapp.com/projects
        │
        ▼
Server sends: <html><head>...</head><body><div id="root"></div></body></html>
              + a 500KB JavaScript bundle
        │
        ▼
Browser parses HTML → renders empty page
        │
        ▼
Browser downloads + executes JavaScript
        │
        ▼
React runs, makes API calls, renders content
        │
        ▼ (2-4 seconds later)
User finally sees the page
```

Problems:
- **Slow first paint** — user sees blank page while JS loads
- **Bad SEO** — search engines see empty HTML
- **No content without JS** — if JS fails, nothing shows

### Server-Side Rendering (SSR) with Next.js
```
Browser requests https://yourapp.com/projects
        │
        ▼
Next.js server (Node.js):
  - Fetches data from backend API
  - Renders React components to HTML
  - Returns COMPLETE HTML page
        │
        ▼
Browser receives FULL HTML → instantly renders content
        │
        ▼
Browser downloads JavaScript bundle (in background)
        │
        ▼
React "hydrates" — attaches event listeners without re-rendering
        │
        ▼
Page is now fully interactive (React takes over)
```

Benefits:
- **Fast first paint** — user sees content immediately
- **Good SEO** — search engines get real HTML content
- **Progressive enhancement** — works even if JS is slow

---

## The App Router — How Next.js Routing Works

Next.js uses **file-system based routing** — the folder structure determines the URLs.

```
frontend/src/app/
├── page.jsx                    → renders at /
├── layout.jsx                  → wraps all pages
│
├── login/
│   └── page.jsx                → renders at /login
│
├── register/
│   └── page.jsx                → renders at /register
│
├── (protected)/                → route GROUP (doesn't affect URL)
│   ├── layout.jsx              → wraps only protected pages
│   │                             (adds auth check)
│   ├── projects/
│   │   ├── page.jsx            → renders at /projects
│   │   ├── [id]/               → DYNAMIC segment
│   │   │   └── page.jsx        → renders at /projects/42
│   │   └── create/
│   │       └── page.jsx        → renders at /projects/create
│   │
│   ├── issues/
│   │   ├── page.jsx            → renders at /issues
│   │   └── [id]/
│   │       └── page.jsx        → renders at /issues/7
│   │
│   ├── notifications/
│   │   └── page.jsx            → renders at /notifications
│   │
│   └── admin/
│       └── page.jsx            → renders at /admin
```

### Route Groups — The `(protected)` Folder

Notice the folder is named `(protected)` with parentheses. Parentheses tell Next.js this is a **route group** — it organizes files but does NOT add to the URL path.

So `/protected/projects` becomes just `/projects`.

Why use route groups? To apply a **shared layout** to multiple routes without affecting their URLs. In this project, `(protected)/layout.jsx` wraps all authenticated pages and checks if the user is logged in.

```javascript
// frontend/src/app/(protected)/layout.jsx
// This layout wraps every page inside (protected)/
// It redirects to /login if the user is not authenticated

export default function ProtectedLayout({ children }) {
  // Check authentication
  // If not logged in → redirect to /login
  // If logged in → render the page
  return <AuthGuard>{children}</AuthGuard>
}
```

### Dynamic Routes — `[id]`

Square brackets in folder names create **dynamic segments**:

```
/projects/[id]/page.jsx

URL /projects/42  → params.id = "42"
URL /projects/99  → params.id = "99"
URL /projects/abc → params.id = "abc"
```

---

## Server Components vs Client Components

This is the most important concept in Next.js App Router.

### Server Components (default)

By default, every component in the App Router is a **Server Component** — it runs on the server, never in the browser.

```javascript
// This runs on the SERVER, not in the browser
// It can directly access databases, file systems, secrets
// It CANNOT use useState, useEffect, browser APIs

async function ProjectPage({ params }) {
  // Direct data fetching — no useEffect needed!
  const projects = await fetch(`${process.env.BACKEND_URL}/projects`)
  const data = await projects.json()
  
  return <ul>{data.map(p => <li key={p.id}>{p.name}</li>)}</ul>
}
```

Server Components:
- Fetch data directly (no client-side API calls needed)
- Keep secrets on the server (API keys never sent to browser)
- Reduce JavaScript bundle size (component code never shipped to browser)
- Cannot use React hooks (`useState`, `useEffect`)
- Cannot add event listeners

### Client Components

When you need interactivity (click handlers, form inputs, browser APIs), you mark a component with `'use client'`:

```javascript
'use client'  // This directive marks it as a Client Component

import { useState } from 'react'

function CreateIssueButton() {
  const [isOpen, setIsOpen] = useState(false)
  
  return (
    <button onClick={() => setIsOpen(true)}>
      Create Issue
    </button>
  )
}
```

Client Components:
- Can use `useState`, `useEffect`, and all React hooks
- Can access browser APIs (`window`, `document`, `localStorage`)
- Ship their code to the browser as JavaScript
- Cannot directly access server-only resources

### Where This Project Uses Each

```
Server Component territory:
- Root layout (app/layout.jsx) — sets up providers
- Page shells that fetch initial data

Client Component territory:
- Forms (require useState for input values)
- Modals (require open/close state)
- Navigation (requires browser routing)
- Anything that reacts to user interaction
```

In this project, most interactive pages are **client components** because they use Redux for state management and RTK Query for data fetching.

---

## Layouts — Shared UI Around Pages

A `layout.jsx` file wraps all pages within the same directory:

```
app/
├── layout.jsx          ← Root layout: wraps EVERYTHING
│                         (sets up Redux provider, global CSS)
│
└── (protected)/
    └── layout.jsx      ← Protected layout: wraps authenticated pages
                          (checks login, renders Navbar)
```

```javascript
// frontend/src/app/layout.jsx
// The root layout — every page in the entire app goes through this

import Providers from './providers'  // Redux store + other providers

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          {children}   {/* ← the actual page renders here */}
        </Providers>
      </body>
    </html>
  )
}
```

```javascript
// frontend/src/app/providers.jsx
// Sets up Redux store and other context providers

'use client'
import { Provider } from 'react-redux'
import { store } from '../store/store'

export default function Providers({ children }) {
  return (
    <Provider store={store}>
      {children}
    </Provider>
  )
}
```

---

## Next.js Configuration

```javascript
// frontend/next.config.mjs

const nextConfig = {
  // Rewrite /api/xxx to the backend URL
  // This is the magic that makes the frontend proxy API calls
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.BACKEND_INTERNAL_URL}/:path*`,
      },
    ]
  },
}
```

This rewrite rule means the frontend NEVER talks directly to the backend from the browser — all API calls go through Next.js's Node.js server first. This:
1. Hides the backend URL from users
2. Allows CORS to work simply (same-origin requests)
3. Lets Nginx route based on `/api/` prefix

---

## How Hydration Works

**Hydration** is the process where the browser-side React "takes over" a server-rendered HTML page.

```
Step 1: Server renders HTML
┌─────────────────────────────────────────────┐
│  <ul>                                        │
│    <li>Project Alpha</li>   ← Static HTML    │
│    <li>Project Beta</li>                     │
│  </ul>                                       │
│  (no event listeners, no JS state)           │
└─────────────────────────────────────────────┘
        │
        ▼
Step 2: Browser downloads React bundle
        │
        ▼
Step 3: React "hydrates" — attaches to existing DOM
┌─────────────────────────────────────────────┐
│  <ul>                                        │
│    <li onClick={...}>Project Alpha</li>  ← Now interactive │
│    <li onClick={...}>Project Beta</li>       │
│  </ul>                                       │
│  (React state attached, event listeners set) │
└─────────────────────────────────────────────┘
```

React does NOT re-render the HTML — it attaches JS behavior to existing DOM nodes. This is why Next.js is fast: users see content before React even loads.

**Hydration errors** occur when server HTML and client React disagree on what to render. Common cause: using `localStorage` during server rendering (it doesn't exist on the server).

---

## The Build Process

When you run `npm run build`:

```
next build

1. TypeScript/JavaScript compilation
2. Static analysis + optimization
3. Pre-render static pages (pages that don't need runtime data)
4. Generate manifest files (what JavaScript chunks go where)
5. Copy public assets

Output: .next/ directory
  .next/
  ├── server/          ← Server-side code (Node.js)
  ├── static/          ← Client-side JS bundles, CSS
  └── standalone/      ← Self-contained for Docker
```

### Multi-stage Docker Build

```dockerfile
# frontend/Dockerfile

# Stage 1: Install dependencies
FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci              # Clean install (reproducible)

# Stage 2: Build the application
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_BASE_URL    # Build-time environment variable
RUN npm run build       # Produces .next/ output

# Stage 3: Production runner (smallest possible image)
FROM node:22-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./
RUN npm ci --omit=dev   # Only production dependencies
EXPOSE 3000
CMD ["npm", "start"]
```

Why three stages? Each stage starts fresh — the final image doesn't include the ~800MB of build tools. Result: a small, secure production image.

---

## Environment Variables in Next.js

Next.js has two types:

```bash
# NEXT_PUBLIC_* variables → available in browser (baked into JS bundle at build time)
NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com

# Regular variables → server-only (never sent to browser)
BACKEND_INTERNAL_URL=http://backend:8000
```

**Critical**: `NEXT_PUBLIC_API_BASE_URL` is baked into the JavaScript bundle at **build time**. If you change it, you must rebuild the image.

```javascript
// In browser code:
fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/projects`)
// ↑ Works — value was embedded during build

// In server code (Next.js server-side):
fetch(`${process.env.BACKEND_INTERNAL_URL}/projects`)
// ↑ Works — read at runtime from server environment
```

---

## File Structure Summary for This Project

```
frontend/src/
├── app/
│   ├── layout.jsx              Root layout (Redux Provider)
│   ├── providers.jsx           Redux store + providers
│   ├── page.jsx                Landing page (/)
│   ├── login/page.jsx          Login page
│   ├── register/page.jsx       Registration page
│   ├── forgot-password/        Password reset request
│   ├── reset-password/         Password reset form
│   ├── verify-email/           Email verification
│   └── (protected)/
│       ├── layout.jsx          Auth guard (redirects if not logged in)
│       ├── projects/
│       │   ├── page.jsx        Project list
│       │   ├── [id]/page.jsx   Project detail
│       │   └── create/page.jsx Create project form
│       ├── issues/
│       │   ├── page.jsx        Issue list
│       │   └── [id]/page.jsx   Issue detail (comments, attachments)
│       ├── notifications/page.jsx
│       ├── profile/page.jsx
│       ├── search/page.jsx
│       └── admin/page.jsx
├── components/                 Shared reusable components
└── store/                      Redux state management
```

---

## Practical Exercise

Open `frontend/src/app/(protected)/projects/page.jsx` and identify:
1. Is it a Server or Client Component? (look for `'use client'` at the top)
2. How does it fetch data? (RTK Query `useGetProjectsQuery()` or direct `fetch`?)
3. What does it render?

Then open `frontend/src/app/(protected)/layout.jsx` and trace the authentication check.

---

## Further Reading & Videos

- **YouTube**: Search "Next.js 14 App Router Crash Course" — Traversy Media or Fireship have excellent overviews
- **YouTube**: Search "Next.js Server Components Explained" — Josh Tried Coding explains this well
- **Official Docs**: [Next.js App Router documentation](https://nextjs.org/docs/app)
- **Official Docs**: [Next.js rendering fundamentals](https://nextjs.org/docs/app/building-your-application/rendering)

---

*Next: [Module 02-02 — React Components and Hooks](./02-react-components.md)*
