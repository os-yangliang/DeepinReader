import { reactive } from 'vue'

// 从 localStorage 恢复状态
function loadPersistedState() {
  try {
    const saved = localStorage.getItem('paperreader_state')
    if (saved) {
      const parsed = JSON.parse(saved)
      return {
        documentInfo: parsed.documentInfo || null,
        pdfUrl: parsed.pdfUrl || null,
        analysisResult: parsed.analysisResult || null,
        documents: parsed.documents || [],
      }
    }
  } catch (e) {
    console.warn('恢复状态失败:', e)
  }
  return { documentInfo: null, pdfUrl: null, analysisResult: null, documents: [] }
}

const initialState = loadPersistedState()

// 主题初始化
function getInitialTheme() {
  const saved = localStorage.getItem('paperreader_theme')
  if (saved) return saved
  // 跟随系统
  if (window.matchMedia?.('(prefers-color-scheme: light)').matches) return 'light'
  return 'dark'
}

export const store = reactive({
  documentInfo: initialState.documentInfo,
  pdfUrl: initialState.pdfUrl,
  analysisResult: initialState.analysisResult,
  documents: initialState.documents,
  theme: getInitialTheme(),
  pendingQuestion: '',  // 标注 → 问答联动

  // 切换主题
  toggleTheme() {
    this.theme = this.theme === 'dark' ? 'light' : 'dark'
    this._applyTheme()
    localStorage.setItem('paperreader_theme', this.theme)
  },

  // 应用主题到 DOM
  _applyTheme() {
    document.documentElement.setAttribute('data-theme', this.theme)
  },

  // 初始化（应用保存的主题）
  initTheme() {
    this._applyTheme()
  },
  
  // 设置当前文档（上传后调用）
  setDocument(info, url, result) {
    this.documentInfo = info
    this.pdfUrl = url
    this.analysisResult = result
    
    // 同步到 documents 列表
    const docId = info?.document_id
    if (docId) {
      const existing = this.documents.find(d => d.document_id === docId)
      if (existing) {
        existing.is_active = true
        existing.filename = info.filename
        existing.title = info.title
        existing.file_url = url
        // 标记是否已分析
        if (result?.analysis || result?.summary) {
          existing.has_summary = true
          existing.analysisResult = result
        }
      } else {
        // 新文档
        this.documents.push({
          document_id: docId,
          filename: info.filename || '',
          title: info.title || '',
          file_url: url,
          page_count: info.page_count || 0,
          is_active: true,
          has_summary: !!(result?.analysis || result?.summary),
          analysisResult: result,
        })
      }
      // 取消其他文档的 active
      this.documents.forEach(d => {
        d.is_active = d.document_id === docId
      })
    }
    this._persist()
  },
  
  // 切换活跃文档（前端状态），接收后端返回的 doc_info
  switchDocument(docId, docInfo) {
    this.documents.forEach(d => {
      d.is_active = d.document_id === docId
    })
    if (docInfo) {
      this.documentInfo = docInfo
      this.pdfUrl = docInfo.file_url || null
    }
    // 恢复该文档的分析结果
    const doc = this.documents.find(d => d.document_id === docId)
    this.analysisResult = doc?.analysisResult || null
    this._persist()
  },

  // 移除文档
  removeDocument(docId) {
    this.documents = this.documents.filter(d => d.document_id !== docId)
    // 如果删除的是当前文档且列表为空，才主动清空视图状态
    if (this.documentInfo?.document_id === docId && this.documents.length === 0) {
      this.clearDocument()
    }
    this._persist()
  },
  
  // 清除所有文档
  clearDocument() {
    this.documentInfo = null
    this.pdfUrl = null
    this.analysisResult = null
    this.documents = []
    localStorage.removeItem('paperreader_state')
  },

  // 持久化到 localStorage
  _persist() {
    try {
      const urlToSave = this.pdfUrl && !this.pdfUrl.startsWith('blob:') ? this.pdfUrl : null
      
      const data = {
        documentInfo: this.documentInfo,
        pdfUrl: urlToSave,
        analysisResult: this.analysisResult,
        documents: this.documents,
      }
      localStorage.setItem('paperreader_state', JSON.stringify(data))
    } catch (e) {
      console.warn('持久化状态失败:', e)
    }
  }
})