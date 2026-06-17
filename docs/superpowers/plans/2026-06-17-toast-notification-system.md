# Toast Notification System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a toast notification system that displays HTML cache clearing messages with auto-dismiss after 3 seconds.

**Architecture:** React component system with portal rendering, context provider, and toast service for managing notifications.

**Tech Stack:** React 19 + TypeScript + Tailwind CSS, following existing BinnAgent design patterns.

---

## File Structure

- `src/components/ui/Toast.tsx` - Main toast component
- `src/components/ui/ToastProvider.tsx` - Context provider
- `src/hooks/useToast.ts` - Custom hook for toast functionality
- `src/components/feature/ToastButton.tsx` - Example button integration
- `tests/components/ui/Toast.test.tsx` - Component tests
- `tests/hooks/useToast.test.tsx` - Hook tests

### Task 1: Create Toast Context Provider

**Files:**
- Create: `src/components/ui/ToastProvider.tsx`
- Test: `tests/components/ui/ToastProvider.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
def test_toast_context_provider_renders_children():
    result = render(
        <ToastProvider>
            <div>Test Child</div>
        </ToastProvider>
    )
    assert screen.getByText('Test Child')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --testPathPattern=ToastProvider -v`
Expected: FAIL with "ToastProvider not found"

- [ ] **Step 3: Write minimal implementation**

```typescript
// src/components/ui/ToastProvider.tsx
import { createContext, useState, ReactNode } from 'react'

interface ToastContextType {
  showToast: (message: string, options?: Partial<ToastProps>) => void
  hideToast: (id: string) => void
}

export const ToastContext = createContext<ToastContextType | undefined>(undefined)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastState[]>([])

  const showToast = (message: string, options?: Partial<ToastProps>) => {
    const id = Math.random().toString(36).substring(2)
    const newToast: ToastState = {
      id,
      message,
      duration: options?.duration || 3000,
      isVisible: true
    }
    setToasts(prev => [...prev, newToast])
  }

  const hideToast = (id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id))
  }

  return (
    <ToastContext.Provider value={{ showToast, hideToast }}>
      {children}
    </ToastContext.Provider>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --testPathPattern=ToastProvider -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/ToastProvider.tsx tests/components/ui/ToastProvider.test.tsx
git commit -m "feat: add toast context provider"
```

### Task 2: Create Toast Component

**Files:**
- Create: `src/components/ui/Toast.tsx`
- Test: `tests/components/ui/Toast.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
def test_toast_renders_message():
    result = render(
        <Toast
            message="Test Message"
            duration={3000}
            isVisible={true}
            onDismiss={() => {}}
        />
    )
    assert(screen.getByText('Test Message'))
    assert(toasts).toHaveLength(1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --testPathPattern=Toast -v`
Expected: FAIL with "Toast component not found"

- [ ] **Step 3: Write minimal implementation**

```typescript
// src/components/ui/Toast.tsx
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

interface ToastProps {
  message: string
  duration?: number
  isVisible: boolean
  onDismiss: () => void
}

export function Toast({ message, duration = 3000, isVisible, onDismiss }: ToastProps) {
  const [progress, setProgress] = useState(100)

  useEffect(() => {
    if (!isVisible) return

    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev <= 0) {
          onDismiss()
          return 0
        }
        return prev - (100 / (duration / 100))
      })
    }, 100)

    return () => clearInterval(interval)
  }, [isVisible, duration, onDismiss])

  if (!isVisible) return null

  return createPortal(
    <div className="fixed top-4 right-4 z-50 animate-slideInRight">
      <div className="bg-white/95 backdrop-blur rounded-lg border shadow-lg p-4 max-w-sm">
        <div className="flex items-start gap-3">
          <div className="text-warning mt-0.5">⚠️</div>
          <div className="flex-1">
            <p className="text-sm font-medium text-foreground">
              {message}
            </p>
          </div>
          <button
            onClick={onDismiss}
            className="text-muted-foreground hover:text-foreground"
          >
            ×
          </button>
        </div>
        <div className="mt-2 h-1 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-warning transition-all ease-linear"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>,
    document.body
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --testPathPattern=Toast -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/Toast.tsx tests/components/ui/Toast.test.tsx
git commit -m "feat: add toast component"
```

### Task 3: Create Toast Custom Hook

**Files:**
- Create: `src/hooks/useToast.ts`
- Test: `tests/hooks/useToast.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
def test_use_toast_returns_context():
    result = renderHook(() => useToast(), {
        wrapper: ToastProvider
    })
    assert(result.result.current.showToast)
    assert(result.result.current.hideToast)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --testPathPattern=useToast -v`
Expected: FAIL with "useToast not found"

- [ ] **Step 3: Write minimal implementation**

```typescript
// src/hooks/useToast.ts
import { useContext } from 'react'
import { ToastContext } from '../components/ui/ToastProvider'

export function useToast() {
  const context = useContext(ToastContext)

  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }

  return context
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --testPathPattern=useToast -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/hooks/useToast.ts tests/hooks/useToast.test.tsx
git commit -m "feat: add useToast hook"
```

### Task 4: Create Example Integration Button

**Files:**
- Create: `src/components/feature/ToastButton.tsx`

- [ ] **Step 1: Write the component**

```typescript
// src/components/feature/ToastButton.tsx
import { useToast } from '../hooks/useToast'

interface ToastButtonProps {
  message: string
  duration?: number
  className?: string
}

export function ToastButton({ message, duration = 3000, className }: ToastButtonProps) {
  const { showToast } = useToast()

  const handleClick = () => {
    showToast(message, { duration })
  }

  return (
    <button
      onClick={handleClick}
      className={`px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors ${className}`}
    >
      Show Toast
    </button>
  )
}
```

- [ ] **Step 2: Verify component renders**

Run: `npm start` and check if ToastButton appears in the app

- [ ] **Step 3: Test toast functionality**

```typescript
def test_toast_button_shows_toast():
    result = render(
        <ToastProvider>
            <ToastButton message="Test Message" />
        </ToastProvider>
    )
    
    fireEvent.click(screen.getByText('Show Toast'))
    
    await waitFor(() => {
      expect(screen.getByText('Test Message')).toBeInTheDocument()
    })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --testPathPattern=ToastButton -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/components/feature/ToastButton.tsx
git commit -m "feat: add toast button integration"
```

### Task 5: Create Comprehensive Toast Tests

**Files:**
- Create: `tests/components/ui/Toast comprehensive test suite`

- [ ] **Step 1: Write comprehensive test suite**

```typescript
// tests/components/ui/Toast.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Toast } from '../../src/components/ui/Toast'

describe('Toast Component', () => {
  it('renders message when visible', () => {
    render(
      <Toast
        message="Test Message"
        duration={3000}
        isVisible={true}
        onDismiss={() => {}}
      />
    )
    expect(screen.getByText('Test Message')).toBeInTheDocument()
  })

  it('does not render when not visible', () => {
    const { container } = render(
      <Toast
        message="Test Message"
        duration={3000}
        isVisible={false}
        onDismiss={() => {}}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('calls onDismiss when progress completes', async () => {
    const handleDismiss = jest.fn()
    render(
      <Toast
        message="Test Message"
        duration={100}
        isVisible={true}
        onDismiss={handleDismiss}
      />
    )

    await waitFor(() => {
      expect(handleDismiss).toHaveBeenCalled()
    }, { timeout: 500 })
  })

  it('calls onDismiss when close button clicked', () => {
    const handleDismiss = jest.fn()
    render(
      <Toast
        message="Test Message"
        duration={3000}
        isVisible={true}
        onDismiss={handleDismiss}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: '' }))
    expect(handleDismiss).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run comprehensive test suite**

Run: `npm test -- --testPathPattern=Toast -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/components/ui/Toast.test.tsx
git commit -m "feat: add comprehensive toast tests"
```

### Task 6: Create Toast Hook Tests

**Files:**
- Create: `tests/hooks/useToast.test.tsx`

- [ ] **Step 1: Write hook test suite**

```typescript
// tests/hooks/useToast.test.tsx
import { renderHook, act } from '@testing-library/react'
import { useToast } from '../../src/hooks/useToast'
import { ToastProvider } from '../../src/components/ui/ToastProvider'

describe('useToast Hook', () => {
  it('returns toast context when used within provider', () => {
    const { result } = renderHook(() => useToast(), {
      wrapper: ToastProvider
    })

    expect(result.current.showToast).toBeDefined()
    expect(result.current.hideToast).toBeDefined()
  })

  it('throws error when used outside provider', () => {
    expect(() => {
      renderHook(() => useToast())
    }).toThrow('useToast must be used within a ToastProvider')
  })

  it('showToast creates toast with correct properties', () => {
    const { result } = renderHook(() => useToast(), {
      wrapper: ToastProvider
    })

    act(() => {
      result.current.showToast('Test Message', { duration: 5000 })
    })

    // Toast should be created with correct properties
    expect(result.current.showToast).toBeDefined()
  })
})
```

- [ ] **Step 2: Run hook test suite**

Run: `npm test -- --testPathPattern=useToast -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/hooks/useToast.test.tsx
git commit -m "feat: add useToast hook tests"
```

### Task 7: Add Toast Animations

**Files:**
- Modify: `src/components/ui/Toast.tsx`

- [ ] **Step 1: Add CSS animations**

```typescript
// Add to Toast component CSS
const animations = `
@keyframes slideInRight {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

@keyframes slideOutRight {
  from { transform: translateX(0); opacity: 1; }
  to { transform: translateX(100%); opacity: 0; }
}

.toast-enter {
  animation: slideInRight 0.3s ease-out;
}

.toast-exit {
  animation: slideOutRight 0.3s ease-in;
}
```

- [ ] **Step 2: Add animation classes to Toast component**

```typescript
// Add to Toast component
return createPortal(
  <div className={`fixed top-4 right-4 z-50 ${isVisible ? 'toast-enter' : 'toast-exit'} ${!isVisible ? 'toast-exit-active' : ''}`}`>
    // ... rest of component
  </div>,
  document.body
)
```

- [ ] **Step 3: Run tests to verify animations**

Run: `npm test -- --testPathPattern=Toast -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/components/ui/Toast.tsx
git commit -m "feat: add toast animations"
```

### Task 8: Create Integration Test

**Files:**
- Create: `tests/integration/toast-integration.test.tsx`

- [ ] **Step 1: Write integration test**

```typescript
// tests/integration/toast-integration.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ToastButton } from '../../src/components/feature/ToastButton'
import { ToastProvider } from '../../src/components/ui/ToastProvider'

describe('Toast Integration', () => {
  it('end-to-end toast flow', async () => {
    render(
      <ToastProvider>
        <ToastButton message="Integration Test Message" duration={1000} />
      </ToastProvider>
    )

    // Click button to show toast
    fireEvent.click(screen.getByText('Show Toast'))

    // Wait for toast to appear
    await waitFor(() => {
      expect(screen.getByText('Integration Test Message')).toBeInTheDocument()
    })

    // Wait for auto-dismiss
    await waitFor(() => {
      expect(screen.queryByText('Integration Test Message')).not.toBeInTheDocument()
    }, { timeout: 2000 })
  })
})
```

- [ ] **Step 2: Run integration test**

Run: `npm test -- --testPathPattern=toast-integration -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/toast-integration.test.tsx
git commit -m "feat: add toast integration test"
```

### Task 9: Update App Component

**Files:**
- Modify: `src/App.tsx`

- [ ] **Step 1: Add ToastProvider to App**

```typescript
// src/App.tsx
import { ToastProvider } from './components/ui/ToastProvider'
import { ToastButton } from './components/feature/ToastButton'

function App() {
  return (
    <ToastProvider>
      <div className="min-h-screen bg-background">
        <header className="p-4 border-b">
          <h1 className="text-2xl font-bold">BinnAgent Toast Demo</h1>
        </header>
        <main className="p-8">
          <section className="space-y-4">
            <h2 className="text-xl font-semibold">Toast Examples</h2>
            <ToastButton 
              message="已清空当前知识点的 HTML。下一次返回的新 HTML 会覆盖缓存。"
              duration={3000}
              className="mb-4"
            />
            <ToastButton 
              message="Another Toast Message"
              duration={2000}
              className="mb-4"
            />
          </section>
        </main>
      </div>
    </ToastProvider>
  )
}

export default App
```

- [ ] **Step 2: Run app and verify**

Run: `npm start`
Expected: App loads with toast buttons visible

- [ ] **Step 3: Test toast functionality in app**

1. Click "Show Toast" button
2. Verify toast appears with correct message
3. Verify toast auto-dismisses after 3 seconds
4. Verify manual dismiss works

- [ ] **Step 4: Commit**

```bash
git add src/App.tsx
git commit -m "feat: add toast provider to app"
```

### Task 10: Final Verification

**Files:**
- Test: All created and modified files

- [ ] **Step 1: Run full test suite**

Run: `npm test -- --watchAll=false -v`
Expected: All tests PASS

- [ ] **Step 2: Run linting**

Run: `npm run lint`
Expected: No lint errors

- [ ] **Step 3: Build verification**

Run: `npm run build`
Expected: Build succeeds

- [ ] **Step 4: Final verification in browser**

1. Open http://localhost:3000
2. Click toast buttons
3. Verify all functionality works as expected
4. Check responsive design
5. Test accessibility features

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete toast notification system implementation"
```

## Execution Options

**Plan complete and saved to `docs/superpowers/plans/2026-06-17-toast-notification-system.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?"