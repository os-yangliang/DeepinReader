<template>
  <div class="pdf-reader">
    <!-- 工具栏 -->
    <div class="pr-toolbar">
      <button class="pr-btn" @click="toggleToc" :class="{ active: showToc }" title="目录">
        <ListTree :size="16" />
      </button>

      <div class="pr-pager">
        <button class="pr-btn" @click="prevPage" :disabled="currentPage <= 1">
          <ChevronLeft :size="15" />
        </button>
        <input
          v-model.number="pageInput"
          class="pr-page-input"
          @keydown.enter="goToPage"
          @blur="goToPage"
        />
        <span class="pr-page-total">/ {{ numPages || '—' }}</span>
        <button class="pr-btn" @click="nextPage" :disabled="currentPage >= numPages">
          <ChevronRight :size="15" />
        </button>
      </div>

      <div class="pr-zoom">
        <button class="pr-btn" @click="zoomOut" title="缩小">
          <ZoomOut :size="15" />
        </button>
        <span class="pr-zoom-label">{{ Math.round(scale * 100) }}%</span>
        <button class="pr-btn" @click="zoomIn" title="放大">
          <ZoomIn :size="15" />
        </button>
      </div>

      <div class="pr-search">
        <Search :size="14" class="pr-search-icon" />
        <input
          v-model="searchQuery"
          class="pr-search-input"
          placeholder="搜索全文…"
          @keydown.enter="doSearch"
        />
        <button v-if="searchResults.length" class="pr-btn" @click="clearSearch" title="清除">
          <X :size="14" />
        </button>
      </div>
    </div>

    <div class="pr-body">
      <!-- 目录 / 搜索侧栏 -->
      <transition name="fade">
        <div v-if="showToc" class="pr-sidebar">
          <!-- Tab -->
          <div class="pr-side-tabs">
            <button class="pr-tab" :class="{ active: sideTab === 'toc' }" @click="sideTab = 'toc'">目录</button>
            <button class="pr-tab" :class="{ active: sideTab === 'search' }" @click="sideTab = 'search'">搜索</button>
          </div>

          <!-- 目录 -->
          <div v-if="sideTab === 'toc'" class="pr-side-scroll">
            <div v-if="toc.length === 0" class="pr-side-empty">该 PDF 无目录大纲</div>
            <div
              v-for="(item, i) in toc"
              :key="i"
              class="pr-toc-item"
              :style="{ paddingLeft: (item.level - 1) * 14 + 8 + 'px' }"
              :class="{ active: item.page === currentPage }"
              @click="jumpToPage(item.page)"
            >
              <span class="pr-toc-title">{{ item.title }}</span>
              <span class="pr-toc-page">{{ item.page }}</span>
            </div>
          </div>

          <!-- 搜索结果 -->
          <div v-else class="pr-side-scroll">
            <div v-if="searchResults.length === 0" class="pr-side-empty">
              {{ searched ? '无匹配结果' : '输入关键词搜索全文' }}
            </div>
            <div
              v-for="(m, i) in searchResults"
              :key="i"
              class="pr-toc-item"
              :class="{ active: m.page === currentPage }"
              @click="jumpToPage(m.page)"
            >
              <FileText :size="13" class="pr-result-icon" />
              <span class="pr-toc-title">第 {{ m.page }} 页</span>
              <span class="pr-toc-page">{{ m.count }} 处</span>
            </div>
          </div>
        </div>
      </transition>

      <!-- PDF 画布 -->
      <div class="pr-canvas" ref="canvasRef">
        <div v-if="loading" class="pr-loading">
          <Loader2 :size="22" class="animate-spin" />
          <span>加载中…</span>
        </div>
        <vue-pdf-embed
          v-show="!loading"
          ref="pdfRef"
          :source="source"
          :page="currentPage"
          :scale="displayScale"
          text-layer
          @progress="onProgress"
          @loaded="onLoaded"
          @loading-failed="onFailed"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import VuePdfEmbed from 'vue-pdf-embed'
import 'vue-pdf-embed/dist/styles/textLayer.css'
import {
  ListTree, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Search, X, FileText, Loader2,
} from 'lucide-vue-next'
import api from '../api'

const props = defineProps({
  source: { type: String, default: '' },
})

const pdfRef = ref(null)
const canvasRef = ref(null)

const currentPage = ref(1)
const pageInput = ref(1)
const numPages = ref(0)
const scale = ref(1.0)
const displayScale = ref(1.0)
const loading = ref(true)

const showToc = ref(false)
const sideTab = ref('toc')
const toc = ref([])

const searchQuery = ref('')
const searchResults = ref([])
const searched = ref(false)

watch(() => props.source, () => {
  loading.value = true
  toc.value = []
  searchResults.value = []
  searched.value = false
  searchQuery.value = ''
  currentPage.value = 1
  pageInput.value = 1
})

function onProgress() {}
function onLoaded(pdf) {
  loading.value = false
  numPages.value = pdf.numPages || 0
  loadToc()
}
function onFailed(err) {
  loading.value = false
  console.error('PDF 加载失败:', err)
}

async function loadToc() {
  try {
    const res = await api.getDocumentToc()
    toc.value = res.toc || []
  } catch (e) {
    toc.value = []
  }
}

function toggleToc() { showToc.value = !showToc.value }

function goToPage() {
  let p = parseInt(pageInput.value, 10)
  if (isNaN(p)) p = currentPage.value
  p = Math.max(1, Math.min(p, numPages.value || 1))
  currentPage.value = p
  pageInput.value = p
}
function jumpToPage(p) {
  const target = Math.max(1, Math.min(p, numPages.value || p))
  currentPage.value = target
  pageInput.value = target
}
function prevPage() { jumpToPage(currentPage.value - 1) }
function nextPage() { jumpToPage(currentPage.value + 1) }

function zoomIn() {
  scale.value = Math.min(3, scale.value + 0.2)
  applyScale()
}
function zoomOut() {
  scale.value = Math.max(0.4, scale.value - 0.2)
  applyScale()
}
function applyScale() {
  if (canvasRef.value) {
    const w = canvasRef.value.clientWidth - 48
    displayScale.value = scale.value
  } else {
    displayScale.value = scale.value
  }
}

async function doSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  searched.value = true
  try {
    const res = await api.searchDocument(q)
    searchResults.value = res.matches || []
    sideTab.value = 'search'
    showToc.value = true
  } catch (e) {
    searchResults.value = []
  }
}
function clearSearch() {
  searchQuery.value = ''
  searchResults.value = []
  searched.value = false
}

// 暴露给父组件：引用跳转
defineExpose({ jumpToPage, searchInDoc: (q) => { searchQuery.value = q; doSearch() } })

onMounted(() => {
  if (canvasRef.value) applyScale()
})
</script>

<style scoped>
.pdf-reader {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* 工具栏 */
.pr-toolbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-glass);
  flex-shrink: 0;
  flex-wrap: wrap;
}
.pr-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 0.5rem;
  color: var(--text-secondary);
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  cursor: pointer;
  transition: all 0.15s;
}
.pr-btn:hover:not(:disabled) { color: var(--text-heading); border-color: var(--border-hover); }
.pr-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.pr-btn.active { color: var(--accent-1); border-color: var(--border-accent); }

.pr-pager { display: flex; align-items: center; gap: 0.25rem; }
.pr-page-input {
  width: 42px;
  padding: 0.3rem 0.35rem;
  border-radius: 0.4rem;
  text-align: center;
  font-size: 0.82rem;
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  color: var(--text-primary);
  outline: none;
}
.pr-page-input:focus { border-color: var(--border-accent); }
.pr-page-total { font-size: 0.78rem; color: var(--text-muted); }

.pr-zoom { display: flex; align-items: center; gap: 0.25rem; }
.pr-zoom-label { font-size: 0.75rem; color: var(--text-muted); min-width: 42px; text-align: center; }

.pr-search { display: flex; align-items: center; gap: 0.35rem; flex: 1; min-width: 140px; }
.pr-search-icon { color: var(--text-muted); flex-shrink: 0; }
.pr-search-input {
  flex: 1;
  padding: 0.35rem 0.5rem;
  border-radius: 0.45rem;
  font-size: 0.8rem;
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  color: var(--text-primary);
  outline: none;
}
.pr-search-input:focus { border-color: var(--border-accent); }

/* body */
.pr-body { flex: 1; display: flex; overflow: hidden; position: relative; }

/* 侧栏 */
.pr-sidebar {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-default);
  background: var(--bg-surface);
  display: flex;
  flex-direction: column;
}
.pr-side-tabs {
  display: flex;
  gap: 0.25rem;
  padding: 0.5rem;
  border-bottom: 1px solid var(--border-default);
}
.pr-tab {
  flex: 1;
  padding: 0.35rem;
  border-radius: 0.45rem;
  font-size: 0.75rem;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
}
.pr-tab.active { color: var(--accent-1); background: rgba(56, 189, 248, 0.1); }
.pr-side-scroll { flex: 1; overflow-y: auto; padding: 0.4rem; }
.pr-side-empty { padding: 1.5rem 0.75rem; text-align: center; font-size: 0.75rem; color: var(--text-muted); }

.pr-toc-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.5rem;
  border-radius: 0.45rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.12s;
}
.pr-toc-item:hover { background: var(--bg-input); color: var(--text-heading); }
.pr-toc-item.active { background: rgba(56, 189, 248, 0.08); color: var(--accent-1); }
.pr-toc-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pr-toc-page { font-size: 0.7rem; color: var(--text-muted); flex-shrink: 0; }
.pr-result-icon { color: var(--text-muted); flex-shrink: 0; }

/* 画布 */
.pr-canvas {
  flex: 1;
  overflow-y: auto;
  display: flex;
  justify-content: center;
  padding: 0.75rem;
  background: var(--bg-inset);
}
.pr-canvas :deep(.vue-pdf-embed) {
  width: fit-content;
  max-width: 100%;
  margin: 0 auto;
  background: #fff;
  border-radius: 0.4rem;
  overflow: hidden;
  box-shadow: var(--shadow-card-lg);
}
.pr-loading {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>