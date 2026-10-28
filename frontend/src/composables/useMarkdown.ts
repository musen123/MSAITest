import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: false,
  highlight: (str: string, lang: string) => {
    if (lang && hljs.getLanguage(lang)) {
      const code = hljs.highlight(str, { language: lang, ignoreIllegals: true }).value
      return `<pre class="hljs"><code>${code}</code></pre>`
    }
    const code = hljs.highlightAuto(str).value
    return `<pre class="hljs"><code>${code}</code></pre>`
  },
})

export function useMarkdown() {
  const render = (content: string): string => {
    if (!content) return ''
    return md.render(content)
  }

  return { render }
}
