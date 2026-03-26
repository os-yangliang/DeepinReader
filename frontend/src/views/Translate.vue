<template>
  <div class="h-[calc(100vh-80px)] flex flex-col">
    <!-- 顶部工具栏 -->
    <div class="h-14 toolbar-glass px-6 flex items-center justify-between z-20">
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <Globe :size="20" class="text-primary-400" />
          <h1 class="text-lg font-semibold text-white">全文翻译</h1>
        </div>
        <div v-if="store.documentInfo" class="flex items-center gap-2 text-gray-400 text-sm border-l border-white/10 pl-4">
          <FileText :size="14" />
          <span class="max-w-[200px] truncate">{{ store.documentInfo.filename }}</span>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <!-- 翻译按钮 -->
        <button 
          v-if="store.pdfUrl && !isTranslating && !translatedUrl"
          @click="startTranslation"
          class="btn-glow text-sm px-4 py-2 flex items-center gap-2"
        >
          <Languages :size="16" />
          开始翻译
        </button>
        
        <!-- 翻译中 -->
        <div v-if="isTranslating" class="flex items-center gap-3 text-sm">
          <Loader2 :size="16" class="text-primary-400 animate-spin" />
          <span class="text-primary-400">{{ translateStatus }}</span>
        </div>

        <!-- 切换显示模式 -->
        <div v-if="translatedUrl || dualUrl" class="flex items-center gap-2">
          <button 
            v-if="dualUrl"
            @click="viewMode = 'dual'"
            class="mode-btn" :class="{ active: viewMode === 'dual' }"
          >
            <Columns2 :size="14" />
            双语对照
          </button>
          <button 
            v-if="translatedUrl"
            @click="viewMode = 'translated'"
            class="mode-btn" :class="{ active: viewMode === 'translated' }"
          >
            <FileText :size="14" />
            仅译文
          </button>
          <button 
            @click="viewMode = 'side-by-side'"
            class="mode-btn" :class="{ active: viewMode === 'side-by-side' }"
          >
            <PanelLeft :size="14" />
            左右对比
          </button>
        </div>

        <!-- 下载 -->
        <a v-if="translatedUrl" :href="translatedUrl" download class="action-btn flex items-center gap-1.5">
          <Download :size="14" />
          下载译文
        </a>
      </div>
    </div>

    <!-- 主体内容区 -->
    <div class="flex-1 flex overflow-hidden relative" @mouseup="handleMouseUp">
      
      <!-- 未加载文档 -->
      <div v-if="!store.pdfUrl" class="absolute inset-0 z-50 flex items-center justify-center bg-gray-900/90 backdrop-blur-sm">
        <div class="text-center max-w-md">
          <div class="empty-icon-wrapper mx-auto mb-6">
            <Languages :size="36" class="text-primary-400/60" />
          </div>
          <h3 class="text-xl font-bold text-white mb-2">尚未加载文档</h3>
          <p class="text-gray-400 mb-8 text-sm leading-relaxed">请先在分析页面上传文档，或从历史记录中打开之前分析过的论文。</p>
          <div class="flex gap-3 justify-center">
            <router-link to="/analyze" class="btn-glow px-6 py-2.5 text-sm flex items-center gap-2">
              <Upload :size="16" />
              去上传
            </router-link>
            <router-link to="/history" class="btn-secondary px-6 py-2.5 text-sm flex items-center gap-2">
              <Clock :size="16" />
              查历史
            </router-link>
          </div>
        </div>
      </div>

      <!-- 模式1: 双语 PDF -->
      <template v-if="viewMode === 'dual' && dualUrl">
        <div class="w-full relative flex flex-col">
          <div class="flex-1 overflow-y-auto custom-scrollbar p-8 flex justify-center">
            <div class="w-full max-w-5xl shadow-2xl">
              <vue-pdf-embed :source="dualUrl" class="rounded-lg overflow-hidden" />
            </div>
          </div>
        </div>
      </template>

      <!-- 模式2: 仅译文 -->
      <template v-else-if="viewMode === 'translated' && translatedUrl">
        <div class="w-full relative flex flex-col">
          <div class="flex-1 overflow-y-auto custom-scrollbar p-8 flex justify-center">
            <div class="w-full max-w-5xl shadow-2xl">
              <vue-pdf-embed :source="translatedUrl" class="rounded-lg overflow-hidden" />
            </div>
          </div>
        </div>
      </template>

      <!-- 模式3: 左右对比（默认） -->
      <template v-else>
        <!-- 左侧：原文 PDF -->
        <div :class="translatedUrl ? 'w-1/2' : 'w-full'" class="bg-gray-900/50 relative flex flex-col border-r border-white/5">
          <div class="pdf-label">📄 原文 <span class="text-gray-600 ml-2 font-normal">（选中文字即可划词翻译）</span></div>
          <div v-if="store.pdfUrl" class="flex-1 overflow-y-auto custom-scrollbar p-6 flex justify-center">
            <div class="w-full max-w-4xl shadow-2xl">
              <vue-pdf-embed :source="store.pdfUrl" class="rounded-lg overflow-hidden" />
            </div>
          </div>
          
          <!-- 翻译引导 -->
          <div v-if="!translatedUrl && !isTranslating && store.pdfUrl" class="absolute bottom-6 left-1/2 transform -translate-x-1/2">
            <div class="translate-cta">
              <Languages :size="18" class="text-primary-400" />
              <span class="text-sm text-gray-300">点击上方「开始翻译」按钮翻译整篇论文 · 选中文字可划词翻译</span>
            </div>
          </div>
        </div>

        <!-- 右侧：译文 PDF -->
        <div v-if="translatedUrl" class="w-1/2 flex flex-col bg-gray-900/80 backdrop-blur-xl">
          <div class="pdf-label">🌐 译文</div>
          <div class="flex-1 overflow-y-auto custom-scrollbar p-6 flex justify-center">
            <div class="w-full max-w-4xl shadow-2xl">
              <vue-pdf-embed :source="translatedUrl" class="rounded-lg overflow-hidden" />
            </div>
          </div>
        </div>
      </template>

      <!-- 划词翻译浮窗 -->
      <transition name="popup">
        <div 
          v-if="selectionPopup.show" 
          class="selection-popup"
          :style="{ top: selectionPopup.y + 'px', left: selectionPopup.x + 'px' }"
        >
          <!-- 未翻译：显示快捷按钮 -->
          <div v-if="!selectionPopup.translation && !selectionPopup.loading" class="popup-action">
            <button @click="translateSelection" class="popup-translate-btn">
              <Languages :size="14" />
              翻译
            </button>
            <button @click="closePopup" class="popup-close">
              <X :size="12" />
            </button>
          </div>

          <!-- 翻译中 -->
          <div v-if="selectionPopup.loading" class="popup-loading">
            <Loader2 :size="14" class="animate-spin text-primary-400" />
            <span class="text-xs text-gray-400">翻译中...</span>
          </div>

          <!-- 翻译结果 -->
          <div v-if="selectionPopup.translation" class="popup-result">
            <div class="popup-header">
              <Languages :size="12" class="text-primary-400" />
              <span class="text-[10px] text-gray-500 uppercase tracking-wider">翻译结果</span>
              <button @click="closePopup" class="ml-auto text-gray-500 hover:text-white transition-colors">
                <X :size="12" />
              </button>
            </div>
            <div class="popup-original">{{ selectionPopup.originalText }}</div>
            <div class="popup-translation">{{ selectionPopup.translation }}</div>
            <button @click="copyTranslation" class="popup-copy-btn">
              <Copy :size="11" />
              {{ copied ? '已复制' : '复制' }}
            </button>
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
  Globe, FileText, Languages, Upload, Clock, Loader2, 
  Download, Columns2, PanelLeft, X, Copy
} from 'lucide-vue-next'

const isTranslating = ref(false)
const translateStatus = ref('')
const translatedUrl = ref('')
const dualUrl = ref('')
const viewMode = ref('side-by-side')
const copied = ref(false)

// 划词翻译状态
const selectionPopup = ref({
  show: false,
  x: 0,
  y: 0,
  selectedText: '',
  originalText: '',
  translation: '',
  loading: false,
})

const handleMouseUp = (event) => {
  // 如果点的是浮窗内部，不处理
  if (event.target.closest('.selection-popup')) return

  const selection = window.getSelection()
  const text = selection?.toString().trim()
  
  if (text && text.length >= 2 && text.length <= 500) {
    // 获取选区位置
    const range = selection.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    
    // 浮窗位置：选区上方居中
    const popupWidth = 300
    let x = rect.left + rect.width / 2 - popupWidth / 2
    let y = rect.top - 10  // 在选区上方

    // 边界修正
    x = Math.max(10, Math.min(x, window.innerWidth - popupWidth - 10))
    if (y < 80) y = rect.bottom + 10  // 如果上方空间不够，放下方

    selectionPopup.value = {
      show: true,
      x,
      y,
      selectedText: text,
      originalText: text,
      translation: '',
      loading: false,
    }
  } else {
    // 没有选中文字，关闭浮窗
    if (selectionPopup.value.show && !selectionPopup.value.translation) {
      closePopup()
    }
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
  } catch (e) {
    console.error('复制失败:', e)
  }
}

// 点击外部关闭
const handleClickOutside = (event) => {
  if (selectionPopup.value.show && !event.target.closest('.selection-popup')) {
    const selection = window.getSelection()
    if (!selection?.toString().trim()) {
      closePopup()
    }
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleClickOutside)
})

const startTranslation = async () => {
  if (isTranslating.value) return
  isTranslating.value = true
  translateStatus.value = '正在准备翻译...'
  
  try {
    for await (const event of api.translateStream()) {
      const stage = event.stage
      
      if (stage === 'translating') {
        translateStatus.value = event.message
      } else if (stage === 'done') {
        translateStatus.value = '翻译完成！'
        if (event.mono_pdf_url) translatedUrl.value = event.mono_pdf_url
        if (event.dual_pdf_url) dualUrl.value = event.dual_pdf_url
        if (event.dual_pdf_url) viewMode.value = 'dual'
        else if (event.mono_pdf_url) viewMode.value = 'side-by-side'
      } else if (stage === 'error') {
        throw new Error(event.message)
      }
    }
  } catch (e) {
    alert('翻译失败: ' + e.message)
  } finally {
    isTranslating.value = false
  }
}
</script>

<style scoped>
.toolbar-glass {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.empty-icon-wrapper {
  width: 80px;
  height: 80px;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(14, 165, 233, 0.12);
}

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

.btn-secondary {
  display: inline-flex;
  align-items: center;
  font-weight: 600;
  color: rgba(148, 163, 184, 0.9);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s;
}
.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(148, 163, 184, 0.8);
  font-size: 12px;
  transition: all 0.2s;
}
.mode-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}
.mode-btn.active {
  background: rgba(14, 165, 233, 0.15);
  border-color: rgba(14, 165, 233, 0.3);
  color: #0ea5e9;
}

.action-btn {
  padding: 6px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(148, 163, 184, 0.8);
  font-size: 12px;
  transition: all 0.2s;
  text-decoration: none;
}
.action-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}

.pdf-label {
  position: sticky;
  top: 0;
  z-index: 10;
  padding: 8px 16px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(148, 163, 184, 0.7);
  background: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  text-align: center;
}

.translate-cta {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-radius: 14px;
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(14, 165, 233, 0.15);
  backdrop-filter: blur(12px);
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-4px); }
}

/* ========== 划词翻译浮窗 ========== */
.selection-popup {
  position: fixed;
  z-index: 100;
  width: 300px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 40px rgba(14, 165, 233, 0.08);
  overflow: hidden;
}

.popup-action {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px;
}

.popup-translate-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.2), rgba(99, 102, 241, 0.15));
  border: 1px solid rgba(14, 165, 233, 0.2);
  color: #38bdf8;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.popup-translate-btn:hover {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.3), rgba(99, 102, 241, 0.25));
  box-shadow: 0 4px 15px rgba(14, 165, 233, 0.2);
}

.popup-close {
  padding: 8px;
  border-radius: 8px;
  color: rgba(148, 163, 184, 0.5);
  cursor: pointer;
  transition: all 0.2s;
}
.popup-close:hover {
  color: white;
  background: rgba(255, 255, 255, 0.06);
}

.popup-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px;
}

.popup-result {
  padding: 12px;
}

.popup-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.popup-original {
  font-size: 11px;
  color: rgba(148, 163, 184, 0.5);
  line-height: 1.5;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  margin-bottom: 8px;
  max-height: 60px;
  overflow-y: auto;
}

.popup-translation {
  font-size: 13px;
  color: rgba(226, 232, 240, 0.95);
  line-height: 1.6;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(14, 165, 233, 0.06);
  border: 1px solid rgba(14, 165, 233, 0.1);
  margin-bottom: 8px;
  max-height: 120px;
  overflow-y: auto;
}

.popup-copy-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  color: rgba(148, 163, 184, 0.6);
  cursor: pointer;
  transition: all 0.2s;
}
.popup-copy-btn:hover {
  color: white;
  background: rgba(255, 255, 255, 0.06);
}

/* 浮窗动画 */
.popup-enter-active {
  animation: popupIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.popup-leave-active {
  animation: popupOut 0.15s ease-in;
}
@keyframes popupIn {
  from { opacity: 0; transform: translateY(8px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes popupOut {
  from { opacity: 1; }
  to { opacity: 0; transform: translateY(4px) scale(0.98); }
}

.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(99, 102, 241, 0.2); border-radius: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(99, 102, 241, 0.4); }
</style>