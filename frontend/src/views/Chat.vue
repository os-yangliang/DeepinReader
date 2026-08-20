<template>
  <div class="chat-page">
    <PageToolbar :icon="MessageCircle" title="智能问答" subtitle="证据驱动的论文问答" :accent="'var(--accent-1)'">
      <template #actions>
        <button v-if="messages.length > 0" class="btn-secondary" @click="clearChat">
          <Trash2 :size="14" />
          清空对话
        </button>
      </template>
    </PageToolbar>

    <div class="chat-body">
      <!-- 未加载文档 -->
      <div v-if="!store.pdfUrl" class="chat-empty-wrap">
        <EmptyState :icon="FileSearch" title="尚未加载文档" description="请先在分析页面上传文档，或从历史记录中打开之前分析过的论文。">
          <router-link to="/analyze" class="btn-primary"><Upload :size="16" /> 去上传</router-link>
          <router-link to="/history" class="btn-secondary"><Clock :size="16" /> 查历史</router-link>
        </EmptyState>
      </div>

      <template v-else>
        <!-- 左侧 PDF 阅读器 -->
        <div class="pdf-pane">
          <PdfReader v-if="store.pdfUrl" ref="pdfReaderRef" :source="store.pdfUrl" />
        </div>

        <!-- 右侧问答 -->
        <div class="qa-pane">
          <div class="qa-scroll" ref="chatContainer">
            <!-- 欢迎 -->
            <div v-if="messages.length === 0" class="qa-welcome">
              <div class="welcome-icon">
                <Bot :size="26" />
              </div>
              <p class="welcome-title">你好，我是你的论文助手</p>
              <p class="welcome-sub">基于 Claim-Evidence 图谱，给出有证据支撑的回答</p>

              <div v-if="suggestedQuestions.length" class="suggestions">
                <button
                  v-for="(q, i) in suggestedQuestions"
                  :key="i"
                  class="suggestion"
                  @click="useQuestion(q)"
                >
                  <Lightbulb :size="14" />
                  <span>{{ q }}</span>
                </button>
              </div>
            </div>

            <!-- 消息 -->
            <div v-else class="msg-list">
              <div v-for="(msg, index) in messages" :key="index" class="msg-row" :class="{ 'from-user': msg.role === 'user' }">
                <div class="avatar" :class="msg.role === 'user' ? 'avatar-user' : 'avatar-ai'">
                  <User :size="14" v-if="msg.role === 'user'" />
                  <Bot :size="14" v-else />
                </div>
                <div class="msg-col">
                  <div class="bubble" :class="msg.role === 'user' ? 'bubble-user' : 'bubble-ai'">
                    <div v-if="msg.content" class="markdown-content" v-html="renderMarkdown(msg.content)"></div>
                    <div v-else class="typing-dots">
                      <span></span><span></span><span></span>
                    </div>
                  </div>

                  <!-- 元信息 -->
                  <div v-if="msg.role === 'assistant' && msg.content" class="meta-card">
                    <div class="meta-head">
                      <span class="meta-pill">{{ formatRouteType(msg.routeType) }}</span>
                      <span class="meta-pill" :class="confidenceClass(msg.confidence)">
                        置信度 {{ formatConfidence(msg.confidence) }}
                      </span>
                    </div>

                    <div v-if="msg.warnings?.length" class="meta-group">
                      <button class="meta-toggle" @click="msg.showWarnings = !msg.showWarnings">
                        <span>风险提示</span>
                        <ChevronDown :size="13" :class="{ 'rotate-180': msg.showWarnings }" />
                      </button>
                      <div v-if="msg.showWarnings" class="meta-list">
                        <div v-for="(w, i) in msg.warnings" :key="i" class="meta-warn">{{ w }}</div>
                      </div>
                    </div>

                    <div v-if="msg.reasoningTrace?.length" class="meta-group">
                      <button class="meta-toggle" @click="msg.showReasoning = !msg.showReasoning">
                        <span>推理路径</span>
                        <ChevronDown :size="13" :class="{ 'rotate-180': msg.showReasoning }" />
                      </button>
                      <ol v-if="msg.showReasoning" class="reasoning-list">
                        <li v-for="(r, i) in msg.reasoningTrace" :key="i">{{ r }}</li>
                      </ol>
                    </div>

                    <div v-if="msg.sourceChunks?.length" class="source-list">
                      <div v-for="(c, i) in msg.sourceChunks" :key="i" class="source-item">
                        <span class="source-text">{{ c }}</span>
                        <button class="source-locate" @click="locateSource(c)" title="定位到原文">
                          <LocateFixed :size="12" /> 定位
                        </button>
                      </div>
                    </div>

                    <div v-if="msg.role === 'assistant' && msg.content && msg.warnings?.length" class="followup-row">
                      <button class="followup-btn" @click="askFollowUp(msg.warnings)">
                        <RefreshCcw :size="12" /> 换种问法追问
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 输入区 -->
          <div class="input-zone">
            <div class="input-box">
              <input
                v-model="inputMessage"
                @keyup.enter="sendMessage"
                type="text"
                placeholder="输入你的问题，回车发送..."
                class="chat-input"
                :disabled="isChatting || !store.documentInfo"
              />
              <button
                class="send-btn"
                :class="{ 'send-btn-stop': isChatting }"
                @click="isChatting ? cancelChat() : sendMessage()"
                :disabled="!isChatting && !inputMessage.trim()"
              >
                <Square :size="17" v-if="isChatting" />
                <Send :size="17" v-else />
              </button>
            </div>
            <p class="input-hint">基于 Plan-and-Solve · 证据充分性估计 · 支持取消</p>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { renderMarkdown } from '../utils/markdown'
import api from '../api'
import { store } from '../store'
import {
  MessageCircle, FileSearch, Upload, Clock, Bot, User,
  Send, Lightbulb, Trash2, Square, ChevronDown, LocateFixed, RefreshCcw,
} from 'lucide-vue-next'

const pdfReaderRef = ref(null)
const inputMessage = ref('')
const isChatting = ref(false)
const activeStream = ref(null)
const messages = ref([])
const chatContainer = ref(null)
const suggestedQuestions = ref([])

const createAssistantMessage = () => ({
  role: 'assistant',
  content: '',
  routeType: 'general',
  confidence: 0,
  warnings: [],
  evidenceSummary: [],
  reasoningTrace: [],
  reasoningPaths: [],
  claimNodes: [],
  evidenceNodes: [],
  resultNodes: [],
  sourceChunks: [],
  showWarnings: true,
  showReasoning: false,
})

const normalizeHistoryMessage = (item) => ({
  role: item.role,
  content: item.content,
  routeType: item.route_type || 'general',
  confidence: item.confidence || 0,
  warnings: item.warnings || [],
  evidenceSummary: item.evidence_summary || [],
  reasoningTrace: item.reasoning_trace || [],
  reasoningPaths: item.reasoning_paths || [],
  claimNodes: item.claim_nodes || [],
  evidenceNodes: item.evidence_nodes || [],
  resultNodes: item.result_nodes || [],
  sourceChunks: item.source_chunks || [],
  showWarnings: false,
  showReasoning: false,
})

const formatRouteType = (route) => ({
  structure: '结构问题',
  method: '方法解释',
  evidence: '证据验证',
  result: '实验结果',
  critical: '批判分析',
  general: '综合问答',
}[route] || '综合问答')

const formatConfidence = (v) => `${Math.round((v || 0) * 100)}%`
const confidenceClass = (v) => {
  const s = v || 0
  if (s >= 0.75) return 'conf-high'
  if (s >= 0.45) return 'conf-mid'
  return 'conf-low'
}

const useQuestion = (q) => {
  inputMessage.value = q
  sendMessage()
}

const clearChat = () => { messages.value = [] }

// 引用定位：取 source chunk 中的关键短语，在 PDF 内搜索并跳转
const locateSource = (chunk) => {
  if (!chunk) return
  const cleaned = String(chunk).replace(/\s+/g, ' ').trim()
  const keyword = cleaned.length > 60 ? cleaned.slice(0, 60) : cleaned
  if (pdfReaderRef.value && pdfReaderRef.value.searchInDoc) {
    pdfReaderRef.value.searchInDoc(keyword.slice(0, 40))
  }
}

// 追问：基于风险提示，建议一个更聚焦的追问问题
const askFollowUp = (warnings) => {
  const first = warnings?.[0] || '该回答的证据可能不足'
  inputMessage.value = `关于"${first.slice(0, 60)}"，能否给出更具体的实验证据？`
  sendMessage()
}

const scrollToBottom = () => {
  if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isChatting.value) return
  const content = inputMessage.value
  inputMessage.value = ''
  isChatting.value = true

  messages.value.push({ role: 'user', content })
  messages.value.push(createAssistantMessage())
  nextTick(() => scrollToBottom())

  try {
    const lastMsg = messages.value[messages.value.length - 1]
    const stream = api.chatStream(content)
    activeStream.value = stream
    for await (const event of stream) {
      if (event.chunk) lastMsg.content += event.chunk
      if (event.__done || event.done) {
        lastMsg.routeType = event.route_type || 'general'
        lastMsg.confidence = event.confidence || 0
        lastMsg.warnings = event.warnings || []
        lastMsg.reasoningTrace = event.reasoning_trace || []
        lastMsg.sourceChunks = event.source_chunks || []
        lastMsg.showWarnings = !!lastMsg.warnings.length
      }
      scrollToBottom()
    }
  } catch (e) {
    messages.value[messages.value.length - 1].content = '回答出错: ' + e.message
  } finally {
    isChatting.value = false
    activeStream.value = null
  }
}

const cancelChat = () => {
  if (activeStream.value?.cancel) activeStream.value.cancel()
  isChatting.value = false
  activeStream.value = null
  const last = messages.value[messages.value.length - 1]
  if (last?.role === 'assistant' && last.content) {
    last.content += '\n\n*— 已停止生成 —*'
  }
}

onMounted(async () => {
  if (store.documentInfo?.document_id) {
    try {
      const s = await api.getSuggestions()
      if (s.questions) suggestedQuestions.value = s.questions
      const r = await api.getCurrentHistoryChat()
      if (r.chat_history) {
        messages.value = r.chat_history.map(normalizeHistoryMessage)
        nextTick(() => scrollToBottom())
      }
    } catch (e) {
      console.error('加载数据失败', e)
    }
  }
  if (store.pendingQuestion) {
    inputMessage.value = store.pendingQuestion
    store.pendingQuestion = ''
    await nextTick()
    sendMessage()
  }
})
</script>

<style scoped>
.chat-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.chat-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}
.chat-empty-wrap {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-inset);
}

/* PDF 面板 */
.pdf-pane {
  width: 46%;
  flex-shrink: 0;
  border-right: 1px solid var(--border-default);
  background: var(--bg-inset);
}

/* 问答面板 */
.qa-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
}
.qa-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

/* 欢迎 */
.qa-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}
.welcome-icon {
  width: 56px;
  height: 56px;
  border-radius: 1.1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-1);
  background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.18);
  margin-bottom: 1rem;
}
.welcome-title { font-size: 1rem; font-weight: 600; color: var(--text-heading); margin-bottom: 0.3rem; }
.welcome-sub { font-size: 0.8rem; color: var(--text-muted); }
.suggestions {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  width: 100%;
  max-width: 440px;
  margin-top: 1.5rem;
}
.suggestion {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  text-align: left;
  padding: 0.75rem 1rem;
  border-radius: 0.75rem;
  font-size: 0.82rem;
  color: var(--text-secondary);
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  cursor: pointer;
  transition: all 0.2s;
}
.suggestion:hover {
  color: var(--text-heading);
  border-color: var(--border-accent);
  background: rgba(56, 189, 248, 0.06);
}
.suggestion svg { color: var(--accent-1); flex-shrink: 0; }

/* 消息 */
.msg-list { display: flex; flex-direction: column; gap: 1.25rem; }
.msg-row {
  display: flex;
  gap: 0.7rem;
  max-width: 88%;
  animation: fadeIn 0.3s ease-out;
}
.msg-row.from-user {
  flex-direction: row-reverse;
  margin-left: auto;
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 0.6rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.avatar-user {
  background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
  color: #fff;
}
.avatar-ai {
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  color: var(--text-muted);
}

.msg-col {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 0;
}
.bubble {
  padding: 0.85rem 1.1rem;
  border-radius: 0.9rem;
  font-size: 0.85rem;
}
.bubble-user {
  background: rgba(56, 189, 248, 0.12);
  border: 1px solid rgba(56, 189, 248, 0.2);
  color: var(--text-primary);
  border-bottom-right-radius: 0.25rem;
}
.bubble-ai {
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  color: var(--text-primary);
  border-bottom-left-radius: 0.25rem;
}

.typing-dots { display: flex; gap: 4px; padding: 0.2rem 0; }
.typing-dots span {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent-1);
  animation: typing 1.2s infinite ease-in-out;
}
.typing-dots span:nth-child(2) { animation-delay: 0.15s; }
.typing-dots span:nth-child(3) { animation-delay: 0.3s; }
@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-5px); opacity: 1; }
}

/* Meta card */
.meta-card {
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  border-radius: 0.75rem;
  padding: 0.7rem 0.85rem;
  font-size: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.meta-head { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.meta-pill {
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.68rem;
  color: var(--accent-1);
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.18);
}
.conf-high { color: var(--positive); background: rgba(52, 211, 153, 0.08); border-color: rgba(52, 211, 153, 0.2); }
.conf-mid { color: var(--warning); background: rgba(251, 191, 36, 0.08); border-color: rgba(251, 191, 36, 0.2); }
.conf-low { color: var(--danger); background: rgba(248, 113, 113, 0.08); border-color: rgba(248, 113, 113, 0.2); }

.meta-toggle {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.72rem;
  color: var(--text-secondary);
  cursor: pointer;
  background: none;
  border: none;
  padding: 0;
}
.meta-toggle:hover { color: var(--text-heading); }
.meta-list { display: flex; flex-direction: column; gap: 0.3rem; }
.meta-warn {
  padding: 0.4rem 0.6rem;
  border-radius: 0.5rem;
  font-size: 0.72rem;
  color: var(--warning);
  background: rgba(251, 191, 36, 0.06);
}
.reasoning-list {
  margin: 0;
  padding-left: 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.72rem;
  color: var(--text-secondary);
}
.source-list { display: flex; flex-direction: column; gap: 0.35rem; }
.source-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.45rem 0.6rem;
  border-radius: 0.5rem;
  font-size: 0.72rem;
  color: var(--text-secondary);
  background: var(--bg-inset);
  border-left: 2px solid var(--accent-1);
}
.source-text { flex: 1; line-height: 1.5; }
.source-locate {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  border-radius: 0.4rem;
  font-size: 0.68rem;
  color: var(--accent-1);
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.18);
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}
.source-locate:hover { background: rgba(56, 189, 248, 0.16); }

.followup-row { display: flex; }
.followup-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.6rem;
  border-radius: 0.4rem;
  font-size: 0.7rem;
  color: var(--accent-1);
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.18);
  cursor: pointer;
  transition: all 0.15s;
}
.followup-btn:hover { background: rgba(56, 189, 248, 0.16); }

/* 输入区 */
.input-zone {
  padding: 0.9rem 1.25rem 0.8rem;
  border-top: 1px solid var(--border-default);
  background: var(--bg-glass);
}
.input-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--bg-input);
  border: 1px solid var(--border-default);
  border-radius: 0.9rem;
  padding: 0.35rem;
  transition: border-color 0.2s;
}
.input-box:focus-within { border-color: var(--border-accent); }
.chat-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 0.88rem;
  padding: 0.55rem 0.7rem;
}
.chat-input::placeholder { color: var(--text-muted); }
.send-btn {
  width: 38px;
  height: 38px;
  border-radius: 0.7rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.send-btn:hover:not(:disabled) { transform: scale(1.05); box-shadow: var(--shadow-glow); }
.send-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.send-btn-stop { background: linear-gradient(135deg, #ef4444, #f97316); }
.input-hint {
  text-align: center;
  font-size: 0.68rem;
  color: var(--text-muted);
  margin-top: 0.45rem;
}
</style>