/**
 * 共享 Markdown 渲染器 — 带语法高亮
 * 所有页面统一使用此模块，保证一致的渲染效果
 */
import { marked } from 'marked'
import hljs from 'highlight.js/lib/core'

// 按需注册常用语言（减小打包体积）
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import java from 'highlight.js/lib/languages/java'
import cpp from 'highlight.js/lib/languages/cpp'
import latex from 'highlight.js/lib/languages/latex'
import matlab from 'highlight.js/lib/languages/matlab'
import r from 'highlight.js/lib/languages/r'
import sql from 'highlight.js/lib/languages/sql'
import yaml from 'highlight.js/lib/languages/yaml'
import markdown from 'highlight.js/lib/languages/markdown'
import diff from 'highlight.js/lib/languages/diff'

hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('java', java)
hljs.registerLanguage('cpp', cpp)
hljs.registerLanguage('c', cpp)
hljs.registerLanguage('latex', latex)
hljs.registerLanguage('tex', latex)
hljs.registerLanguage('matlab', matlab)
hljs.registerLanguage('r', r)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('diff', diff)

// 配置 marked 使用 highlight.js
marked.setOptions({
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch (e) { /* fallback */ }
    }
    // 自动检测语言
    try {
      return hljs.highlightAuto(code).value
    } catch (e) { /* fallback */ }
    return code
  },
  breaks: false,
  gfm: true,
})

/**
 * 渲染 Markdown 为 HTML（带语法高亮）
 */
export function renderMarkdown(text) {
  if (!text) return ''
  return marked(text)
}

// 也导出 marked 本身以便需要时直接使用
export { marked, hljs }
