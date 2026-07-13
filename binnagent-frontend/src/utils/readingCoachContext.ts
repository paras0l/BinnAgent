import type { ReadingMaterial, ReadingSentence, ReadingWorkspace } from '@/data/readingWorkshop'

interface ReadingCoachContextInput {
  material: ReadingMaterial
  materialId: string | null
  workspace: ReadingWorkspace
  currentSentence: ReadingSentence | null
  selectedText: string | null
  extensiveNotes: {
    gist: string
    attitude: string
    paragraphFunction: string
    centralSentence: string
  }
  intensiveNotes: {
    mainStructure: string
    phraseNotes: string
    evidenceNote: string
  }
  grammarTopics: string[]
}

export function buildReadingCoachContext({
  material,
  materialId,
  workspace,
  currentSentence,
  selectedText,
  extensiveNotes,
  intensiveNotes,
  grammarTopics,
}: ReadingCoachContextInput) {
  return {
    artifactId: materialId ?? 'unsaved-reading-session',
    artifactType: 'reading_session',
    artifactTitle: material.title.trim() || '未命名阅读材料',
    eventType: 'reading_coach_question',
    payload: {
      contextVersion: 1,
      instruction: '结合当前阅读现场回答，优先解释用户正在看的材料；不要复述整份上下文。',
      workspace,
      material: {
        id: materialId,
        title: material.title.trim() || null,
        text: material.text,
        level: material.level,
        goal: material.goal,
      },
      focus: {
        sentenceOrder: currentSentence?.order ?? null,
        sentence: currentSentence?.text ?? null,
        selectedText: selectedText?.trim() || null,
      },
      learnerWork: {
        extensiveNotes,
        intensiveNotes,
        grammarTopics,
      },
    },
  }
}
