import { describe, expect, it } from 'vitest'
import { expressionForMotion, motionForVariant, nextTapMotion, pickAutonomousMotion } from './petMotionMachine'

describe('pet motion machine', () => {
  it('maps semantic notifications to distinct motions', () => {
    expect(motionForVariant('info')).toBe('speaking')
    expect(motionForVariant('success')).toBe('celebrating')
    expect(motionForVariant('warning')).toBe('concerned')
    expect(motionForVariant('error')).toBe('concerned')
  })

  it('selects a compatible fallback pose for every important state', () => {
    expect(expressionForMotion('working')).toBe('working')
    expect(expressionForMotion('bored')).toBe('thinking')
    expect(expressionForMotion('landing')).toBe('celebrate')
    expect(expressionForMotion('surprised')).toBe('surprised')
    expect(expressionForMotion('sleepy')).toBe('sleepy')
    expect(expressionForMotion('stretching')).toBe('stretching')
  })

  it('varies repeated tap reactions', () => {
    expect(nextTapMotion('idle')).toBe('celebrating')
    expect(nextTapMotion('celebrating')).toBe('watching')
    expect(nextTapMotion('watching')).toBe('working')
  })

  it('selects bounded autonomous motions without immediately repeating', () => {
    expect(pickAutonomousMotion(-1, 'idle')).toBe('watching')
    expect(pickAutonomousMotion(1, 'idle')).toBe('sleepy')
    expect(pickAutonomousMotion(0, 'watching')).toBe('bored')
    expect(pickAutonomousMotion(0.65, 'idle')).toBe('working')
    expect(expressionForMotion('watching')).toBe('thinking')
    expect(expressionForMotion('peeking')).toBe('surprised')
  })
})
