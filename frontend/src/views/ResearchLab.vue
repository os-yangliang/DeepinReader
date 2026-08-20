<template>
  <div class="lab-page">
    <PageToolbar :icon="FlaskConical" title="虚拟课题组" subtitle="AI 多角色学术研讨" :accent="'var(--accent-3)'" />

    <div class="lab-body">
      <div class="lab-inner">
        <!-- 未加载文档 -->
        <div v-if="!store.documentInfo" class="lab-empty">
          <EmptyState :icon="Upload" title="请先上传并分析论文" description="课题组需要论文的分析结果作为讨论基础">
            <router-link to="/" class="btn-primary"><Upload :size="15" /> 去上传论文</router-link>
          </EmptyState>
        </div>

        <template v-else>
          <!-- 控制栏 -->
          <div v-if="!isDiscussing && !isFinished" class="card control-card">
            <div class="control-head">
              <h3>开始课题组讨论</h3>
              <p>论文：{{ store.documentInfo?.title || store.documentInfo?.filename || '未知' }}</p>
            </div>

            <div class="mode-grid">
              <button @click="mode = 'quick'" class="mode-card" :class="{ active: mode === 'quick' }">
                <div class="mode-title"><Zap :size="14" class="text-amber" /> 快速模式</div>
                <p>3 个阶段，约 3 分钟</p>
              </button>
              <button @click="mode = 'deep'" class="mode-card" :class="{ active: mode === 'deep' }">
                <div class="mode-title"><Brain :size="14" class="text-violet" /> 深度模式</div>
                <p>5 个阶段，约 6 分钟</p>
              </button>
            </div>

            <label class="field-label">关注方向（可选）</label>
            <input v-model="userFocus" placeholder="例如：将该方法应用到医学图像分析" class="input" />

            <button @click="startDiscussion" class="lab-start-btn">
              <FlaskConical :size="15" /> 开始课题组讨论
            </button>
          </div>

          <!-- 进度条 -->
          <div v-if="isDiscussing || isFinished" class="phase-row">
            <div v-for="(phase, idx) in phaseList" :key="phase.id"
              class="phase-chip"
              :class="phaseChipClass(phase.id)">
              <Check v-if="completedPhases.has(phase.id)" :size="12" />
              <Loader v-else-if="currentPhase === phase.id" :size="12" class="animate-spin" />
              <span v-else class="phase-num">{{ idx + 1 }}</span>
              <span>{{ phase.label }}</span>
            </div>
          </div>

          <!-- 讨论记录 -->
          <div v-if="messages.length > 0" class="card discussion-card">
            <div class="discussion-head">
              <MessageCircle :size="14" />
              <span>讨论记录 ({{ messages.filter(m => m.type === 'message').length }} 条发言)</span>
              <span v-if="isDiscussing" class="streaming-dot"></span>
            </div>
            <div class="discussion-body" ref="discussionRef">
              <template v-for="(msg, idx) in messages" :key="idx">
                <div v-if="msg.type === 'phase'" class="phase-divider">
                  <span>{{ msg.label }}</span>
                </div>
                <div v-else-if="msg.type === 'message'" class="agent-msg">
                  <div class="agent-avatar" :class="agentBgClass(msg.agentId)">{{ msg.agentEmoji }}</div>
                  <div class="agent-body">
                    <div class="agent-name-row">
                      <span class="agent-name">{{ msg.agentName }}</span>
                      <span v-if="msg.agentRole" class="agent-role">{{ msg.agentRole }}</span>
                    </div>
                    <div class="markdown-content agent-content" v-html="renderMarkdown(msg.content)"></div>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <!-- 研究提案 -->
          <div v-if="proposal" class="card proposal-card">
            <div class="proposal-head">
              <div class="proposal-title"><FileText :size="14" class="text-violet" /> 研究提案</div>
              <button @click="copyProposal" class="btn-ghost text-accent">
                <Copy :size="12" /> {{ copied ? '已复制 ✓' : '复制' }}
              </button>
            </div>
            <div class="markdown-content proposal-content" v-html="renderMarkdown(proposal)"></div>
          </div>

          <!-- 操作栏 -->
          <div v-if="isDiscussing || isFinished" class="lab-actions">
            <button v-if="isDiscussing" @click="stopDiscussion" class="btn-danger">
              <Square :size="12" /> 停止讨论
            </button>
            <button v-if="isFinished" @click="resetDiscussion" class="btn-secondary">
              <RefreshCw :size="13" /> 重新讨论
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick } from 'vue'
import { FlaskConical, Upload, Zap, Brain, Square, RefreshCw, Copy, FileText, Check, Loader, MessageCircle } from 'lucide-vue-next'
import { store } from '../store'
import api from '../api'
import { renderMarkdown } from '../utils/markdown'

const mode = ref('quick')
const userFocus = ref('')
const isDiscussing = ref(false)
const isFinished = ref(false)
const messages = reactive([])
const proposal = ref('')
const copied = ref(false)
const currentPhase = ref('')
const completedPhases = reactive(new Set())
const discussionRef = ref(null)

let stopped = false
let currentMsgIndex = -1

const phaseList = computed(() => {
  const all = [
    { id: 'paper_review', label: '📄 论文解读' },
    { id: 'brainstorm', label: '💡 头脑风暴' },
    { id: 'advisor_review', label: '🧑‍🏫 导师点评' },
    { id: 'deep_dive', label: '🔬 深入讨论' },
    { id: 'final_plan', label: '📋 终审分工' },
  ]
  return mode.value === 'quick' ? all.slice(0, 3) : all
})

function agentBgClass(agentId) {
  return { advisor: 'bg-blue', phd_senior: 'bg-green', phd_junior: 'bg-amber', master: 'bg-violet' }[agentId] || 'bg-gray'
}

function phaseChipClass(phaseId) {
  if (completedPhases.has(phaseId)) return 'done'
  if (currentPhase.value === phaseId) return 'current'
  return ''
}

const scrollDiscussion = () => {
  nextTick(() => {
    if (discussionRef.value) discussionRef.value.scrollTop = discussionRef.value.scrollHeight
  })
}

async function startDiscussion() {
  isDiscussing.value = true
  isFinished.value = false
  stopped.value = false
  messages.length = 0
  proposal.value = ''
  completedPhases.clear()
  currentPhase.value = ''
  currentMsgIndex = -1

  try {
    for await (const data of api.labDiscussStream({ mode: mode.value, user_focus: userFocus.value })) {
      if (stopped.value) break
      handleEvent(data)
      scrollDiscussion()
    }
  } catch (e) {
    messages.push({ type: 'message', agentId: 'system', agentEmoji: '⚠️', agentName: '系统', agentRole: '', content: `讨论出错: ${e.message}` })
  } finally {
    isDiscussing.value = false
    isFinished.value = true
    stopped.value = false
  }
}

function handleEvent(data) {
  const t = data.type
  switch (t) {
    case 'phase_start':
      currentPhase.value = data.phase
      messages.push({ type: 'phase', label: data.phase_label })
      break
    case 'phase_end':
      completedPhases.add(data.phase)
      break
    case 'speaking':
      messages.push({ type: 'message', agentId: data.agent, agentEmoji: data.agent_emoji, agentName: data.agent_name, agentRole: data.agent_role, content: '' })
      currentMsgIndex = messages.length - 1
      break
    case 'chunk':
      if (currentMsgIndex >= 0 && messages[currentMsgIndex]) messages[currentMsgIndex].content += data.content
      break
    case 'proposal_start':
      proposal.value = ''
      break
    case 'proposal_chunk':
      proposal.value += data.content
      break
    case 'proposal':
      proposal.value = data.content || proposal.value
      break
    case 'done':
      if (data.proposal) proposal.value = data.proposal
      break
    case 'error':
      messages.push({ type: 'message', agentId: 'system', agentEmoji: '⚠️', agentName: '系统', agentRole: '', content: data.message })
      break
  }
}

function stopDiscussion() { stopped.value = true }

function resetDiscussion() {
  isDiscussing.value = false
  isFinished.value = false
  messages.length = 0
  proposal.value = ''
  completedPhases.clear()
  currentPhase.value = ''
}

function copyProposal() {
  if (proposal.value) {
    navigator.clipboard.writeText(proposal.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}
</script>

<style scoped>
.lab-page { height: 100vh; display: flex; flex-direction: column; }
.lab-body { flex: 1; overflow-y: auto; }
.lab-inner { max-width: 880px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }
.lab-empty { padding: 4rem 0; }

.control-card { padding: 1.25rem; margin-bottom: 1rem; }
.control-head { margin-bottom: 1rem; }
.control-head h3 { font-size: 0.9rem; font-weight: 600; color: var(--text-heading); }
.control-head p { font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem; }

.mode-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem; margin-bottom: 1rem; }
.mode-card {
  text-align: left; padding: 0.75rem 0.9rem; border-radius: 0.7rem;
  background: var(--bg-input); border: 1px solid var(--border-default);
  cursor: pointer; transition: all 0.18s;
}
.mode-card:hover { border-color: var(--border-hover); }
.mode-card.active { background: rgba(139, 92, 246, 0.08); border-color: rgba(139, 92, 246, 0.35); }
.mode-title { display: flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; font-weight: 600; color: var(--text-heading); }
.mode-card p { font-size: 0.68rem; color: var(--text-muted); margin-top: 0.25rem; }
.text-amber { color: var(--warning); }
.text-violet { color: var(--accent-3); }

.field-label { display: block; font-size: 0.72rem; color: var(--text-secondary); font-weight: 500; margin: 0.8rem 0 0.4rem; }
.lab-start-btn {
  width: 100%; display: flex; align-items: center; justify-content: center; gap: 0.5rem;
  margin-top: 1rem; padding: 0.7rem; border-radius: 0.7rem;
  font-size: 0.85rem; font-weight: 600; color: #fff;
  background: linear-gradient(135deg, #8b5cf6, #6366f1); border: none;
  cursor: pointer; transition: all 0.2s;
}
.lab-start-btn:hover { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(139, 92, 246, 0.35); }

.phase-row { display: flex; gap: 0.6rem; margin-bottom: 1rem; flex-wrap: wrap; }
.phase-chip {
  flex: 1; min-width: 120px; display: flex; align-items: center; gap: 0.4rem;
  padding: 0.55rem 0.7rem; border-radius: 0.6rem; font-size: 0.75rem;
  color: var(--text-muted); background: var(--bg-input); border: 1px solid var(--border-default);
}
.phase-chip.done { color: var(--positive); background: rgba(52, 211, 153, 0.08); border-color: rgba(52, 211, 153, 0.2); }
.phase-chip.current { color: var(--accent-3); background: rgba(139, 92, 246, 0.08); border-color: rgba(139, 92, 246, 0.3); }
.phase-num {
  width: 16px; height: 16px; border-radius: 50%; display: flex; align-items: center;
  justify-content: center; font-size: 0.6rem; border: 1px solid currentColor;
}

.discussion-card { margin-bottom: 1rem; padding: 0; overflow: hidden; }
.discussion-head {
  padding: 0.9rem 1rem; border-bottom: 1px solid var(--border-default);
  font-size: 0.82rem; color: var(--text-secondary);
  display: flex; align-items: center; gap: 0.5rem;
}
.streaming-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent-3); animation: pulse 1s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.discussion-body { padding: 0 1rem 1rem; max-height: 440px; overflow-y: auto; }
.phase-divider {
  display: flex; align-items: center; gap: 0.6rem; margin: 0.9rem 0;
  font-size: 0.7rem; color: var(--text-muted);
}
.phase-divider::before, .phase-divider::after { content: ''; flex: 1; height: 1px; background: var(--border-default); }
.agent-msg { display: flex; gap: 0.6rem; margin-bottom: 0.8rem; }
.agent-avatar {
  width: 30px; height: 30px; border-radius: 0.6rem; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 0.9rem;
}
.bg-blue { background: rgba(56, 189, 248, 0.15); }
.bg-green { background: rgba(52, 211, 153, 0.15); }
.bg-amber { background: rgba(251, 191, 36, 0.15); }
.bg-violet { background: rgba(139, 92, 246, 0.15); }
.bg-gray { background: var(--bg-input); }
.agent-body { min-width: 0; flex: 1; }
.agent-name-row { display: flex; align-items: center; gap: 0.4rem; }
.agent-name { font-size: 0.76rem; font-weight: 600; color: var(--text-heading); }
.agent-role { font-size: 0.65rem; color: var(--text-muted); }
.agent-content { font-size: 0.8rem; margin-top: 0.2rem; }

.proposal-card { padding: 1.25rem; margin-bottom: 1rem; background: rgba(139, 92, 246, 0.04); border-color: rgba(139, 92, 246, 0.18); }
.proposal-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.8rem; }
.proposal-title { display: flex; align-items: center; gap: 0.4rem; font-size: 0.88rem; font-weight: 600; color: var(--text-heading); }
.proposal-content { font-size: 0.85rem; }
.text-accent { color: var(--accent-1); }

.lab-actions { display: flex; gap: 0.6rem; }
.btn-danger {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.55rem 1rem; border-radius: 0.7rem; font-size: 0.8rem;
  color: var(--danger); background: rgba(248, 113, 113, 0.08);
  border: 1px solid rgba(248, 113, 113, 0.2); cursor: pointer; transition: all 0.15s;
}
.btn-danger:hover { background: rgba(248, 113, 113, 0.15); }
.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>