<template>
  <div class="min-h-screen relative">
    <!-- 背景效果 -->
    <div class="bg-mesh"></div>
    <div class="bg-grid"></div>
    
    <!-- 顶部导航栏 -->
    <nav class="fixed top-0 left-0 right-0 z-50 nav-glass">
      <div class="max-w-7xl mx-auto px-6">
        <div class="flex items-center justify-between h-16">
          <!-- Logo -->
          <router-link to="/" class="flex items-center gap-3 group">
            <div class="logo-container">
              <div class="logo-icon">
                <BookOpen :size="22" class="text-white" />
              </div>
              <div class="logo-glow"></div>
            </div>
            <div class="flex flex-col">
              <span class="font-display text-lg font-semibold text-white leading-tight tracking-wide">
                PaperReader
              </span>
              <span class="text-[10px] text-gray-400 tracking-widest uppercase">AI论文助手</span>
            </div>
          </router-link>
          
          <!-- 导航链接 -->
          <div class="flex items-center gap-1 bg-white/[0.03] rounded-xl p-1 border border-white/[0.06]">
            <router-link 
              v-for="link in navLinks" 
              :key="link.to"
              :to="link.to"
              class="nav-item"
              :class="{ 'nav-item-active': $route.path === link.to }"
            >
              <component :is="link.icon" :size="16" />
              <span>{{ link.label }}</span>
            </router-link>
          </div>

          <!-- 主题切换 + 文档切换 -->
          <div class="flex items-center gap-2">
            <button @click="store.toggleTheme()" class="theme-toggle-btn" :title="store.theme === 'dark' ? '切换亮色主题' : '切换暗色主题'">
              <Sun v-if="store.theme === 'dark'" :size="16" />
              <Moon v-else :size="16" />
            </button>
            <button 
              v-if="store.documents.length > 0" 
              @click="showDocPanel = !showDocPanel"
              class="doc-toggle-btn"
              :class="{ 'doc-toggle-active': showDocPanel }"
            >
              <Layers :size="16" />
              <span class="text-xs">{{ store.documents.length }} 篇</span>
            </button>
          </div>
        </div>
      </div>
    </nav>

    <!-- 文档侧边栏 -->
    <transition name="slide-panel">
      <div v-if="showDocPanel" class="doc-panel">
        <div class="doc-panel-header">
          <div class="flex items-center gap-2">
            <Layers :size="16" class="text-primary-400" />
            <span class="text-sm font-semibold text-white">已加载文档</span>
          </div>
          <button @click="showDocPanel = false" class="text-gray-500 hover:text-white transition-colors">
            <X :size="16" />
          </button>
        </div>
        
        <div class="doc-list">
          <div 
            v-for="doc in store.documents" :key="doc.document_id"
            class="doc-item group"
            :class="{ 'doc-item-active': doc.is_active }"
            @click="handleSwitchDoc(doc.document_id)"
          >
            <div class="flex items-center gap-3 flex-1 min-w-0">
              <div class="doc-icon" :class="doc.is_active ? 'doc-icon-active' : ''">
                <FileText :size="14" />
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm truncate" :class="doc.is_active ? 'text-white font-medium' : 'text-gray-300'">
                  {{ doc.filename }}
                </p>
                <p class="text-[10px] text-gray-500 truncate">
                  {{ doc.title || '未分析' }} · {{ doc.page_count }} 页
                  <span v-if="doc.has_summary" class="text-emerald-500">· ✓ 已分析</span>
                </p>
              </div>
            </div>
            <button 
              @click.stop="handleRemoveDoc(doc.document_id)" 
              class="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-all p-1 rounded hover:bg-red-500/10"
            >
              <Trash2 :size="13" />
            </button>
          </div>
        </div>

        <div v-if="store.documents.length === 0" class="p-6 text-center">
          <p class="text-gray-500 text-sm">尚未加载文档</p>
        </div>
      </div>
    </transition>
    
    <!-- 遮罩 -->
    <transition name="fade">
      <div v-if="showDocPanel" @click="showDocPanel = false" class="fixed inset-0 z-30 bg-black/30 backdrop-blur-sm"></div>
    </transition>

    <!-- 主内容区 -->
    <main class="relative z-10 pt-24 pb-12 px-6 min-h-[calc(100vh-120px)]">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <keep-alive :include="['Home', 'History', 'Search']">
            <component :is="Component" :key="$route.path" />
          </keep-alive>
        </transition>
      </router-view>
    </main>
    
    <!-- 页脚 -->
    <footer class="relative z-10 border-t border-white/5 py-6">
      <div class="max-w-7xl mx-auto px-6 flex items-center justify-between">
        <div class="flex items-center gap-2 text-gray-500 text-sm">
          <Sparkles :size="14" class="text-primary-500/60" />
          <span>Powered by LangChain & LangGraph Multi-Agent</span>
        </div>
        <div class="text-gray-600 text-xs">PaperReader v2.0</div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { BookOpen, Home, FileSearch, Globe, MessageCircle, Code2, Clock, Sparkles, Search, Network, Layers, X, FileText, Trash2, Sun, Moon, GitCompare, FlaskConical } from 'lucide-vue-next'
import { store } from './store'
import api from './api'

onMounted(() => { store.initTheme() })
const showDocPanel = ref(false)

const navLinks = [
  { to: '/', icon: Home, label: '首页' },
  { to: '/analyze', icon: FileSearch, label: '分析' },
  { to: '/translate', icon: Globe, label: '翻译' },
  { to: '/chat', icon: MessageCircle, label: '问答' },
  { to: '/codegen', icon: Code2, label: '代码' },
  { to: '/search', icon: Search, label: '搜索' },
  { to: '/mindmap', icon: Network, label: '导图' },
  { to: '/compare', icon: GitCompare, label: '对比' },
  { to: '/lab', icon: FlaskConical, label: '课题组' },
  { to: '/history', icon: Clock, label: '历史' },
]

const handleSwitchDoc = async (docId) => {
  if (store.documentInfo?.document_id === docId) return
  try {
    const res = await api.switchDocument(docId)
    if (res.success) {
      store.switchDocument(docId, res.document_info)
    }
  } catch (e) {
    console.error('切换文档失败:', e)
  }
}

const handleRemoveDoc = async (docId) => {
  try {
    const isActive = store.documentInfo?.document_id === docId
    await api.removeDocument(docId)
    store.removeDocument(docId)
    
    // 如果删除的是当前文档，并且还有其他文档，前端主动请求切换，以便拉取最新上下文和状态
    if (isActive && store.documents.length > 0) {
      const nextId = store.documents[0].document_id
      await handleSwitchDoc(nextId)
    }
  } catch (e) {
    console.error('移除文档失败:', e)
  }
}
</script>

<style scoped>
/* 导航栏玻璃态 */
.nav-glass {
  background: var(--bg-glass);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid var(--border-default);
  box-shadow: var(--shadow-card);
  transition: background 0.3s, border-color 0.3s;
}

/* Logo 容器 */
.logo-container {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}
.logo-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0ea5e9, #6366f1, #d946ef);
  position: relative;
  z-index: 2;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.group:hover .logo-icon {
  transform: scale(1.08) rotate(-3deg);
  box-shadow: 0 0 25px rgba(14, 165, 233, 0.5);
}
.logo-glow {
  position: absolute;
  inset: -4px;
  border-radius: 16px;
  background: linear-gradient(135deg, #0ea5e9, #6366f1, #d946ef);
  opacity: 0;
  filter: blur(12px);
  transition: opacity 0.4s;
  z-index: 1;
}
.group:hover .logo-glow { opacity: 0.4; }

/* 导航项 */
.nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
  white-space: nowrap;
}
.nav-item:hover {
  color: var(--text-heading);
  background: var(--bg-input);
}
.nav-item-active {
  color: var(--text-heading) !important;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.2), rgba(99, 102, 241, 0.15)) !important;
  border: 1px solid rgba(14, 165, 233, 0.2);
  box-shadow: 0 0 20px rgba(14, 165, 233, 0.1);
}

/* 主题切换按钮 */
.theme-toggle-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.3s;
}
.theme-toggle-btn:hover {
  color: #f59e0b;
  background: var(--bg-surface-hover);
  border-color: rgba(245, 158, 11, 0.3);
  box-shadow: 0 0 15px rgba(245, 158, 11, 0.15);
}

/* 文档切换按钮 */
.doc-toggle-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 10px;
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
  font-weight: 500;
  transition: all 0.3s;
  cursor: pointer;
}
.doc-toggle-btn:hover {
  background: var(--bg-surface-hover);
  color: var(--text-heading);
}
.doc-toggle-active {
  background: rgba(14, 165, 233, 0.12) !important;
  border-color: rgba(14, 165, 233, 0.3) !important;
  color: #38bdf8 !important;
}

/* 文档侧边栏 */
.doc-panel {
  position: fixed;
  top: 64px;
  right: 0;
  width: 360px;
  max-height: calc(100vh - 64px);
  z-index: 40;
  background: var(--bg-elevated);
  backdrop-filter: blur(20px);
  border-left: 1px solid var(--border-default);
  border-bottom: 1px solid var(--border-default);
  border-bottom-left-radius: 16px;
  box-shadow: var(--shadow-card);
  overflow-y: auto;
}
.doc-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-default);
}
.doc-list {
  padding: 8px;
}
.doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.doc-item:hover {
  background: var(--bg-input);
}
.doc-item-active {
  background: rgba(14, 165, 233, 0.08) !important;
  border: 1px solid rgba(14, 165, 233, 0.15);
}
.doc-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-input);
  color: var(--text-muted);
  flex-shrink: 0;
}
.doc-icon-active {
  background: rgba(14, 165, 233, 0.15);
  color: #38bdf8;
}

/* 侧边栏动画 */
.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.25s;
}
.slide-panel-enter-from,
.slide-panel-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 页面切换动画 */
.page-enter-active {
  animation: slideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.page-leave-active {
  animation: fadeOut 0.15s ease-in;
}
@keyframes slideUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeOut {
  from { opacity: 1; }
  to { opacity: 0; }
}
</style>
