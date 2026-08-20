<template>
  <div class="history-page">
    <PageToolbar :icon="Clock" title="历史记录" subtitle="查看和管理已分析的论文" :accent="'var(--accent-1)'">
      <template #actions>
        <button class="btn-secondary" @click="refreshList">
          <RefreshCw :size="14" /> 刷新列表
        </button>
      </template>
    </PageToolbar>

    <div class="history-body">
      <div class="history-inner">
        <div v-if="loading" class="loading-wrap">
          <Loader2 :size="24" class="animate-spin text-accent" />
          <p>加载中...</p>
        </div>

        <EmptyState
          v-else-if="historyList.length === 0"
          :icon="Inbox"
          title="暂无历史记录"
          description="上传并分析论文后，记录将显示在这里"
        >
          <router-link to="/analyze" class="btn-primary"><Upload :size="16" /> 去分析论文</router-link>
        </EmptyState>

        <div v-else class="history-list">
          <div v-for="item in historyList" :key="item.id" class="history-card card card-hover">
            <div class="file-icon">
              <FileText :size="18" />
            </div>
            <div class="file-info">
              <p class="file-name">{{ item.filename }}</p>
              <div class="file-meta">
                <span v-if="item.title" class="file-title" :title="item.title">{{ item.title }}</span>
                <span><FileText :size="11" /> {{ item.page_count }} 页</span>
                <span><Type :size="11" /> {{ (item.word_count / 1000).toFixed(1) }}k 字</span>
                <span><Calendar :size="11" /> {{ formatDate(item.analyzed_at) }}</span>
              </div>
            </div>
            <div class="file-actions">
              <button class="btn-ghost text-accent" @click="loadHistory(item.id)">
                <ExternalLink :size="14" /> 打开
              </button>
              <button class="btn-ghost text-danger" @click="deleteHistory(item.id)">
                <Trash2 :size="14" /> 删除
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { store } from '../store'
import {
  Clock, RefreshCw, Loader2, Inbox, Upload, FileText, Type, Calendar, ExternalLink, Trash2,
} from 'lucide-vue-next'

const router = useRouter()
const historyList = ref([])
const loading = ref(true)

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const refreshList = async () => {
  loading.value = true
  try {
    const res = await api.getHistory()
    historyList.value = res.history || []
  } catch (e) {
    console.error('获取历史记录失败:', e)
  } finally {
    loading.value = false
  }
}

const loadHistory = async (id) => {
  try {
    const res = await api.loadHistory(id)
    if (res.success) {
      store.setDocument(res.document_info, res.document_info.file_url || null, {
        success: true, document_info: res.document_info,
        structure: res.structure, summary: res.summary,
        analysis: res.summary || res.structure || '',
      })
      router.push('/analyze')
    }
  } catch (e) {
    alert('加载失败: ' + e.message)
  }
}

const deleteHistory = async (id) => {
  if (!confirm('确定要删除这条记录吗？相关的对话记录也会被删除。')) return
  try {
    await api.deleteHistory(id)
    if (store.documentInfo && store.documentInfo.document_id === id) store.clearDocument()
    await refreshList()
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

onMounted(() => refreshList())
</script>

<style scoped>
.history-page { height: 100vh; display: flex; flex-direction: column; }
.history-body { flex: 1; overflow-y: auto; }
.history-inner {
  max-width: 880px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
}

.loading-wrap {
  display: flex; flex-direction: column; align-items: center; gap: 0.8rem;
  padding: 4rem 0; color: var(--text-muted); font-size: 0.82rem;
}
.text-accent { color: var(--accent-1); }
.text-danger { color: var(--danger); }

.history-list { display: flex; flex-direction: column; gap: 0.75rem; }
.history-card {
  display: flex; align-items: center; gap: 0.9rem;
  padding: 1rem 1.25rem;
}

.file-icon {
  width: 42px; height: 42px; border-radius: 0.75rem;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  color: var(--accent-1); background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.14);
}
.file-info { flex: 1; min-width: 0; }
.file-name {
  font-size: 0.88rem; font-weight: 500; color: var(--text-heading);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.file-meta {
  display: flex; align-items: center; gap: 0.9rem; flex-wrap: wrap;
  margin-top: 0.35rem; font-size: 0.72rem; color: var(--text-muted);
}
.file-meta span { display: inline-flex; align-items: center; gap: 0.25rem; }
.file-title {
  max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.file-actions {
  display: flex; gap: 0.3rem; flex-shrink: 0;
  opacity: 0; transition: opacity 0.18s;
}
.history-card:hover .file-actions { opacity: 1; }

.text-accent { color: var(--accent-1); }
.text-danger { color: var(--danger); }
.text-muted { color: var(--text-muted); }
.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>