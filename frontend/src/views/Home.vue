<template>
  <div class="home">
    <div class="home-inner">
      <!-- Hero -->
      <section class="hero">
        <div class="hero-badge">
          <Sparkles :size="13" />
          <span>LangChain × LangGraph 多智能体</span>
        </div>

        <h1 class="hero-title">
          用 AI 深度理解<br />
          <span class="gradient-text">每一篇学术论文</span>
        </h1>

        <p class="hero-desc">
          上传 Paper，自动结构化解析、生成分析报告、智能问答、全文翻译与代码复现，
          让论文阅读从「逐字啃」变成「一眼懂」。
        </p>

        <div class="hero-pills">
          <span class="pill pill-accent"><Zap :size="12" /> PDF / Word</span>
          <span class="pill pill-accent"><Brain :size="12" /> 多智能体</span>
          <span class="pill pill-accent"><Globe :size="12" /> 联网搜索</span>
        </div>
      </section>

      <!-- 上传区 -->
      <section class="upload-section">
        <div
          class="upload-hero"
          :class="{ 'is-dragging': isDragging, 'is-uploading': isUploading }"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="handleDrop"
        >
          <template v-if="isUploading">
            <Loader2 :size="36" class="spinner" />
            <p class="upload-status">{{ uploadStatus }}</p>
            <p class="upload-hint">解析完成后将自动跳转到分析页...</p>
          </template>

          <template v-else>
            <div class="upload-icon">
              <FileUp :size="26" />
            </div>
            <h3 class="upload-title">{{ isDragging ? '松开鼠标上传' : '拖拽论文到此处' }}</h3>
            <p class="upload-hint">或点击下方按钮选择文件 · 支持 PDF 格式</p>
            <button class="btn-primary upload-btn" @click="triggerFileInput">
              <Upload :size="17" />
              <span>选择论文上传</span>
              <ArrowRight :size="15" />
            </button>
            <input ref="fileInputRef" type="file" accept=".pdf" class="hidden" @change="handleFileSelect" />
          </template>
        </div>
      </section>

      <!-- 功能 -->
      <section class="features-section">
        <div class="section-head">
          <h2 class="section-title">核心能力</h2>
          <p class="section-desc">覆盖论文阅读全流程的智能工具链</p>
        </div>
        <div class="features-grid">
          <router-link
            v-for="f in features"
            :key="f.title"
            :to="f.to"
            class="feature-card card-hover"
          >
            <div class="feature-icon" :style="{ background: f.gradient }">
              <component :is="f.icon" :size="20" />
            </div>
            <h3 class="feature-title">{{ f.title }}</h3>
            <p class="feature-desc">{{ f.desc }}</p>
          </router-link>
        </div>
      </section>

      <!-- 工作流 -->
      <section class="features-section">
        <div class="section-head">
          <h2 class="section-title">工作流程</h2>
          <p class="section-desc">多智能体协作的论文理解管线</p>
        </div>
        <div class="workflow">
          <div v-for="(step, i) in steps" :key="step.title" class="workflow-step">
            <div class="workflow-node" :style="{ background: step.gradient }">
              <component :is="step.icon" :size="20" />
            </div>
            <div class="workflow-step-body">
              <span class="workflow-index">0{{ i + 1 }}</span>
              <h4 class="workflow-title">{{ step.title }}</h4>
              <p class="workflow-desc">{{ step.desc }}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight, Upload, Sparkles, FileSearch, BarChart3, Globe,
  Zap, Brain, Languages, MessageCircle, FileUp, Loader2,
  Search, GitCompare, FlaskConical,
} from 'lucide-vue-next'
import api from '../api'
import { store } from '../store'

const router = useRouter()
const fileInputRef = ref(null)
const isDragging = ref(false)
const isUploading = ref(false)
const uploadStatus = ref('')

const triggerFileInput = () => fileInputRef.value?.click()

const handleFileSelect = (e) => {
  const f = e.target.files?.[0]
  if (f) {
    e.target.value = ''
    startUpload(f)
  }
}

const handleDrop = (e) => {
  isDragging.value = false
  const f = e.dataTransfer.files?.[0]
  if (f && f.type === 'application/pdf') startUpload(f)
  else alert('请上传 PDF 文件')
}

const startUpload = async (file) => {
  isUploading.value = true
  uploadStatus.value = '正在上传并解析文档...'
  try {
    const blobUrl = URL.createObjectURL(file)
    store.setDocument({ filename: file.name }, blobUrl, null)

    uploadStatus.value = '正在解析文档结构...'
    const result = await api.uploadDocument(file)
    if (!result.success) throw new Error(result.error || '上传失败')

    const docInfo = result.document_info
    if (blobUrl.startsWith('blob:')) URL.revokeObjectURL(blobUrl)
    store.setDocument(docInfo, docInfo.file_url, null)
    uploadStatus.value = '解析完成，正在跳转...'

    setTimeout(() => router.push('/analyze'), 500)
  } catch (e) {
    alert('上传失败: ' + e.message)
    store.clearDocument()
  } finally {
    setTimeout(() => { isUploading.value = false }, 1000)
  }
}

const features = [
  { to: '/analyze', icon: FileSearch, title: '智能分析', desc: '自动提取结构，生成覆盖方法、创新点与结论的结构化报告', gradient: 'linear-gradient(135deg, #0ea5e9, #06b6d4)' },
  { to: '/chat', icon: MessageCircle, title: '智能问答', desc: '基于证据图谱的问答，带推理路径与置信度', gradient: 'linear-gradient(135deg, #6366f1, #8b5cf6)' },
  { to: '/translate', icon: Languages, title: '全文翻译', desc: '逐段学术级翻译，支持划词翻译与原文对照', gradient: 'linear-gradient(135deg, #f59e0b, #ef4444)' },
  { to: '/compare', icon: BarChart3, title: '多文档对比', desc: '2-3 篇论文深度对比，全景把握研究差异', gradient: 'linear-gradient(135deg, #06b6d4, #3b82f6)' },
  { to: '/search', icon: Search, title: '智能搜索', desc: '检索 Semantic Scholar 数据库，发现相关研究', gradient: 'linear-gradient(135deg, #10b981, #059669)' },
  { to: '/lab', icon: FlaskConical, title: '课题组研讨', desc: 'AI 导师与学生围绕论文研讨，共创研究提案', gradient: 'linear-gradient(135deg, #8b5cf6, #ec4899)' },
]

const steps = [
  { icon: Upload, title: '上传论文', desc: 'PDF / Word 学术文档', gradient: 'linear-gradient(135deg, #3b82f6, #6366f1)' },
  { icon: Search, title: '智能解析', desc: '结构抽取与向量索引', gradient: 'linear-gradient(135deg, #8b5cf6, #a855f7)' },
  { icon: BarChart3, title: '深度分析', desc: '生成可视化分析报告', gradient: 'linear-gradient(135deg, #06b6d4, #10b981)' },
  { icon: MessageCircle, title: '证据问答', desc: '多轮对话证据问答', gradient: 'linear-gradient(135deg, #f59e0b, #ef4444)' },
  { icon: GitCompare, title: '对比研讨', desc: '多文档对比与灵感共创', gradient: 'linear-gradient(135deg, #10b981, #059669)' },
]
</script>

<style scoped>
.home {
  height: 100vh;
  overflow-y: auto;
}
.home-inner {
  max-width: 1080px;
  margin: 0 auto;
  padding: 3.5rem 2rem 5rem;
}

/* Hero */
.hero {
  text-align: center;
  padding: 0.5rem 0 3rem;
}
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 1rem;
  border-radius: 9999px;
  font-size: 0.78rem;
  color: var(--accent-1);
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.2);
  margin-bottom: 1.5rem;
}
.hero-title {
  font-family: 'Sora', 'Noto Sans SC', sans-serif;
  font-weight: 700;
  font-size: clamp(2rem, 4.5vw, 3.25rem);
  line-height: 1.2;
  color: var(--text-heading);
  letter-spacing: -0.02em;
}
.hero-desc {
  font-size: 1rem;
  color: var(--text-secondary);
  max-width: 620px;
  margin: 1.25rem auto 0;
  line-height: 1.75;
}
.hero-pills {
  display: flex;
  justify-content: center;
  gap: 0.6rem;
  margin-top: 1.5rem;
  flex-wrap: wrap;
}

/* Upload */
.upload-section {
  max-width: 720px;
  margin: 0 auto 4rem;
}
.upload-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 3rem 2rem;
  border-radius: 1.5rem;
  border: 1.5px dashed var(--border-hover);
  background: var(--bg-surface);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  cursor: pointer;
  transition: all 0.3s ease;
}
.upload-hero:hover,
.upload-hero.is-dragging {
  border-color: var(--border-accent);
  background: rgba(56, 189, 248, 0.04);
  box-shadow: var(--shadow-glow);
}
.upload-hero.is-dragging {
  transform: scale(1.01);
}
.upload-icon {
  width: 60px;
  height: 60px;
  border-radius: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-1);
  background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.2);
  margin-bottom: 1.1rem;
  transition: transform 0.3s ease;
}
.upload-hero:hover .upload-icon {
  transform: scale(1.06) translateY(-2px);
}
.upload-title {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--text-heading);
  margin-bottom: 0.4rem;
}
.upload-hint {
  font-size: 0.82rem;
  color: var(--text-muted);
  margin-bottom: 1.4rem;
}
.upload-btn { padding: 0.75rem 1.6rem; }
.spinner { color: var(--accent-1); margin-bottom: 1rem; }
.upload-status { font-size: 1rem; font-weight: 600; color: var(--accent-1); margin-bottom: 0.3rem; }

/* Sections */
.features-section { margin-bottom: 4rem; }
.section-head {
  text-align: center;
  margin-bottom: 2rem;
}
.section-title {
  font-family: 'Sora', 'Noto Sans SC', sans-serif;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-heading);
  margin-bottom: 0.4rem;
}
.section-desc {
  font-size: 0.85rem;
  color: var(--text-muted);
}

/* Feature cards */
.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}
@media (max-width: 900px) {
  .features-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .features-grid { grid-template-columns: 1fr; }
}
.feature-card {
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  border-radius: 1rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  text-decoration: none;
  cursor: pointer;
}
.feature-icon {
  width: 44px;
  height: 44px;
  border-radius: 0.9rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  margin-bottom: 1rem;
  box-shadow: 0 4px 14px rgba(2, 6, 23, 0.2);
}
.feature-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-heading);
  margin-bottom: 0.35rem;
}
.feature-desc {
  font-size: 0.8rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

/* Workflow */
.workflow {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}
.workflow-step {
  flex: 1;
  min-width: 160px;
  text-align: center;
  padding: 1.5rem 1rem;
  border-radius: 1rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
}
.workflow-node {
  width: 48px;
  height: 48px;
  border-radius: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  margin: 0 auto 0.9rem;
  box-shadow: 0 4px 14px rgba(2, 6, 23, 0.2);
}
.workflow-step-body { display: flex; flex-direction: column; }
.workflow-index {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-bottom: 0.4rem;
}
.workflow-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-heading);
  margin-bottom: 0.3rem;
}
.workflow-desc {
  font-size: 0.76rem;
  color: var(--text-muted);
  line-height: 1.5;
}
</style>