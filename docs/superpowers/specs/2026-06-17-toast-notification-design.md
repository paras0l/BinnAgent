# Toast Notification System Design

**Date**: 2026-06-17
**Topic**: Unified User Notification System
**Design File**: `docs/superpowers/specs/2026-06-17-toast-notification-design.md`

## Overview

This design documents the unified toast notification system for BinnAgent. User-facing transient notifications should use this system instead of ad hoc banners, console logs, alert dialogs, or page-local message state unless the message must remain visible as part of the page content.

## Requirements

### Core Requirements
- **Unified API**: Business code calls `useToast().showToast(message, options)`.
- **Variants**: `info`, `success`, `warning`, and `error`.
- **Timing**: Auto-dismiss defaults to 4 seconds; important warnings may extend to 5-7 seconds.
- **Style**: Matches the existing BinnAgent card/header design system.
- **Position**: Fixed top-center, below the app header on authenticated pages.
- **Focus behavior**: Toasts must never request focus, move focus, or block keyboard flow.
- **Queue behavior**: Show at most three active toasts; newest notifications remain visible.
- **Pause behavior**: Hovering, focusing, or clicking a toast pauses its dismissal countdown. Clicking a paused toast resumes it. The close button only dismisses the toast.

### User Experience Goals
1. **Visible**: Notifications appear in one predictable, prominent area.
2. **Non-intrusive**: Notifications do not block user workflow or steal focus.
3. **Clear timing**: A progress bar shows remaining time before dismissal.
4. **Accessible**: Screen reader support uses a polite live region.
5. **Consistent**: Follows existing BinnAgent design patterns.
6. **Responsive**: Works across all device sizes.

## Architecture

### Component Structure

```typescript
// Core components
ToastProvider - State management and context
ToastContainer - Portal-based container
Toast - Individual toast component
ToastProgress - Auto-dismiss progress indicator
ToastIcon - Visual indicator (info/success/warning/error)

// Data types
interface ToastState {
  id: string
  message: string
  title?: string
  variant: 'info' | 'success' | 'warning' | 'error'
  duration: number
}
```

### Technical Architecture

1. **ToastContext**: Manages toast state and lifecycle
2. **Portal Rendering**: Renders to document.body to avoid z-index issues
3. **Animation System**: CSS-based animations for smooth transitions
4. **Hook API**: Pages and components trigger notifications through `useToast`

## Visual Design

### Design System (matching existing Header component)

**Colors**:
- Primary: `--primary` (from existing design)
- Secondary: `--muted-foreground`
- Background: `rgba(255, 255, 255, 0.95)` with backdrop blur
- Border: `--border` with subtle opacity

**Typography**:
- Font size: `14px` (consistent with Header buttons)
- Line height: `1.4`
- Font weight: `500` (medium weight)

**Spacing & Layout**:
- Border radius: `8px` (matches Header button radius)
- Padding: `16px`, with right padding for the close button
- Icon size: `16px`
- Max width: `448px` (prevents overflow while allowing readable Chinese text)

### Visual Mockup

```
┌─────────────────────────┐
│                         │
│   ┌─────────────────┐   │
│   │                 │   │
│   │  ⚠️  已清空当前 │   │  ← top-center toast with warning icon
│   │  知识点的 HTML。 │   │
│   │  下一次返回的新 │   │
│   │  HTML 会覆盖缓存。│ │
│   │                 │   │
│   │  [⏱️ 3s]         │   │  ← Progress bar (3s remaining)
│   └─────────────────┘   │
└─────────────────────────┘
```

### Animation Specifications

**Enter**:
```css
@keyframes toast-enter {
  from { transform: translateY(-0.75rem) scale(0.98); opacity: 0; }
  to { transform: translateY(0) scale(1); opacity: 1; }
}
```

**Progress**:
```css
@keyframes toast-progress {
  from { transform: scaleX(1); }
  to { transform: scaleX(0); }
}
```

**Duration**: 180ms for entry. Reduced-motion users receive no animation.

## User Interaction Flow

### 1. Trigger
- User action or async result needs transient feedback.
- Component calls `showToast(message, { variant, duration, title })`.

### 2. Display
- Toast appears at the top-center of the viewport
- Progress bar starts at 100% and counts down to 0
- Toast remains visible for its configured duration

### 3. User Controls
- **Manual dismiss**: User can click the close button at any time
- **Auto-dismiss**: Toast automatically disappears after its configured duration
- **Pause/resume**: Hover or keyboard focus pauses while the pointer/focus remains on the toast. A direct toast click pins the pause state; another click resumes the countdown.
- **Progress indication**: Visual countdown shows remaining time
- **No focus capture**: The toast does not call `focus()` and does not require acknowledgement

### 4. Cleanup
- Toast fades out and slides out
- Component is removed from DOM after animation completes

## Technical Implementation

### Component API

```typescript
interface ToastProps {
  id: string
  message: string
  title?: string
  duration?: number // default: 3000ms
  onDismiss: (id: string) => void
  variant?: 'info' | 'success' | 'warning' | 'error' // default: 'info'
}

interface ToastContextValue {
  showToast: (message: string, options?: ToastOptions) => string
  hideToast: (id: string) => void
}
```

### Key Features

1. **Portal Rendering**: Renders to document.body to avoid stacking context issues
2. **Animation Control**: Uses CSS animations with JavaScript timing control
3. **Accessibility**: Full ARIA support for screen readers
4. **Focus Safety**: Close buttons are keyboard reachable when the user tabs naturally, but toast display never steals focus
5. **Responsive Design**: Adapts to different screen sizes
6. **Performance**: Efficient lifecycle management

### Accessibility Implementation

```typescript
// ARIA attributes
aria-live="polite" // For screen readers
aria-atomic="true" // Entire message announced
role="status" // Important but non-interruptive
aria-label="Notification: [message]" // Custom label
```

### Animation Implementation

```typescript
// Animation timing
const ANIMATION_DURATION = 300 //ms
const AUTO_DISMISS_DURATION = 3000 //ms

// Animation classes
toast-enter
toast-progress
```

## Integration Points

### Page Integration

```typescript
// Example integration with button that clears cache
const { showToast } = useToast()

const handleCacheClear = () => {
  // Clear HTML cache logic
  showToast('已清空当前知识点的 HTML。下一次返回的新 HTML 会覆盖缓存。', {
    duration: 5000,
    variant: 'warning'
  })
}
```

### Usage Rules

- Use toast for transient success, warning, recoverable error, copy, save, delete, cache, and lock-state feedback.
- Keep inline page errors only for blocking states that must remain visible, such as a failed page load with a retry button.
- Do not use `window.alert` or `console.log` as user notification.
- Do not create page-local `message` state for transient notifications.

## Testing Strategy

### Unit Tests
- Component rendering and props validation
- Animation state transitions
- Accessibility attribute verification
- Event handling and lifecycle management

### Integration Tests
- Toast context provider functionality
- Portal rendering verification
- Event emitter integration
- Button click integration

### User Acceptance Tests
- Visual regression testing
- User interaction flow validation
- Responsive design verification
- Accessibility compliance testing

## Performance Considerations

1. **Lazy Loading**: Toast components loaded only when needed
2. **Animation Optimization**: Hardware-accelerated CSS animations
3. **Memory Management**: Proper cleanup of animation timers
4. **Bundle Size**: Tree-shaken components for smaller bundles

## Migration & Deployment

### Phase 1: Development
- Implement core Toast components
- Integrate with existing button/feature
- Add basic styling and animations

### Phase 2: Testing
- Unit and integration testing
- Accessibility testing
- Cross-browser compatibility

### Phase 3: Production
- Gradual rollout to users
- Performance monitoring
- User feedback collection

## Files to Modify

### New Files
- `binnagent-frontend/src/components/ui/Toast.tsx` - Toast component
- `binnagent-frontend/src/components/ui/ToastContext.ts` - Context type and hook API contract
- `binnagent-frontend/src/components/ui/ToastProvider.tsx` - Context provider and portal container
- `binnagent-frontend/src/hooks/useToast.ts` - Custom hook for toast functionality

### Modified Files
- `binnagent-frontend/src/main.tsx` - Wraps the whole app in `ToastProvider`
- `binnagent-frontend/src/App.tsx` - Uses toast for app-level locked actions
- `binnagent-frontend/src/pages/*.tsx` - Use `useToast` for transient feedback

## Dependencies

### Required
- React (for component architecture)
- TypeScript (for type safety)

### Optional
- Framer Motion (for enhanced animations)
- React Portal (for portal rendering)

## Risk Assessment

### Low Risk
- Component architecture is straightforward
- Design follows existing patterns
- Integration points are clear

### Medium Risk
- Animation timing and transitions
- Accessibility implementation
- Performance on slower devices

### High Risk
- None identified

## Success Metrics

1. **User Satisfaction**: Positive feedback on notification usefulness
2. **Performance**: No impact on page load times
3. **Accessibility**: WCAG 2.1 AA compliance
4. **Usability**: Intuitive user interaction patterns
5. **Maintainability**: Clean, well-documented code

## Conclusion

The Toast Notification System provides a non-intrusive, user-friendly way to inform users about HTML cache clearing operations. By following the existing BinnAgent design system and implementing robust accessibility features, this system enhances the user experience while maintaining consistency with the application.

The design is ready for implementation and will significantly improve the user experience when HTML cache clearing occurs.
