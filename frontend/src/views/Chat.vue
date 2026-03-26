<template>
  <div class="h-[calc(100vh-80px)] flex flex-col">
    <!-- 顶部工具栏 -->
    <div class="h-14 toolbar-glass px-6 flex items-center justify-between z-20">
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <MessageCircle :size="20" class="text-primary-400" />
          <h1 class="text-lg font-semibold text-white">智能问答</h1>
        </div>
        <div v-if="store.documentInfo" class="flex items-center gap-2 text-gray-400 text-sm border-l border-white/10 pl-4">
          <FileText :size="14" />
          <span class="max-w-[200px] truncate">{{ store.documentInfo.filename }}</span>
        </div>
      </div>
      <div v-if="messages.length > 0" class="flex items-center gap-2">
        <button @click="clearChat" class="text-xs px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white border border-white/5 transition-all flex items-center gap-1.5">
          <Trash2 :size="12" />
          清空对话
        </button>
      </div>
    </div>

    <!-- 主体内容区 -->
    <div class="flex-1 flex overflow-hidden relative">
      
      <!-- 未加载文档时的提示 -->
      <div v-if="!store.pdfUrl" class="absolute inset-0 z-50 flex items-center justify-center bg-gray-900/90 backdrop-blur-sm">
        <div class="text-center max-w-md">
          <div class="empty-icon-wrapper mx-auto mb-6">
            <FileSearch :size="36" class="text-primary-400/60" />
          </div>
          <h3 class="text-xl font-bold text-white mb-2">尚未加载文档</h3>
          <p class="text-gray-400 mb-8 text-sm leading-relaxed">请先在分析页面上传文档，或从历史记录中打开之前分析过的论文。</p>
          <div class="flex gap-3 justify-center">
            <router-link to="/analyze" class="btn-glow px-6 py-2.5 text-sm flex items-center gap-2">
              <Upload :size="16" />
              去上传
            </router-link>
            <router-link to="/history" class="btn-secondary px-6 py-2.5 text-sm flex items-center gap-2">
              <Clock :size="16" />
              查历史
            </router-link>
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
      <div class="w-1/2 flex flex-col bg-gray-900/80 backdrop-blur-xl">
        <!-- 消息区域 -->
        <div class="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-4" ref="chatContainer">
          
          <!-- 欢迎状态 -->
          <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full py-8">
            <div class="welcome-icon mb-6">
              <Bot :size="28" class="text-primary-400" />
            </div>
            <p class="text-gray-400 text-sm mb-2">👋 你好！我是你的论文助手</p>
            <p v-if="suggestedQuestions.length === 0" class="text-gray-500 text-xs">你可以问我任何关于这篇论文的问题</p>
            
            <!-- 建议问题 -->
            <div v-if="suggestedQuestions.length > 0" class="grid grid-cols-1 gap-2 max-w-sm w-full mt-6">
              <button 
                v-for="(q, i) in suggestedQuestions" 
                :key="i"
                @click="useQuestion(q)"
                class="suggestion-chip group"
              >
                <Lightbulb :size="14" class="text-primary-500 flex-shrink-0 group-hover:scale-110 transition-transform" />
                <span class="text-left">{{ q }}</span>
              </button>
            </div>
          </div>
          
          <!-- 消息列表 -->
          <div v-for="(msg, index) in messages" :key="index">
            <div class="flex gap-3 animate-fade-in" :class="msg.role === 'user' ? 'flex-row-reverse' : ''">
              <!-- 头像 -->
              <div class="avatar" :class="msg.role === 'user' ? 'avatar-user' : 'avatar-ai'">
                <User :size="14" v-if="msg.role === 'user'" />
                <Bot :size="14" v-else />
              </div>
              <!-- 消息内容 -->
              <div class="message-bubble" :class="msg.role === 'user' ? 'message-user' : 'message-ai'">
                <div v-if="msg.content" class="markdown-content text-sm" v-html="renderMarkdown(msg.content)"></div>
                <div v-else class="flex gap-1.5 h-5 items-center px-2">
                  <span class="typing-dot"></span>
                  <span class="typing-dot" style="animation-delay: 0.15s"></span>
                  <span class="typing-dot" style="animation-delay: 0.3s"></span>
                </div>
              </div>
            </div>
            <!-- 引用来源 -->
            <div v-if="msg.sources && msg.sources.length" class="ml-11 mt-2 mb-4">
              <button @click="msg.showSources = !msg.showSources" class="text-xs text-primary-400/70 hover:text-primary-400 flex items-center gap-1 mb-2 transition-colors">
                <BookMarked :size="12" />
                {{ msg.showSources ? '收起' : '查看' }}引用来源 ({{ msg.sources.length }})
              </button>
              <div v-if="msg.showSources" class="space-y-2">
                <div v-for="(src, si) in msg.sources" :key="si" class="source-card">
                  <div class="flex items-center gap-2 mb-1">
                    <span class="source-badge">📄 第 {{ src.page }} 页</span>
                    <span v-if="src.section" class="text-[10px] text-gray-500">{{ src.section }}</span>
                  </div>
                  <p class="text-xs text-gray-400 leading-relaxed">{{ src.text }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 输入区域 -->
        <div class="p-4 border-t border-white/5">
          <div class="input-wrapper">
            <input 
              v-model="inputMessage" 
              @keyup.enter="sendMessage"
              type="text" 
              placeholder="输入你的问题..." 
              class="chat-input"
              :disabled="isChatting || !store.documentInfo"
            >
            <button 
              @click="isChatting ? cancelChat() : sendMessage()"
              :disabled="!isChatting && !inputMessage.trim()"
              class="send-btn"
              :class="{ 'send-btn-cancel': isChatting }"
            >
              <Square :size="18" v-if="isChatting" />
              <Send :size="18" v-else />
            </button>
          </div>
          <p class="text-[11px] text-gray-600 mt-2 text-center">基于 Plan-and-Solve 策略 · 支持联网搜索</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { renderMarkdown } from '../utils/markdown'
import VuePdfEmbed from 'vue-pdf-embed'
import api from '../api'
import { store } from '../store'
import { 
  MessageCircle, FileText, FileSearch, Upload, Clock, Bot, User, 
  Send, Loader2, Lightbulb, Trash2, BookMarked, Square 
} from 'lucide-vue-next'

const inputMessage = ref('')
const isChatting = ref(false)
const activeStream = ref(null) // 当前活跃的流（用于取消）
const messages = ref([])
const chatContainer = ref(null)
const suggestedQuestions = ref([])



const useQuestion = (q) => {
  inputMessage.value = q
  sendMessage()
}

const clearChat = () => {
  messages.value = []
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isChatting.value) return
  
  const content = inputMessage.value
  inputMessage.value = ''
  isChatting.value = true
  
  messages.value.push({ role: 'user', content })
  messages.value.push({ role: 'assistant', content: '', sources: null, showSources: false }) 
  
  nextTick(() => scrollToBottom())
  
  try {
    let responseText = ''
    const lastMsg = messages.value[messages.value.length - 1]
    const stream = api.chatStream(content)
    activeStream.value = stream  // 保存引用以便取消
    for await (const chunk of stream) {
      responseText += chunk
      const srcIdx = responseText.indexOf('\n__SOURCES__')
      if (srcIdx !== -1) {
        lastMsg.content = responseText.substring(0, srcIdx)
        try {
          const srcJson = responseText.substring(srcIdx + 12)
          lastMsg.sources = JSON.parse(srcJson)
        } catch(e) {}
      } else {
        lastMsg.content = responseText
      }
      scrollToBottom()
    }
    const finalIdx = responseText.indexOf('\n__SOURCES__')
    if (finalIdx !== -1) {
      lastMsg.content = responseText.substring(0, finalIdx)
      try {
        lastMsg.sources = JSON.parse(responseText.substring(finalIdx + 12))
      } catch(e) {}
    }
  } catch (e) {
    messages.value[messages.value.length - 1].content = '回答出错: ' + e.message
  } finally {
    isChatting.value = false
    activeStream.value = null
  }
}

const cancelChat = () => {
  if (activeStream.value?.cancel) {
    activeStream.value.cancel()
  }
  isChatting.value = false
  activeStream.value = null
  // 追加提示
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg?.role === 'assistant' && lastMsg.content) {
    lastMsg.content += '\n\n*— 已停止生成 —*'
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
            const suggestionsRes = await api.getSuggestions()
            if (suggestionsRes.questions) {
                suggestedQuestions.value = suggestionsRes.questions
            }
            const res = await api.getHistoryChat(store.documentInfo.document_id)
            if (res.chat_history) {
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
    
    // 处理从标注页传来的问题
    if (store.pendingQuestion) {
        inputMessage.value = store.pendingQuestion
        store.pendingQuestion = ''
        await nextTick()
        sendMessage()
    }
})
</script>

<style scoped>
.toolbar-glass {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

/* Empty state icon */
.empty-icon-wrapper {
  width: 80px;
  height: 80px;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(14, 165, 233, 0.12);
}

/* Welcome */
.welcome-icon {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(99, 102, 241, 0.1));
  border: 1px solid rgba(14, 165, 233, 0.1);
}

/* Suggestion chips */
.suggestion-chip {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: rgba(203, 213, 225, 0.9);
  font-size: 13px;
  line-height: 1.5;
  transition: all 0.3s;
  text-align: left;
}

.suggestion-chip:hover {
  background: rgba(14, 165, 233, 0.08);
  border-color: rgba(14, 165, 233, 0.2);
  color: white;
  transform: translateX(4px);
}

/* Avatar */
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-user {
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: white;
}

.avatar-ai {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #94a3b8;
}

/* Message bubbles */
.message-bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 16px;
}

.message-user {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.15), rgba(99, 102, 241, 0.12));
  border: 1px solid rgba(14, 165, 233, 0.15);
  border-bottom-right-radius: 4px;
  color: rgba(226, 232, 240, 0.95);
}

.message-ai {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-bottom-left-radius: 4px;
  color: rgba(203, 213, 225, 0.9);
}

/* Typing indicator */
.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(14, 165, 233, 0.6);
  animation: typing-bounce 1.2s ease-in-out infinite;
}

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

/* Input area */
.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.chat-input {
  width: 100%;
  padding: 14px 52px 14px 20px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: white;
  font-size: 14px;
  outline: none;
  transition: all 0.3s;
}

.chat-input:focus {
  border-color: rgba(14, 165, 233, 0.4);
  background: rgba(255, 255, 255, 0.06);
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1);
}

.chat-input::placeholder {
  color: rgba(100, 116, 139, 0.6);
}

.send-btn {
  position: absolute;
  right: 6px;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  transition: all 0.3s;
  cursor: pointer;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 15px rgba(14, 165, 233, 0.4);
}

.send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.send-btn-cancel {
  background: linear-gradient(135deg, #ef4444, #f97316) !important;
  opacity: 1 !important;
  cursor: pointer !important;
  animation: cancel-pulse 1.5s ease-in-out infinite;
}
.send-btn-cancel:hover {
  box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4) !important;
}
@keyframes cancel-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.3); }
  50% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
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

/* Scrollbar */
.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(99, 102, 241, 0.2); border-radius: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(99, 102, 241, 0.4); }

/* Source cards */
.source-card {
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(14, 165, 233, 0.04);
  border: 1px solid rgba(14, 165, 233, 0.1);
  max-width: 80%;
}
.source-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(14, 165, 233, 0.1);
  color: rgba(14, 165, 233, 0.8);
  white-space: nowrap;
}
</style>