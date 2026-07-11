import type { ToastVariant } from './ToastContext'

export type PetMotionState =
  | 'idle'
  | 'watching'
  | 'speaking'
  | 'celebrating'
  | 'concerned'
  | 'working'
  | 'dragging'
  | 'landing'
  | 'bored'
  | 'surprised'
  | 'sleepy'
  | 'stretching'
  | 'peeking'

export type PetExpression = 'hello' | 'thinking' | 'working' | 'celebrate' | 'surprised' | 'sleepy' | 'stretching'

const AUTONOMOUS_MOTIONS: readonly PetMotionState[] = ['watching', 'watching', 'bored', 'working', 'stretching', 'sleepy']

export function pickAutonomousMotion(randomValue: number, previous: PetMotionState): PetMotionState {
  const safeRandom = Math.max(0, Math.min(0.999999, randomValue))
  let index = Math.floor(safeRandom * AUTONOMOUS_MOTIONS.length)
  let attempts = 0
  while (AUTONOMOUS_MOTIONS[index] === previous && attempts < AUTONOMOUS_MOTIONS.length) {
    index = (index + 1) % AUTONOMOUS_MOTIONS.length
    attempts += 1
  }
  return AUTONOMOUS_MOTIONS[index]
}

export function motionForVariant(variant: ToastVariant): PetMotionState {
  if (variant === 'success') return 'celebrating'
  if (variant === 'warning' || variant === 'error') return 'concerned'
  return 'speaking'
}

export function expressionForMotion(motion: PetMotionState): PetExpression {
  if (motion === 'celebrating' || motion === 'landing') return 'celebrate'
  if (motion === 'concerned' || motion === 'bored') return 'thinking'
  if (motion === 'working') return 'working'
  if (motion === 'watching') return 'thinking'
  if (motion === 'surprised') return 'surprised'
  if (motion === 'sleepy') return 'sleepy'
  if (motion === 'stretching') return 'stretching'
  if (motion === 'peeking') return 'surprised'
  return 'hello'
}

export function nextTapMotion(previous: PetMotionState): PetMotionState {
  if (previous === 'celebrating') return 'watching'
  if (previous === 'watching') return 'working'
  return 'celebrating'
}
