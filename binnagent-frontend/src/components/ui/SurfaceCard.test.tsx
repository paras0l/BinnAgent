import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { SurfaceCard } from './SurfaceCard'

describe('SurfaceCard', () => {
  it('raises focused controls above later backdrop stacking contexts', () => {
    const html = renderToString(<SurfaceCard><button type="button">Open</button></SurfaceCard>)

    expect(html).toContain('relative')
    expect(html).toContain('focus-within:z-20')
    expect(html).toContain('backdrop-blur-sm')
  })
})
