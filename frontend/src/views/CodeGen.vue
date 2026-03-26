<template>
  <div class="h-[calc(100vh-80px)] flex flex-col">
    <!-- 顶部工具栏 -->
    <div class="h-14 toolbar-glass px-6 flex items-center justify-between z-20">
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <Code2 :size="20" class="text-emerald-400" />
          <h1 class="text-lg font-semibold text-white">代码复现</h1>
        </div>
        <div v-if="store.documentInfo" class="flex items-center gap-2 text-gray-400 text-sm border-l border-white/10 pl-4">
          <FileText :size="14" />
          <span class="max-w-[200px] truncate">{{ store.documentInfo.filename }}</span>
        </div>
      </div>
      <div class="flex items-center gap-2" v-if="files.length">
        <button @click="copyCurrentFile" class="action-btn">
          <Copy :size="13" />
          {{ copyLabel }}
        </button>
        <button @click="downloadAllFiles" class="action-btn">
          <Download :size="13" />
          下载全部
        </button>
        <button @click="resetGeneration" class="action-btn">
          <RotateCcw :size="13" />
          重新生成
        </button>
      </div>
    </div>

    <!-- 主体内容区 -->
    <div class="flex-1 flex overflow-hidden relative">
      
      <!-- 未加载文档 -->
      <div v-if="!store.pdfUrl" class="absolute inset-0 z-50 flex items-center justify-center bg-gray-900/90 backdrop-blur-sm">
        <div class="text-center max-w-md">
          <div class="empty-icon-wrapper mx-auto mb-6">
            <Code2 :size="36" class="text-emerald-400/60" />
          </div>
          <h3 class="text-xl font-bold text-white mb-2">尚未加载文档</h3>
          <p class="text-gray-400 mb-8 text-sm leading-relaxed">请先在分析页面上传文档。</p>
          <div class="flex gap-3 justify-center">
            <router-link to="/analyze" class="btn-glow px-6 py-2.5 text-sm flex items-center gap-2">
              <Upload :size="16" /> 去上传
            </router-link>
          </div>
        </div>
      </div>

      <!-- 左侧：配置 + 文件树 -->
      <div class="w-[360px] bg-gray-900/50 relative flex flex-col border-r border-white/5">
        
        <!-- 配置区域 -->
        <div class="config-panel">
          <div class="config-card">
            <div class="flex items-center gap-3 mb-4">
              <div class="config-icon">
                <Settings :size="18" class="text-emerald-400" />
              </div>
              <div>
                <h3 class="font-semibold text-white text-sm">代码生成配置</h3>
                <p class="text-xs text-gray-500">生成多文件项目代码</p>
              </div>
            </div>

            <!-- 目标框架 -->
            <div class="mb-3">
              <label class="text-xs text-gray-400 mb-1.5 block font-medium">目标框架</label>
              <div class="grid grid-cols-3 gap-2">
                <button 
                  v-for="fw in frameworks" :key="fw.value"
                  @click="targetFramework = fw.value"
                  class="framework-chip"
                  :class="{ 'framework-chip-active': targetFramework === fw.value }"
                >
                  <component :is="fw.icon" :size="14" />
                  {{ fw.label }}
                </button>
              </div>
            </div>

            <!-- 需求描述 -->
            <div class="mb-3">
              <label class="text-xs text-gray-400 mb-1.5 block font-medium">需求描述</label>
              <textarea v-model="userRequest" rows="2" placeholder="例如：复现论文中核心算法..." class="code-textarea"></textarea>
            </div>

            <!-- 快捷模板 -->
            <div class="flex flex-wrap gap-1.5 mb-3">
              <button v-for="tpl in templates" :key="tpl" @click="userRequest = tpl" class="template-chip">
                <Sparkles :size="10" />
                {{ tpl }}
              </button>
            </div>

            <!-- 生成按钮 -->
            <button @click="startGeneration" :disabled="isGenerating" class="btn-generate w-full">
              <Loader2 :size="18" class="animate-spin" v-if="isGenerating" />
              <Rocket :size="18" v-else />
              {{ isGenerating ? '正在生成...' : '开始生成代码' }}
            </button>
          </div>
        </div>

        <!-- 文件树 -->
        <div v-if="files.length" class="flex-1 overflow-y-auto custom-scrollbar border-t border-white/5">
          <div class="px-4 py-3 text-xs text-gray-500 font-medium uppercase tracking-wider flex items-center gap-2">
            <FolderTree :size="13" />
            项目文件 ({{ files.length }})
          </div>
          <div 
            v-for="(f, i) in files" :key="i"
            @click="activeFileIndex = i"
            class="file-item group"
            :class="{ 'file-item-active': activeFileIndex === i }"
          >
            <component :is="getFileIcon(f.name)" :size="15" :class="getFileIconColor(f.name)" />
            <span class="truncate flex-1">{{ f.name }}</span>
            <span class="text-[10px] text-gray-600 group-hover:hidden">{{ f.lines }}行</span>
            <button 
              @click.stop="deleteFile(i)" 
              class="hidden group-hover:flex items-center justify-center w-5 h-5 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-colors"
            >
              <Trash2 :size="12" />
            </button>
          </div>
        </div>
      </div>

      <!-- 右侧：代码输出面板 -->
      <div class="flex-1 flex flex-col bg-gray-900/80 backdrop-blur-xl">
        
        <!-- 文件 tab -->
        <div v-if="files.length" class="h-10 flex items-center px-4 border-b border-white/5 bg-gray-900/50 gap-1 overflow-x-auto">
          <div class="flex items-center gap-1.5 px-3 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs">
            <component :is="getFileIcon(activeFile?.name || '')" :size="12" />
            {{ activeFile?.name || '无文件' }}
          </div>
        </div>

        <div class="flex-1 overflow-y-auto custom-scrollbar">
          
          <!-- 空状态 -->
          <div v-if="!rawOutput && !isGenerating" class="flex flex-col items-center justify-center h-full text-center p-8">
            <div class="empty-code-icon mb-4">
              <Terminal :size="32" class="text-gray-600" />
            </div>
            <h3 class="text-sm font-medium text-gray-400 mb-2">代码输出区</h3>
            <p class="text-xs text-gray-600 max-w-xs">配置好参数后点击"开始生成代码"，AI 将根据论文生成多文件项目代码</p>
          </div>

          <!-- 生成中指示 -->
          <div v-if="isGenerating && !activeFile" class="flex items-center gap-3 m-6 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
            <Loader2 :size="16" class="text-emerald-400 animate-spin" />
            <span class="text-emerald-400 text-sm">AI 正在生成项目代码...</span>
          </div>

          <!-- 代码内容 -->
          <div v-if="activeFile" class="p-6">
            <div class="code-output markdown-content prose prose-invert max-w-none text-sm" v-html="renderedActiveFile"></div>
          </div>

          <!-- 流式输出（未解析到文件时显示原始内容） -->
          <div v-if="isGenerating && !files.length && rawOutput" class="p-6">
            <div class="flex items-center gap-3 mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
              <Loader2 :size="16" class="text-emerald-400 animate-spin" />
              <span class="text-emerald-400 text-sm">AI 正在生成项目代码...</span>
            </div>
            <div class="code-output markdown-content prose prose-invert max-w-none text-sm" v-html="renderedRaw"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { renderMarkdown } from '../utils/markdown'
import api from '../api'
import { store } from '../store'
import { 
  Code2, FileText, Upload, Settings, Rocket, Loader2,
  Copy, Download, RotateCcw, Terminal, Sparkles, CheckCircle,
  Braces, Database, Cpu, FolderTree, FileCode, FileJson,
  File, FileType, BookOpen, Trash2
} from 'lucide-vue-next'

const targetFramework = ref('Python (PyTorch)')
const userRequest = ref('生成论文核心算法的完整实现代码')
const isGenerating = ref(false)
const rawOutput = ref('')
const files = ref([]) // [{name, content, lines}]
const activeFileIndex = ref(0)
const copyLabel = ref('复制代码')

const frameworks = [
  { value: 'Python (PyTorch)', label: 'PyTorch', icon: Cpu },
  { value: 'Python (TensorFlow/Keras)', label: 'TF/Keras', icon: Database },
  { value: 'Python (纯 NumPy/SciPy)', label: 'NumPy', icon: Braces },
]

const templates = [
  '生成论文核心算法的完整实现代码',
  '复现论文中的模型架构代码',
  '生成实验训练流程代码',
  '生成数据预处理和加载代码',
]

const activeFile = computed(() => files.value[activeFileIndex.value] || null)

const renderedActiveFile = computed(() => {
  if (!activeFile.value) return ''
  return renderMarkdown(activeFile.value.content)
})

const renderedRaw = computed(() => rawOutput.value ? renderMarkdown(rawOutput.value) : '')

// 解析 LLM 输出为多个文件
const parseFiles = (text) => {
  const result = []
  // 匹配 ### FILE: xxx ### 格式
  const parts = text.split(/^### FILE:\s*(.+?)\s*###\s*$/gm)
  
  if (parts.length <= 1) {
    // 没有文件分隔符，作为单文件
    if (text.trim()) {
      const lines = text.trim().split('\n').length
      result.push({ name: 'main.py', content: text.trim(), lines })
    }
    return result
  }
  
  // parts: [前导文字, 文件名1, 内容1, 文件名2, 内容2, ...]
  for (let i = 1; i < parts.length; i += 2) {
    const name = parts[i].trim()
    const content = (parts[i + 1] || '').trim()
    if (name && content) {
      const lines = content.split('\n').length
      result.push({ name, content, lines })
    }
  }
  return result
}

// 实时解析
watch(rawOutput, (text) => {
  if (!text) return
  const parsed = parseFiles(text)
  if (parsed.length > 0) {
    files.value = parsed
    // 首次解析到文件时选中第一个
    if (activeFileIndex.value >= parsed.length) {
      activeFileIndex.value = 0
    }
  }
})

const getFileIcon = (name) => {
  if (!name) return File
  if (name.endsWith('.md')) return BookOpen
  if (name.endsWith('.txt')) return FileType
  if (name.endsWith('.json')) return FileJson
  return FileCode
}

const getFileIconColor = (name) => {
  if (!name) return 'text-gray-500'
  if (name.endsWith('.py')) return 'text-yellow-400'
  if (name.endsWith('.md')) return 'text-blue-400'
  if (name.endsWith('.txt')) return 'text-gray-400'
  if (name.endsWith('.json')) return 'text-green-400'
  return 'text-emerald-400'
}

const startGeneration = async () => {
  if (isGenerating.value) return
  isGenerating.value = true
  rawOutput.value = ''
  files.value = []
  activeFileIndex.value = 0
  
  try {
    for await (const chunk of api.codeGenerateStream(userRequest.value, targetFramework.value)) {
      rawOutput.value += chunk
    }
  } catch (e) {
    rawOutput.value += '\n\n[生成中断: ' + e.message + ']'
  } finally {
    isGenerating.value = false
    // 最终解析
    const parsed = parseFiles(rawOutput.value)
    if (parsed.length > 0) {
      files.value = parsed
    }
  }
}

const resetGeneration = () => {
  rawOutput.value = ''
  files.value = []
  activeFileIndex.value = 0
}

const deleteFile = (index) => {
  files.value.splice(index, 1)
  if (activeFileIndex.value >= files.value.length) {
    activeFileIndex.value = Math.max(0, files.value.length - 1)
  }
}

const copyCurrentFile = async () => {
  try {
    const content = activeFile.value?.content || rawOutput.value
    // 提取纯代码
    const codeMatch = content.match(/```(?:\w*)\n([\s\S]*?)```/)
    await navigator.clipboard.writeText(codeMatch ? codeMatch[1] : content)
    copyLabel.value = '✅ 已复制'
    setTimeout(() => { copyLabel.value = '复制代码' }, 2000)
  } catch (e) { alert('复制失败') }
}

const downloadAllFiles = async () => {
  if (!files.value.length) return
  
  const JSZip = (await import('jszip')).default
  const zip = new JSZip()
  
  for (const f of files.value) {
    // 提取代码块内容（去除 markdown 格式）
    const codeMatch = f.content.match(/```(?:\w*)\n([\s\S]*?)```/)
    const content = codeMatch ? codeMatch[1] : f.content
    zip.file(f.name, content)
  }
  
  const blob = await zip.generateAsync({ type: 'blob' })
  const projectName = (store.documentInfo?.filename || 'paper').replace(/\.[^.]+$/, '') + '_code'
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `${projectName}.zip`; a.click()
  URL.revokeObjectURL(url)
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
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.12);
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

/* Config Panel */
.config-panel {
  padding: 12px;
}
.config-card {
  padding: 16px;
  border-radius: 16px;
  background: rgba(16, 185, 129, 0.03);
  border: 1px solid rgba(16, 185, 129, 0.08);
}
.config-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(16, 185, 129, 0.1);
}

/* Framework Chips */
.framework-chip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(148, 163, 184, 0.8);
  transition: all 0.3s;
  cursor: pointer;
}
.framework-chip:hover {
  background: rgba(255, 255, 255, 0.06);
  color: white;
}
.framework-chip-active {
  background: rgba(16, 185, 129, 0.12) !important;
  border-color: rgba(16, 185, 129, 0.3) !important;
  color: #34d399 !important;
  box-shadow: 0 0 15px rgba(16, 185, 129, 0.1);
}

/* Template chips */
.template-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: rgba(148, 163, 184, 0.7);
  transition: all 0.2s;
  cursor: pointer;
}
.template-chip:hover {
  background: rgba(16, 185, 129, 0.08);
  border-color: rgba(16, 185, 129, 0.2);
  color: #6ee7b7;
}

/* Textarea */
.code-textarea {
  width: 100%;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: white;
  font-size: 12px;
  resize: none;
  outline: none;
  transition: all 0.3s;
}
.code-textarea:focus {
  border-color: rgba(16, 185, 129, 0.4);
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1);
}
.code-textarea::placeholder { color: rgba(100, 116, 139, 0.5); }

/* Generate button */
.btn-generate {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 13px;
  color: white;
  background: linear-gradient(135deg, #10b981, #059669);
  transition: all 0.3s;
  cursor: pointer;
}
.btn-generate:hover:not(:disabled) {
  box-shadow: 0 8px 30px rgba(16, 185, 129, 0.4);
  transform: translateY(-2px);
}
.btn-generate:disabled {
  opacity: 0.7;
  cursor: not-allowed;
  transform: none;
}

/* File tree */
.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 13px;
  color: rgba(148, 163, 184, 0.8);
  cursor: pointer;
  transition: all 0.15s;
  border-left: 2px solid transparent;
}
.file-item:hover {
  background: rgba(255, 255, 255, 0.03);
  color: white;
}
.file-item-active {
  background: rgba(16, 185, 129, 0.06) !important;
  border-left-color: #10b981;
  color: white !important;
}

/* Empty state */
.empty-code-icon {
  width: 72px;
  height: 72px;
  border-radius: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

/* Code output */
.code-output { line-height: 1.7; }
.code-output :deep(pre) {
  background: rgba(0, 0, 0, 0.4) !important;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 16px 20px;
  overflow-x: auto;
  margin: 12px 0;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
}
.code-output :deep(code) {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
}
.code-output :deep(p code) {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.2);
  padding: 2px 6px;
  border-radius: 4px;
  color: #6ee7b7;
}

/* Action buttons */
.action-btn {
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
  cursor: pointer;
}
.action-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}

/* Scrollbar */
.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(16, 185, 129, 0.2); border-radius: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(16, 185, 129, 0.4); }
</style>
