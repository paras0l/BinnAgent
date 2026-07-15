import { afterEach, describe, expect, it, vi } from 'vitest'
import appSource from '@/App.tsx?raw'
import type { ReadingMaterialHistoryItem } from '@/data/readingWorkshop'
import exploreSource from '@/pages/ExplorePage.tsx?raw'
import knowledgeBaseSource from '@/pages/KnowledgeBasePage.tsx?raw'
import {
  deriveReadingSourceLabel,
  normalizeReadingWorkshopDraft,
  readReadingWorkshopDraft,
  readingDraftPersistenceAction,
  readingMaterialDraftScope,
  runWithReadingNavigationBlocker,
  writeReadingWorkshopDraft,
  type ReadingWorkshopDraftV1,
} from '@/data/readingWorkshopSession'

const UNTITLED_HISTORY_ITEM: ReadingMaterialHistoryItem = {
  id: 'material-history-2',
  learner_id: 'learner-1',
  title: null,
  text: 'Readers change speed when a sentence becomes difficult.',
  level: 'general',
  goal: 'mixed',
  material_type: 'passage',
  word_count: 8,
  sentence_count: 1,
  source: 'unit_llm_generation',
  generation_context: {
    source_title: 'Grade 7 English',
    unit_title: 'Reading Strategies',
  },
  created_at: '2026-07-14T00:00:00Z',
  updated_at: '2026-07-14T00:00:00Z',
}

function buildDraft(scopeId: string, text: string): ReadingWorkshopDraftV1 {
  return {
    version: 2,
    learnerId: 'learner-1',
    scopeId,
    savedAt: Date.now(),
    workspace: 'extensive',
    material: { title: '', text, level: 'general', goal: 'mixed', material_type: 'passage' },
    extensiveNotes: { gist: '', attitude: '', paragraphFunction: '', centralSentence: '' },
    intensiveNotesBySentenceId: {},
    selectedSentenceId: null,
    selectedGrammarOptionIds: [],
    openedGrammarTopics: [],
    coachThreadId: null,
    coachMessages: [],
    coachDraft: '',
    activeMaterialId: null,
    activeMaterialRecord: null,
    saveStatus: 'idle',
    titleMode: 'empty',
    titleSuggestionStatus: 'idle',
    autoTitleSourceText: '',
    clientAttemptId: 'attempt-session-1',
    attemptSubmitted: false,
    lastSubmittedEvidenceFingerprint: null,
    completeStatus: 'idle',
    completionResult: null,
  }
}

function createLocalStorageMock() {
  const values = new Map<string, string>()
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('ReadingWorkshopPage session helpers', () => {
  it('recovers an untitled saved material and replaces an invalid attempt id', () => {
    const draft = normalizeReadingWorkshopDraft({
      version: 1,
      learnerId: 'learner-1',
      savedAt: Date.now(),
      workspace: 'intensive',
      material: {
        title: '',
        text: UNTITLED_HISTORY_ITEM.text,
        level: 'general',
        goal: 'mixed',
        material_type: 'passage',
      },
      extensiveNotes: {
        gist: 'Readers adjust their strategy.',
        attitude: '',
        paragraphFunction: '',
        centralSentence: UNTITLED_HISTORY_ITEM.text,
      },
      intensiveNotesBySentenceId: {},
      selectedSentenceId: null,
      selectedGrammarOptionIds: [],
      openedGrammarTopics: [],
      coachThreadId: 'thread-1',
      coachMessages: [{ id: 'message-1', role: 'assistant', content: 'Try the main verb first.' }],
      coachDraft: '',
      activeMaterialId: UNTITLED_HISTORY_ITEM.id,
      activeMaterialRecord: UNTITLED_HISTORY_ITEM,
      saveStatus: 'saved',
      titleMode: 'empty',
      titleSuggestionStatus: 'idle',
      autoTitleSourceText: '',
      clientAttemptId: 'bad',
    }, 'learner-1')

    expect(draft?.activeMaterialRecord?.title).toBeNull()
    expect(draft?.saveStatus).toBe('saved')
    expect(draft?.coachMessages).toHaveLength(1)
    expect(draft?.clientAttemptId.length).toBeGreaterThanOrEqual(8)
  })

  it('derives the displayed source from the active record after a material switch', () => {
    expect(deriveReadingSourceLabel({
      record: UNTITLED_HISTORY_ITEM,
      initialMaterialId: 'material-history-1',
      initialSourceLabel: 'Old textbook · Old unit',
    })).toBe('Grade 7 English · Reading Strategies')

    expect(deriveReadingSourceLabel({
      record: { ...UNTITLED_HISTORY_ITEM, id: 'material-history-1' },
      initialMaterialId: 'material-history-1',
      initialSourceLabel: 'Current textbook · Current unit',
    })).toBe('Current textbook · Current unit')
  })

  it('keeps scratch and explicit material drafts in separate buckets', () => {
    vi.stubGlobal('window', { localStorage: createLocalStorageMock() })
    const scratch = buildDraft(readingMaterialDraftScope(null), 'Scratch article A.')
    const materialB = buildDraft(readingMaterialDraftScope('material-b'), 'Textbook article B.')

    writeReadingWorkshopDraft(scratch)
    writeReadingWorkshopDraft(materialB)

    expect(readReadingWorkshopDraft('learner-1', 'scratch')?.material.text).toBe('Scratch article A.')
    expect(readReadingWorkshopDraft('learner-1', 'material:material-b')?.material.text).toBe('Textbook article B.')
  })

  it('lets a generic entry follow the active material scope after scratch is saved', () => {
    vi.stubGlobal('window', { localStorage: createLocalStorageMock() })
    writeReadingWorkshopDraft(buildDraft('scratch', 'Unsaved scratch.'))
    writeReadingWorkshopDraft({
      ...buildDraft('material:saved-1', 'Saved scratch.'),
      activeMaterialId: 'saved-1',
      saveStatus: 'saved',
    })

    expect(readReadingWorkshopDraft('learner-1')?.scopeId).toBe('material:saved-1')
    expect(readReadingWorkshopDraft('learner-1')?.material.text).toBe('Saved scratch.')
  })

  it('restores completed and uncertain submission state consistently', () => {
    const completed = normalizeReadingWorkshopDraft({
      ...buildDraft('material:completed', 'Completed article.'),
      attemptSubmitted: true,
      completeStatus: 'completed',
      completionResult: {
        material_id: 'completed',
        attempt_id: 'attempt-1',
        reading_value: 12,
        message: 'saved',
      },
    }, 'learner-1', 'material:completed')
    const uncertain = normalizeReadingWorkshopDraft({
      ...buildDraft('material:uncertain', 'Uncertain article.'),
      attemptSubmitted: true,
      lastSubmittedEvidenceFingerprint: 'reading-evidence-1234',
    }, 'learner-1', 'material:uncertain')

    expect(completed?.completeStatus).toBe('completed')
    expect(completed?.completionResult?.attempt_id).toBe('attempt-1')
    expect(uncertain?.completeStatus).toBe('error')
    expect(uncertain?.attemptSubmitted).toBe(true)
  })

  it('treats a valid legacy attempt id as potentially submitted', () => {
    const legacyDraft = normalizeReadingWorkshopDraft({
      ...buildDraft('scratch', 'Legacy article.'),
      version: 1,
      clientAttemptId: 'legacy-attempt-123',
    }, 'learner-1')

    expect(legacyDraft?.clientAttemptId).toBe('legacy-attempt-123')
    expect(legacyDraft?.attemptSubmitted).toBe(true)
    expect(legacyDraft?.completeStatus).toBe('error')
  })

  it('defers guarded navigation until confirmation and skips draft resurrection after discard', () => {
    const navigate = vi.fn()
    let runPendingNavigation: () => void = () => {
      throw new Error('Expected a pending navigation callback')
    }
    const result = runWithReadingNavigationBlocker((pending) => {
      runPendingNavigation = pending
      return true
    }, navigate)

    expect(result).toBe('blocked')
    expect(navigate).not.toHaveBeenCalled()
    expect(readingDraftPersistenceAction({ skipPersist: true, hasContent: true })).toBe('skip')
    runPendingNavigation()
    expect(navigate).toHaveBeenCalledOnce()
  })

  it('threads the reading navigation blocker through every shell entry path', () => {
    expect(appSource.match(/onReadingNavigationBlockerChange=\{handleReadingNavigationBlockerChange\}/g)).toHaveLength(2)
    expect(appSource).toContain('onNavigationBlockerChange={handleReadingNavigationBlockerChange}')
    expect(exploreSource).toContain('onNavigationBlockerChange={onReadingNavigationBlockerChange}')
    expect(knowledgeBaseSource).toContain('onNavigationBlockerChange={onReadingNavigationBlockerChange}')
  })
})
