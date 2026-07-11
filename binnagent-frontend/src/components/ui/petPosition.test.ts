import { describe, expect, it } from 'vitest'
import { clampPetPosition, peekSideForPosition, positionAfterPeek } from './petPosition'

describe('pet position', () => {
  const viewport = { width: 1280, height: 720 }

  it('keeps a valid position unchanged', () => {
    expect(clampPetPosition({ x: -120, y: -80 }, viewport)).toEqual({ x: -120, y: -80 })
  })

  it('recovers a pet saved beyond every viewport edge', () => {
    expect(clampPetPosition({ x: -5000, y: -5000 }, viewport)).toEqual({ x: -1130, y: -560 })
    expect(clampPetPosition({ x: 5000, y: 5000 }, viewport)).toEqual({ x: 8, y: 8 })
  })

  it('re-clamps the position for a smaller viewport', () => {
    expect(clampPetPosition({ x: -900, y: -500 }, { width: 640, height: 480 })).toEqual({ x: -490, y: -320 })
  })

  it('detects both screen edges as peek zones', () => {
    expect(peekSideForPosition({ x: 0, y: -20 }, viewport)).toBe('right')
    expect(peekSideForPosition({ x: -1110, y: -20 }, viewport)).toBe('left')
    expect(peekSideForPosition({ x: -200, y: -20 }, viewport)).toBeNull()
  })

  it('moves the pet back into the viewport after a peek click', () => {
    expect(positionAfterPeek({ x: 0, y: -20 }, viewport, 'right')).toEqual({ x: -92, y: -20 })
    expect(positionAfterPeek({ x: -1130, y: -20 }, viewport, 'left')).toEqual({ x: -1018, y: -20 })
  })
})
