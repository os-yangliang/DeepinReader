<template>
  <div class="h-[calc(100vh-80px)] flex flex-col">
    <!-- 顶部工具栏 -->
    <div class="h-14 glass-card border-b border-white/5 px-6 flex items-center justify-between z-20">
      <div class="flex items-center gap-4">
        <h1 class="text-xl font-bold gradient-text">🌐 全文翻译</h1>
        <div v-if="store.documentInfo" class="text-gray-400 text-sm border-l border-white/10 pl-4">
          {{ store.documentInfo.filename }}
        </div>
      </div>
    </div>

    <!-- 主体内容区 -->
    <div class="flex-1 flex overflow-hidden relative">
      
      <!-- 未加载文档时的提示 -->
      <div v-if="!store.pdfUrl" class="absolute inset-0 z-50 flex items-center justify-center bg-gray-900/90 backdrop-blur-sm">
        <div class="text-center">
          <div class="text-6xl mb-4">📄</div>
          <h3 class="text-xl font-bold text-white mb-2">未加载文档</h3>
          <p class="text-gray-400 mb-6">请先在分析页面上传文档，或在历史记录中打开文档。</p>
          <div class="flex gap-4 justify-center">
            <router-link to="/analyze" class="btn-primary px-6 py-2">去上传</router-link>
            <router-link to="/history" class="btn-secondary px-6 py-2">查历史</router-link>
          </div>
        </div>
      </div>

      <!-- 左侧：PDF 阅读器 -->
      <div class="w-1/2 bg-gray-900/50 relative flex flex-col border-r border-white/5">
        <div v-if="store.pdfUrl" class="flex-1 overflow-y-auto custom-scrollbar p-8 flex justify-center">
          <div class="w-full max-w-4xl shadow-2xl">
            <vue-pdf-embed :source="store.pdfUrl" class="rounded-lg overflow-hidden" />
          </div>
        </div>
      </div>

      <!-- 右侧：翻译面板 -->
      <div class="w-1/2 glass-card border-l border-white/5 flex flex-col bg-gray-900/80 backdrop-blur-xl">
        <div class="flex-1 overflow-y-auto custom-scrollbar p-8">
           <div class="p-4 rounded-xl bg-white/5 border border-white/10 mb-4">
            <h3 class="font-bold text-white mb-2">🤖 AI 全文翻译</h3>
            <p class="text-xs text-gray-400">基于段落语义的智能翻译，保持原文逻辑。</p>
          </div>
          
          <button 
            v-if="!isTranslating && !translationContent"
            @click="startTranslation"
            class="btn-primary w-full py-2 flex items-center justify-center gap-2"
          >
            <span>🌐</span> 开始全文翻译
          </button>

          <div v-if="translationContent" class="markdown-content prose prose-invert max-w-none text-sm">
            <div v-html="renderedTranslation"></div>
          </div>
          
          <div v-if="isTranslating" class="flex justify-center py-4">
            <div class="loading-dots text-primary-400">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import VuePdfEmbed from 'vue-pdf-embed'
import api from '../api'
import { store } from '../store'

const isTranslating = ref(false)
const translationContent = ref('')

const renderedTranslation = computed(() => translationContent.value ? marked(translationContent.value) : '')

const startTranslation = async () => {
  if (isTranslating.value) return
  isTranslating.value = true
  translationContent.value = '' 
  
  try {
    for await (const chunk of api.translateStream()) {
      translationContent.value += chunk
    }
  } catch (e) {
    translationContent.value += '\n\n[翻译中断: ' + e.message + ']'
  } finally {
    isTranslating.value = false
  }
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
</style>