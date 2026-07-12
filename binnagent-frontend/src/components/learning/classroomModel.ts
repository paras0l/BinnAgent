export type ClassroomPhaseKind =
  | 'briefing'
  | 'cards'
  | 'grammar'
  | 'audio'
  | 'textbook'
  | 'challenge'
  | 'reflection'

export type VocabularyConfidence = 'known' | 'fuzzy' | 'unknown'

export interface PhaseGateEvidence {
  vocabularyClassified: number
  vocabularyRequired: number
  grammarAnswered: number
  grammarRequired: number
  grammarTransferLength: number
  continuousAudioPlayed: boolean
  listenedCueCount: number
  textbookAnswerCount: number
  challengeCompleted: boolean
}

export interface PhaseGate {
  canContinue: boolean
  evidence: string
  requirement: string
}

export function getPhaseGate(kind: ClassroomPhaseKind, evidence: PhaseGateEvidence): PhaseGate {
  switch (kind) {
    case 'briefing':
      return { canContinue: true, evidence: '目标已确认', requirement: '确认今天的目标和完成标准' }
    case 'cards': {
      const required = Math.max(1, evidence.vocabularyRequired)
      return {
        canContinue: evidence.vocabularyClassified >= required,
        evidence: `已判断 ${evidence.vocabularyClassified}/${required} 个词`,
        requirement: `至少判断 ${required} 个词是“会、模糊或不会”`,
      }
    }
    case 'grammar':
      return {
        canContinue: evidence.grammarAnswered >= evidence.grammarRequired && evidence.grammarTransferLength >= 8,
        evidence: `辨析 ${evidence.grammarAnswered}/${evidence.grammarRequired} · 迁移句 ${evidence.grammarTransferLength >= 8 ? '已写' : '待写'}`,
        requirement: '完成全部辨析题，并写出自己的迁移表达',
      }
    case 'audio':
      return {
        canContinue: evidence.continuousAudioPlayed || evidence.listenedCueCount >= 3,
        evidence: evidence.continuousAudioPlayed ? '已完整播放教材原声' : `已精听 ${evidence.listenedCueCount}/3 句`,
        requirement: '完整播放一次教材原声，或精听至少 3 句',
      }
    case 'textbook':
      return {
        canContinue: evidence.textbookAnswerCount >= 1,
        evidence: evidence.textbookAnswerCount ? `已保存 ${evidence.textbookAnswerCount} 页作答` : '尚未留下作答',
        requirement: '至少保存一页教材作答',
      }
    case 'challenge':
      return {
        canContinue: evidence.challengeCompleted,
        evidence: evidence.challengeCompleted ? '挑战已提交并获得反馈' : '等待提交挑战',
        requirement: '提交挑战并查看反馈',
      }
    case 'reflection':
      return { canContinue: false, evidence: '课堂已完成', requirement: '返回学习中心' }
  }
}

export function isPhaseAccessible(
  targetIndex: number,
  currentIndex: number,
  currentGateOpen: boolean,
): boolean {
  return targetIndex <= currentIndex
    || (targetIndex === currentIndex + 1 && currentGateOpen)
}

export const NEXT_ACTION_LABELS = {
  relisten: '回到原声，再听一次',
  review_vocabulary: '回到词汇，复习标记词',
  review_pattern: '回到语法，重看结构',
  continue: '继续下一页',
} as const
