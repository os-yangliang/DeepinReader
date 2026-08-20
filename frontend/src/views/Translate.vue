<template>
  <div class="translate-page">
    <PageToolbar :icon="Globe" title="全文翻译" subtitle="学术级双语对照" :accent="'var(--accent-1)'">
      <template #actions>
        <button v-if="store.pdfUrl && !isTranslating && !translatedUrl" class="btn-primary" @click="startTranslation">
          <Languages :size="16" />
          开始翻译
        </button>
        <button v-if="translateError && !isTranslating && !translatedUrl" class="btn-secondary" @click="startTranslation">
          <RotateCcw :size="14" /> 重试
        </button>
        <div v-if="isTranslating" class="translating-hint">
          <Loader2 :size="15" class="spin" />
          <span>{{ translateStatus }}</span>
        </div>

        <div v-if="translatedUrl || dualUrl" class="mode-switch">
          <button v-if="dualUrl" @click="viewMode = 'dual'" class="mode-btn" :class="{ active: viewMode === 'dual' }">
            <Columns2 :size="14" /> 双语
          </button>
          <button v-if="translatedUrl" @click="viewMode = 'translated'" class="mode-btn" :class="{ active: viewMode === 'translated' }">
            <FileText :size="14" /> 译文
          </button>
          <button @click="viewMode = 'side-by-side'" class="mode-btn" :class="{ active: viewMode === 'side-by-side' }">
            <PanelLeft :size="14" /> 对照
          </button>
        </div>

        <a v-if="translatedUrl" :href="translatedUrl" download class="btn-secondary">
          <Download :size="14" /> 下载
        </a>
      </template>
    </PageToolbar>

    <div class="translate-body" @mouseup="handleMouseUp">
      <!-- 未加载文档 -->
      <div v-if="!store.pdfUrl" class="empty-wrap">
        <EmptyState :icon="Languages" title="尚未加载文档" description="请先在分析页面上传文档，或从历史记录中打开之前分析过的论文。">
          <router-link to="/analyze" class="btn-primary"><Upload :size="16" /> 去上传</router-link>
          <router-link to="/history" class="btn-secondary"><Clock :size="16" /> 查历史</router-link>
        </EmptyState>
      </div>

      <!-- 双语 PDF -->
      <template v-else-if="viewMode === 'dual' && dualUrl">
        <div class="full-pane">
          <div class="full-scroll">
            <div class="pdf-doc">
              <vue-pdf-embed :source="dualUrl" />
            </div>
          </div>
        </div>
      </template>

      <!-- 仅译文 -->
      <template v-else-if="viewMode === 'translated' && translatedUrl">
        <div class="full-pane">
          <div class="full-scroll">
            <div class="pdf-doc">
              <vue-pdf-embed :source="translatedUrl" />
            </div>
          </div>
        </div>
      </template>

      <!-- 左右对照 -->
      <template v-else>
        <div class="half-pane" :class="{ 'w-full-pane': !translatedUrl }">
          <div class="pane-label">原文</div>
          <div v-if="store.pdfUrl" class="pane-scroll">
            <div class="pdf-doc">
              <vue-pdf-embed :source="store.pdfUrl" />
            </div>
          </div>
        </div>
        <div v-if="translatedUrl" class="half-pane">
          <div class="pane-label">译文</div>
          <div class="pane-scroll">
            <div class="pdf-doc">
              <vue-pdf-embed :source="translatedUrl" />
            </div>
          </div>
        </div>
      </template>

      <!-- 划词翻译浮窗 -->
      <transition name="popup">
        <div v-if="selectionPopup.show" class="selection-popup" :style="{ top: selectionPopup.y + 'px', left: selectionPopup.x + 'px' }">
          <div v-if="!selectionPopup.translation && !selectionPopup.loading" class="popup-action">
            <button @click="translateSelection" class="popup-translate-btn">
              <Languages :size="14" /> 翻译
            </button>
            <button @click="closePopup" class="popup-close"><X :size="12" /></button>
          </div>
          <div v-if="selectionPopup.loading" class="popup-loading">
            <Loader2 :size="14" class="spin" />
            <span>翻译中...</span>
          </div>
          <div v-if="selectionPopup.translation" class="popup-result">
            <div class="popup-header">
              <span>翻译结果</span>
              <button @click="closePopup" class="popup-close"><X :size="12" /></button>
            </div>
            <div class="popup-original">{{ selectionPopup.originalText }}</div>
            <div class="popup-translation">{{ selectionPopup.translation }}</div>
            <button @click="copyTranslation" class="popup-copy">{{ copied ? '已复制' : '复制' }}</button>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import VuePdfEmbed from 'vue-pdf-embed'
import api from '../api'
import { store } from '../store'
import {
  Globe, Languages, Upload, Clock, Loader2, Download,
  Columns2, PanelLeft, X, Copy, FileText, RotateCcw,
} from 'lucide-vue-next'

const translateError = ref('')

const isTranslating = ref(false)
const translateStatus = ref('')
const translatedUrl = ref('')
const dualUrl = ref('')
const viewMode = ref('side-by-side')
const copied = ref(false)

const selectionPopup = ref({
  show: false, x: 0, y: 0, selectedText: '',
  originalText: '', translation: '', loading: false,
})

const handleMouseUp = (event) => {
  if (event.target.closest('.selection-popup')) return
  const selection = window.getSelection()
  const text = selection?.toString().trim()
  if (text && text.length >= 2 && text.length <= 500) {
    const range = selection.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    const popupWidth = 300
    let x = rect.left + rect.width / 2 - popupWidth / 2
    let y = rect.top - 10
    x = Math.max(10, Math.min(x, window.innerWidth - popupWidth - 10))
    if (y < 80) y = rect.bottom + 10
    selectionPopup.value = {
      show: true, x, y, selectedText: text, originalText: text, translation: '', loading: false,
    }
  } else if (selectionPopup.value.show && !selectionPopup.value.translation) {
    closePopup()
  }
}

const translateSelection = async () => {
  const text = selectionPopup.value.selectedText
  if (!text) return
  selectionPopup.value.loading = true
  try {
    const res = await api.translateText(text)
    selectionPopup.value.translation = res.translation
    selectionPopup.value.originalText = res.original
  } catch (e) {
    selectionPopup.value.translation = '翻译失败: ' + (e.response?.data?.detail || e.message)
  } finally {
    selectionPopup.value.loading = false
  }
}

const closePopup = () => {
  selectionPopup.value.show = false
  selectionPopup.value.translation = ''
  selectionPopup.value.loading = false
  copied.value = false
}

const copyTranslation = async () => {
  try {
    await navigator.clipboard.writeText(selectionPopup.value.translation)
    copied.value = true
    setTimeout(() => { copied.value = false }, 1500)
  } catch (e) { console.error('复制失败:', e) }
}

const handleClickOutside = (event) => {
  if (selectionPopup.value.show && !event.target.closest('.selection-popup')) {
    const s = window.getSelection()
    if (!s?.toString().trim()) closePopup()
  }
}

onMounted(() => document.addEventListener('mousedown', handleClickOutside))
onBeforeUnmount(() => document.removeEventListener('mousedown', handleClickOutside))

const startTranslation = async () => {
  if (isTranslating.value) return
  isTranslating.value = true
  translateError.value = ''
  translateStatus.value = '正在准备翻译...'
  try {
    for await (const event of api.translateStream()) {
      const stage = event.stage
      if (stage === 'translating') translateStatus.value = event.message
      else if (stage === 'done') {
        translateStatus.value = '翻译完成！'
        if (event.mono_pdf_url) translatedUrl.value = event.mono_pdf_url
        if (event.dual_pdf_url) dualUrl.value = event.dual_pdf_url
        if (event.dual_pdf_url) viewMode.value = 'dual'
        else if (event.mono_pdf_url) viewMode.value = 'side-by-side'
      } else if (stage === 'error') throw new Error(event.message)
    }
  } catch (e) {
    translateError.value = e.message || '翻译失败'
  } finally {
    isTranslating.value = false
  }
}
</script>

<style scoped>
.translate-page { height: 100vh; display: flex; flex-direction: column; }
.translate-body { flex: 1; display: flex; overflow: hidden; position: relative; }
.empty-wrap {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  background: var(--bg-inset);
}

.translating-hint {
  display: flex; align-items: center; gap: 0.4rem; font-size: 0.82rem; color: var(--accent-1);
}
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.mode-switch {
  display: flex; align-items: center; gap: 0.25rem; padding: 0.2rem;
  background: var(--bg-input); border: 1px solid var(--border-default); border-radius: 0.6rem;
}
.mode-btn {
  display: flex; align-items: center; gap: 0.3rem;
  padding: 0.35rem 0.7rem; border-radius: 0.45rem;
  font-size: 0.75rem; color: var(--text-secondary);
  background: none; border: none; cursor: pointer; transition: all 0.15s;
}
.mode-btn:hover { color: var(--text-heading); }
.mode-btn.active {
  color: var(--accent-1); background: rgba(56, 189, 248, 0.12);
}

.full-pane, .half-pane {
  display: flex; flex-direction: column; min-width: 0;
  background: var(--bg-inset);
}
.half-pane { width: 50%; border-right: 1px solid var(--border-default); }
.half-pane:last-child { border-right: none; background: var(--bg-surface); }
.full-pane { width: 100%; }
.w-full-pane { width: 100%; border-right: none; }

.pane-label {
  padding: 0.55rem 1rem; font-size: 0.75rem; font-weight: 600;
  color: var(--text-secondary); background: var(--bg-glass);
  border-bottom: 1px solid var(--border-default); text-align: center; flex-shrink: 0;
}
.pane-scroll, .full-scroll { flex: 1; overflow-y: auto; padding: 1.5rem; }
.pdf-doc {
  max-width: 720px; margin: 0 auto; background: #fff; border-radius: 0.5rem;
  overflow: hidden; box-shadow: var(--shadow-card-lg);
}

/* 划词浮窗 */
.selection-popup {
  position: fixed; z-index: 100; width: 300px;
  border-radius: 0.85rem;
  background: var(--bg-elevated);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-default);
  box-shadow: var(--shadow-card-lg);
  overflow: hidden;
}
.popup-action { display: flex; align-items: center; gap: 0.3rem; padding: 0.4rem; }
.popup-translate-btn {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 0.4rem;
  padding: 0.5rem; border-radius: 0.6rem; font-size: 0.8rem; font-weight: 500;
  color: var(--accent-1); background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.2); cursor: pointer; transition: all 0.15s;
}
.popup-translate-btn:hover { background: rgba(56, 189, 248, 0.18); }
.popup-close {
  padding: 0.4rem; border-radius: 0.5rem; color: var(--text-muted);
  cursor: pointer; transition: all 0.15s; background: none; border: none;
}
.popup-close:hover { color: var(--text-heading); background: var(--bg-input); }
.popup-loading {
  display: flex; align-items: center; justify-content: center; gap: 0.5rem;
  padding: 1rem; font-size: 0.8rem; color: var(--text-secondary);
}
.popup-result { padding: 0.9rem; }
.popup-header {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 0.68rem; color: var(--text-muted); margin-bottom: 0.6rem;
}
.popup-original {
  font-size: 0.75rem; color: var(--text-muted); line-height: 1.5;
  padding: 0.5rem 0.6rem; border-radius: 0.5rem; background: var(--bg-input);
  margin-bottom: 0.5rem; max-height: 60px; overflow-y: auto;
}
.popup-translation {
  font-size: 0.82rem; color: var(--text-primary); line-height: 1.6;
  padding: 0.6rem; border-radius: 0.6rem; background: rgba(56, 189, 248, 0.06);
  border: 1px solid rgba(56, 189, 248, 0.14); margin-bottom: 0.5rem;
  max-height: 120px; overflow-y: auto;
}
.popup-copy {
  padding: 0.3rem 0.7rem; border-radius: 0.5rem; font-size: 0.72rem;
  color: var(--accent-1); background: rgba(56, 189, 248, 0.1); border: none;
  cursor: pointer; transition: all 0.15s;
}
.popup-copy:hover { background: rgba(56, 189, 248, 0.2); }

.popup-enter-active { transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1); }
.popup-leave-active { transition: all 0.1s ease; }
.popup-enter-from, .popup-leave-to { opacity: 0; transform: translateY(6px) scale(0.96); }
</style>