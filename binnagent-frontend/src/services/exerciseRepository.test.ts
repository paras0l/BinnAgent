import { describe, expect, it } from 'vitest'
import { BUILTIN_EXERCISES } from '@/data/exercises/builtinExercises'
import { getExercisesForTarget, normalizeExerciseTargetId } from './exerciseRepository'

describe('exerciseRepository', () => {
  it('returns exercises by exact target type and id with a limit', () => {
    const exercises = getExercisesForTarget(
      { type: 'grammar_topic', id: 'present-for-future', label: '主将从现' },
      { limit: 1 },
    )

    expect(exercises).toHaveLength(1)
    expect(exercises[0]?.target).toMatchObject({
      type: 'grammar_topic',
      id: 'present-for-future',
    })
  })

  it('returns an empty array when the target has no builtin exercises', () => {
    expect(
      getExercisesForTarget({ type: 'grammar_topic', id: 'missing-topic', label: 'Missing' }),
    ).toEqual([])
  })

  it('keeps target metadata on every builtin exercise item', () => {
    expect(BUILTIN_EXERCISES.every((exercise) => exercise.target.type && exercise.target.id)).toBe(true)
  })

  it('normalizes vocabulary terms to stable target ids', () => {
    expect(normalizeExerciseTargetId('Look up')).toBe('look-up')
    expect(normalizeExerciseTargetId('significant')).toBe('significant')
  })
})
