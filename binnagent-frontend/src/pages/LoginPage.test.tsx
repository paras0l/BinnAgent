import { describe, expect, it } from 'vitest'
import loginPageSource from './LoginPage.tsx?raw'

describe('LoginPage account flow', () => {
  it('requires email lookup before learner selection or invitation registration', () => {
    expect(loginPageSource).toContain("fetch('/api/learners/lookup'")
    expect(loginPageSource).toContain("fetch('/api/learners/login'")
    expect(loginPageSource).toContain("fetch('/api/email-verifications'")
    expect(loginPageSource).toContain("fetch('/api/email-verifications/confirm'")
    expect(loginPageSource).toContain("invite_code: normalizedInviteCode")
    expect(loginPageSource).toContain('verification_token: verificationToken')
    expect(loginPageSource).toContain('同一邮箱可以绑定并管理多个学习者')
    expect(loginPageSource).toContain('learnerToBind')
  })

  it('keeps the left panel focused on the product value proposition', () => {
    expect(loginPageSource).toContain('创建你的英语学习空间')
    expect(loginPageSource).toContain('围绕词汇、教材、写作和学习状态持续练习')
    expect(loginPageSource).toContain("['今日学习路径', '词汇复习计划', '写作表达资产', '学习状态跟踪']")
  })
})
