# Module 02-02 — React 19: Components, Hooks & Patterns

---

## Learning Objectives

After this module you will:
- Understand what React is and how it works internally
- Know the component lifecycle and hooks system
- Understand how this project's components are structured
- Know when to use which hook and why

---

## What Is React?

React is a JavaScript library for building user interfaces. Its core idea is simple:

```
UI = f(state)
```

Your UI is a pure function of your application's state. When state changes, React re-runs the function and updates what's shown on screen.

```
Without React (imperative):
  "Find the button element, change its text to 'Loading...', 
   disable it, add a spinner, then re-enable it when done"

With React (declarative):
  "Here's how the button should look when isLoading=true
   and how it should look when isLoading=false.
   React figures out the minimal DOM changes needed."
```

This is called **declarative programming** — you describe WHAT you want, not HOW to achieve it.

---

## How React Works Internally

React maintains a **virtual DOM** — a JavaScript representation of the real DOM:

```
Real DOM (slow to update):
┌───────────────────────────────────────────────────────────────┐
│  <div class="issue-list">                                     │
│    <div class="issue">Fix login bug</div>                     │
│    <div class="issue">Add dark mode</div>                     │
│  </div>                                                       │
└───────────────────────────────────────────────────────────────┘

React Virtual DOM (JavaScript objects, fast):
{
  type: 'div',
  props: { className: 'issue-list' },
  children: [
    { type: 'div', props: { className: 'issue' }, children: ['Fix login bug'] },
    { type: 'div', props: { className: 'issue' }, children: ['Add dark mode'] }
  ]
}
```

When state changes, React:
1. Creates a new Virtual DOM
2. **Diffs** it against the previous Virtual DOM (finds minimum changes)
3. Applies only the necessary changes to the real DOM

```
State change: new issue added

Old VDOM:                    New VDOM:
[issue1, issue2]             [issue1, issue2, issue3]

React diff: only issue3 is new
React DOM update: only inserts one new div
```

This **reconciliation** process is why React is fast — minimal real DOM operations.

---

## React Components

A component is a function that returns JSX (HTML-like syntax in JavaScript):

```javascript
// Simple component
function IssueCard({ title, status, priority }) {
  return (
    <div className="issue-card">
      <h3>{title}</h3>
      <span className={`status ${status.toLowerCase()}`}>{status}</span>
      <span className={`priority ${priority.toLowerCase()}`}>{priority}</span>
    </div>
  )
}

// Usage
<IssueCard 
  title="Fix login bug" 
  status="IN_PROGRESS" 
  priority="HIGH" 
/>
```

**Props** (short for properties) are the inputs to a component — like function arguments.

### Component Composition

React encourages **composition** — building complex UIs from small, reusable pieces:

```
ProjectPage
├── Navbar
├── ProjectHeader
│   ├── ProjectTitle
│   └── MemberAvatarList
│       └── Avatar (×3)
└── IssueList
    ├── IssueCard (×10)
    │   ├── StatusBadge
    │   ├── PriorityBadge
    │   └── AssigneeBadge
    └── LoadMoreButton
```

Each box is a separate component file. Small components are:
- Easy to test in isolation
- Reusable across multiple pages
- Easy to reason about

---

## React Hooks

Hooks are functions that let you "hook into" React's internal systems from functional components.

### useState — Local Component State

```javascript
'use client'
import { useState } from 'react'

function CreateIssueModal() {
  // [currentValue, setterFunction] = useState(initialValue)
  const [isOpen, setIsOpen] = useState(false)
  const [title, setTitle] = useState('')
  
  if (!isOpen) {
    return <button onClick={() => setIsOpen(true)}>Create Issue</button>
  }
  
  return (
    <div className="modal">
      <input 
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Issue title..."
      />
      <button onClick={() => {
        // Submit the issue
        setIsOpen(false)
      }}>
        Submit
      </button>
    </div>
  )
}
```

**How useState works internally:**

```
Component renders for the first time:
  useState(false) 
  → React allocates slot #0 in a "state array" for this component
  → Returns [false, setter]

User clicks button → setter(true) called:
  → React marks component as "needs re-render"
  → React re-runs the component function
  → useState(false) is called again
  → React IGNORES the initial value (false)
  → Reads slot #0 from state array → returns true
  → Component now renders with isOpen=true
```

This is why hooks must always be called in the **same order** — React tracks them by position, not by name.

### useEffect — Side Effects

Use `useEffect` for anything that needs to happen AFTER rendering: API calls, timers, subscriptions, DOM manipulation.

```javascript
'use client'
import { useEffect, useState } from 'react'

function NotificationBadge({ userId }) {
  const [count, setCount] = useState(0)
  
  useEffect(() => {
    // This runs AFTER the component renders
    
    // Start polling for new notifications
    const interval = setInterval(async () => {
      const response = await fetch(`/api/notifications/count`)
      const data = await response.json()
      setCount(data.unread_count)
    }, 30000) // every 30 seconds
    
    // CLEANUP FUNCTION — runs when component unmounts
    // or before effect runs again
    return () => clearInterval(interval)
    
  }, [userId]) // DEPENDENCY ARRAY — effect only re-runs when userId changes
  
  return <span className="badge">{count}</span>
}
```

**The dependency array controls when the effect runs:**

```javascript
useEffect(() => { ... })            // Runs after EVERY render (dangerous)
useEffect(() => { ... }, [])        // Runs once after FIRST render
useEffect(() => { ... }, [userId])  // Runs when userId changes
```

**Note**: In this project, most data fetching is done with **RTK Query** (not useEffect) because it handles caching, loading states, and refetching automatically. useEffect is reserved for non-API side effects.

### useCallback — Memoized Callbacks

Prevents functions from being recreated on every render (optimization):

```javascript
const handleSearch = useCallback((query) => {
  dispatch(setSearchQuery(query))
}, [dispatch])  // only recreate if dispatch changes
```

### useMemo — Memoized Computed Values

Expensive calculations are cached between renders:

```javascript
const filteredIssues = useMemo(() => {
  return issues.filter(issue => 
    issue.title.toLowerCase().includes(searchQuery.toLowerCase())
  )
}, [issues, searchQuery])  // only recompute when these change
```

### Custom Hooks — Extracting Reusable Logic

Custom hooks let you extract and reuse stateful logic:

```javascript
// frontend/src/hooks/useDebounce.js
// Used throughout the project to delay search queries

import { useState, useEffect } from 'react'

export function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value)
  
  useEffect(() => {
    // Wait `delay` ms after last change before updating
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)
    
    // Cancel the timer if value changes again before delay expires
    return () => clearTimeout(timer)
  }, [value, delay])
  
  return debouncedValue
}

// Usage in search:
const debouncedQuery = useDebounce(searchQuery, 300)
// Only fires API call 300ms after user stops typing
```

---

## Component Patterns in This Project

### Pattern 1: Protected Routes

```javascript
// frontend/src/components/ProtectedRoute/index.jsx

'use client'
import { useSelector } from 'react-redux'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useSelector(state => state.auth)
  const router = useRouter()
  
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [isAuthenticated, isLoading, router])
  
  if (isLoading) return <LoadingSpinner />
  if (!isAuthenticated) return null
  
  return children
}
```

### Pattern 2: Role-Based Rendering

```javascript
// frontend/src/components/RoleGate/index.jsx

'use client'
import { useSelector } from 'react-redux'

// Only render children if user has one of the allowed roles
export function RoleGate({ allowedRoles, children, fallback = null }) {
  const { user } = useSelector(state => state.auth)
  
  if (!user || !allowedRoles.includes(user.role)) {
    return fallback
  }
  
  return children
}

// Usage:
<RoleGate allowedRoles={['ADMIN', 'PROJECT_LEADER']}>
  <DeleteProjectButton />
</RoleGate>
// Non-admin users see nothing (or the fallback)
```

### Pattern 3: Skeleton Loading States

```javascript
// frontend/src/components/SkeletonCard/index.jsx
// Shows placeholder UI while data is loading

export function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <div className="skeleton-line" style={{ width: '70%' }} />
      <div className="skeleton-line" style={{ width: '40%' }} />
      <div className="skeleton-line" style={{ width: '90%' }} />
    </div>
  )
}

// Usage in a page:
function ProjectList() {
  const { data: projects, isLoading } = useGetProjectsQuery()
  
  if (isLoading) {
    return (
      <>
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </>
    )
  }
  
  return projects.map(p => <ProjectCard key={p.id} project={p} />)
}
```

### Pattern 4: Modal with Portal

```javascript
// frontend/src/components/CreateIssueModal/index.jsx

'use client'
import { useState } from 'react'
import { useCreateIssueMutation } from '../../store/features/issues/issuesApi'

export function CreateIssueModal({ projectId }) {
  const [isOpen, setIsOpen] = useState(false)
  
  // RTK Query mutation — automatically handles loading/error state
  const [createIssue, { isLoading }] = useCreateIssueMutation()
  
  async function handleSubmit(formData) {
    try {
      await createIssue({ projectId, ...formData }).unwrap()
      setIsOpen(false)
    } catch (error) {
      console.error('Failed to create issue:', error)
    }
  }
  
  return (
    <>
      <button onClick={() => setIsOpen(true)}>+ Create Issue</button>
      
      {isOpen && (
        <div className="modal-overlay">
          <div className="modal">
            <IssueForm onSubmit={handleSubmit} isLoading={isLoading} />
            <button onClick={() => setIsOpen(false)}>Cancel</button>
          </div>
        </div>
      )}
    </>
  )
}
```

### Pattern 5: Optimistic Updates

For a responsive UI, update the local state BEFORE the server confirms:

```javascript
// When user marks an issue as done, show it as done immediately
// Roll back if the server returns an error

const [updateIssue] = useUpdateIssueMutation()

async function markAsDone(issue) {
  // Optimistically update UI
  dispatch(updateIssueLocally({ id: issue.id, status: 'DONE' }))
  
  try {
    await updateIssue({ id: issue.id, status: 'DONE' }).unwrap()
    // Server confirmed — nothing more to do
  } catch (err) {
    // Server failed — roll back
    dispatch(updateIssueLocally({ id: issue.id, status: issue.status }))
    alert('Failed to update issue')
  }
}
```

---

## JSX — JavaScript + HTML

JSX is syntactic sugar — it looks like HTML but is compiled to JavaScript:

```javascript
// What you write (JSX):
const element = (
  <div className="card">
    <h2>{issue.title}</h2>
    <p>Assigned to: {issue.assignee.name}</p>
  </div>
)

// What React actually compiles it to:
const element = React.createElement('div', { className: 'card' },
  React.createElement('h2', null, issue.title),
  React.createElement('p', null, 'Assigned to: ', issue.assignee.name)
)
```

**Key JSX rules:**
- Use `className` instead of `class` (JS reserved word)
- Use `{expression}` to embed JavaScript values
- Self-closing tags need `/`: `<img />` not `<img>`
- Return only ONE root element (use `<>...</>` fragments if needed)
- `key` prop required for lists

---

## Component State vs Server State

A common confusion is mixing these two types:

```
LOCAL / UI STATE (use useState or Redux local slice)
  - Is this modal open?
  - What's in this text input right now?
  - Which tab is selected?
  → Changes don't need to be stored in the database

SERVER STATE (use RTK Query)
  - List of all projects from the API
  - Issue details
  - User profile data
  → Fetched from the server, must stay in sync
```

This project correctly uses:
- **Redux Toolkit slices** for UI state (auth status, modal open/closed)
- **RTK Query** for all server data (projects, issues, comments, etc.)

---

## Event Handling

React events are synthetic wrappers around browser events:

```javascript
// Click event
<button onClick={(event) => handleClick(event)}>Click</button>

// Form submission (must preventDefault to stop page reload)
<form onSubmit={(e) => {
  e.preventDefault()
  handleSubmit(formData)
}}>

// Input change
<input 
  value={title}
  onChange={(e) => setTitle(e.target.value)} 
/>

// Keyboard event
<input onKeyDown={(e) => {
  if (e.key === 'Enter') submitForm()
}} />
```

---

## Component File Structure

Each component in this project follows this pattern:

```
frontend/src/components/
└── CreateIssueModal/
    ├── index.jsx         ← Main component
    └── styles.module.css ← Scoped CSS (optional)
```

CSS Modules scope styles to only that component — no naming conflicts:

```css
/* CreateIssueModal/styles.module.css */
.modal {
  background: white;
  border-radius: 8px;
}

.title {
  font-size: 1.5rem;
}
```

```javascript
import styles from './styles.module.css'

function CreateIssueModal() {
  return (
    <div className={styles.modal}>
      <h2 className={styles.title}>Create Issue</h2>
    </div>
  )
}
```

---

## Further Reading & Videos

- **YouTube**: Search "React Hooks Explained" — Web Dev Simplified has a clear breakdown
- **YouTube**: Search "React useState and useEffect Tutorial" — Codevolution
- **YouTube**: Search "React Composition Patterns" — good for component design
- **Official Docs**: [React documentation](https://react.dev) — completely rewritten, excellent with interactive examples
- **Official Docs**: [React hooks reference](https://react.dev/reference/react)

---

*Next: [Module 02-03 — Redux Toolkit & RTK Query](./03-state-management.md)*
