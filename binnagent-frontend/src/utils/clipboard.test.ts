import { afterEach, describe, expect, it, vi } from 'vitest'
import { copyTextToClipboard } from './clipboard'

describe('copyTextToClipboard', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses the asynchronous clipboard API when it is available', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    await expect(copyTextToClipboard('BINN-ABC123')).resolves.toBe(true)
    expect(writeText).toHaveBeenCalledWith('BINN-ABC123')
  })

  it('falls back to a selected textarea when clipboard is unavailable over HTTP', async () => {
    const textarea = {
      value: '',
      style: {},
      setAttribute: vi.fn(),
      select: vi.fn(),
      setSelectionRange: vi.fn(),
      remove: vi.fn(),
    }
    const appendChild = vi.fn()
    const execCommand = vi.fn().mockReturnValue(true)
    vi.stubGlobal('navigator', {})
    vi.stubGlobal('document', {
      body: { appendChild },
      createElement: vi.fn().mockReturnValue(textarea),
      execCommand,
    })

    await expect(copyTextToClipboard('BINN-HTTP123')).resolves.toBe(true)
    expect(textarea.value).toBe('BINN-HTTP123')
    expect(appendChild).toHaveBeenCalledWith(textarea)
    expect(textarea.select).toHaveBeenCalledOnce()
    expect(textarea.setSelectionRange).toHaveBeenCalledWith(0, 12)
    expect(execCommand).toHaveBeenCalledWith('copy')
    expect(textarea.remove).toHaveBeenCalledOnce()
  })

  it('uses the fallback when the asynchronous clipboard API rejects', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('permission denied'))
    const textarea = {
      value: '',
      style: {},
      setAttribute: vi.fn(),
      select: vi.fn(),
      setSelectionRange: vi.fn(),
      remove: vi.fn(),
    }
    const execCommand = vi.fn().mockReturnValue(true)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    vi.stubGlobal('document', {
      body: { appendChild: vi.fn() },
      createElement: vi.fn().mockReturnValue(textarea),
      execCommand,
    })

    await expect(copyTextToClipboard('BINN-FALLBACK')).resolves.toBe(true)
    expect(writeText).toHaveBeenCalledOnce()
    expect(execCommand).toHaveBeenCalledWith('copy')
  })
})
