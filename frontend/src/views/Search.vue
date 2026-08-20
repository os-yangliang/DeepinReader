<template>
  <div class="search-page">
    <PageToolbar :icon="Search" title="相关论文" subtitle="Semantic Scholar 检索" :accent="'var(--accent-1)'" />

    <div class="search-body">
      <div class="search-inner">
        <!-- 搜索栏 -->
        <div class="search-bar card">
          <div class="search-row">
            <div class="search-input-wrap">
              <Search :size="18" class="search-icon" />
              <input
                v-model="searchQuery"
                @keydown.enter="doSearch"
                type="text"
                class="search-input"
                :placeholder="defaultQuery ? `默认搜索: ${defaultQuery.slice(0, 40)}...` : '输入搜索关键词...'"
              />
            </div>
            <button @click="doSearch" class="btn-primary" :disabled="isSearching">
              <Loader2 v-if="isSearching" :size="16" class="animate-spin" />
              <Search v-else :size="16" />
              搜索
            </button>
          </div>

          <div v-if="store.documentInfo" class="quick-row">
            <button @click="searchByTitle" class="quick-tag">
              <FileText :size="12" /> 按论文标题搜索
            </button>
            <button v-for="(kw, i) in suggestedKeywords" :key="i" @click="searchQuery = kw; doSearch()" class="quick-tag">
              {{ kw }}
            </button>
          </div>
        </div>

        <!-- 统计 -->
        <div v-if="searchResult" class="result-stat">
          搜索 <span class="hl">{{ searchResult.query }}</span> 找到
          <span class="hl">{{ searchResult.total.toLocaleString() }}</span> 篇论文
        </div>

        <!-- 空状态 -->
        <div v-if="!searchResult && !isSearching" class="empty-wrap">
          <EmptyState :icon="BookOpen" title="发现相关研究" :description="store.documentInfo ? '搜索 Semantic Scholar 的 2 亿+ 学术论文数据库。' : '输入关键词开始搜索。'">
            <button v-if="store.documentInfo" class="btn-primary" @click="searchByTitle">
              <Sparkles :size="16" /> 自动搜索相关论文
            </button>
          </EmptyState>
        </div>

        <!-- 搜索中 -->
        <div v-if="isSearching" class="loading-wrap">
          <Loader2 :size="26" class="animate-spin text-accent" />
          <p>正在搜索 Semantic Scholar...</p>
        </div>

        <!-- 结果 -->
        <div v-if="searchResult && !isSearching" class="result-list">
          <div v-for="(paper, index) in searchResult.papers" :key="index" class="paper-card card card-hover">
            <div class="paper-main">
              <a :href="paper.url" target="_blank" rel="noopener" class="paper-title">{{ paper.title }}</a>
              <div class="paper-meta">
                <span v-if="paper.year" class="meta-item"><Calendar :size="12" /> {{ paper.year }}</span>
                <span v-if="paper.authors.length" class="meta-item"><Users :size="12" /> {{ paper.authors.join(', ') }}</span>
                <span v-if="paper.citationCount" class="meta-item cite"><Quote :size="12" /> {{ paper.citationCount.toLocaleString() }}</span>
              </div>
              <p v-if="paper.abstract" class="paper-abstract">{{ paper.abstract }}</p>
            </div>
            <div class="paper-actions">
              <a :href="paper.url" target="_blank" rel="noopener" class="btn-secondary btn-sm"><ExternalLink :size="13" /> 详情</a>
              <a v-if="paper.pdfUrl" :href="paper.pdfUrl" target="_blank" rel="noopener" class="btn-primary btn-sm"><FileDown :size="13" /> PDF</a>
              <a v-if="paper.doi" :href="`https://doi.org/${paper.doi}`" target="_blank" rel="noopener" class="btn-ghost"><Link :size="13" /> DOI</a>
            </div>
          </div>
          <div v-if="searchResult.papers.length === 0" class="no-result">未找到相关论文，请尝试其他关键词</div>
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
  Calendar, Users, Quote, ExternalLink, FileDown, Link,
} from 'lucide-vue-next'

const searchQuery = ref('')
const isSearching = ref(false)
const searchResult = ref(null)

const defaultQuery = computed(() => {
  if (!store.documentInfo) return ''
  return store.documentInfo.title || store.documentInfo.filename || ''
})

const suggestedKeywords = computed(() => {
  const title = defaultQuery.value
  if (!title) return []
  const words = title.split(/[\s,.:;]+/).filter(w => w.length > 3)
  if (words.length <= 3) return []
  const mid = Math.ceil(words.length / 2)
  return [
    words.slice(0, mid).join(' '),
    words.slice(mid).join(' '),
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
  if (store.documentInfo?.title) searchByTitle()
})
</script>

<style scoped>
.search-page { height: 100vh; display: flex; flex-direction: column; }
.search-body { flex: 1; overflow-y: auto; }
.search-inner {
  max-width: 820px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
}

.search-bar { padding: 1.25rem; margin-bottom: 1.5rem; }
.search-row { display: flex; gap: 0.6rem; }
.search-input-wrap { position: relative; flex: 1; }
.search-icon {
  position: absolute; left: 1rem; top: 50%; transform: translateY(-50%);
  color: var(--text-muted);
}
.search-input {
  width: 100%; padding: 0.75rem 1rem 0.75rem 2.6rem;
  border-radius: 0.75rem; font-size: 0.88rem;
  background: var(--bg-input); border: 1px solid var(--border-default);
  color: var(--text-primary); outline: none; transition: all 0.2s;
}
.search-input:focus { border-color: var(--border-accent); box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.1); }
.search-input::placeholder { color: var(--text-muted); }

.quick-row {
  display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.8rem;
}
.quick-tag {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.35rem 0.8rem; border-radius: 0.6rem; font-size: 0.75rem;
  color: var(--accent-1); background: rgba(56, 189, 248, 0.07);
  border: 1px solid rgba(56, 189, 248, 0.16); cursor: pointer; transition: all 0.15s;
}
.quick-tag:hover { background: rgba(56, 189, 248, 0.13); }

.result-stat {
  font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 1rem;
}
.hl { color: var(--accent-1); font-weight: 500; }

.empty-wrap { padding: 4rem 0; }
.loading-wrap {
  display: flex; flex-direction: column; align-items: center; gap: 0.8rem;
  padding: 4rem 0; color: var(--text-muted); font-size: 0.82rem;
}
.text-accent { color: var(--accent-1); }

.result-list { display: flex; flex-direction: column; gap: 0.9rem; }
.paper-card { padding: 1.25rem 1.5rem; }
.paper-main { margin-bottom: 1rem; }
.paper-title {
  font-size: 1rem; font-weight: 600; color: var(--text-heading);
  text-decoration: none; line-height: 1.4; transition: color 0.15s;
}
.paper-title:hover { color: var(--accent-1); }
.paper-meta {
  display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
  margin-top: 0.5rem; font-size: 0.74rem; color: var(--text-muted);
}
.meta-item { display: inline-flex; align-items: center; gap: 0.3rem; }
.meta-item.cite { color: var(--warning); }
.paper-abstract {
  margin-top: 0.7rem; font-size: 0.8rem; line-height: 1.65; color: var(--text-secondary);
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.paper-actions {
  display: flex; gap: 0.5rem; padding-top: 0.9rem;
  border-top: 1px solid var(--border-default);
}
.btn-sm { padding: 0.4rem 0.85rem; font-size: 0.78rem; }
.no-result {
  text-align: center; padding: 3rem 0; font-size: 0.82rem; color: var(--text-muted);
}
.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>