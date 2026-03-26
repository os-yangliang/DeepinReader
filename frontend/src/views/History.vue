<template>
  <div class="max-w-7xl mx-auto">
    <div class="flex items-center justify-between mb-8">
      <div class="flex items-center gap-3">
        <div class="icon-wrapper">
          <Clock :size="20" class="text-primary-400" />
        </div>
        <div>
          <h1 class="text-2xl font-bold text-white">历史记录</h1>
          <p class="text-gray-500 text-xs mt-0.5">查看和管理已分析的论文</p>
        </div>
      </div>
      <button @click="refreshList" class="action-btn flex items-center gap-2">
        <RefreshCw :size="14" />
        刷新列表
      </button>
    </div>

    <div class="glass-card rounded-2xl overflow-hidden border border-white/5">
      <!-- Loading -->
      <div v-if="loading" class="p-16 text-center">
        <Loader2 :size="24" class="text-primary-400 animate-spin mx-auto mb-3" />
        <p class="text-gray-500 text-sm">加载中...</p>
      </div>
      
      <!-- Empty state -->
      <div v-else-if="historyList.length === 0" class="p-16 text-center">
        <div class="empty-icon-wrapper mx-auto mb-4">
          <Inbox :size="32" class="text-gray-600" />
        </div>
        <h3 class="text-lg font-semibold text-white mb-2">暂无历史记录</h3>
        <p class="text-gray-400 text-sm mb-6">上传并分析论文后，记录将显示在这里</p>
        <router-link to="/analyze" class="btn-glow px-6 py-2.5 text-sm inline-flex items-center gap-2">
          <Upload :size="16" />
          去分析论文
        </router-link>
      </div>

      <!-- Table -->
      <div v-else>
        <div class="grid gap-3 p-4">
          <div v-for="item in historyList" :key="item.id" 
               class="history-card group">
            <div class="flex items-center gap-4 flex-1 min-w-0">
              <!-- 文件图标 -->
              <div class="file-icon">
                <FileText :size="18" class="text-primary-400/70" />
              </div>
              
              <!-- 文件信息 -->
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-sm font-medium text-white truncate">{{ item.filename }}</span>
                </div>
                <div class="flex items-center gap-3 text-xs text-gray-500">
                  <span v-if="item.title" class="truncate max-w-[200px]" :title="item.title">{{ item.title }}</span>
                  <span class="flex items-center gap-1"><FileText :size="11" /> {{ item.page_count }}页</span>
                  <span class="flex items-center gap-1"><Type :size="11" /> {{ (item.word_count / 1000).toFixed(1) }}k字</span>
                  <span class="flex items-center gap-1"><Calendar :size="11" /> {{ formatDate(item.analyzed_at) }}</span>
                </div>
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <button 
                @click="loadHistory(item.id)" 
                class="action-btn-sm text-primary-400 hover:bg-primary-500/10"
              >
                <ExternalLink :size="14" />
                打开
              </button>
              <button 
                @click="deleteHistory(item.id)" 
                class="action-btn-sm text-red-400 hover:bg-red-500/10"
              >
                <Trash2 :size="14" />
                删除
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
  Clock, RefreshCw, Loader2, Inbox, Upload, FileText, Type, 
  Calendar, ExternalLink, Trash2 
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
.icon-wrapper {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(14, 165, 233, 0.12);
}

.empty-icon-wrapper {
  width: 72px;
  height: 72px;
  border-radius: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.btn-glow {
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

.action-btn {
  padding: 8px 16px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(148, 163, 184, 0.8);
  font-size: 13px;
  transition: all 0.2s;
}
.action-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}

.history-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.04);
  transition: all 0.3s;
}

.history-card:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
  transform: translateX(4px);
}

.file-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(14, 165, 233, 0.06);
  border: 1px solid rgba(14, 165, 233, 0.1);
  flex-shrink: 0;
}

.action-btn-sm {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.2s;
}
</style>