import { describe, expect, it } from 'vitest'
import { parseChatArtifacts } from './chatArtifacts'

describe('parseChatArtifacts', () => {
  it('promotes markdown images into an image board and keeps narrative text', () => {
    const parsed = parseChatArtifacts(
      'message-1',
      '这里有两个方向。\n\n![知识地图](/assets/map.png)\n![课程舞台](https://example.com/lesson.jpg)',
    )

    expect(parsed.content).toBe('这里有两个方向。')
    expect(parsed.artifacts).toEqual([
      {
        id: 'message-1-image-board',
        type: 'image_board',
        title: '对话图片板',
        items: [
          { id: 'message-1-image-1', title: '知识地图', imageUrl: '/assets/map.png' },
          {
            id: 'message-1-image-2',
            title: '课程舞台',
            imageUrl: 'https://example.com/lesson.jpg',
          },
        ],
      },
    ])
  })

  it('leaves unsupported image URLs in the markdown body', () => {
    const content = '![本地文件](file:///tmp/private.png)'
    expect(parseChatArtifacts('message-2', content)).toEqual({ content, artifacts: [] })
  })

  it('extracts an isolated HTML CSS JS widget from a chat fence', () => {
    const parsed = parseChatArtifacts(
      'message-3',
      [
        '试试这个小工具：',
        '```binnagent-widget',
        '<!-- title: 单词配对 -->',
        '<!-- height: 420 -->',
        '<button id="pick">apple</button>',
        '<style>button{color:teal}</style>',
        '<script>document.querySelector("#pick").onclick=()=>binnagent.emit("answer",{value:"apple"})</script>',
        '```',
      ].join('\n'),
    )

    expect(parsed.content).toBe('试试这个小工具：')
    expect(parsed.artifacts[0]).toMatchObject({
      id: 'message-3-interactive-1',
      type: 'interactive_html',
      title: '单词配对',
      html: '<button id="pick">apple</button>',
      css: 'button{color:teal}',
      javascript: 'document.querySelector("#pick").onclick=()=>binnagent.emit("answer",{value:"apple"})',
      height: 420,
    })
  })
})
