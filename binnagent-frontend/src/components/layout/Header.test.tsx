import { describe, expect, it } from 'vitest'
import source from './Header.tsx?raw'

describe('Header', () => {
  it('starts expanded, then keeps the original scroll-collapse interaction', () => {
    expect(source).toContain('useState(false)')
    expect(source).toContain('suppressCollapseUntilRef.current = Date.now() + 1200')
    expect(source).toContain("window.addEventListener('scroll'")
    expect(source).toContain('展开顶部菜单')
    expect(source).toContain('scrollDelta > 0')
  })
})
