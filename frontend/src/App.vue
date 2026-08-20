<template>
  <div class="min-h-screen">
    <!-- 背景 -->
    <div class="bg-mesh"></div>
    <div class="bg-grid"></div>

    <!-- 侧边导航 -->
    <aside class="sidebar">
      <!-- Logo -->
      <router-link to="/" class="sidebar-logo">
        <div class="logo-mark">
          <BookOpen :size="20" />
        </div>
        <div class="logo-text">
          <span class="logo-title">DeepinReader</span>
          <span class="logo-sub">AI 论文助手</span>
        </div>
      </router-link>

      <!-- 导航分组 -->
      <nav class="sidebar-nav">
        <router-link
          v-for="link in navLinks"
          :key="link.to"
          :to="link.to"
          class="nav-link"
          :class="{ 'nav-link-active': isActive(link.to) }"
          :title="link.label"
        >
          <component :is="link.icon" :size="18" />
          <span>{{ link.label }}</span>
        </router-link>
      </nav>

      <!-- 底部操作 -->
      <div class="sidebar-footer">
        <button class="nav-link nav-link-muted" @click="store.toggleTheme()" :title="store.theme === 'dark' ? '切换亮色' : '切换暗色'">
          <Sun v-if="store.theme === 'dark'" :size="18" />
          <Moon v-else :size="18" />
          <span>{{ store.theme === 'dark' ? '亮色' : '暗色' }}</span>
        </button>
        <button
          v-if="store.documents.length > 0"
          class="nav-link nav-link-muted"
          :class="{ 'nav-link-active': showDocPanel }"
          @click="showDocPanel = !showDocPanel"
          :title="'已加载文档'"
        >
          <Layers :size="18" />
          <span>{{ store.documents.length }} 篇文档</span>
        </button>
      </div>
    </aside>

    <!-- 文档侧边栏 -->
    <transition name="slide-panel">
      <div v-if="showDocPanel" class="doc-panel">
        <div class="doc-panel-header">
          <div class="doc-panel-title">
            <Layers :size="16" class="text-accent" />
            <span>已加载文档</span>
          </div>
          <button @click="showDocPanel = false" class="icon-btn">
            <X :size="16" />
          </button>
        </div>

        <div class="doc-list">
          <div
            v-for="doc in store.documents"
            :key="doc.document_id"
            class="doc-item"
            :class="{ 'doc-item-active': doc.is_active }"
            @click="handleSwitchDoc(doc.document_id)"
          >
            <div class="doc-icon" :class="{ 'doc-icon-active': doc.is_active }">
              <FileText :size="15" />
            </div>
            <div class="doc-meta">
              <p class="doc-name" :class="{ active: doc.is_active }">{{ doc.filename }}</p>
              <p class="doc-sub">
                {{ doc.page_count || 0 }} 页
                <span v-if="doc.has_summary" class="text-positive">· 已分析</span>
              </p>
            </div>
            <button class="icon-btn doc-delete" @click.stop="handleRemoveDoc(doc.document_id)">
              <Trash2 :size="14" />
            </button>
          </div>
        </div>

        <div v-if="store.documents.length === 0" class="doc-empty">
          <Layers :size="22" class="text-muted" />
          <p>尚未加载文档</p>
        </div>
      </div>
    </transition>

    <!-- 遮罩 -->
    <transition name="fade">
      <div v-if="showDocPanel" class="panel-mask" @click="showDocPanel = false"></div>
    </transition>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" :key="$route.path" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  BookOpen, Home, FileSearch, Globe, MessageCircle,
  Clock, Search, GitCompare, FlaskConical,
  Layers, X, FileText, Trash2, Sun, Moon,
} from 'lucide-vue-next'
import { store } from './store'
import api from './api'

const route = useRoute()
const showDocPanel = ref(false)

onMounted(() => store.initTheme())

const navLinks = [
  { to: '/', icon: Home, label: '首页' },
  { to: '/analyze', icon: FileSearch, label: '分析' },
  { to: '/chat', icon: MessageCircle, label: '问答' },
  { to: '/translate', icon: Globe, label: '翻译' },
  { to: '/compare', icon: GitCompare, label: '对比' },
  { to: '/search', icon: Search, label: '搜索' },
  { to: '/lab', icon: FlaskConical, label: '课题组' },
  { to: '/history', icon: Clock, label: '历史' },
]

const isActive = (to) => (to === '/' ? route.path === '/' : route.path.startsWith(to))

const handleSwitchDoc = async (docId) => {
  if (store.documentInfo?.document_id === docId) return
  try {
    const res = await api.switchDocument(docId)
    if (res.success) store.switchDocument(docId, res.document_info)
  } catch (e) {
    console.error('切换文档失败:', e)
  }
}

const handleRemoveDoc = async (docId) => {
  try {
    const isActive = store.documentInfo?.document_id === docId
    await api.removeDocument(docId)
    store.removeDocument(docId)
    if (isActive && store.documents.length > 0) {
      await handleSwitchDoc(store.documents[0].document_id)
    }
  } catch (e) {
    console.error('移除文档失败:', e)
  }
}
</script>

<style scoped>
/* ===== 侧边栏 ===== */
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 220px;
  z-index: 50;
  display: flex;
  flex-direction: column;
  background: var(--bg-glass);
  backdrop-filter: blur(20px) saturate(160%);
  -webkit-backdrop-filter: blur(20px) saturate(160%);
  border-right: 1px solid var(--border-default);
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1.5rem 1.25rem 1.25rem;
  text-decoration: none;
  border-bottom: 1px solid var(--border-default);
}

.logo-mark {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, var(--accent-1), var(--accent-2), var(--accent-3));
  box-shadow: 0 4px 16px rgba(56, 189, 248, 0.35);
  flex-shrink: 0;
}

.logo-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.logo-title {
  font-family: 'Sora', sans-serif;
  font-weight: 700;
  font-size: 1rem;
  color: var(--text-heading);
  letter-spacing: 0.01em;
}
.logo-sub {
  font-size: 0.68rem;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 1px;
}

/* ===== 导航 ===== */
.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.62rem 0.85rem;
  border-radius: 0.65rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
  text-decoration: none;
  transition: all 0.18s ease;
  border: 1px solid transparent;
  white-space: nowrap;
}
.nav-link:hover {
  color: var(--text-heading);
  background: var(--bg-input);
}
.nav-link-active {
  color: var(--accent-1);
  background: rgba(56, 189, 248, 0.08);
  border-color: rgba(56, 189, 248, 0.18);
}
.nav-link-muted {
  background: transparent;
}

.sidebar-footer {
  padding: 0.75rem;
  border-top: 1px solid var(--border-default);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* ===== 文档面板 ===== */
.doc-panel {
  position: fixed;
  top: 0;
  left: 220px;
  bottom: 0;
  width: 320px;
  z-index: 60;
  display: flex;
  flex-direction: column;
  background: var(--bg-elevated);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-right: 1px solid var(--border-default);
  box-shadow: var(--shadow-card-lg);
}

.doc-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.1rem;
  border-bottom: 1px solid var(--border-default);
}
.doc-panel-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-heading);
}
.text-accent { color: var(--accent-1); }

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.4rem;
  border-radius: 0.5rem;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
  border: none;
  background: transparent;
}
.icon-btn:hover {
  color: var(--text-heading);
  background: var(--bg-input);
}

.doc-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.6rem;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.7rem;
  border-radius: 0.75rem;
  cursor: pointer;
  transition: all 0.18s;
  border: 1px solid transparent;
}
.doc-item:hover {
  background: var(--bg-surface-hover);
}
.doc-item-active {
  background: rgba(56, 189, 248, 0.06);
  border-color: rgba(56, 189, 248, 0.16);
}

.doc-icon {
  width: 34px;
  height: 34px;
  border-radius: 0.6rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-input);
  color: var(--text-muted);
  flex-shrink: 0;
}
.doc-icon-active {
  background: rgba(56, 189, 248, 0.14);
  color: var(--accent-1);
}

.doc-meta {
  flex: 1;
  min-width: 0;
}
.doc-name {
  font-size: 0.82rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.doc-name.active { color: var(--text-heading); font-weight: 500; }
.doc-sub { font-size: 0.7rem; color: var(--text-muted); margin-top: 1px; }
.text-positive { color: var(--positive); }

.doc-delete {
  opacity: 0;
  flex-shrink: 0;
}
.doc-item:hover .doc-delete { opacity: 1; }
.doc-delete:hover { color: var(--danger); background: rgba(248, 113, 113, 0.12); }

.doc-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  color: var(--text-muted);
  font-size: 0.78rem;
}
.text-muted { color: var(--text-muted); }

.panel-mask {
  position: fixed;
  inset: 0;
  z-index: 55;
  background: rgba(2, 6, 23, 0.4);
  backdrop-filter: blur(2px);
}

/* ===== 主内容 ===== */
.main-content {
  position: relative;
  z-index: 10;
  margin-left: 220px;
  min-height: 100vh;
}

/* ===== 过渡 ===== */
.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.25s;
}
.slide-panel-enter-from,
.slide-panel-leave-to {
  transform: translateX(-100%);
  opacity: 0;
}
.fade-enter-active,
.fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from,
.fade-leave-to { opacity: 0; }
</style>