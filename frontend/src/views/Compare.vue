<template>
  <div class="h-[calc(100vh-80px)] flex flex-col">
    <!-- 工具栏 -->
    <div class="h-14 toolbar-glass px-6 flex items-center justify-between z-20">
      <div class="flex items-center gap-2">
        <GitCompare :size="20" class="text-primary-400" />
        <h1 class="text-lg font-semibold text-white">论文对比分析</h1>
      </div>
      <div class="flex items-center gap-3">
        <span v-if="selectedIds.length" class="text-xs text-gray-400">
          已选 {{ selectedIds.length }}/3 篇
        </span>
        <button 
          v-if="selectedIds.length >= 2 && !isComparing && !comparisonResult"
          @click="startCompare"
          class="btn-glow text-sm px-5 py-2 flex items-center gap-2"
        >
          <Sparkles :size="16" />
          开始对比分析
        </button>
        <div v-if="isComparing" class="flex items-center gap-2 text-sm">
          <Loader2 :size="16" class="text-primary-400 animate-spin" />
          <span class="text-primary-400">AI 对比分析中...</span>
        </div>
        <button v-if="comparisonResult" @click="resetCompare" class="action-btn">
          <RotateCcw :size="13" />
          重新对比
        </button>
      </div>
    </div>

    <div class="flex-1 flex overflow-hidden">
      <!-- 左侧：文档选择 -->
      <div class="doc-select-panel border-r border-white/5">
        <div class="p-4">
          <h3 class="text-sm font-semibold text-white mb-1">选择论文</h3>
          <p class="text-xs text-gray-500 mb-4">选择 2-3 篇已分析的论文进行对比</p>
          
          <div v-if="documents.length === 0" class="empty-state">
            <FileSearch :size="32" class="text-gray-600 mb-3" />
            <p class="text-gray-500 text-sm mb-1">暂无已加载的文档</p>
            <p class="text-gray-600 text-xs">请先在分析页上传并分析论文</p>
          </div>

          <div v-else class="space-y-2">
            <div 
              v-for="doc in documents" :key="doc.document_id"
              class="doc-select-card"
              :class="{ 
                'doc-selected': isSelected(doc.document_id),
                'doc-disabled': !doc.has_summary 
              }"
              @click="toggleSelect(doc)"
            >
              <div class="flex items-center gap-3">
                <!-- 选择指示 -->
                <div class="select-indicator" :class="{ active: isSelected(doc.document_id) }">
                  <Check v-if="isSelected(doc.document_id)" :size="12" />
                  <span v-else class="text-xs text-gray-600">{{ getSelectOrder(doc.document_id) || '' }}</span>
                </div>
                
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 mb-1">
                    <FileText :size="13" class="text-gray-500 flex-shrink-0" />
                    <span class="text-sm text-white truncate">{{ doc.title || doc.filename }}</span>
                  </div>
                  <div class="flex items-center gap-2 text-xs text-gray-500">
                    <span v-if="doc.page_count">{{ doc.page_count }} 页</span>
                    <span v-if="doc.has_summary" class="text-green-400/70 flex items-center gap-1">
                      <BarChart3 :size="10" /> 已分析
                    </span>
                    <span v-else class="text-yellow-500/70">未分析</span>
                  </div>
                </div>

                <!-- 选中序号 -->
                <div v-if="isSelected(doc.document_id)" class="order-badge">
                  {{ getSelectOrder(doc.document_id) }}
                </div>
              </div>
            </div>
          </div>

          <!-- 提示 -->
          <div v-if="documents.length > 0 && documents.filter(d => d.has_summary).length < 2" class="mt-4 p-3 rounded-lg bg-yellow-500/5 border border-yellow-500/10">
            <p class="text-xs text-yellow-500/80">
              ⚠️ 至少需要 2 篇已分析的论文才能进行对比
            </p>
          </div>
        </div>
      </div>

      <!-- 右侧：对比结果 -->
      <div class="flex-1 bg-gray-900/80 backdrop-blur-xl flex flex-col">
        <div ref="resultRef" class="flex-1 overflow-y-auto custom-scrollbar p-8">
          <!-- 空状态 -->
          <div v-if="!streamingContent && !comparisonResult" class="flex flex-col items-center justify-center h-full text-center">
            <div class="compare-empty-icon mb-6">
              <GitCompare :size="40" class="text-gray-600" />
            </div>
            <h3 class="text-lg font-semibold text-white mb-2">论文对比分析</h3>
            <p class="text-gray-400 text-sm mb-1">选择左侧 2-3 篇已分析的论文</p>
            <p class="text-gray-500 text-xs">AI 将自动生成结构化对比报告</p>
            
            <div class="mt-8 grid grid-cols-3 gap-4 max-w-md">
              <div v-for="item in previewItems" :key="item.label" class="preview-card">
                <component :is="item.icon" :size="18" class="text-primary-400/60 mb-2" />
                <span class="text-xs text-gray-500">{{ item.label }}</span>
              </div>
            </div>
          </div>

          <!-- 内容 -->
          <div v-if="streamingContent || comparisonResult">
            <div class="flex items-center gap-2 mb-6">
              <GitCompare :size="16" class="text-primary-400" />
              <span class="text-sm font-medium text-white">对比分析报告</span>
              <span v-if="isComparing" class="streaming-dot ml-1"></span>
              <div class="flex-1"></div>
              <div v-if="!isComparing && displayContent" class="flex items-center gap-2">
                <button @click="copyResult" class="action-btn">
                  <Copy :size="13" />
                  {{ copyLabel }}
                </button>
                <button @click="downloadResult" class="action-btn">
                  <Download :size="13" />
                  下载 MD
                </button>
              </div>
            </div>
            
            <!-- 选中论文标签 -->
            <div class="flex flex-wrap gap-2 mb-6">
              <div v-for="(id, idx) in selectedIds" :key="id" class="paper-tag">
                <span class="tag-number">{{ idx + 1 }}</span>
                <span class="text-xs">{{ getDocTitle(id) }}</span>
              </div>
            </div>

            <div class="markdown-content prose prose-invert max-w-none text-sm" v-html="renderedContent"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { renderMarkdown } from '../utils/markdown'
import api from '../api'
import { store } from '../store'
import {
  GitCompare, FileSearch, FileText, BarChart3, Check, Sparkles,
  Loader2, RotateCcw, Copy, Download, Table, Lightbulb, Scale
} from 'lucide-vue-next'

const documents = ref([])
const selectedIds = ref([])
const isComparing = ref(false)
const streamingContent = ref('')
const comparisonResult = ref('')
const resultRef = ref(null)
const copyLabel = ref('复制')

const previewItems = [
  { icon: Table, label: '对比表格' },
  { icon: Scale, label: '方法对比' },
  { icon: Lightbulb, label: '创新分析' },
]

onMounted(async () => {
  try {
    const res = await api.getDocuments()
    documents.value = res.documents || []
  } catch (e) {
    console.error('获取文档列表失败:', e)
  }
})

const isSelected = (id) => selectedIds.value.includes(id)
const getSelectOrder = (id) => {
  const idx = selectedIds.value.indexOf(id)
  return idx >= 0 ? idx + 1 : 0
}
const getDocTitle = (id) => {
  const doc = documents.value.find(d => d.document_id === id)
  return doc?.title || doc?.filename || id
}

const toggleSelect = (doc) => {
  if (!doc.has_summary) return
  const idx = selectedIds.value.indexOf(doc.document_id)
  if (idx >= 0) {
    selectedIds.value.splice(idx, 1)
  } else if (selectedIds.value.length < 3) {
    selectedIds.value.push(doc.document_id)
  }
}

const displayContent = computed(() => streamingContent.value || comparisonResult.value || '')
const renderedContent = computed(() => displayContent.value ? renderMarkdown(displayContent.value) : '')

watch(streamingContent, async () => {
  await nextTick()
  if (resultRef.value) resultRef.value.scrollTop = resultRef.value.scrollHeight
})

const startCompare = async () => {
  if (selectedIds.value.length < 2) return
  isComparing.value = true
  streamingContent.value = ''
  comparisonResult.value = ''

  try {
    for await (const event of api.compareStream(selectedIds.value)) {
      if (event.stage === 'analyzing' && event.chunk) {
        streamingContent.value += event.chunk
      } else if (event.stage === 'done') {
        comparisonResult.value = event.analysis
        streamingContent.value = ''
      } else if (event.stage === 'error') {
        throw new Error(event.message)
      }
    }
  } catch (e) {
    console.error('对比分析失败:', e)
    if (!streamingContent.value) {
      streamingContent.value = `> ⚠️ 对比分析失败: ${e.message}`
    }
  } finally {
    isComparing.value = false
  }
}

const resetCompare = () => {
  streamingContent.value = ''
  comparisonResult.value = ''
}

const copyResult = async () => {
  try {
    await navigator.clipboard.writeText(displayContent.value)
    copyLabel.value = '✅ 已复制'
    setTimeout(() => { copyLabel.value = '复制' }, 2000)
  } catch (e) { alert('复制失败') }
}

const downloadResult = () => {
  const blob = new Blob([displayContent.value], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'paper_comparison.md'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.toolbar-glass {
  background: var(--bg-glass);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-default);
}

.doc-select-panel {
  width: 320px;
  flex-shrink: 0;
  background: var(--bg-surface);
  overflow-y: auto;
}

.doc-select-card {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border-default);
  cursor: pointer;
  transition: all 0.25s;
}
.doc-select-card:hover { background: var(--bg-surface-hover); border-color: var(--border-hover); }
.doc-selected {
  background: rgba(14, 165, 233, 0.06) !important;
  border-color: rgba(14, 165, 233, 0.25) !important;
}
.doc-disabled {
  opacity: 0.45;
  cursor: not-allowed !important;
}
.doc-disabled:hover { background: transparent !important; }

.select-indicator {
  width: 24px; height: 24px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-input); border: 1px solid var(--border-default);
  flex-shrink: 0; transition: all 0.25s; color: var(--text-muted);
}
.select-indicator.active {
  background: #0ea5e9; border-color: #0ea5e9; color: white;
}
.order-badge {
  width: 22px; height: 22px; border-radius: 7px;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: white; font-size: 11px; font-weight: 700; flex-shrink: 0;
}

.compare-empty-icon {
  width: 80px; height: 80px; border-radius: 24px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-input); border: 1px solid var(--border-default);
}
.preview-card {
  display: flex; flex-direction: column; align-items: center;
  padding: 16px 12px; border-radius: 12px;
  background: var(--bg-surface); border: 1px solid var(--border-default);
}

.paper-tag {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 12px 4px 4px; border-radius: 8px;
  background: rgba(14, 165, 233, 0.08); border: 1px solid rgba(14, 165, 233, 0.15);
}
.tag-number {
  width: 20px; height: 20px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: white; font-size: 10px; font-weight: 700;
}

.streaming-dot {
  display: inline-block; width: 6px; height: 6px;
  border-radius: 50%; background: #0ea5e9;
  animation: pulse-dot 1s ease-in-out infinite;
}
@keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.btn-glow {
  display: inline-flex; align-items: center; font-weight: 600; color: white;
  border-radius: 12px; background: linear-gradient(135deg, #0ea5e9, #6366f1);
  transition: all 0.3s;
}
.btn-glow:hover { box-shadow: 0 8px 25px rgba(14, 165, 233, 0.4); transform: translateY(-2px); }

.action-btn {
  display: flex; align-items: center; gap: 5px; padding: 6px 12px; border-radius: 8px;
  background: var(--bg-input); border: 1px solid var(--border-default);
  color: var(--text-secondary); font-size: 12px; transition: all 0.2s; cursor: pointer;
}
.action-btn:hover { background: var(--bg-surface-hover); color: var(--text-heading); }

.empty-state { text-align: center; padding: 32px 16px; }

.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(99, 102, 241, 0.2); border-radius: 3px; }
</style>
