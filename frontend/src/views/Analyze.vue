<template>
  <div class="h-[calc(100vh-80px)] flex flex-col">
    <!-- 顶部工具栏 -->
    <div class="h-14 toolbar-glass px-6 flex items-center justify-between z-20">
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <FileSearch :size="20" class="text-primary-400" />
          <h1 class="text-lg font-semibold text-white">论文分析</h1>
        </div>
        <div v-if="store.documentInfo" class="flex items-center gap-2 text-gray-400 text-sm border-l border-white/10 pl-4">
          <FileText :size="14" />
          <span class="max-w-[200px] truncate">{{ store.documentInfo.filename }}</span>
          <span v-if="isDocReady" class="text-green-400 text-xs flex items-center gap-1">
            <Check :size="12" /> 就绪
          </span>
        </div>
      </div>
      
      <div class="flex items-center gap-3">
        <!-- 上传按钮 -->
        <button 
          v-if="!store.pdfUrl"
          @click="triggerFileInput"
          class="btn-glow text-sm px-4 py-2 flex items-center gap-2"
        >
          <Upload :size="16" />
          上传论文
        </button>

        <!-- 上传中 -->
        <div v-if="isUploading" class="flex items-center gap-3 text-sm">
          <Loader2 :size="16" class="text-primary-400 animate-spin" />
          <span class="text-primary-400">{{ uploadStatus }}</span>
        </div>

        <!-- 开始分析 -->
        <button 
          v-if="isDocReady && !isAnalyzing && !store.analysisResult && !streamingContent"
          @click="startAnalysis"
          class="btn-glow text-sm px-5 py-2 flex items-center gap-2"
        >
          <Sparkles :size="16" />
          开始智能分析
        </button>
        
        <!-- 分析中 -->
        <div v-if="isAnalyzing" class="flex items-center gap-3 text-sm">
          <Loader2 :size="16" class="text-primary-400 animate-spin" />
          <span class="text-primary-400">{{ progressMessage }}</span>
          <span class="text-primary-500/70 font-mono text-xs">{{ progressPercent }}%</span>
        </div>

        <!-- 标注按钮 -->
        <button 
          v-if="store.pdfUrl" 
          @click="showAnnotations = !showAnnotations"
          class="action-btn flex items-center gap-1.5"
          :class="{ 'annotation-btn-active': showAnnotations }"
        >
          <Highlighter :size="14" />
          标注
          <span v-if="annotations.length" class="anno-badge">{{ annotations.length }}</span>
        </button>

        <button 
          v-if="store.pdfUrl"
          @click="resetUpload"
          class="text-gray-400 hover:text-white text-sm px-3 py-2 transition-colors flex items-center gap-1.5"
        >
          <RotateCcw :size="14" />
          {{ !store.analysisResult ? '取消' : '重新上传' }}
        </button>
      </div>
    </div>

    <!-- 进度条 -->
    <div v-if="isAnalyzing" class="progress-bar-container">
      <div class="progress-bar" :style="{ width: progressPercent + '%' }">
        <div class="progress-bar-glow"></div>
      </div>
    </div>

    <!-- 主体内容区 -->
    <div class="flex-1 flex overflow-hidden relative">
      
      <!-- 左侧：PDF 阅读器 -->
      <div class="pdf-panel bg-gray-900/50 relative flex flex-col border-r border-white/5"
           :class="{ 'pdf-panel-narrow': showAnnotations }"
           @mouseup="handlePdfSelection">
        <div v-if="store.pdfUrl" class="flex-1 overflow-y-auto custom-scrollbar p-8 flex justify-center">
          <div class="w-full max-w-4xl shadow-2xl">
            <vue-pdf-embed :source="store.pdfUrl" class="rounded-lg overflow-hidden" />
          </div>
        </div>
        
        <!-- 上传空状态 -->
        <div v-else class="flex-1 flex flex-col items-center justify-center p-12 text-center"
             @dragover.prevent="isDragging = true"
             @dragleave.prevent="isDragging = false"
             @drop.prevent="handleDrop">
          
          <div class="upload-zone" :class="{ 'upload-zone-active': isDragging }">
            <div class="upload-icon-wrapper">
              <div class="upload-icon">
                <FileUp :size="32" class="text-primary-400/70" />
              </div>
              <div class="upload-icon-ring"></div>
            </div>
            <h3 class="text-lg font-semibold text-white mb-2">上传学术论文</h3>
            <p class="text-gray-400 text-sm mb-6">拖拽文件到此处，或点击选择文件</p>
            <p class="text-gray-500 text-xs mb-6">支持 PDF 格式 · 选中文字可添加标注</p>
            
            <button @click="triggerFileInput" class="btn-glow px-8 py-3 text-sm flex items-center gap-2 mx-auto">
              <Upload :size="16" />
              选择文件
            </button>
            <input ref="fileInputRef" type="file" accept=".pdf" class="hidden" @change="handleFileSelect" />
          </div>
        </div>

        <!-- 选中文字后的高亮弹窗 -->
        <transition name="popup">
          <div v-if="selectionPopup.show" class="highlight-popup" :style="{ top: selectionPopup.y + 'px', left: selectionPopup.x + 'px' }">
            <div class="highlight-popup-inner">
              <div class="highlight-colors">
                <button v-for="c in highlightColors" :key="c.name" 
                  @click="addAnnotation(c.color)" 
                  class="color-dot" :style="{ background: c.color }"
                  :title="c.name">
                </button>
              </div>
              <button @click="selectionPopup.show = false" class="popup-close-sm">
                <X :size="12" />
              </button>
            </div>
          </div>
        </transition>
      </div>

      <!-- 右侧：分析结果面板 -->
      <div class="result-panel flex flex-col bg-gray-900/80 backdrop-blur-xl"
           :class="{ 'result-panel-narrow': showAnnotations }">
        <div ref="resultPanelRef" class="flex-1 overflow-y-auto custom-scrollbar p-8">
          <!-- 空状态 -->
          <div v-if="!streamingContent && !store.analysisResult" class="flex flex-col items-center justify-center h-full text-center">
            <div class="empty-icon-wrapper mb-4">
              <BarChart3 :size="28" class="text-gray-600" />
            </div>
            <p v-if="isDocReady" class="text-gray-400 text-sm">✅ 文档已就绪，点击上方「开始智能分析」生成 AI 报告<br><span class="text-gray-500 text-xs">选中 PDF 文字可添加高亮标注</span></p>
            <p v-else class="text-gray-500 text-sm">上传论文后生成 AI 分析报告</p>
          </div>
          
          <!-- 流式输出中 / 分析结果 -->
          <div v-if="streamingContent || store.analysisResult">
            <div class="flex items-center justify-between mb-6">
              <div class="flex items-center gap-2">
                <Sparkles :size="16" class="text-primary-400" />
                <span class="text-sm font-medium text-white">分析报告</span>
                <span v-if="isAnalyzing" class="streaming-dot ml-2"></span>
              </div>
              <div v-if="!isAnalyzing && displayContent" class="flex items-center gap-2">
                <button @click="copyMarkdown" class="action-btn">
                  <Copy :size="13" />
                  {{ copyLabel }}
                </button>
                <button @click="downloadMarkdown" class="action-btn">
                  <Download :size="13" />
                  下载 MD
                </button>
                <button @click="exportWord" class="action-btn export-word-btn">
                  <FileDown :size="13" />
                  {{ exportLabel }}
                </button>
              </div>
            </div>
            <div class="markdown-content prose prose-invert max-w-none text-sm" v-html="renderedContent"></div>
          </div>
        </div>
      </div>

      <!-- 标注侧边栏 -->
      <transition name="slide-anno">
        <div v-if="showAnnotations" class="anno-sidebar">
          <div class="anno-header">
            <div class="flex items-center gap-2">
              <Highlighter :size="16" class="text-primary-400" />
              <span class="text-sm font-semibold text-white">标注笔记</span>
              <span class="text-xs text-gray-500">{{ annotations.length }}</span>
            </div>
            <button @click="showAnnotations = false" class="text-gray-500 hover:text-white transition-colors">
              <X :size="16" />
            </button>
          </div>

          <div v-if="annotations.length === 0" class="anno-empty">
            <Highlighter :size="24" class="text-gray-600 mb-2" />
            <p class="text-gray-500 text-xs">选中 PDF 文字后<br>点击颜色即可添加标注</p>
          </div>

          <div v-else class="anno-list custom-scrollbar">
            <div v-for="(anno, idx) in annotations" :key="anno.id" class="anno-item" :style="{ borderLeftColor: anno.color }">
              <div class="anno-text" :style="{ backgroundColor: anno.color + '15' }">
                "{{ anno.text.length > 80 ? anno.text.slice(0, 80) + '...' : anno.text }}"
              </div>
              
              <!-- 笔记 -->
              <div v-if="anno.note" class="anno-note">
                <StickyNote :size="11" class="text-gray-500 flex-shrink-0 mt-0.5" />
                <span>{{ anno.note }}</span>
              </div>

              <!-- 操作栏 -->
              <div class="anno-actions">
                <button @click="askAboutAnnotation(anno)" class="anno-action-btn" title="让 AI 解释">
                  <MessageCircle :size="12" />
                  问 AI
                </button>
                <button @click="editNote(idx)" class="anno-action-btn" title="编辑笔记">
                  <Edit3 :size="12" />
                </button>
                <button @click="removeAnnotation(idx)" class="anno-action-btn anno-delete" title="删除">
                  <Trash2 :size="12" />
                </button>
                <span class="text-[10px] text-gray-600 ml-auto">{{ formatTime(anno.timestamp) }}</span>
              </div>

              <!-- 编辑笔记输入 -->
              <div v-if="editingIndex === idx" class="anno-note-edit">
                <input 
                  v-model="editNoteText" 
                  @keydown.enter="saveNote(idx)"
                  @keydown.escape="editingIndex = -1"
                  placeholder="输入笔记..."
                  class="anno-note-input"
                  ref="noteInputRef"
                />
                <button @click="saveNote(idx)" class="anno-save-btn">
                  <Check :size="12" />
                </button>
              </div>
            </div>
          </div>

          <!-- 底部：导出标注 -->
          <div v-if="annotations.length > 0" class="anno-footer">
            <button @click="exportAnnotations" class="anno-export-btn">
              <Download :size="13" />
              导出标注
            </button>
            <button @click="clearAnnotations" class="anno-clear-btn">
              <Trash2 :size="13" />
            </button>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { renderMarkdown } from '../utils/markdown'
import VuePdfEmbed from 'vue-pdf-embed'
import api from '../api'
import { store } from '../store'
import { 
  FileSearch, FileText, Upload, Loader2, RotateCcw, FileUp,
  BarChart3, Sparkles, Copy, Download, Check, X, Highlighter,
  MessageCircle, Edit3, Trash2, StickyNote, FileDown
} from 'lucide-vue-next'

const router = useRouter()
const file = ref(null) 
const isDragging = ref(false)
const isUploading = ref(false)
const isAnalyzing = ref(false)
const isDocReady = computed(() => !!store.documentInfo?.document_id)
const uploadStatus = ref('')
const fileInputRef = ref(null)
const resultPanelRef = ref(null)
const streamingContent = ref('')
const progressPercent = ref(0)
const progressMessage = ref('准备分析...')

// 标注相关
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

// 从 localStorage 加载标注
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

// 监听文档切换，重新加载标注
watch(() => store.documentInfo, () => {
  annotations.value = []
  loadAnnotations()
}, { immediate: true })

// PDF 文字选中
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
  
  annotations.value.unshift({
    id: Date.now(),
    text,
    color,
    note: '',
    timestamp: new Date().toISOString(),
  })
  
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
  // focus input
  const inputs = document.querySelectorAll('.anno-note-input')
  inputs[0]?.focus()
}

const saveNote = (idx) => {
  annotations.value[idx].note = editNoteText.value.trim()
  editingIndex.value = -1
  editNoteText.value = ''
  saveAnnotationsToStorage()
}

const askAboutAnnotation = (anno) => {
  // 将标注文本存入 store，然后跳转到问答页
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
  let md = `# 📝 ${docName} — 标注笔记\n\n`
  md += `> 共 ${annotations.value.length} 条标注\n\n---\n\n`
  
  annotations.value.forEach((anno, i) => {
    md += `### ${i + 1}. 高亮\n\n`
    md += `> ${anno.text}\n\n`
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
  return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`
}

// ---- 以下为原有逻辑 ----

const displayContent = computed(() => {
  if (streamingContent.value) return streamingContent.value
  const r = store.analysisResult
  if (r) return r.analysis || r.summary || ''
  return ''
})

const renderedContent = computed(() => displayContent.value ? renderMarkdown(displayContent.value) : '')

watch(streamingContent, async () => {
  await nextTick()
  if (resultPanelRef.value) {
    resultPanelRef.value.scrollTop = resultPanelRef.value.scrollHeight
  }
})

const triggerFileInput = () => fileInputRef.value?.click()

const handleFileSelect = (e) => {
  const selectedFile = e.target.files?.[0]
  if (selectedFile) {
    file.value = selectedFile
    const url = URL.createObjectURL(selectedFile)
    store.setDocument({ filename: selectedFile.name }, url, null)
    e.target.value = ''
    uploadOnly(selectedFile)
  }
}

const handleDrop = (e) => {
  isDragging.value = false
  const droppedFile = e.dataTransfer.files?.[0]
  if (droppedFile && droppedFile.type === 'application/pdf') {
    file.value = droppedFile
    const url = URL.createObjectURL(droppedFile)
    store.setDocument({ filename: droppedFile.name }, url, null)
    uploadOnly(droppedFile)
  } else {
    alert('请上传 PDF 文件')
  }
}

const uploadOnly = async (uploadFile) => {
  isUploading.value = true
  isAnalyzing.value = false
  streamingContent.value = ''
  uploadStatus.value = '正在解析文档...'
  
  try {
    const result = await api.uploadDocument(uploadFile)
    if (!result.success) throw new Error(result.error || '上传失败')
    const docInfo = result.document_info
    if (store.pdfUrl?.startsWith('blob:')) URL.revokeObjectURL(store.pdfUrl)
    store.setDocument(docInfo, docInfo.file_url, null)
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

const resetUpload = async () => {
  file.value = null
  streamingContent.value = ''
  isAnalyzing.value = false
  // 只清除当前文档的视图状态，保留所有已加载文档（后端+前端）
  store.documentInfo = null
  store.pdfUrl = null
  store.analysisResult = null
  store._persist()
}

const copyLabel = ref('复制 MD')
const getMarkdownContent = () => {
  if (store.analysisResult) return store.analysisResult.analysis || store.analysisResult.summary || ''
  return streamingContent.value || ''
}

const copyMarkdown = async () => {
  try {
    await navigator.clipboard.writeText(getMarkdownContent())
    copyLabel.value = '✅ 已复制'
    setTimeout(() => { copyLabel.value = '复制 MD' }, 2000)
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
    exportLabel.value = '✅ 已导出'
    setTimeout(() => { exportLabel.value = '导出 Word' }, 2000)
  } catch (e) {
    console.error('导出失败:', e)
    exportLabel.value = '导出失败'
    setTimeout(() => { exportLabel.value = '导出 Word' }, 2000)
  }
}
</script>

<style scoped>
.toolbar-glass {
  background: var(--bg-glass);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-default);
  transition: background 0.3s;
}

/* 进度条 */
.progress-bar-container {
  height: 3px;
  background: var(--bg-input);
  position: relative;
  z-index: 20;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #0ea5e9, #6366f1, #8b5cf6);
  border-radius: 0 3px 3px 0;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  min-width: 2%;
}
.progress-bar-glow {
  position: absolute;
  right: 0;
  top: -3px;
  width: 60px;
  height: 9px;
  background: radial-gradient(ellipse, rgba(99, 102, 241, 0.6), transparent);
  border-radius: 50%;
  animation: progress-pulse 1.5s ease-in-out infinite;
}
@keyframes progress-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

/* 弹性面板布局 */
.pdf-panel { width: 50%; transition: width 0.3s ease; }
.result-panel { width: 50%; transition: width 0.3s ease; }
.pdf-panel-narrow { width: 38%; }
.result-panel-narrow { width: 32%; }

.btn-glow {
  display: inline-flex;
  align-items: center;
  font-weight: 600;
  color: white;
  border-radius: 12px;
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  transition: all 0.3s;
}
.btn-glow:hover {
  box-shadow: 0 8px 25px rgba(14, 165, 233, 0.4);
  transform: translateY(-2px);
}

.upload-zone {
  padding: 48px;
  border-radius: 24px;
  border: 2px dashed var(--border-default);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.03), rgba(99, 102, 241, 0.03));
  transition: all 0.4s;
  max-width: 480px;
  width: 100%;
}
.upload-zone-active {
  border-color: rgba(14, 165, 233, 0.5);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(99, 102, 241, 0.06));
  box-shadow: 0 0 40px rgba(14, 165, 233, 0.15);
}
.upload-icon-wrapper { position: relative; width: 72px; height: 72px; margin: 0 auto 20px; }
.upload-icon {
  width: 72px; height: 72px; border-radius: 22px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(14, 165, 233, 0.08); border: 1px solid rgba(14, 165, 233, 0.12);
  position: relative; z-index: 2;
}
.upload-icon-ring {
  position: absolute; inset: -8px; border-radius: 28px;
  border: 1px solid rgba(14, 165, 233, 0.08);
  animation: upload-pulse 2s ease-in-out infinite;
}
@keyframes upload-pulse {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.08); opacity: 0.2; }
}

.empty-icon-wrapper {
  width: 64px; height: 64px; border-radius: 20px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-input); border: 1px solid var(--border-default);
}

.streaming-dot {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #0ea5e9;
  animation: pulse-dot 1s ease-in-out infinite;
}
@keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.action-btn {
  display: flex; align-items: center; gap: 5px; padding: 6px 12px; border-radius: 8px;
  background: var(--bg-input); border: 1px solid var(--border-default);
  color: var(--text-secondary); font-size: 12px; transition: all 0.2s; cursor: pointer;
}
.action-btn:hover { background: var(--bg-surface-hover); color: var(--text-heading); }
.export-word-btn:hover { border-color: rgba(14, 165, 233, 0.3); color: #38bdf8 !important; }

.annotation-btn-active {
  background: rgba(14, 165, 233, 0.12) !important;
  border-color: rgba(14, 165, 233, 0.3) !important;
  color: #38bdf8 !important;
}
.anno-badge {
  font-size: 10px; font-weight: 700; background: #0ea5e9; color: white;
  border-radius: 6px; padding: 1px 5px; min-width: 16px; text-align: center;
}

/* ===== 高亮弹窗 ===== */
.highlight-popup {
  position: fixed; z-index: 100;
  border-radius: 12px;
  background: var(--bg-elevated);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border-default);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
  padding: 6px;
}
.highlight-popup-inner { display: flex; align-items: center; gap: 4px; }
.highlight-colors { display: flex; gap: 5px; padding: 4px 6px; }
.color-dot {
  width: 22px; height: 22px; border-radius: 50%; cursor: pointer;
  border: 2px solid transparent; transition: all 0.2s;
}
.color-dot:hover { transform: scale(1.2); border-color: white; box-shadow: 0 0 10px currentColor; }
.popup-close-sm {
  padding: 4px; border-radius: 6px; color: var(--text-muted);
  cursor: pointer; transition: all 0.2s;
}
.popup-close-sm:hover { color: var(--text-heading); background: var(--bg-input); }

.popup-enter-active { animation: popupIn 0.15s ease-out; }
.popup-leave-active { animation: popupOut 0.1s ease-in; }
@keyframes popupIn { from { opacity: 0; transform: translateY(6px) scale(0.95); } to { opacity: 1; transform: none; } }
@keyframes popupOut { from { opacity: 1; } to { opacity: 0; transform: translateY(4px); } }

/* ===== 标注侧边栏 ===== */
.anno-sidebar {
  width: 30%;
  min-width: 280px;
  max-width: 360px;
  display: flex;
  flex-direction: column;
  background: var(--bg-elevated);
  backdrop-filter: blur(16px);
  border-left: 1px solid var(--border-default);
}
.anno-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid var(--border-default);
}
.anno-empty {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; padding: 32px; text-align: center;
}
.anno-list { flex: 1; overflow-y: auto; padding: 8px; }
.anno-item {
  padding: 10px 12px; border-radius: 10px; margin-bottom: 6px;
  background: var(--bg-surface); border-left: 3px solid;
  transition: all 0.2s;
}
.anno-item:hover { background: var(--bg-surface-hover); }
.anno-text {
  font-size: 12px; color: var(--text-primary); line-height: 1.6;
  padding: 6px 8px; border-radius: 6px; margin-bottom: 6px;
  font-style: italic;
}
.anno-note {
  display: flex; gap: 4px; font-size: 11px; color: var(--text-secondary);
  padding: 4px 0; margin-bottom: 4px;
}
.anno-actions { display: flex; align-items: center; gap: 4px; }
.anno-action-btn {
  display: flex; align-items: center; gap: 3px;
  padding: 3px 8px; border-radius: 6px; font-size: 11px;
  color: var(--text-muted); cursor: pointer; transition: all 0.2s;
}
.anno-action-btn:hover { color: #38bdf8; background: rgba(14, 165, 233, 0.08); }
.anno-delete:hover { color: #f87171 !important; background: rgba(248, 113, 113, 0.08) !important; }
.anno-note-edit {
  display: flex; gap: 4px; margin-top: 6px;
}
.anno-note-input {
  flex: 1; padding: 6px 10px; border-radius: 8px; font-size: 12px;
  background: var(--bg-input); border: 1px solid var(--border-accent);
  color: var(--text-primary); outline: none;
}
.anno-note-input:focus { border-color: #0ea5e9; }
.anno-save-btn {
  padding: 6px; border-radius: 8px; background: rgba(14, 165, 233, 0.15);
  color: #38bdf8; cursor: pointer; transition: all 0.2s;
}
.anno-save-btn:hover { background: rgba(14, 165, 233, 0.25); }
.anno-footer {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 12px; border-top: 1px solid var(--border-default);
}
.anno-export-btn {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 8px; border-radius: 8px; font-size: 12px;
  background: var(--bg-input); color: var(--text-secondary);
  cursor: pointer; transition: all 0.2s;
}
.anno-export-btn:hover { background: var(--bg-surface-hover); color: var(--text-heading); }
.anno-clear-btn {
  padding: 8px; border-radius: 8px; color: var(--text-muted);
  cursor: pointer; transition: all 0.2s;
}
.anno-clear-btn:hover { color: #f87171; background: rgba(248, 113, 113, 0.08); }

.slide-anno-enter-active, .slide-anno-leave-active {
  transition: width 0.3s ease, opacity 0.2s;
}
.slide-anno-enter-from, .slide-anno-leave-to {
  width: 0 !important; min-width: 0 !important; opacity: 0;
}

.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(99, 102, 241, 0.2); border-radius: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(99, 102, 241, 0.4); }
</style>