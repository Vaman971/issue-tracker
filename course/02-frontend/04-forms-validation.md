# Module 02-04 — React Hook Form & Zod: Forms and Validation

---

## Learning Objectives

After this module you will:
- Understand controlled vs uncontrolled form inputs
- Know why React Hook Form is faster than controlled forms
- Understand Zod for schema-based validation
- See how login, register, and issue forms are built in this project

---

## The Problem with Forms in React

### Naive Approach (Controlled Components)

```javascript
// Every keystroke re-renders the entire component
function CreateIssueForm() {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('MEDIUM')
  const [errors, setErrors] = useState({})
  
  function validate() {
    const errors = {}
    if (!title.trim()) errors.title = 'Title is required'
    if (title.length > 200) errors.title = 'Too long'
    if (!description) errors.description = 'Description required'
    return errors
  }
  
  function handleSubmit(e) {
    e.preventDefault()
    const errors = validate()
    if (Object.keys(errors).length > 0) {
      setErrors(errors)
      return
    }
    // submit...
  }
  
  return (
    <form onSubmit={handleSubmit}>
      <input value={title} onChange={e => setTitle(e.target.value)} />
      {errors.title && <span>{errors.title}</span>}
      
      <textarea value={description} onChange={e => setDescription(e.target.value)} />
      {errors.description && <span>{errors.description}</span>}
      
      <select value={priority} onChange={e => setPriority(e.target.value)}>
        <option>MEDIUM</option>
        <option>HIGH</option>
      </select>
      
      <button type="submit">Create</button>
    </form>
  )
}
```

Problems:
- Every keystroke triggers a re-render (performance issue on large forms)
- Validation logic is tangled with component logic
- Manual error state management
- No reusability

---

## React Hook Form

React Hook Form uses **uncontrolled inputs** — the form values are stored in the DOM, not in React state. React only reads the values when needed (on submit or on blur).

```javascript
'use client'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

// Step 1: Define validation schema with Zod
const createIssueSchema = z.object({
  title: z.string()
    .min(1, 'Title is required')
    .max(200, 'Title must be under 200 characters'),
    
  description: z.string()
    .min(1, 'Description is required'),
    
  priority: z.enum(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'], {
    required_error: 'Priority is required'
  }),
  
  assignee_ids: z.array(z.number()).optional(),
})

// Infer TypeScript type from schema
type CreateIssueData = z.infer<typeof createIssueSchema>

function CreateIssueForm({ projectId }) {
  // Step 2: Initialize React Hook Form
  const {
    register,      // Connect inputs to the form
    handleSubmit,  // Wrap your submit handler
    formState: {   // Form state (errors, loading, etc.)
      errors,
      isSubmitting,
    },
    reset,         // Reset form to initial values
    watch,         // Watch a field's value in real-time
  } = useForm({
    // Step 3: Connect Zod schema for validation
    resolver: zodResolver(createIssueSchema),
    defaultValues: {
      priority: 'MEDIUM',
    }
  })
  
  // Step 4: Submit handler (only called if validation passes)
  const onSubmit = async (data) => {
    // data is already validated and typed
    await createIssue({ projectId, ...data })
  }
  
  return (
    // Step 5: Wrap with handleSubmit (validates before calling onSubmit)
    <form onSubmit={handleSubmit(onSubmit)}>
      
      <div>
        {/* Step 6: Register input — connects it to React Hook Form */}
        <input 
          {...register('title')}
          placeholder="Issue title"
        />
        {/* Display validation errors */}
        {errors.title && <span>{errors.title.message}</span>}
      </div>
      
      <div>
        <textarea 
          {...register('description')}
          placeholder="Describe the issue..."
        />
        {errors.description && <span>{errors.description.message}</span>}
      </div>
      
      <div>
        <select {...register('priority')}>
          <option value="LOW">Low</option>
          <option value="MEDIUM">Medium</option>
          <option value="HIGH">High</option>
          <option value="CRITICAL">Critical</option>
        </select>
        {errors.priority && <span>{errors.priority.message}</span>}
      </div>
      
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Creating...' : 'Create Issue'}
      </button>
    </form>
  )
}
```

**Performance**: React Hook Form avoids re-renders on each keystroke. The input values live in the DOM — React only touches the virtual DOM when validation state changes (on blur or submit).

---

## Zod — Schema-Based Validation

Zod lets you define data schemas that validate at runtime and generate TypeScript types.

### Why Zod?

```
Problem: You can't trust any input that comes from outside your code:
  - User form submissions
  - API responses
  - URL parameters
  - LocalStorage values

Zod solution: Define the shape you expect, validate against it, 
get back type-safe data or a clear error.
```

### Zod Schema Building Blocks

```javascript
import { z } from 'zod'

// Primitive types
z.string()
z.number()
z.boolean()
z.date()

// String modifiers
z.string()
  .min(3, 'At least 3 characters')
  .max(100, 'At most 100 characters')
  .email('Must be a valid email')
  .url('Must be a valid URL')
  .regex(/^[a-z]+$/, 'Only lowercase letters')
  .trim()            // Strips whitespace before validation
  .toLowerCase()     // Transforms to lowercase

// Number modifiers
z.number()
  .int('Must be an integer')
  .positive('Must be positive')
  .min(1, 'Minimum 1')
  .max(100, 'Maximum 100')

// Enums
z.enum(['ADMIN', 'DEVELOPER', 'QA', 'VIEWER'])

// Optional and nullable
z.string().optional()           // string | undefined
z.string().nullable()           // string | null
z.string().nullish()            // string | null | undefined

// Arrays
z.array(z.string())
z.array(z.number()).min(1, 'Select at least one')

// Objects
z.object({
  email: z.string().email(),
  password: z.string().min(8),
  role: z.enum(['ADMIN', 'DEVELOPER']).optional()
})

// Union types
z.union([z.string(), z.number()])

// Custom validation
z.string().refine(
  (val) => val.startsWith('ISSUE-'),
  { message: 'Must start with ISSUE-' }
)
```

### Validation Schemas Used in This Project

#### Login Form Schema
```javascript
const loginSchema = z.object({
  email: z.string()
    .email('Please enter a valid email'),
  
  password: z.string()
    .min(1, 'Password is required'),
})
```

#### Register Form Schema
```javascript
const registerSchema = z.object({
  name: z.string()
    .min(2, 'Name must be at least 2 characters')
    .max(50, 'Name is too long'),
    
  email: z.string()
    .email('Please enter a valid email'),
    
  password: z.string()
    .min(8, 'Password must be at least 8 characters')
    .regex(/[A-Z]/, 'Must contain at least one uppercase letter')
    .regex(/[0-9]/, 'Must contain at least one number'),
    
  confirmPassword: z.string(),
}).refine(
  (data) => data.password === data.confirmPassword,
  {
    message: "Passwords don't match",
    path: ['confirmPassword'], // Shows error on confirmPassword field
  }
)
```

#### Create Project Schema
```javascript
const createProjectSchema = z.object({
  name: z.string()
    .min(1, 'Project name is required')
    .max(100, 'Name must be under 100 characters'),
    
  description: z.string()
    .max(1000, 'Description must be under 1000 characters')
    .optional(),
    
  leader_id: z.number({
    required_error: 'Please select a project leader'
  }),
})
```

### Parsing vs Safeparsing

```javascript
const schema = z.object({ email: z.string().email() })

// parse() — throws if validation fails
try {
  const data = schema.parse({ email: 'not-an-email' })
} catch (err) {
  // err.errors = [{ path: ['email'], message: 'Invalid email' }]
}

// safeParse() — returns result object, never throws
const result = schema.safeParse({ email: 'not-an-email' })
if (!result.success) {
  console.log(result.error.issues)  // Array of validation errors
} else {
  console.log(result.data)          // Validated, typed data
}
```

In React Hook Form, the `zodResolver` calls `safeParse` internally and maps errors to the form's error state.

---

## The zodResolver Bridge

```javascript
import { zodResolver } from '@hookform/resolvers/zod'

// How zodResolver works:
function zodResolver(schema) {
  return async (values) => {
    const result = schema.safeParse(values)
    
    if (result.success) {
      return { values: result.data, errors: {} }
    }
    
    // Map Zod errors to React Hook Form error format
    const errors = {}
    result.error.issues.forEach(issue => {
      const path = issue.path.join('.')
      errors[path] = { message: issue.message }
    })
    
    return { values: {}, errors }
  }
}
```

---

## Advanced Form Patterns

### Controlled Select Components

When using custom select components (not native `<select>`), use `Controller`:

```javascript
import { Controller } from 'react-hook-form'

function AssigneeSelect({ control }) {
  return (
    <Controller
      name="assignee_ids"
      control={control}
      render={({ field, fieldState }) => (
        <UserMultiSelect
          value={field.value}
          onChange={field.onChange}
          error={fieldState.error?.message}
        />
      )}
    />
  )
}
```

### Dynamic Fields

```javascript
import { useFieldArray } from 'react-hook-form'

function LabelManager({ control }) {
  const { fields, append, remove } = useFieldArray({
    control,
    name: 'labels'
  })
  
  return (
    <>
      {fields.map((field, index) => (
        <div key={field.id}>
          <input {...register(`labels.${index}.name`)} />
          <button onClick={() => remove(index)}>Remove</button>
        </div>
      ))}
      <button onClick={() => append({ name: '' })}>Add Label</button>
    </>
  )
}
```

### Watch — Live Field Values

```javascript
const watchedPriority = watch('priority')
// Updates as user changes the priority field
// Useful for conditional rendering

{watchedPriority === 'CRITICAL' && (
  <div className="warning">
    Critical issues require immediate attention
  </div>
)}
```

---

## Form State Machine

React Hook Form tracks the form state as a state machine:

```
Initial state
    │ user fills in fields
    ▼
Dirty (has unsaved changes)
    │ user submits
    ▼
Submitting (isSubmitting=true)
    │ validation runs
    ├─► Validation fails → Invalid (errors shown, stays on form)
    │
    └─► Validation passes → onSubmit called
              │
              ├─► API succeeds → Submitted (isSubmitSuccessful=true)
              │
              └─► API fails → throw error → form shows error
```

---

## Error Display Patterns

```javascript
// Inline field errors:
{errors.title && (
  <p role="alert" className="field-error">
    {errors.title.message}
  </p>
)}

// Error summary at top of form:
{Object.keys(errors).length > 0 && (
  <div className="error-summary">
    Please fix the following errors:
    <ul>
      {Object.entries(errors).map(([field, error]) => (
        <li key={field}>{field}: {error.message}</li>
      ))}
    </ul>
  </div>
)}
```

---

## Dual Validation — Frontend & Backend

This project validates on BOTH sides:

```
Frontend (Zod):
  - Fast feedback as user types
  - No unnecessary API calls
  - Client-side only (can be bypassed)

Backend (Pydantic):
  - Server-side authority
  - Cannot be bypassed
  - Database-level constraints as final safety net

Example: Email uniqueness
  Frontend: "Email looks valid" (format check only)
  Backend: "That email is already registered" (database check)
```

---

## Further Reading & Videos

- **YouTube**: Search "React Hook Form Tutorial" — Web Dev Simplified covers it clearly
- **YouTube**: Search "Zod Tutorial TypeScript Validation" — Matt Pocock (total TypeScript)
- **Official Docs**: [React Hook Form documentation](https://react-hook-form.com)
- **Official Docs**: [Zod documentation](https://zod.dev)

---

*Next: [Module 02-05 — Authentication, JWT Flow & Protected Routes](./05-auth-protected-routes.md)*
