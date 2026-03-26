<template>
  <div class="h-[calc(100vh-80px)] flex flex-col">
    <!-- 顶部工具栏 -->
    <div class="h-14 toolbar-glass px-6 flex items-center justify-between z-20">
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <Search :size="20" class="text-primary-400" />
          <h1 class="text-lg font-semibold text-white">相关论文</h1>
        </div>
      </div>
    </div>

    <!-- 主体 -->
    <div class="flex-1 overflow-y-auto custom-scrollbar">
      <div class="max-w-4xl mx-auto px-6 py-8">
        
        <!-- 搜索栏 -->
        <div class="search-bar mb-8">
          <div class="flex gap-3">
            <div class="flex-1 relative">
              <Search :size="18" class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
              <input 
                v-model="searchQuery"
                @keydown.enter="doSearch"
                type="text"
                class="search-input"
                :placeholder="defaultQuery ? `默认搜索: ${defaultQuery.slice(0, 40)}...` : '输入搜索关键词...'"
              />
            </div>
            <button @click="doSearch" class="btn-glow px-6 py-3 text-sm" :disabled="isSearching">
              <Loader2 v-if="isSearching" :size="16" class="animate-spin" />
              <Search v-else :size="16" />
              搜索
            </button>
          </div>
          
          <!-- 快速搜索按钮 -->
          <div v-if="store.documentInfo" class="flex gap-2 mt-3">
            <button 
              @click="searchByTitle"
              class="quick-tag"
            >
              <FileText :size="12" />
              按论文标题搜索
            </button>
            <button 
              v-for="(kw, i) in suggestedKeywords"
              :key="i"
              @click="searchQuery = kw; doSearch()"
              class="quick-tag"
            >
              {{ kw }}
            </button>
          </div>
        </div>

        <!-- 搜索统计 -->
        <div v-if="searchResult" class="flex items-center justify-between mb-6">
          <div class="text-sm text-gray-400">
            搜索 "<span class="text-primary-400">{{ searchResult.query }}</span>" 
            找到 <span class="text-white font-medium">{{ searchResult.total.toLocaleString() }}</span> 篇论文
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="!searchResult && !isSearching" class="flex flex-col items-center justify-center py-20 text-center">
          <div class="empty-icon-wrapper mb-6">
            <BookOpen :size="32" class="text-primary-400/50" />
          </div>
          <h3 class="text-lg font-semibold text-white mb-2">发现相关研究</h3>
          <p class="text-gray-400 text-sm max-w-md">
            搜索 Semantic Scholar 的 2 亿+ 学术论文数据库，
            <span v-if="store.documentInfo">或基于当前论文自动推荐相关研究。</span>
            <span v-else>输入关键词开始搜索。</span>
          </p>
          <button v-if="store.documentInfo" @click="searchByTitle" class="btn-glow px-6 py-2.5 text-sm mt-6 flex items-center gap-2">
            <Sparkles :size="16" />
            自动搜索相关论文
          </button>
        </div>

        <!-- 搜索中 -->
        <div v-if="isSearching" class="flex flex-col items-center py-16">
          <Loader2 :size="28" class="text-primary-400 animate-spin mb-4" />
          <p class="text-gray-400 text-sm">正在搜索 Semantic Scholar...</p>
        </div>

        <!-- 搜索结果列表 -->
        <div v-if="searchResult && !isSearching" class="space-y-4">
          <div 
            v-for="(paper, index) in searchResult.papers" 
            :key="index" 
            class="paper-card"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="flex-1 min-w-0">
                <!-- 标题 -->
                <a :href="paper.url" target="_blank" rel="noopener" class="paper-title">
                  {{ paper.title }}
                </a>
                
                <!-- 元信息 -->
                <div class="flex items-center gap-3 mt-2 text-xs text-gray-500 flex-wrap">
                  <span v-if="paper.year" class="flex items-center gap-1">
                    <Calendar :size="12" />
                    {{ paper.year }}
                  </span>
                  <span v-if="paper.authors.length" class="flex items-center gap-1 truncate max-w-[300px]">
                    <Users :size="12" />
                    {{ paper.authors.join(', ') }}
                  </span>
                  <span v-if="paper.citationCount" class="flex items-center gap-1 text-amber-400/80">
                    <Quote :size="12" />
                    {{ paper.citationCount.toLocaleString() }} 引用
                  </span>
                </div>
                
                <!-- 摘要 -->
                <p v-if="paper.abstract" class="text-gray-400 text-xs mt-3 leading-relaxed line-clamp-3">
                  {{ paper.abstract }}
                </p>
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <div class="flex items-center gap-2 mt-4 pt-3 border-t border-white/5">
              <a :href="paper.url" target="_blank" rel="noopener" class="action-btn">
                <ExternalLink :size="13" />
                Semantic Scholar
              </a>
              <a v-if="paper.pdfUrl" :href="paper.pdfUrl" target="_blank" rel="noopener" class="action-btn action-btn-primary">
                <FileDown :size="13" />
                下载 PDF
              </a>
              <a v-if="paper.doi" :href="`https://doi.org/${paper.doi}`" target="_blank" rel="noopener" class="action-btn">
                <Link :size="13" />
                DOI
              </a>
            </div>
          </div>
          
          <div v-if="searchResult.papers.length === 0" class="text-center py-12 text-gray-500 text-sm">
            未找到相关论文，请尝试其他关键词
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
import { store } from '../store'
import { 
  Search, FileText, BookOpen, Sparkles, Loader2,
  Calendar, Users, Quote, ExternalLink, FileDown, Link
} from 'lucide-vue-next'

const searchQuery = ref('')
const isSearching = ref(false)
const searchResult = ref(null)

const defaultQuery = computed(() => {
  if (!store.documentInfo) return ''
  return store.documentInfo.title || store.documentInfo.filename || ''
})

const suggestedKeywords = computed(() => {
  // 从标题中提取关键短语
  const title = defaultQuery.value
  if (!title) return []
  const words = title.split(/[\s,.:;]+/).filter(w => w.length > 3)
  if (words.length <= 3) return []
  // 取前半段和后半段做两个查询
  const mid = Math.ceil(words.length / 2)
  return [
    words.slice(0, mid).join(' '),
    words.slice(mid).join(' ')
  ].filter(q => q.length > 5)
})

const doSearch = async () => {
  if (isSearching.value) return
  isSearching.value = true
  
  try {
    const query = searchQuery.value.trim() || ''
    searchResult.value = await api.searchPapers(query, 10)
  } catch (e) {
    alert('搜索失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    isSearching.value = false
  }
}

const searchByTitle = () => {
  searchQuery.value = defaultQuery.value
  doSearch()
}

onMounted(() => {
  // 如果已有文档，自动搜索
  if (store.documentInfo?.title) {
    searchByTitle()
  }
})
</script>

<style scoped>
.toolbar-glass {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.search-bar {
  padding: 24px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.search-input {
  width: 100%;
  padding: 12px 16px 12px 44px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: white;
  font-size: 14px;
  outline: none;
  transition: all 0.3s;
}
.search-input:focus {
  border-color: rgba(14, 165, 233, 0.4);
  box-shadow: 0 0 20px rgba(14, 165, 233, 0.1);
}
.search-input::placeholder {
  color: rgba(148, 163, 184, 0.5);
}

.btn-glow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: white;
  border-radius: 14px;
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  transition: all 0.3s;
}
.btn-glow:hover {
  box-shadow: 0 8px 25px rgba(14, 165, 233, 0.4);
  transform: translateY(-1px);
}
.btn-glow:disabled {
  opacity: 0.6;
  pointer-events: none;
}

.quick-tag {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 8px;
  background: rgba(14, 165, 233, 0.06);
  border: 1px solid rgba(14, 165, 233, 0.12);
  color: rgba(14, 165, 233, 0.8);
  font-size: 12px;
  transition: all 0.2s;
}
.quick-tag:hover {
  background: rgba(14, 165, 233, 0.12);
  border-color: rgba(14, 165, 233, 0.25);
  color: #0ea5e9;
}

.empty-icon-wrapper {
  width: 80px;
  height: 80px;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(14, 165, 233, 0.06);
  border: 1px solid rgba(14, 165, 233, 0.1);
}

.paper-card {
  padding: 20px 24px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 0.3s;
}
.paper-card:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(14, 165, 233, 0.15);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}

.paper-title {
  font-weight: 600;
  font-size: 15px;
  color: white;
  text-decoration: none;
  line-height: 1.5;
  display: inline-block;
  transition: color 0.2s;
}
.paper-title:hover {
  color: #0ea5e9;
}

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
  text-decoration: none;
  transition: all 0.2s;
}
.action-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}
.action-btn-primary {
  background: rgba(14, 165, 233, 0.08);
  border-color: rgba(14, 165, 233, 0.15);
  color: rgba(14, 165, 233, 0.9);
}
.action-btn-primary:hover {
  background: rgba(14, 165, 233, 0.15);
  color: #0ea5e9;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(99, 102, 241, 0.2); border-radius: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(99, 102, 241, 0.4); }
</style>
