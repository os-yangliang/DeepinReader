<template>
  <div class="compare-page">
    <PageToolbar :icon="GitCompare" title="论文对比" subtitle="多文档深度对比分析" :accent="'var(--accent-1)'">
      <template #actions>
        <span v-if="selectedIds.length" class="select-count">已选 {{ selectedIds.length }}/3</span>
        <button v-if="selectedIds.length >= 2 && !isComparing && !comparisonResult" class="btn-primary" @click="startCompare">
          <Sparkles :size="16" /> 开始对比分析
        </button>
        <div v-if="isComparing" class="comparing-hint">
          <Loader2 :size="15" class="animate-spin" /> AI 对比分析中...
        </div>
        <button v-if="comparisonResult" class="btn-secondary" @click="resetCompare">
          <RotateCcw :size="14" /> 重新对比
        </button>
      </template>
    </PageToolbar>

    <div class="compare-body">
      <!-- 左侧文档选择 -->
      <div class="select-pane">
        <div class="select-head">
          <h3>选择论文</h3>
          <p>选择 2-3 篇已分析的论文进行对比</p>
        </div>

        <EmptyState v-if="documents.length === 0" :icon="FileSearch" title="暂无已加载文档" description="请先在分析页上传并分析论文" />

        <div v-else class="select-list">
          <div
            v-for="doc in documents"
            :key="doc.document_id"
            class="select-card"
            :class="{ selected: isSelected(doc.document_id), disabled: !doc.has_summary }"
            @click="toggleSelect(doc)"
          >
            <div class="select-indicator" :class="{ active: isSelected(doc.document_id) }">
              <Check v-if="isSelected(doc.document_id)" :size="12" />
              <span v-else>{{ getSelectOrder(doc.document_id) || '' }}</span>
            </div>
            <div class="select-info">
              <p class="select-title">{{ doc.title || doc.filename }}</p>
              <p class="select-sub">
                {{ doc.page_count || 0 }} 页
                <span :class="doc.has_summary ? 'analyzed' : 'not-analyzed'">
                  {{ doc.has_summary ? '已分析' : '未分析' }}
                </span>
              </p>
            </div>
            <div v-if="isSelected(doc.document_id)" class="order-badge">{{ getSelectOrder(doc.document_id) }}</div>
          </div>
        </div>
      </div>

      <!-- 右侧结果 -->
      <div class="result-pane">
        <div class="result-scroll" ref="resultRef">
          <EmptyState
            v-if="!streamingContent && !comparisonResult"
            :icon="GitCompare"
            title="论文对比分析"
            description="选择左侧 2-3 篇已分析的论文，AI 将自动生成结构化对比报告"
          />

          <div v-else class="result-content">
            <div class="result-head">
              <GitCompare :size="16" class="text-accent" />
              <span>对比分析报告</span>
              <span v-if="isComparing" class="streaming-dot"></span>
              <div class="flex-1"></div>
              <button v-if="!isComparing && displayContent" class="btn-ghost" @click="copyResult">
                <Copy :size="14" /> {{ copyLabel }}
              </button>
              <button v-if="!isComparing && displayContent" class="btn-ghost" @click="downloadResult">
                <Download :size="14" /> 下载 MD
              </button>
            </div>

            <div class="paper-tags">
              <div v-for="(id, idx) in selectedIds" :key="id" class="paper-tag">
                <span class="tag-num">{{ idx + 1 }}</span>
                <span>{{ getDocTitle(id) }}</span>
              </div>
            </div>

            <div class="markdown-content" v-html="renderedContent"></div>
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
  GitCompare, FileSearch, Check, Sparkles, Loader2, RotateCcw, Copy, Download,
} from 'lucide-vue-next'

const documents = ref([])
const selectedIds = ref([])
const isComparing = ref(false)
const streamingContent = ref('')
const comparisonResult = ref('')
const resultRef = ref(null)
const copyLabel = ref('复制')

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
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else if (selectedIds.value.length < 3) selectedIds.value.push(doc.document_id)
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
      if (event.stage === 'analyzing' && event.chunk) streamingContent.value += event.chunk
      else if (event.stage === 'done') {
        comparisonResult.value = event.analysis
        streamingContent.value = ''
      } else if (event.stage === 'error') throw new Error(event.message)
    }
  } catch (e) {
    console.error('对比分析失败:', e)
    if (!streamingContent.value) streamingContent.value = `> ⚠️ 对比分析失败: ${e.message}`
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
    copyLabel.value = '已复制'
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
.compare-page { height: 100vh; display: flex; flex-direction: column; }
.compare-body { flex: 1; display: flex; overflow: hidden; }

.select-count { font-size: 0.78rem; color: var(--text-muted); }
.comparing-hint {
  display: flex; align-items: center; gap: 0.4rem; font-size: 0.82rem; color: var(--accent-1);
}

/* 左侧选择面板 */
.select-pane {
  width: 300px; flex-shrink: 0; border-right: 1px solid var(--border-default);
  background: var(--bg-surface); overflow-y: auto; display: flex; flex-direction: column;
}
.select-head { padding: 1.1rem; border-bottom: 1px solid var(--border-default); }
.select-head h3 { font-size: 0.88rem; font-weight: 600; color: var(--text-heading); margin-bottom: 0.2rem; }
.select-head p { font-size: 0.72rem; color: var(--text-muted); }
.select-list { padding: 0.7rem; display: flex; flex-direction: column; gap: 0.5rem; }
.select-card {
  display: flex; align-items: center; gap: 0.6rem; padding: 0.7rem;
  border-radius: 0.7rem; border: 1px solid var(--border-default);
  cursor: pointer; transition: all 0.18s;
}
.select-card:hover { background: var(--bg-input); border-color: var(--border-hover); }
.select-card.selected {
  background: rgba(56, 189, 248, 0.06); border-color: rgba(56, 189, 248, 0.3);
}
.select-card.disabled { opacity: 0.45; cursor: not-allowed; }
.select-card.disabled:hover { background: transparent; }

.select-indicator {
  width: 22px; height: 22px; border-radius: 0.5rem;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  background: var(--bg-input); border: 1px solid var(--border-default);
  color: var(--text-muted); font-size: 0.7rem;
}
.select-indicator.active { background: var(--accent-1); border-color: var(--accent-1); color: #fff; }

.select-info { flex: 1; min-width: 0; }
.select-title { font-size: 0.8rem; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.select-sub { font-size: 0.7rem; color: var(--text-muted); margin-top: 2px; }
.analyzed { color: var(--positive); margin-left: 0.4rem; }
.not-analyzed { color: var(--warning); margin-left: 0.4rem; }

.order-badge {
  width: 20px; height: 20px; border-radius: 0.5rem;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
  color: #fff; font-size: 0.68rem; font-weight: 700; flex-shrink: 0;
}

/* 右侧结果 */
.result-pane {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
  background: var(--bg-inset);
}
.result-scroll { flex: 1; overflow-y: auto; height: 100%; }
.result-content { padding: 1.5rem 2rem; }
.result-head {
  display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;
  font-size: 0.9rem; font-weight: 600; color: var(--text-heading);
}
.text-accent { color: var(--accent-1); }
.streaming-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--accent-1);
  animation: pulse 1s infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.paper-tags { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.3rem; }
.paper-tag {
  display: flex; align-items: center; gap: 0.4rem; padding: 0.3rem 0.8rem 0.3rem 0.35rem;
  border-radius: 0.5rem; font-size: 0.75rem; color: var(--text-secondary);
  background: var(--bg-input); border: 1px solid var(--border-default);
}
.tag-num {
  width: 20px; height: 20px; border-radius: 0.4rem;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
  color: #fff; font-size: 0.65rem; font-weight: 700;
}

.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>