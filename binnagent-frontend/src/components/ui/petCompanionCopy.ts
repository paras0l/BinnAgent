export function loadingCompanionMessage(title: string): string {
  if (title.includes('记忆')) return '我正在把我们之前的学习线索整理回来，等一下就能接着走。'
  if (title.includes('教材') || title.includes('课程') || title.includes('学习')) {
    return '我陪你把这一段学习材料准备好，我们很快就能继续。'
  }
  if (title.includes('词') || title.includes('发音')) return '我正在把词汇和发音线索放到一起，我们马上开始。'
  if (title.includes('生成') || title.includes('准备')) return '这一步需要多想一会儿，我陪你等，我们一起看结果。'
  return '我陪你一起把需要的内容整理好，稍等一下，我们马上继续。'
}

export function companionizePetMessage(message: string): string {
  return message
    .replaceAll('你应该', '我们可以')
    .replaceAll('请完成', '我们一起完成')
    .replaceAll('请先', '我们先')
    .replaceAll('错误，请重试', '还差一点，我们一起再试')
    .replaceAll('失败，请稍后重试', '还没完成，我们稍后一起再试')
    .replaceAll('失败，请重试', '还没完成，我们一起再试')
    .replaceAll('让我来教你', '我陪你拆开它')
}
