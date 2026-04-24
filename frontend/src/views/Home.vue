<template>
  <div class="max-w-6xl mx-auto">
    <!-- Hero Section -->
    <section class="text-center pt-12 pb-20 animate-fade-in relative">
      <!-- 装饰粒子 -->
      <div class="hero-particles">
        <div class="particle-dot" v-for="n in 6" :key="n" :style="particleStyle(n)"></div>
      </div>

      <!-- Logo + 标题 -->
      <div class="relative inline-flex flex-col items-center mb-8">
        <div class="hero-icon-wrapper">
          <div class="hero-icon">
            <BookOpen :size="48" class="text-white/90" />
          </div>
          <div class="hero-icon-ring hero-icon-ring-1"></div>
          <div class="hero-icon-ring hero-icon-ring-2"></div>
          <div class="hero-glow"></div>
        </div>
      </div>
      
      <h1 class="text-5xl md:text-6xl font-display font-bold mb-6 leading-tight">
        <span class="gradient-text">DeepinReader</span>
      </h1>
      
      <p class="text-lg text-gray-400 max-w-2xl mx-auto mb-12 leading-relaxed">
        基于 <span class="text-primary-400 font-medium">LangChain + LangGraph</span> 多智能体架构，
        <br class="hidden sm:block">
        让 AI 帮你 <span class="text-white font-medium">深度理解</span> 每一篇学术论文
      </p>
      
      <!-- 小标签 -->
      <div class="flex items-center justify-center gap-3 mt-8">
        <span class="badge"><Zap :size="12" /> PDF / Word</span>
        <span class="badge"><Brain :size="12" /> 多智能体</span>
        <span class="badge"><Globe :size="12" /> 联网搜索</span>
      </div>
    </section>

    <!-- 上传区域 -->
    <section class="py-8">
      <div 
        class="upload-hero"
        :class="{ 'upload-hero-active': isDragging, 'upload-hero-uploading': isUploading }"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
      >
        <div class="upload-hero-bg"></div>
        <div class="relative z-10 text-center py-12 px-8">
          <!-- 上传中 -->
          <template v-if="isUploading">
            <Loader2 :size="40" class="text-primary-400 animate-spin mx-auto mb-4" />
            <p class="text-primary-400 font-medium text-lg mb-1">{{ uploadStatus }}</p>
            <p class="text-gray-500 text-sm">请稍候，即将跳转到分析页...</p>
          </template>

          <!-- 正常状态 -->
          <template v-else>
            <div class="upload-hero-icon mx-auto mb-5">
              <FileUp :size="32" class="text-primary-400/80" />
            </div>
            <h3 class="text-xl font-bold text-white mb-2">
              {{ isDragging ? '松开鼠标上传' : '拖拽论文到这里开始' }}
            </h3>
            <p class="text-gray-400 text-sm mb-6">或点击下方按钮选择文件 · 支持 PDF 格式</p>
            <button @click="triggerFileInput" class="cta-primary group">
              <div class="cta-shine"></div>
              <Upload :size="18" />
              <span>选择论文上传</span>
              <ArrowRight :size="16" class="transition-transform group-hover:translate-x-1" />
            </button>
            <input ref="fileInputRef" type="file" accept=".pdf" class="hidden" @change="handleFileSelect" />
          </template>
        </div>
      </div>
    </section>
    
    <!-- 核心功能 -->
    <section class="py-16">
      <div class="text-center mb-12">
        <h2 class="text-3xl font-bold text-white mb-3">核心功能</h2>
        <p class="text-gray-500">五大智能模块，覆盖论文阅读全流程</p>
      </div>
      
      <div class="grid md:grid-cols-2 lg:grid-cols-5 gap-5">
        <div 
          v-for="(feature, index) in features" 
          :key="feature.title"
          class="feature-card group"
          :style="{ animationDelay: `${index * 0.1}s` }"
        >
          <div class="feature-icon" :style="{ background: feature.gradient }">
            <component :is="feature.icon" :size="24" class="text-white" />
          </div>
          <h3 class="text-base font-semibold text-white mb-2">{{ feature.title }}</h3>
          <p class="text-gray-400 text-sm leading-relaxed">{{ feature.desc }}</p>
          
          <!-- 悬浮光效 -->
          <div class="feature-hover-glow" :style="{ background: feature.glowColor }"></div>
        </div>
      </div>
    </section>
    
    <!-- 技术架构 -->
    <section class="py-16">
      <div class="text-center mb-12">
        <h2 class="text-3xl font-bold text-white mb-3">工作流程</h2>
        <p class="text-gray-500">基于多智能体协作的论文理解系统</p>
      </div>
      
      <div class="workflow-container">
        <div class="workflow-line"></div>
        <div class="grid grid-cols-5 gap-4 relative z-10">
          <div v-for="(step, index) in steps" :key="step.title" class="workflow-step group">
            <div class="workflow-number">
              <span class="text-sm font-bold">{{ index + 1 }}</span>
            </div>
            <div class="workflow-icon" :style="{ background: step.gradient }">
              <component :is="step.icon" :size="22" class="text-white" />
            </div>
            <h4 class="text-sm font-semibold text-white mt-3 mb-1">{{ step.title }}</h4>
            <p class="text-gray-500 text-xs leading-relaxed">{{ step.desc }}</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { 
  BookOpen, ArrowRight, Upload, Sparkles,
  FileSearch, BarChart3, Globe, Zap, Brain, Search, Languages, Code2,
  MessageCircle, FileUp, Loader2
} from 'lucide-vue-next'
import api from '../api'
import { store } from '../store'

const router = useRouter()
const fileInputRef = ref(null)
const isDragging = ref(false)
const isUploading = ref(false)
const uploadStatus = ref('')

const particleStyle = (n) => ({
  '--delay': `${n * 1.2}s`,
  '--x': `${Math.random() * 100}%`,
  '--y': `${Math.random() * 100}%`,
  '--size': `${2 + Math.random() * 3}px`,
})

const triggerFileInput = () => fileInputRef.value?.click()

const handleFileSelect = (e) => {
  const selectedFile = e.target.files?.[0]
  if (selectedFile) {
    e.target.value = ''
    startUpload(selectedFile)
  }
}

const handleDrop = (e) => {
  isDragging.value = false
  const droppedFile = e.dataTransfer.files?.[0]
  if (droppedFile && droppedFile.type === 'application/pdf') {
    startUpload(droppedFile)
  } else {
    alert('请上传 PDF 文件')
  }
}

const startUpload = async (file) => {
  isUploading.value = true
  uploadStatus.value = '正在上传并解析文档...'
  
  try {
    // 先设置本地预览
    const blobUrl = URL.createObjectURL(file)
    store.setDocument({ filename: file.name }, blobUrl, null)

    // 上传到后端
    uploadStatus.value = '正在解析文档结构...'
    const result = await api.uploadDocument(file)
    
    if (!result.success) throw new Error(result.error || '上传失败')
    
    const docInfo = result.document_info
    if (blobUrl.startsWith('blob:')) URL.revokeObjectURL(blobUrl)
    store.setDocument(docInfo, docInfo.file_url, null)
    
    uploadStatus.value = '解析完成，正在跳转...'
    
    // 跳转到分析页
    setTimeout(() => {
      router.push('/analyze')
    }, 500)
    
  } catch (e) {
    alert('上传失败: ' + e.message)
    store.clearDocument()
  } finally {
    setTimeout(() => {
      isUploading.value = false
    }, 1000)
  }
}

const features = [
  {
    icon: FileSearch,
    title: '智能解析',
    desc: '支持 PDF 和 Word 格式，自动提取文档结构与关键信息',
    gradient: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
    glowColor: 'radial-gradient(circle, rgba(59,130,246,0.15), transparent 70%)',
  },
  {
    icon: BarChart3,
    title: '深度分析',
    desc: '自动生成结构化报告，覆盖方法、创新点、实验结果等',
    gradient: 'linear-gradient(135deg, #8b5cf6, #ec4899)',
    glowColor: 'radial-gradient(circle, rgba(139,92,246,0.15), transparent 70%)',
  },
  {
    icon: MessageCircle,
    title: '智能问答',
    desc: '基于 RAG + Plan-and-Solve 策略，精准回答论文相关问题',
    gradient: 'linear-gradient(135deg, #10b981, #06b6d4)',
    glowColor: 'radial-gradient(circle, rgba(16,185,129,0.15), transparent 70%)',
  },
  {
    icon: Code2,
    title: '代码复现',
    desc: 'AI 根据论文方法生成可运行的实现代码，支持多框架',
    gradient: 'linear-gradient(135deg, #10b981, #059669)',
    glowColor: 'radial-gradient(circle, rgba(16,185,129,0.15), transparent 70%)',
  },
  {
    icon: Languages,
    title: '全文翻译',
    desc: '逐段翻译保持学术风格，支持划词翻译与原文对照',
    gradient: 'linear-gradient(135deg, #f59e0b, #ef4444)',
    glowColor: 'radial-gradient(circle, rgba(245,158,11,0.15), transparent 70%)',
  },
]

const steps = [
  { icon: Upload, title: '上传论文', desc: 'PDF/Word 学术文档', gradient: 'linear-gradient(135deg, #3b82f6, #6366f1)' },
  { icon: Search, title: '智能解析', desc: '提取结构与向量索引', gradient: 'linear-gradient(135deg, #8b5cf6, #a855f7)' },
  { icon: BarChart3, title: '深度分析', desc: '生成可视化分析报告', gradient: 'linear-gradient(135deg, #06b6d4, #10b981)' },
  { icon: MessageCircle, title: '问答交互', desc: '多轮对话深入理解', gradient: 'linear-gradient(135deg, #f59e0b, #ef4444)' },
  { icon: Code2, title: '代码复现', desc: 'AI 生成实现代码', gradient: 'linear-gradient(135deg, #10b981, #059669)' },
]
</script>

<style scoped>
/* Hero 图标 */
.hero-icon-wrapper {
  position: relative;
  width: 100px;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
}
.hero-icon {
  width: 80px;
  height: 80px;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0ea5e9, #6366f1, #d946ef);
  position: relative;
  z-index: 3;
  box-shadow: 0 10px 40px rgba(14, 165, 233, 0.3);
  animation: float 6s ease-in-out infinite;
}
.hero-icon-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(14, 165, 233, 0.15);
  animation: pulse-ring 3s ease-in-out infinite;
}
.hero-icon-ring-1 { inset: -12px; }
.hero-icon-ring-2 { inset: -28px; border-color: rgba(99, 102, 241, 0.08); animation-delay: 1.5s; }
.hero-glow {
  position: absolute;
  inset: -20px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(14, 165, 233, 0.2), transparent 70%);
  filter: blur(20px);
  z-index: 1;
}

@keyframes pulse-ring {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.1); opacity: 0.5; }
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-12px); }
}

/* 上传区域 */
.upload-hero {
  position: relative;
  border-radius: 24px;
  border: 2px dashed rgba(14, 165, 233, 0.2);
  overflow: hidden;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
}
.upload-hero:hover {
  border-color: rgba(14, 165, 233, 0.35);
}
.upload-hero-active {
  border-color: rgba(14, 165, 233, 0.6) !important;
  border-style: solid;
  transform: scale(1.01);
}
.upload-hero-uploading {
  border-color: rgba(14, 165, 233, 0.4);
  border-style: solid;
}
.upload-hero-bg {
  position: absolute;
  inset: 0;
  background: 
    radial-gradient(circle at 30% 50%, rgba(14, 165, 233, 0.06), transparent 50%),
    radial-gradient(circle at 70% 50%, rgba(99, 102, 241, 0.06), transparent 50%);
  transition: opacity 0.3s;
}
.upload-hero:hover .upload-hero-bg,
.upload-hero-active .upload-hero-bg {
  opacity: 1.5;
}
.upload-hero-icon {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(14, 165, 233, 0.12);
  transition: all 0.3s;
}
.upload-hero:hover .upload-hero-icon {
  transform: scale(1.05);
  background: rgba(14, 165, 233, 0.12);
  box-shadow: 0 8px 30px rgba(14, 165, 233, 0.15);
}

/* CTA 按钮 */
.cta-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 14px 32px;
  font-weight: 600;
  font-size: 15px;
  color: white;
  border-radius: 14px;
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  position: relative;
  overflow: hidden;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 4px 20px rgba(14, 165, 233, 0.3);
}
.cta-primary:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 40px rgba(14, 165, 233, 0.45);
}
.cta-shine {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
  transition: left 0.6s;
}
.cta-primary:hover .cta-shine { left: 100%; }

/* Badges */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
  color: rgba(148, 163, 184, 0.8);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

/* Feature Cards */
.feature-card {
  position: relative;
  overflow: hidden;
  padding: 28px 24px;
  border-radius: 20px;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
  animation: fadeInUp 0.6s ease-out both;
}
.feature-card:hover {
  transform: translateY(-6px);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
}
.feature-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.feature-card:hover .feature-icon { transform: scale(1.1) rotate(-5deg); }
.feature-hover-glow {
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity 0.5s;
  pointer-events: none;
}
.feature-card:hover .feature-hover-glow { opacity: 1; }

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Workflow */
.workflow-container {
  position: relative;
  padding: 32px;
  border-radius: 24px;
  background: rgba(15, 23, 42, 0.3);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.workflow-line {
  position: absolute;
  top: 96px;
  left: 60px;
  right: 60px;
  height: 2px;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6, #06b6d4, #f59e0b);
  opacity: 0.3;
  border-radius: 1px;
}
.workflow-step { text-align: center; position: relative; }
.workflow-number {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 8px;
  background: rgba(14, 165, 233, 0.15);
  color: #38bdf8;
  font-size: 11px;
}
.workflow-icon {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.workflow-step:hover .workflow-icon {
  transform: scale(1.12);
  box-shadow: 0 8px 30px rgba(0,0,0,0.3);
}

/* Hero 粒子 */
.hero-particles {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}
.particle-dot {
  position: absolute;
  width: var(--size);
  height: var(--size);
  border-radius: 50%;
  background: rgba(14, 165, 233, 0.4);
  left: var(--x);
  top: var(--y);
  animation: particle-float 8s ease-in-out infinite;
  animation-delay: var(--delay);
}
@keyframes particle-float {
  0%, 100% { transform: translate(0, 0); opacity: 0.3; }
  25% { transform: translate(10px, -20px); opacity: 0.6; }
  50% { transform: translate(-5px, -40px); opacity: 0.2; }
  75% { transform: translate(15px, -20px); opacity: 0.5; }
}
</style>
