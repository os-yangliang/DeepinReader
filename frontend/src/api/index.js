import axios from 'axios';
import { wsRequest, isWsAvailable } from '../utils/websocket';

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'

// 创建 axios 实例
const apiClient = axios.create({
  baseURL,
  timeout: 60000,
})

// ==================== SSE 降级 Helper ====================

function createSSEStream(url, options = {}) {
  return async function* () {
    const response = await fetch(`${baseURL}${url}`, {
      method: options.method || 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: options.body ? JSON.stringify(options.body) : undefined
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '请求失败');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.error) throw new Error(data.error);
            if (data.done) return;
            if (data.chunk) yield data.chunk;
          } catch (e) {
            if (e.message && !e.message.includes('JSON')) throw e;
            console.warn('解析 SSE 数据失败:', line);
          }
        }
      }
    }
  }();
}

// SSE 版事件流（返回完整事件对象，非纯 chunk）
function createSSEEventStream(url, options = {}) {
  return async function* () {
    const response = await fetch(`${baseURL}${url}`, {
      method: options.method || 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: options.body ? JSON.stringify(options.body) : undefined
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '请求失败');
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try { yield JSON.parse(line.slice(6)) } catch (e) {}
        }
      }
    }
  }();
}

// 流式上传并分析 (仅 SSE，文件上传不走 WS)
function uploadAndAnalyzeStream(file) {
  const formData = new FormData()
  formData.append('file', file)

  return (async function* () {
    const response = await fetch(`${baseURL}/upload/stream`, {
      method: 'POST',
      body: formData
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || '上传失败')
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try { yield JSON.parse(line.slice(6)) } catch (e) {}
        }
      }
    }
  })()
}

// ==================== WebSocket 流式 Helper ====================

/**
 * 创建 WS 流式请求，返回可取消的异步迭代器
 * 兼容现有 for-await 模式，但额外提供 cancel() 能力
 */
function createWsStream(type, data = {}) {
  const { stream, cancel, requestId } = wsRequest(type, data)
  
  // 包装为兼容现有消费模式的迭代器
  const wrappedStream = (async function* () {
    for await (const item of stream) {
      if (item.__done || item.__cancelled) {
        // 如果 done 事件中有有用数据，也 yield 出去
        if (Object.keys(item).length > 1) {
          const { __done, __cancelled, ...rest } = item
          if (Object.keys(rest).length > 0) {
            yield rest
          }
        }
        return
      }
      yield item
    }
  })()

  // 附加 cancel 方法到迭代器
  wrappedStream.cancel = cancel
  wrappedStream.requestId = requestId
  return wrappedStream
}

/**
 * 创建 WS 聊天流，yield chunk 文本（兼容 chatStream 旧接口）
 */
function createWsChatStream(message) {
  const { stream, cancel, requestId } = wsRequest('chat', { message })
  const wrappedStream = (async function* () {
    for await (const item of stream) {
      if (item.__done || item.__cancelled) return
      if (item.chunk) yield item.chunk
    }
  })()
  wrappedStream.cancel = cancel
  wrappedStream.requestId = requestId
  return wrappedStream
}

/**
 * 创建 WS 代码生成流，yield chunk 文本
 */
function createWsCodeStream(userRequest, targetFramework) {
  const { stream, cancel, requestId } = wsRequest('code_generate', {
    user_request: userRequest,
    target_framework: targetFramework,
  })
  const wrappedStream = (async function* () {
    for await (const item of stream) {
      if (item.__done || item.__cancelled) return
      if (item.chunk) yield item.chunk
    }
  })()
  wrappedStream.cancel = cancel
  wrappedStream.requestId = requestId
  return wrappedStream
}


// ==================== API ====================

/**
 * 创建带 SSE 降级的流式方法
 * WS 失败时自动回退到 SSE，对消费者完全透明
 */
function withFallback(wsFactory, sseFactory) {
  // 创建 WS 流一次，捕获 cancel
  let wsStream = null
  let cancelFn = () => {}
  try {
    wsStream = wsFactory()
    cancelFn = wsStream.cancel || (() => {})
  } catch {
    // wsFactory 同步抛出 — 直接用 SSE
    wsStream = null
  }

  const wrapper = (async function* () {
    if (wsStream) {
      let useSSE = false
      try {
        const iterator = wsStream[Symbol.asyncIterator]()
        const first = await iterator.next()
        if (!first.done) {
          yield first.value
          while (true) {
            const r = await iterator.next()
            if (r.done) return
            yield r.value
          }
        }
      } catch (e) {
        console.warn('[API] WS 失败，降级到 SSE:', e.message)
        useSSE = true
      }
      if (!useSSE) return
    }
    // SSE 降级
    const sseStream = sseFactory()
    for await (const item of sseStream) {
      yield item
    }
  })()

  wrapper.cancel = cancelFn
  return wrapper
}

export const paperAPI = {
  // 快速上传
  uploadDocument: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await apiClient.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
    return res.data
  },

  // 流式 AI 分析 (WS 优先，SSE 降级)
  analyzeStream: () => {
    return withFallback(
      () => createWsStream('analyze'),
      () => createSSEEventStream('/analyze/stream')
    )
  },

  // 流式上传并分析 (仅 SSE)
  uploadAndAnalyzeStream: (file) => uploadAndAnalyzeStream(file),

  // 非流式上传分析
  uploadAndAnalyze: async (file, onProgress) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await apiClient.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percentCompleted)
        }
      }
    })
    return res.data
  },

  getDocument: async () => {
    const res = await apiClient.get('/document')
    return res.data
  },

  // 普通问答
  chat: async (message) => {
    const res = await apiClient.post('/chat', { message })
    return res.data
  },
  
  // 流式问答 (WS 优先 — 支持中途打断)
  chatStream: (message) => {
    return withFallback(
      () => createWsChatStream(message),
      () => createSSEStream('/chat/stream', { body: { message } })
    )
  },
  
  // 流式翻译 (WS 优先)
  translateStream: () => {
    return withFallback(
      () => createWsStream('translate'),
      () => createSSEEventStream('/translate/stream')
    )
  },

  // 划词翻译
  translateText: async (text) => {
    const res = await apiClient.post('/translate/text', { text })
    return res.data
  },

  // 导出分析报告 (Word)
  exportReport: async (annotations = []) => {
    const res = await apiClient.post('/export/report', { annotations }, {
      responseType: 'blob',
    })
    const disposition = res.headers['content-disposition']
    let filename = 'analysis_report.docx'
    if (disposition) {
      const match = disposition.match(/filename\*?=(?:UTF-8'')?([^;\n]+)/i)
      if (match) filename = decodeURIComponent(match[1].replace(/['"]/g, ''))
    }
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  },

  // 流式代码生成 (WS 优先)
  codeGenerateStream: (userRequest, targetFramework) => {
    return withFallback(
      () => createWsCodeStream(userRequest, targetFramework),
      () => createSSEStream('/code/generate', {
        body: { user_request: userRequest, target_framework: targetFramework }
      })
    )
  },

  // 论文对比分析 (WS 优先)
  compareStream: (docIds) => {
    return withFallback(
      () => createWsStream('compare', { doc_ids: docIds }),
      () => createSSEEventStream('/compare/stream', { body: { doc_ids: docIds } })
    )
  },

  getSuggestions: async () => {
    const res = await apiClient.get('/suggestions')
    return res.data
  },

  searchPapers: async (query = '', limit = 10) => {
    const res = await apiClient.post('/search', { query, limit })
    return res.data
  },

  generateMindmap: async () => {
    const res = await apiClient.post('/mindmap')
    return res.data
  },

  clearChat: async () => {
    const res = await apiClient.post('/clear')
    return res.data
  },

  clearDocument: async () => {
    const res = await apiClient.delete('/document')
    return res.data
  },

  getDocuments: async () => {
    const res = await apiClient.get('/documents')
    return res.data
  },

  switchDocument: async (documentId) => {
    const res = await apiClient.post('/documents/switch', { document_id: documentId })
    return res.data
  },

  removeDocument: async (documentId) => {
    const res = await apiClient.delete(`/documents/${documentId}`)
    return res.data
  },
  
  getHistory: async () => {
    const res = await apiClient.get('/history')
    return res.data
  },
  
  getHistoryDetail: async (historyId) => {
    const res = await apiClient.get(`/history/${historyId}`)
    return res.data
  },
  
  loadHistory: async (historyId) => {
    const res = await apiClient.post(`/history/${historyId}/load`)
    return res.data
  },
  
  deleteHistory: async (historyId) => {
    const res = await apiClient.delete(`/history/${historyId}`)
    return res.data
  },
  
  getHistoryChat: async (historyId) => {
    const res = await apiClient.get(`/history/${historyId}/chat`)
    return res.data
  }
}

export default {
  ...paperAPI
}
