<template>
  <div class="h-[calc(100vh-80px)] flex flex-col">
    <!-- 顶部工具栏 -->
    <div class="h-14 glass-card border-b border-white/5 px-6 flex items-center justify-between z-20">
      <div class="flex items-center gap-4">
        <h1 class="text-xl font-bold gradient-text">💬 智能问答</h1>
        <div v-if="store.documentInfo" class="text-gray-400 text-sm border-l border-white/10 pl-4">
          {{ store.documentInfo.filename }}
        </div>
      </div>
    </div>

    <!-- 主体内容区 -->
    <div class="flex-1 flex overflow-hidden relative">
      
      <!-- 未加载文档时的提示 -->
      <div v-if="!store.pdfUrl" class="absolute inset-0 z-50 flex items-center justify-center bg-gray-900/90 backdrop-blur-sm">
        <div class="text-center">
          <div class="text-6xl mb-4">📄</div>
          <h3 class="text-xl font-bold text-white mb-2">未加载文档</h3>
          <p class="text-gray-400 mb-6">请先在分析页面上传文档，或在历史记录中打开文档。</p>
          <div class="flex gap-4 justify-center">
            <router-link to="/analyze" class="btn-primary px-6 py-2">去上传</router-link>
            <router-link to="/history" class="btn-secondary px-6 py-2">查历史</router-link>
          </div>
        </div>
      </div>

      <!-- 左侧：PDF 阅读器 -->
      <div class="w-1/2 bg-gray-900/50 relative flex flex-col border-r border-white/5">
        <div v-if="store.pdfUrl" class="flex-1 overflow-y-auto custom-scrollbar p-8 flex justify-center">
          <div class="w-full max-w-4xl shadow-2xl">
            <vue-pdf-embed :source="store.pdfUrl" class="rounded-lg overflow-hidden" />
          </div>
        </div>
      </div>

      <!-- 右侧：问答面板 -->
      <div class="w-1/2 glass-card border-l border-white/5 flex flex-col bg-gray-900/80 backdrop-blur-xl">
        <div class="flex-1 overflow-y-auto space-y-4 mb-4 pr-2 p-6" ref="chatContainer">
          <div v-if="messages.length === 0" class="text-center py-8 text-gray-500 text-sm">
            <p class="mb-4">👋 你好！我是你的论文助手。</p>
            <p v-if="suggestedQuestions.length === 0">你可以问我任何关于这篇论文的问题。</p>
            
            <!-- 建议问题 -->
            <div v-if="suggestedQuestions.length > 0" class="grid grid-cols-1 gap-2 max-w-md mx-auto mt-6">
              <button 
                v-for="(q, i) in suggestedQuestions" 
                :key="i"
                @click="useQuestion(q)"
                class="text-left px-4 py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/5 hover:border-primary-500/30 transition-all text-gray-300 text-sm flex items-center gap-2 group"
              >
                <span class="text-primary-500 group-hover:scale-110 transition-transform">💡</span>
                {{ q }}
              </button>
            </div>
          </div>
          
          <div v-for="(msg, index) in messages" :key="index" 
               class="flex gap-3" :class="msg.role === 'user' ? 'flex-row-reverse' : ''">
            <div class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-sm"
                 :class="msg.role === 'user' ? 'bg-primary-500 text-white' : 'bg-gray-700 text-gray-300'">
              {{ msg.role === 'user' ? '我' : 'AI' }}
            </div>
            <div class="max-w-[85%] p-3 rounded-2xl text-sm"
                 :class="msg.role === 'user' ? 'bg-primary-500/20 text-white rounded-tr-sm' : 'bg-white/5 text-gray-300 rounded-tl-sm'">
              <div v-if="msg.content" v-html="renderMarkdown(msg.content)"></div>
              <div v-else class="flex gap-1 h-5 items-center">
                <span class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"></span>
                <span class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce delay-100"></span>
                <span class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce delay-200"></span>
              </div>
            </div>
          </div>
        </div>
        
        <div class="relative p-6 pt-0">
          <input 
            v-model="inputMessage" 
            @keyup.enter="sendMessage"
            type="text" 
            placeholder="输入问题..." 
            class="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-primary-500/50 transition-colors"
            :disabled="isChatting || !store.documentInfo"
          >
          <button 
            @click="sendMessage"
            :disabled="isChatting || !inputMessage.trim()"
            class="absolute right-8 top-1/2 -translate-y-1/2 -mt-3 p-1.5 rounded-lg text-primary-400 hover:text-white hover:bg-primary-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { marked } from 'marked'
import VuePdfEmbed from 'vue-pdf-embed'
import api from '../api'
import { store } from '../store'

const inputMessage = ref('')
const isChatting = ref(false)
const messages = ref([])
const chatContainer = ref(null)
const suggestedQuestions = ref([])

const renderMarkdown = (text) => marked(text || '')

const useQuestion = (q) => {
  inputMessage.value = q
  sendMessage()
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isChatting.value) return
  
  const content = inputMessage.value
  inputMessage.value = ''
  isChatting.value = true
  
  messages.value.push({ role: 'user', content })
  messages.value.push({ role: 'assistant', content: '' }) 
  
  nextTick(() => scrollToBottom())
  
  try {
    let responseText = ''
    for await (const chunk of api.chatStream(content)) {
      responseText += chunk
      messages.value[messages.value.length - 1].content = responseText
      scrollToBottom()
    }
  } catch (e) {
    messages.value[messages.value.length - 1].content = '回答出错: ' + e.message
  } finally {
    isChatting.value = false
  }
}

const scrollToBottom = () => {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

// 加载历史对话和建议问题
onMounted(async () => {
    if (store.documentInfo?.document_id) {
        try {
            // 加载建议问题
            const suggestionsRes = await api.getSuggestions()
            if (suggestionsRes.questions) {
                suggestedQuestions.value = suggestionsRes.questions
            }

            // 加载历史对话
            const res = await api.getHistoryChat(store.documentInfo.document_id)
            if (res.chat_history) {
                // 转换格式
                messages.value = res.chat_history.map(item => ({
                    role: item.role,
                    content: item.content
                }))
                nextTick(() => scrollToBottom())
            }
        } catch(e) {
            console.error("加载数据失败", e)
        }
    }
})
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
</style>