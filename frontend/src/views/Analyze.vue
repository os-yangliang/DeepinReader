<template>
  <div class="h-[calc(100vh-80px)] flex flex-col">
    <!-- 顶部工具栏 -->
    <div class="h-14 glass-card border-b border-white/5 px-6 flex items-center justify-between z-20">
      <div class="flex items-center gap-4">
        <h1 class="text-xl font-bold gradient-text">📄 论文分析</h1>
        <div v-if="store.documentInfo" class="text-gray-400 text-sm border-l border-white/10 pl-4">
          {{ store.documentInfo.filename }}
        </div>
      </div>
      
      <div class="flex items-center gap-3">
        <!-- 上传按钮 (如果未加载文档) -->
        <button 
          v-if="!store.pdfUrl"
          @click="triggerFileInput"
          class="btn-primary text-sm px-4 py-2 flex items-center gap-2"
        >
          <span>📤</span> 上传论文
        </button>
        
        <!-- 开始分析 (仅在已选择文件但未分析时显示) -->
        <button 
          v-if="store.pdfUrl && !isAnalyzing && !store.analysisResult"
          @click="startAnalysisProcess"
          class="btn-primary text-sm px-4 py-2 flex items-center gap-2 animate-pulse"
        >
          <span>🚀</span> 开始智能分析
        </button>
        
        <!-- 分析进行中指示器 -->
        <div v-if="isAnalyzing" class="flex items-center gap-3 text-sm">
          <div class="flex gap-1">
            <span class="w-2 h-2 bg-primary-400 rounded-full animate-bounce"></span>
            <span class="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></span>
            <span class="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></span>
          </div>
          <span class="text-primary-400">{{ analyzeStatus }}</span>
        </div>

        <!-- 重新上传 -->
        <button 
          v-if="store.pdfUrl"
          @click="resetUpload"
          class="text-gray-400 hover:text-white text-sm px-3 py-2 transition-colors"
        >
          {{ !store.analysisResult ? '取消' : '重新上传' }}
        </button>
      </div>
    </div>

    <!-- 主体内容区 (双栏布局) -->
    <div class="flex-1 flex overflow-hidden relative">
      
      <!-- 左侧：PDF 阅读器 -->
      <div class="w-1/2 bg-gray-900/50 relative flex flex-col border-r border-white/5">
        <div v-if="store.pdfUrl" class="flex-1 overflow-y-auto custom-scrollbar p-8 flex justify-center">
          <div class="w-full max-w-4xl shadow-2xl">
            <vue-pdf-embed :source="store.pdfUrl" class="rounded-lg overflow-hidden" />
          </div>
        </div>
        
        <!-- 空状态 -->
        <div v-else class="flex-1 flex flex-col items-center justify-center p-12 text-center"
             @dragover.prevent="isDragging = true"
             @dragleave.prevent="isDragging = false"
             @drop.prevent="handleDrop">
          
          <div class="glass-card p-12 rounded-3xl border border-white/10 max-w-lg w-full transition-all duration-300"
               :class="{ 'border-primary-500/50 bg-primary-500/5': isDragging }">
            <div class="w-20 h-20 mx-auto rounded-3xl flex items-center justify-center text-5xl mb-6
                        bg-gradient-to-br from-primary-500/20 to-accent-500/20 border border-white/10">
              📄
            </div>
            <h3 class="text-xl font-bold text-white mb-2">上传论文 PDF</h3>
            <p class="text-gray-400 mb-8">支持拖拽上传，AI 将自动分析并生成结构报告</p>
            
            <button @click="triggerFileInput" class="btn-primary w-full py-3">
              选择文件
            </button>
            <input ref="fileInputRef" type="file" accept=".pdf" class="hidden" @change="handleFileSelect" />
          </div>
          
          <!-- 分析进度 -->
          <div v-if="isAnalyzing" class="mt-8 w-full max-w-md">
            <div class="flex justify-between text-sm text-gray-400 mb-2">
              <span>{{ analyzeStatus }}</span>
              <span>{{ uploadProgress }}%</span>
            </div>
            <div class="h-2 bg-gray-800 rounded-full overflow-hidden">
              <div class="h-full bg-gradient-to-r from-primary-500 to-accent-500 transition-all duration-300"
                   :style="{ width: `${uploadProgress}%` }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：分析结果面板 -->
      <div class="w-1/2 glass-card border-l border-white/5 flex flex-col bg-gray-900/80 backdrop-blur-xl">
        <div class="flex-1 overflow-y-auto custom-scrollbar p-8">
          <div v-if="!store.analysisResult" class="text-center py-12 text-gray-500">
            请先上传论文以获取分析报告
          </div>
          <template v-else>
            <div class="animate-fade-in">
              <h3 class="text-lg font-bold text-white mb-4">📑 结构分析</h3>
              <div class="markdown-content prose prose-invert max-w-none text-sm" v-html="renderedStructure"></div>
            </div>
            <div class="border-t border-white/10 my-6"></div>
            <div class="animate-fade-in">
              <h3 class="text-lg font-bold text-white mb-4">💡 核心摘要</h3>
              <div class="markdown-content prose prose-invert max-w-none text-sm" v-html="renderedSummary"></div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import VuePdfEmbed from 'vue-pdf-embed'
import api from '../api'
import { store } from '../store'

const router = useRouter()
const isLoggedIn = inject('isLoggedIn', ref(false))

// 状态
const file = ref(null) 
const isDragging = ref(false)
const isAnalyzing = ref(false)
const uploadProgress = ref(0)
const analyzeStatus = ref('')
const fileInputRef = ref(null)

// 计算属性
const renderedStructure = computed(() => store.analysisResult?.structure ? marked(store.analysisResult.structure) : '')
const renderedSummary = computed(() => store.analysisResult?.summary ? marked(store.analysisResult.summary) : '')

// 检查登录
const checkLogin = () => {
  const token = localStorage.getItem('access_token')
  return !!token
}

// 触发文件选择
const triggerFileInput = () => {
  if (!checkLogin()) { router.push('/login'); return }
  fileInputRef.value?.click()
}

// 处理文件选择
const handleFileSelect = (e) => {
  const selectedFile = e.target.files?.[0]
  if (selectedFile) {
    file.value = selectedFile
    const url = URL.createObjectURL(selectedFile)
    
    // 更新全局状态 (初始状态，尚未分析)
    store.setDocument({ filename: selectedFile.name }, url, null)
    
    e.target.value = ''
  }
}

// 处理拖拽
const handleDrop = (e) => {
  isDragging.value = false
  if (!checkLogin()) { router.push('/login'); return }
  const droppedFile = e.dataTransfer.files?.[0]
  if (droppedFile && droppedFile.type === 'application/pdf') {
    file.value = droppedFile
    const url = URL.createObjectURL(droppedFile)
    store.setDocument({ filename: droppedFile.name }, url, null)
  } else {
    alert('请上传 PDF 文件')
  }
}

// 启动分析流程
const startAnalysisProcess = () => {
  if (file.value) {
    handleUpload(file.value)
  }
}

// 上传逻辑
const handleUpload = async (uploadFile) => {
  isAnalyzing.value = true
  uploadProgress.value = 0
  analyzeStatus.value = '正在上传...'
  
  try {
    const result = await api.uploadAndAnalyze(uploadFile, (p) => {
      uploadProgress.value = p
      if (p >= 100) {
        analyzeStatus.value = '🤖 AI 正在分析论文结构...(可能需要1-2分钟)'
      }
    })
    
    if (result.success) {
      // 释放本地 Blob URL，使用后端 URL
      if (store.pdfUrl && store.pdfUrl.startsWith('blob:')) {
        URL.revokeObjectURL(store.pdfUrl)
      }
      
      // 更新全局状态 (包含分析结果)
      store.setDocument(
        result.document_info, 
        result.document_info.file_url,
        {
          success: true,
          document_info: result.document_info,
          structure: result.structure,
          summary: result.summary
        }
      )
    } else {
      throw new Error(result.error)
    }
  } catch (e) {
    alert('分析失败: ' + e.message)
  } finally {
    isAnalyzing.value = false
  }
}

// 重新上传
const resetUpload = async () => {
  file.value = null
  store.clearDocument()
  try { await api.clearDocument() } catch (e) {}
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
</style>