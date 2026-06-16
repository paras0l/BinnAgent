const STORAGE_KEY = 'binnGrammarPendingPrompt'

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message.type !== 'string') return false

  if (message.type === 'BINN_GRAMMAR_PROMPT_READY') {
    const payload = {
      prompt: String(message.prompt || ''),
      topicTitle: String(message.topicTitle || ''),
      sourceUrl: String(message.sourceUrl || ''),
      targetUrl: String(message.targetUrl || ''),
      sourceTabId: sender.tab?.id ?? null,
      createdAt: Date.now(),
    }
    chrome.storage.local.set({ [STORAGE_KEY]: payload }, () => {
      sendResponse({ ok: true })
    })
    return true
  }

  if (message.type === 'BINN_GRAMMAR_RETURN_HTML') {
    chrome.storage.local.get(STORAGE_KEY, (items) => {
      const pending = items[STORAGE_KEY]
      const html = String(message.html || '').trim()
      if (!pending || !html) {
        sendResponse({ ok: false, reason: 'missing-pending-or-html' })
        return
      }

      const deliverToTab = (tabId) => {
        chrome.tabs.update(tabId, { active: true }, () => {
          chrome.tabs.sendMessage(tabId, { type: 'BINN_GRAMMAR_HTML_RETURNED', html }, () => {
            sendResponse({ ok: !chrome.runtime.lastError })
          })
        })
      }

      if (typeof pending.sourceTabId === 'number') {
        deliverToTab(pending.sourceTabId)
        return
      }

      if (pending.sourceUrl) {
        chrome.tabs.create({ url: pending.sourceUrl, active: true }, (tab) => {
          if (!tab?.id) {
            sendResponse({ ok: false, reason: 'source-tab-create-failed' })
            return
          }
          window.setTimeout(() => deliverToTab(tab.id), 1200)
        })
        return
      }

      sendResponse({ ok: false, reason: 'missing-source-tab' })
    })
    return true
  }

  return false
})
