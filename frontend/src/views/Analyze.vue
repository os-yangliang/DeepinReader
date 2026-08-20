<template>
  <div class="analyze-page">
    <PageToolbar :icon="FileSearch" title="论文分析" subtitle="结构化智能解析" :accent="'var(--accent-1)'">
      <template #actions>
        <button v-if="!store.pdfUrl" class="btn-primary" @click="triggerFileInput">
          <Upload :size="16" /> 上传论文
        </button>
        <div v-if="isUploading" class="status-hint">
          <Loader2 :size="15" class="animate-spin" /> {{ uploadStatus }}
        </div>

        <button
          v-if="isDocReady && !isAnalyzing && !store.analysisResult && !streamingContent"
          class="btn-primary"
          @click="startAnalysis"
        >
          <Sparkles :size="16" /> 开始智能分析
        </button>
        <div v-if="isAnalyzing" class="status-hint">
          <Loader2 :size="15" class="animate-spin" />
          <span>{{ progressMessage }}</span>
          <span class="mono">{{ progressPercent }}%</span>
        </div>

        <button v-if="store.pdfUrl" class="btn-secondary" :class="{ active: showAnnotations }" @click="showAnnotations = !showAnnotations">
          <Highlighter :size="14" /> 标注
          <span v-if="annotations.length" class="badge-count">{{ annotations.length }}</span>
        </button>
        <button v-if="store.pdfUrl" class="btn-ghost" @click="resetUpload">
          <RotateCcw :size="14" /> {{ !store.analysisResult ? '取消' : '重新上传' }}
        </button>
      </template>
    </PageToolbar>

    <!-- 进度条 -->
    <div v-if="isAnalyzing" class="progress-track">
      <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
    </div>

    <div class="analyze-body">
      <!-- 左侧 PDF -->
      <div class="pdf-pane" :class="{ narrow: showAnnotations }" @mouseup="handlePdfSelection">
        <div v-if="store.pdfUrl" class="pdf-scroll">
          <div class="pdf-doc">
            <vue-pdf-embed :source="store.pdfUrl" />
          </div>
        </div>

        <!-- 空状态上传 -->
        <div v-else class="upload-empty"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="handleDrop">
          <div class="upload-zone" :class="{ active: isDragging }">
            <FileUp :size="32" />
            <h3>上传学术论文</h3>
            <p>拖拽文件到此处，或点击选择文件 · 支持 PDF 格式</p>
            <button class="btn-primary" @click="triggerFileInput">
              <Upload :size="16" /> 选择文件
            </button>
            <input ref="fileInputRef" type="file" accept=".pdf" class="hidden" @change="handleFileSelect" />
          </div>
        </div>

        <!-- 高亮弹窗 -->
        <transition name="popup">
          <div v-if="selectionPopup.show" class="highlight-popup" :style="{ top: selectionPopup.y + 'px', left: selectionPopup.x + 'px' }">
            <button v-for="c in highlightColors" :key="c.name" class="color-dot" :style="{ background: c.color }" :title="c.name" @click="addAnnotation(c.color)"></button>
            <button @click="selectionPopup.show = false" class="popup-close"><X :size="12" /></button>
          </div>
        </transition>
      </div>

      <!-- 右侧结果 -->
      <div class="result-pane" :class="{ narrow: showAnnotations }">
        <div ref="resultPanelRef" class="result-scroll">
          <!-- 空状态 -->
          <div v-if="!streamingContent && !store.analysisResult" class="result-empty">
            <EmptyState
              :icon="BarChart3"
              :title="isDocReady ? '文档已就绪' : '等待上传'"
              :description="isDocReady ? '点击上方「开始智能分析」生成 AI 报告；选中 PDF 文字可添加高亮标注' : '上传论文后生成 AI 分析报告'"
            />
          </div>

          <!-- 内容 -->
          <div v-else class="result-content">
            <div class="result-head">
              <Sparkles :size="16" class="text-accent" />
              <span>分析报告</span>
              <span v-if="isAnalyzing" class="streaming-dot"></span>
              <div class="flex-1"></div>
              <div v-if="!isAnalyzing && sections.length > 1" class="view-switch">
                <button class="view-btn" :class="{ active: reportView === 'cards' }" @click="reportView = 'cards'">
                  <LayoutGrid :size="13" /> 卡片
                </button>
                <button class="view-btn" :class="{ active: reportView === 'raw' }" @click="reportView = 'raw'">
                  <AlignLeft :size="13" /> 原文
                </button>
              </div>
              <button v-if="!isAnalyzing && displayContent" class="btn-ghost" @click="copyMarkdown"><Copy :size="14" /> {{ copyLabel }}</button>
              <button v-if="!isAnalyzing && displayContent" class="btn-ghost" @click="downloadMarkdown"><Download :size="14" /> MD</button>
              <button v-if="!isAnalyzing && displayContent" class="btn-ghost text-accent" @click="exportWord"><FileDown :size="14" /> {{ exportLabel }}</button>
            </div>

            <!-- 流式输出中：显示原始流 -->
            <div v-if="isAnalyzing" class="markdown-content" v-html="renderedContent"></div>

            <!-- 卡片视图 -->
            <div v-else-if="reportView === 'cards' && sections.length > 1" class="report-sections">
              <div v-for="(sec, i) in sections" :key="i" class="report-section card">
                <button class="section-head" @click="sec.open = !sec.open">
                  <span class="section-title">{{ sec.title }}</span>
                  <ChevronDown :size="15" class="section-chevron" :class="{ 'rotate-180': !sec.open }" />
                </button>
                <div v-show="sec.open" class="section-body markdown-content" v-html="renderSection(sec.body)"></div>
              </div>
            </div>

            <!-- 原文视图 -->
            <div v-else class="markdown-content" v-html="renderedContent"></div>
          </div>
        </div>
      </div>

      <!-- 标注侧边栏 -->
      <transition name="slide">
        <div v-if="showAnnotations" class="anno-pane">
          <div class="anno-head">
            <Highlighter :size="16" class="text-accent" />
            <span>标注笔记</span>
            <span class="anno-count">{{ annotations.length }}</span>
            <button @click="showAnnotations = false" class="icon-btn"><X :size="16" /></button>
          </div>

          <div v-if="annotations.length === 0" class="anno-empty">
            <Highlighter :size="22" />
            <p>选中 PDF 文字后<br />点击颜色即可添加标注</p>
          </div>

          <div v-else class="anno-list">
            <div v-for="(anno, idx) in annotations" :key="anno.id" class="anno-item" :style="{ borderLeftColor: anno.color }">
              <div class="anno-text" :style="{ backgroundColor: anno.color + '18' }">"{{ anno.text.length > 80 ? anno.text.slice(0, 80) + '...' : anno.text }}"</div>

              <div v-if="anno.note" class="anno-note">
                <StickyNote :size="11" />
                <span>{{ anno.note }}</span>
              </div>

              <div class="anno-actions">
                <button @click="askAboutAnnotation(anno)" class="anno-btn" title="让 AI 解释"><MessageCircle :size="12" /> 问 AI</button>
                <button @click="editNote(idx)" class="anno-btn" title="编辑笔记"><Edit3 :size="12" /></button>
                <button @click="removeAnnotation(idx)" class="anno-btn danger" title="删除"><Trash2 :size="12" /></button>
                <span class="anno-time">{{ formatTime(anno.timestamp) }}</span>
              </div>

              <div v-if="editingIndex === idx" class="anno-edit">
                <input v-model="editNoteText" @keydown.enter="saveNote(idx)" @keydown.escape="editingIndex = -1" placeholder="输入笔记..." class="anno-input" ref="noteInputRef" />
                <button @click="saveNote(idx)" class="anno-save"><Check :size="12" /></button>
              </div>
            </div>
          </div>

          <div v-if="annotations.length > 0" class="anno-foot">
            <button @click="exportAnnotations" class="btn-secondary flex-1"><Download :size="13" /> 导出</button>
            <button @click="clearAnnotations" class="icon-btn danger"><Trash2 :size="14" /></button>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { renderMarkdown } from '../utils/markdown'
import VuePdfEmbed from 'vue-pdf-embed'
import api from '../api'
import { store } from '../store'
import {
  FileSearch, Upload, Loader2, RotateCcw, FileUp, BarChart3, Sparkles,
  Copy, Download, Check, X, Highlighter, MessageCircle, Edit3, Trash2,
  StickyNote, FileDown, LayoutGrid, AlignLeft, ChevronDown,
} from 'lucide-vue-next'

const router = useRouter()
const fileInputRef = ref(null)
const isDragging = ref(false)
const isUploading = ref(false)
const isAnalyzing = ref(false)
const isDocReady = computed(() => !!store.documentInfo?.document_id)
const uploadStatus = ref('')
const resultPanelRef = ref(null)
const streamingContent = ref('')
const progressPercent = ref(0)
const progressMessage = ref('准备分析...')
const profileDetail = ref(null)
const profileLoading = ref(false)

// 标注
const showAnnotations = ref(false)
const annotations = ref([])
const selectionPopup = ref({ show: false, x: 0, y: 0, text: '' })
const editingIndex = ref(-1)
const editNoteText = ref('')
const noteInputRef = ref(null)

const highlightColors = [
  { name: '黄色', color: '#fbbf24' },
  { name: '绿色', color: '#34d399' },
  { name: '蓝色', color: '#60a5fa' },
  { name: '紫色', color: '#a78bfa' },
  { name: '粉色', color: '#f472b6' },
]

const loadAnnotations = () => {
  const docId = store.documentInfo?.document_id || store.documentInfo?.filename
  if (!docId) return
  try {
    const saved = localStorage.getItem(`annotations_${docId}`)
    if (saved) annotations.value = JSON.parse(saved)
  } catch (e) { console.warn('加载标注失败:', e) }
}

const saveAnnotationsToStorage = () => {
  const docId = store.documentInfo?.document_id || store.documentInfo?.filename
  if (!docId) return
  localStorage.setItem(`annotations_${docId}`, JSON.stringify(annotations.value))
}

const loadProfileDetail = async () => {
  if (!store.documentInfo?.document_id) {
    profileDetail.value = null
    return
  }
  profileLoading.value = true
  try {
    profileDetail.value = await api.getDocumentProfileDetail()
  } catch (e) {
    profileDetail.value = null
  } finally {
    profileLoading.value = false
  }
}

watch(() => store.documentInfo?.document_id, async () => {
  annotations.value = []
  loadAnnotations()
  await loadProfileDetail()
}, { immediate: true })

const handlePdfSelection = (event) => {
  if (event.target.closest('.highlight-popup')) return
  const selection = window.getSelection()
  const text = selection?.toString().trim()
  if (text && text.length >= 2 && text.length <= 500) {
    const range = selection.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    let x = rect.left + rect.width / 2 - 100
    let y = rect.top - 50
    x = Math.max(10, Math.min(x, window.innerWidth - 220))
    if (y < 80) y = rect.bottom + 10
    selectionPopup.value = { show: true, x, y, text }
  } else {
    selectionPopup.value.show = false
  }
}

const addAnnotation = (color) => {
  const text = selectionPopup.value.text
  if (!text) return
  annotations.value.unshift({ id: Date.now(), text, color, note: '', timestamp: new Date().toISOString() })
  selectionPopup.value.show = false
  showAnnotations.value = true
  saveAnnotationsToStorage()
  window.getSelection()?.removeAllRanges()
}

const removeAnnotation = (idx) => {
  annotations.value.splice(idx, 1)
  saveAnnotationsToStorage()
}

const editNote = async (idx) => {
  editingIndex.value = idx
  editNoteText.value = annotations.value[idx].note || ''
  await nextTick()
  const inputs = document.querySelectorAll('.anno-input')
  inputs[0]?.focus()
}

const saveNote = (idx) => {
  annotations.value[idx].note = editNoteText.value.trim()
  editingIndex.value = -1
  editNoteText.value = ''
  saveAnnotationsToStorage()
}

const askAboutAnnotation = (anno) => {
  store.pendingQuestion = `请解释论文中以下内容的含义：\n\n"${anno.text}"${anno.note ? '\n\n我的笔记：' + anno.note : ''}`
  router.push('/chat')
}

const clearAnnotations = () => {
  if (confirm('确定清除所有标注？')) {
    annotations.value = []
    saveAnnotationsToStorage()
  }
}

const exportAnnotations = () => {
  const docName = store.documentInfo?.filename || 'paper'
  let md = `# 📝 ${docName} — 标注笔记\n\n> 共 ${annotations.value.length} 条标注\n\n---\n\n`
  annotations.value.forEach((anno, i) => {
    md += `### ${i + 1}. 高亮\n\n> ${anno.text}\n\n`
    if (anno.note) md += `**笔记**: ${anno.note}\n\n`
    md += `_${new Date(anno.timestamp).toLocaleString()}_\n\n---\n\n`
  })
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = docName.replace(/\.[^.]+$/, '') + '_annotations.md'
  a.click()
  URL.revokeObjectURL(url)
}

const formatTime = (ts) => {
  const d = new Date(ts)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

// 分析
const displayContent = computed(() => {
  if (streamingContent.value) return streamingContent.value
  const r = store.analysisResult
  if (r) return r.analysis || r.summary || ''
  return ''
})
const renderedContent = computed(() => displayContent.value ? renderMarkdown(displayContent.value) : '')

// 报告卡片化：按二级标题拆分为可折叠卡片
const reportView = ref('cards')
const sections = computed(() => {
  const md = displayContent.value
  if (!md) return []
  const lines = md.split('\n')
  const result = []
  let current = null
  let prefix = ''
  for (const line of lines) {
    const m = line.match(/^##\s+(.+)$/)
    if (m) {
      if (current) result.push(current)
      current = { title: m[1].trim().replace(/[#*`]/g, ''), body: '', open: true }
    } else if (current) {
      current.body += line + '\n'
    } else {
      prefix += line + '\n'
    }
  }
  if (current) result.push(current)
  if (!result.length && prefix.trim()) {
    result.push({ title: '分析报告', body: prefix, open: true })
  } else if (prefix.trim()) {
    result.unshift({ title: '概述', body: prefix, open: true })
  }
  return result
})

const renderSection = (body) => renderMarkdown(body)

watch(streamingContent, async () => {
  await nextTick()
  if (resultPanelRef.value) resultPanelRef.value.scrollTop = resultPanelRef.value.scrollHeight
})

const triggerFileInput = () => fileInputRef.value?.click()

const handleFileSelect = (e) => {
  const f = e.target.files?.[0]
  if (f) {
    e.target.value = ''
    const url = URL.createObjectURL(f)
    store.setDocument({ filename: f.name }, url, null)
    uploadOnly(f)
  }
}

const handleDrop = (e) => {
  isDragging.value = false
  const f = e.dataTransfer.files?.[0]
  if (f && f.type === 'application/pdf') {
    const url = URL.createObjectURL(f)
    store.setDocument({ filename: f.name }, url, null)
    uploadOnly(f)
  } else alert('请上传 PDF 文件')
}

const uploadOnly = async (uploadFile) => {
  isUploading.value = true
  isAnalyzing.value = false
  streamingContent.value = ''
  uploadStatus.value = '正在解析文档...'
  profileDetail.value = null
  try {
    const result = await api.uploadDocument(uploadFile)
    if (!result.success) throw new Error(result.error || '上传失败')
    const docInfo = result.document_info
    if (store.pdfUrl?.startsWith('blob:')) URL.revokeObjectURL(store.pdfUrl)
    store.setDocument(docInfo, docInfo.file_url, null)
    await loadProfileDetail()
  } catch (e) {
    alert('上传失败: ' + e.message)
  } finally {
    isUploading.value = false
  }
}

const startAnalysis = async () => {
  if (isAnalyzing.value) return
  isAnalyzing.value = true
  streamingContent.value = ''
  progressPercent.value = 0
  progressMessage.value = '准备分析...'
  try {
    for await (const event of api.analyzeStream()) {
      const stage = event.stage
      if (stage === 'progress') {
        progressPercent.value = event.percent || 0
        progressMessage.value = event.message || 'AI 分析中...'
      } else if (stage === 'analyzing' && event.chunk) {
        streamingContent.value += event.chunk
      } else if (stage === 'done') {
        progressPercent.value = 100
        progressMessage.value = '分析完成！'
        store.setDocument(store.documentInfo, store.pdfUrl, {
          success: true,
          document_info: store.documentInfo,
          analysis: event.analysis,
        })
        streamingContent.value = ''
        await loadProfileDetail()
      } else if (stage === 'error') {
        throw new Error(event.message)
      }
    }
  } catch (e) {
    console.error('AI 分析失败:', e.message)
    if (!streamingContent.value) {
      streamingContent.value = `> ⚠️ AI 分析失败: ${e.message}\n\n文档已解析就绪，你可以正常使用问答、翻译、代码功能。`
    }
  } finally {
    isAnalyzing.value = false
    progressPercent.value = 0
  }
}

const resetUpload = () => {
  streamingContent.value = ''
  isAnalyzing.value = false
  profileDetail.value = null
  store.documentInfo = null
  store.pdfUrl = null
  store.analysisResult = null
  store._persist()
}

const copyLabel = ref('复制')
const getMarkdownContent = () => {
  if (store.analysisResult) return store.analysisResult.analysis || store.analysisResult.summary || ''
  return streamingContent.value || ''
}
const copyMarkdown = async () => {
  try {
    await navigator.clipboard.writeText(getMarkdownContent())
    copyLabel.value = '已复制'
    setTimeout(() => { copyLabel.value = '复制' }, 2000)
  } catch (e) { alert('复制失败') }
}
const downloadMarkdown = () => {
  const content = getMarkdownContent()
  const filename = (store.documentInfo?.filename || 'analysis').replace(/\.[^.]+$/, '') + '_analysis.md'
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}
const exportLabel = ref('导出 Word')
const exportWord = async () => {
  exportLabel.value = '生成中...'
  try {
    await api.exportReport(annotations.value)
    exportLabel.value = '已导出'
    setTimeout(() => { exportLabel.value = '导出 Word' }, 2000)
  } catch (e) {
    exportLabel.value = '导出失败'
    setTimeout(() => { exportLabel.value = '导出 Word' }, 2000)
  }
}
</script>

<style scoped>
.analyze-page { height: 100vh; display: flex; flex-direction: column; }
.status-hint {
  display: flex; align-items: center; gap: 0.4rem; font-size: 0.82rem; color: var(--accent-1);
}
.mono { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; }
.badge-count {
  font-size: 0.65rem; font-weight: 700; background: var(--accent-1); color: #fff;
  border-radius: 0.4rem; padding: 0.05rem 0.35rem;
}
.btn-secondary.active {
  color: var(--accent-1); background: rgba(56, 189, 248, 0.1);
  border-color: rgba(56, 189, 248, 0.3);
}

/* 进度条 */
.progress-track {
  height: 3px; background: var(--bg-input); position: relative; flex-shrink: 0;
}
.progress-fill {
  height: 100%; background: linear-gradient(90deg, var(--accent-1), var(--accent-2), var(--accent-3));
  border-radius: 0 3px 3px 0; transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1); min-width: 2%;
}

/* Body */
.analyze-body { flex: 1; display: flex; overflow: hidden; position: relative; }

/* PDF 面板 */
.pdf-pane {
  width: 50%; flex-shrink: 0; border-right: 1px solid var(--border-default);
  background: var(--bg-inset); display: flex; flex-direction: column;
  transition: width 0.3s ease;
}
.pdf-pane.narrow { width: 38%; }
.pdf-scroll { flex: 1; overflow-y: auto; padding: 1.5rem; }
.pdf-doc {
  max-width: 780px; margin: 0 auto; background: #fff;
  border-radius: 0.5rem; overflow: hidden; box-shadow: var(--shadow-card-lg);
}

/* 上传空状态 */
.upload-empty { flex: 1; display: flex; align-items: center; justify-content: center; padding: 2rem; }
.upload-zone {
  display: flex; flex-direction: column; align-items: center; text-align: center;
  gap: 0.8rem; padding: 3rem 2rem; max-width: 420px; width: 100%;
  border: 2px dashed var(--border-hover); border-radius: 1.25rem;
  color: var(--accent-1); background: var(--bg-surface); transition: all 0.25s;
}
.upload-zone.active {
  border-color: var(--border-accent); background: rgba(56, 189, 248, 0.05);
  box-shadow: var(--shadow-glow);
}
.upload-zone h3 { font-size: 1rem; font-weight: 600; color: var(--text-heading); }
.upload-zone p { font-size: 0.8rem; color: var(--text-muted); }

/* 高亮弹窗 */
.highlight-popup {
  position: fixed; z-index: 100; display: flex; align-items: center; gap: 0.4rem;
  padding: 0.4rem; border-radius: 0.7rem;
  background: var(--bg-elevated); backdrop-filter: blur(16px);
  border: 1px solid var(--border-default); box-shadow: var(--shadow-card-lg);
}
.color-dot {
  width: 24px; height: 24px; border-radius: 50%; cursor: pointer;
  border: 2px solid transparent; transition: all 0.15s;
}
.color-dot:hover { transform: scale(1.2); border-color: #fff; }
.popup-close {
  padding: 0.35rem; border-radius: 0.45rem; color: var(--text-muted);
  cursor: pointer; background: none; border: none; transition: all 0.15s;
}
.popup-close:hover { color: var(--text-heading); background: var(--bg-input); }
.popup-enter-active { transition: all 0.15s ease-out; }
.popup-leave-active { transition: all 0.1s ease-in; }
.popup-enter-from, .popup-leave-to { opacity: 0; transform: translateY(6px) scale(0.95); }

/* 结果面板 */
.result-pane {
  width: 50%; display: flex; flex-direction: column;
  background: var(--bg-surface); transition: width 0.3s ease;
}
.result-pane.narrow { width: 32%; }
.result-scroll { flex: 1; overflow-y: auto; }
.result-empty { height: 100%; }
.result-content { padding: 1.5rem 2rem; }
.result-head {
  display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;
  font-size: 0.9rem; font-weight: 600; color: var(--text-heading);
}
.text-accent { color: var(--accent-1); }
.streaming-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--accent-1); animation: pulse 1s infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* 报告卡片视图 */
.view-switch {
  display: flex; align-items: center; gap: 0.2rem;
  padding: 0.2rem; border-radius: 0.5rem;
  background: var(--bg-input); border: 1px solid var(--border-default);
}
.view-btn {
  display: inline-flex; align-items: center; gap: 0.3rem;
  padding: 0.3rem 0.6rem; border-radius: 0.4rem; font-size: 0.72rem;
  color: var(--text-secondary); background: none; border: none; cursor: pointer;
  transition: all 0.15s;
}
.view-btn:hover { color: var(--text-heading); }
.view-btn.active { color: var(--accent-1); background: rgba(56, 189, 248, 0.12); }

.report-sections { display: flex; flex-direction: column; gap: 0.7rem; }
.report-section { padding: 0; overflow: hidden; }
.section-head {
  display: flex; align-items: center; justify-content: space-between;
  width: 100%; padding: 0.8rem 1rem; cursor: pointer;
  background: none; border: none; text-align: left;
}
.section-title {
  font-size: 0.88rem; font-weight: 600; color: var(--text-heading);
  font-family: 'Sora', 'Noto Sans SC', sans-serif;
}
.section-chevron {
  color: var(--text-muted); transition: transform 0.2s; flex-shrink: 0;
}
.section-body {
  padding: 0 1rem 1rem; border-top: 1px solid var(--border-default);
}

/* 标注侧边栏 */
.anno-pane {
  width: 300px; flex-shrink: 0; display: flex; flex-direction: column;
  background: var(--bg-elevated); border-left: 1px solid var(--border-default);
}
.anno-head {
  display: flex; align-items: center; gap: 0.5rem; padding: 0.9rem 1rem;
  border-bottom: 1px solid var(--border-default); font-size: 0.88rem;
  font-weight: 600; color: var(--text-heading);
}
.anno-count { font-size: 0.72rem; color: var(--text-muted); }
.anno-head .icon-btn { margin-left: auto; }
.icon-btn {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 0.4rem; border-radius: 0.5rem; color: var(--text-muted);
  cursor: pointer; background: none; border: none; transition: all 0.15s;
}
.icon-btn:hover { color: var(--text-heading); background: var(--bg-input); }
.icon-btn.danger:hover { color: var(--danger); background: rgba(248, 113, 113, 0.1); }

.anno-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 0.5rem; text-align: center; color: var(--text-muted); font-size: 0.75rem;
}
.anno-list { flex: 1; overflow-y: auto; padding: 0.6rem; }
.anno-item {
  padding: 0.7rem; border-radius: 0.7rem; margin-bottom: 0.5rem;
  background: var(--bg-surface); border-left: 3px solid;
}
.anno-text {
  font-size: 0.75rem; color: var(--text-primary); line-height: 1.6;
  padding: 0.4rem 0.5rem; border-radius: 0.4rem; margin-bottom: 0.4rem; font-style: italic;
}
.anno-note {
  display: flex; gap: 0.4rem; font-size: 0.72rem; color: var(--text-secondary);
  margin-bottom: 0.4rem;
}
.anno-actions { display: flex; align-items: center; gap: 0.3rem; margin-bottom: 0.3rem; }
.anno-btn {
  display: flex; align-items: center; gap: 0.25rem; padding: 0.25rem 0.5rem;
  border-radius: 0.4rem; font-size: 0.68rem; color: var(--text-muted);
  cursor: pointer; background: none; border: none; transition: all 0.15s;
}
.anno-btn:hover { color: var(--accent-1); background: rgba(56, 189, 248, 0.1); }
.anno-btn.danger:hover { color: var(--danger); background: rgba(248, 113, 113, 0.1); }
.anno-time { margin-left: auto; font-size: 0.62rem; color: var(--text-muted); }
.anno-edit { display: flex; gap: 0.35rem; }
.anno-input {
  flex: 1; padding: 0.4rem 0.6rem; border-radius: 0.45rem; font-size: 0.72rem;
  background: var(--bg-input); border: 1px solid var(--border-accent);
  color: var(--text-primary); outline: none;
}
.anno-save {
  padding: 0.3rem; border-radius: 0.45rem; color: var(--accent-1);
  background: rgba(56, 189, 248, 0.12); border: none; cursor: pointer;
}
.anno-foot {
  display: flex; gap: 0.4rem; padding: 0.7rem; border-top: 1px solid var(--border-default);
}

.slide-enter-active, .slide-leave-active { transition: width 0.3s ease, opacity 0.2s; }
.slide-enter-from, .slide-leave-to { width: 0 !important; opacity: 0; }
.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>