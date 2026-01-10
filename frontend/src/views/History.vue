<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-8">
      <h1 class="text-2xl font-bold gradient-text">📚 历史记录</h1>
      <button @click="refreshList" class="btn-secondary text-sm px-4 py-2">
        刷新列表
      </button>
    </div>

    <div class="glass-card rounded-2xl overflow-hidden border border-white/5">
      <div v-if="loading" class="p-12 text-center text-gray-500">
        加载中...
      </div>
      
      <div v-else-if="historyList.length === 0" class="p-12 text-center">
        <div class="text-6xl mb-4">📭</div>
        <h3 class="text-xl font-bold text-white mb-2">暂无历史记录</h3>
        <p class="text-gray-400 mb-6">上传并分析论文后，记录将显示在这里</p>
        <router-link to="/analyze" class="btn-primary px-6 py-2 inline-block">
          去分析论文
        </router-link>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead class="bg-white/5 text-gray-400 uppercase">
            <tr>
              <th class="px-6 py-4 font-medium">文件名</th>
              <th class="px-6 py-4 font-medium">标题</th>
              <th class="px-6 py-4 font-medium">页数/字数</th>
              <th class="px-6 py-4 font-medium">分析时间</th>
              <th class="px-6 py-4 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-white/5">
            <tr v-for="item in historyList" :key="item.id" class="hover:bg-white/5 transition-colors">
              <td class="px-6 py-4 font-medium text-white">
                <div class="flex items-center gap-3">
                  <span class="text-2xl">📄</span>
                  {{ item.filename }}
                </div>
              </td>
              <td class="px-6 py-4 text-gray-300 max-w-xs truncate" :title="item.title">
                {{ item.title || '未知标题' }}
              </td>
              <td class="px-6 py-4 text-gray-400">
                {{ item.page_count }}页 / {{ (item.word_count / 1000).toFixed(1) }}k字
              </td>
              <td class="px-6 py-4 text-gray-400">
                {{ formatDate(item.analyzed_at) }}
              </td>
              <td class="px-6 py-4 text-right">
                <div class="flex items-center justify-end gap-2">
                  <button 
                    @click="loadHistory(item.id)" 
                    class="text-primary-400 hover:text-primary-300 px-3 py-1 hover:bg-white/10 rounded transition-colors"
                  >
                    打开
                  </button>
                  <button 
                    @click="deleteHistory(item.id)" 
                    class="text-red-400 hover:text-red-300 px-3 py-1 hover:bg-white/10 rounded transition-colors"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { store } from '../store'

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
      // 更新全局状态
      store.setDocument(
        res.document_info,
        res.document_info.file_url || null, // 历史记录可能没有 file_url，需要后端配合
        {
            success: true,
            document_info: res.document_info,
            structure: res.structure,
            summary: res.summary
        }
      )
      
      // 默认跳转到分析页
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
    // 如果删除的是当前打开的文档，清除状态
    if (store.documentInfo && store.documentInfo.document_id === id) {
      store.clearDocument()
    }
    await refreshList()
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

onMounted(() => {
  refreshList()
})
</script>