export interface PetPositionValue {
  x: number
  y: number
}

export interface PetViewport {
  width: number
  height: number
}

export type PetPeekSide = 'left' | 'right'

const RIGHT_MARGIN = 8
const BOTTOM_MARGIN = 8
const VISIBLE_WIDTH = 150
const VISIBLE_HEIGHT = 160

export function clampPetPosition(position: PetPositionValue, viewport: PetViewport): PetPositionValue {
  return {
    x: Math.min(RIGHT_MARGIN, Math.max(-viewport.width + VISIBLE_WIDTH, position.x)),
    y: Math.min(BOTTOM_MARGIN, Math.max(-viewport.height + VISIBLE_HEIGHT, position.y)),
  }
}

export function peekSideForPosition(position: PetPositionValue, viewport: PetViewport): PetPeekSide | null {
  if (position.x >= -8) return 'right'
  if (position.x <= -viewport.width + VISIBLE_WIDTH + 25) return 'left'
  return null
}

export function positionAfterPeek(position: PetPositionValue, viewport: PetViewport, side: PetPeekSide): PetPositionValue {
  const x = side === 'right' ? -92 : -viewport.width + VISIBLE_WIDTH + 112
  return clampPetPosition({ x, y: position.y }, viewport)
}
