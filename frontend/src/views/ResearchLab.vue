<template>
  <div class="max-w-7xl mx-auto">
    <!-- 头部 -->
    <div class="text-center mb-6">
      <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-purple-500/10 border border-purple-500/20 mb-3">
        <FlaskConical :size="14" class="text-purple-400" />
        <span class="text-xs font-medium text-purple-300">AI Research Lab</span>
      </div>
      <h1 class="text-3xl font-display font-bold text-heading mb-1">🧪 虚拟课题组</h1>
      <p class="text-secondary text-sm">AI 课题组围绕论文展开学术讨论，挖掘新 Idea，产出研究提案</p>
    </div>

    <!-- 未加载文档提示 -->
    <div v-if="!store.documentInfo" class="card p-12 text-center">
      <Upload :size="48" class="mx-auto mb-4 text-muted opacity-40" />
      <p class="text-secondary mb-2">请先上传并分析论文</p>
      <p class="text-muted text-sm">课题组需要论文的分析结果作为讨论基础</p>
      <router-link to="/" class="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-lg bg-primary-500/20 text-primary-400 hover:bg-primary-500/30 transition-colors text-sm">
        <Upload :size="14" /> 去上传论文
      </router-link>
    </div>

    <!-- 主内容 -->
    <div v-else>

      <!-- 控制栏（未开始时显示） -->
      <div v-if="!isDiscussing && !isFinished" class="card p-5 mb-5">
        <div class="flex items-center gap-4 mb-3">
          <div class="flex-1">
            <h3 class="text-heading font-semibold text-sm">开始课题组讨论</h3>
            <p class="text-muted text-xs mt-0.5">论文：{{ store.documentInfo?.title || store.documentInfo?.filename || '未知' }}</p>
          </div>
        </div>

        <div class="flex gap-3 mb-3">
          <button @click="mode = 'quick'" class="flex-1 p-3 rounded-xl border transition-all text-left"
            :class="mode === 'quick' ? 'border-primary-500/50 bg-primary-500/10' : 'border-border bg-surface hover:border-primary-500/30'">
            <div class="flex items-center gap-2 mb-0.5">
              <Zap :size="14" class="text-amber-400" />
              <span class="text-heading font-medium text-xs">快速模式</span>
            </div>
            <p class="text-muted text-[10px]">3 个阶段，约 3 分钟</p>
          </button>
          <button @click="mode = 'deep'" class="flex-1 p-3 rounded-xl border transition-all text-left"
            :class="mode === 'deep' ? 'border-primary-500/50 bg-primary-500/10' : 'border-border bg-surface hover:border-primary-500/30'">
            <div class="flex items-center gap-2 mb-0.5">
              <Brain :size="14" class="text-purple-400" />
              <span class="text-heading font-medium text-xs">深度模式</span>
            </div>
            <p class="text-muted text-[10px]">5 个阶段，约 6 分钟</p>
          </button>
        </div>

        <div class="mb-3">
          <label class="text-[10px] text-muted block mb-1">关注方向（可选）</label>
          <input v-model="userFocus" placeholder="例如：将该方法应用到医学图像分析"
            class="w-full px-3 py-2 rounded-lg bg-input border border-border text-xs text-heading placeholder:text-muted focus:outline-none focus:border-primary-500/50" />
        </div>

        <button @click="startDiscussion"
          class="w-full py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-medium text-sm hover:from-purple-500 hover:to-indigo-500 transition-all flex items-center justify-center gap-2">
          <FlaskConical :size="14" /> 开始课题组讨论
        </button>
      </div>

      <!-- Phaser 游戏画面 -->
      <div class="card overflow-hidden mb-4" :class="{ 'ring-1 ring-purple-500/30': isDiscussing }">
        <div ref="gameContainer" class="game-canvas-wrapper"></div>
      </div>

      <!-- 讨论进度条 -->
      <div v-if="isDiscussing || isFinished" class="flex gap-2 mb-4">
        <div v-for="(phase, idx) in phaseList" :key="phase.id"
          class="flex-1 flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs transition-all"
          :class="phaseChipClass(phase.id)">
          <Check v-if="completedPhases.has(phase.id)" :size="12" />
          <Loader v-else-if="currentPhase === phase.id" :size="12" class="animate-spin" />
          <span v-else class="w-3 h-3 rounded-full border border-current flex items-center justify-center text-[8px]">{{ idx+1 }}</span>
          <span>{{ phase.label }}</span>
        </div>
      </div>

      <!-- 文字讨论记录（可折叠） -->
      <details v-if="messages.length > 0" class="card mb-4" :open="!isDiscussing">
        <summary class="p-4 cursor-pointer text-sm text-secondary hover:text-heading transition-colors flex items-center gap-2">
          <MessageCircle :size="14" />
          <span>讨论记录 ({{ messages.filter(m => m.type === 'message').length }} 条发言)</span>
        </summary>
        <div class="px-4 pb-4 space-y-3 max-h-96 overflow-y-auto">
          <template v-for="(msg, idx) in messages" :key="idx">
            <div v-if="msg.type === 'phase'" class="flex items-center gap-2 my-3">
              <div class="h-px flex-1 bg-border"></div>
              <span class="text-[10px] text-muted px-2">{{ msg.label }}</span>
              <div class="h-px flex-1 bg-border"></div>
            </div>
            <div v-else-if="msg.type === 'message'" class="flex gap-2">
              <div class="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-sm" :class="agentBgClass(msg.agentId)">
                {{ msg.agentEmoji }}
              </div>
              <div class="flex-1 min-w-0">
                <span class="text-heading text-xs font-medium">{{ msg.agentName }}</span>
                <div class="text-xs text-secondary mt-0.5 leading-relaxed prose-sm" v-html="renderMarkdown(msg.content)"></div>
              </div>
            </div>
          </template>
        </div>
      </details>

      <!-- 研究提案 -->
      <div v-if="proposal" class="card p-5 border-purple-500/20 bg-purple-500/5 mb-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <FileText :size="14" class="text-purple-400" />
            <span class="text-heading font-semibold text-sm">📝 研究提案</span>
          </div>
          <button @click="copyProposal"
            class="px-3 py-1 rounded-lg bg-primary-500/10 text-primary-400 text-xs hover:bg-primary-500/20 transition-colors flex items-center gap-1">
            <Copy :size="12" /> {{ copied ? '已复制 ✓' : '复制' }}
          </button>
        </div>
        <div class="text-sm text-secondary leading-relaxed prose-content" v-html="renderMarkdown(proposal)"></div>
      </div>

      <!-- 操作栏 -->
      <div v-if="isDiscussing || isFinished" class="flex gap-3">
        <button v-if="isDiscussing" @click="cancelDiscussion"
          class="px-4 py-2 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors text-xs flex items-center gap-2">
          <X :size="12" /> 停止讨论
        </button>
        <button v-if="isFinished" @click="resetDiscussion"
          class="px-4 py-2 rounded-lg bg-surface border border-border hover:bg-surface-hover transition-colors text-xs text-secondary flex items-center gap-2">
          <RefreshCw :size="12" /> 重新讨论
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import Phaser from 'phaser'
import { FlaskConical, Upload, Zap, Brain, X, RefreshCw, Copy, FileText, Check, Loader, MessageCircle } from 'lucide-vue-next'
import { store } from '../store'
import { wsRequest } from '../utils/websocket'
import { renderMarkdown } from '../utils/markdown'
import LabScene from '../game/LabScene.js'
import { gameBus } from '../game/GameBridge.js'

const mode = ref('quick')
const userFocus = ref('')
const isDiscussing = ref(false)
const isFinished = ref(false)
const messages = reactive([])
const proposal = ref('')
const copied = ref(false)
const currentPhase = ref('')
const completedPhases = reactive(new Set())
const gameContainer = ref(null)

let cancelFn = null
let phaserGame = null
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
  return { advisor: 'bg-blue-500/15', phd_senior: 'bg-emerald-500/15', phd_junior: 'bg-amber-500/15', master: 'bg-purple-500/15' }[agentId] || 'bg-surface'
}

function phaseChipClass(phaseId) {
  if (completedPhases.has(phaseId)) return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
  if (currentPhase.value === phaseId) return 'bg-primary-500/10 text-primary-400 border border-primary-500/20'
  return 'bg-surface text-muted border border-border'
}

// ===== Phaser 初始化 =====
onMounted(() => {
  if (gameContainer.value) {
    initPhaser()
  }
})

onBeforeUnmount(() => {
  if (cancelFn) cancelFn()
  destroyPhaser()
})

function initPhaser() {
  if (phaserGame) return

  phaserGame = new Phaser.Game({
    type: Phaser.AUTO,
    parent: gameContainer.value,
    width: 800,
    height: 500,
    backgroundColor: '#0f172a',
    scene: [LabScene],
    physics: { default: 'arcade', arcade: { debug: false } },
    scale: {
      mode: Phaser.Scale.FIT,
      autoCenter: Phaser.Scale.CENTER_BOTH,
    },
    render: {
      pixelArt: false,
      antialias: true,
    },
  })
}

function destroyPhaser() {
  gameBus.clear()
  if (phaserGame) {
    phaserGame.destroy(true)
    phaserGame = null
  }
}

// ===== 讨论控制 =====
async function startDiscussion() {
  isDiscussing.value = true
  isFinished.value = false
  messages.length = 0
  proposal.value = ''
  completedPhases.clear()
  currentPhase.value = ''
  currentMsgIndex = -1

  // 重置游戏场景
  gameBus.emit('reset')

  const { stream, cancel } = wsRequest('lab_discuss', {
    mode: mode.value,
    user_focus: userFocus.value,
  })
  cancelFn = cancel

  try {
    for await (const data of stream) {
      if (data.__done) {
        if (data.proposal) proposal.value = data.proposal
        gameBus.emit('done')
        break
      }
      if (data.__cancelled) {
        gameBus.emit('reset')
        break
      }
      handleEvent(data)
    }
  } catch (e) {
    messages.push({ type: 'message', agentId: 'system', agentEmoji: '⚠️', agentName: '系统', agentRole: '', content: `讨论出错: ${e.message}` })
  } finally {
    isDiscussing.value = false
    isFinished.value = true
    cancelFn = null
  }
}

function handleEvent(data) {
  const t = data.type

  // 转发给 Phaser
  gameBus.emit(t, data)

  switch (t) {
    case 'phase_start':
      currentPhase.value = data.phase
      messages.push({ type: 'phase', label: data.phase_label })
      break

    case 'phase_end':
      completedPhases.add(data.phase)
      break

    case 'speaking':
      messages.push({
        type: 'message', agentId: data.agent, agentEmoji: data.agent_emoji,
        agentName: data.agent_name, agentRole: data.agent_role, content: '',
      })
      currentMsgIndex = messages.length - 1
      break

    case 'chunk':
      if (currentMsgIndex >= 0 && messages[currentMsgIndex]) {
        messages[currentMsgIndex].content += data.content
      }
      break

    case 'proposal_start':
      break

    case 'proposal_chunk':
      proposal.value += data.content
      break
  }
}

function cancelDiscussion() { if (cancelFn) cancelFn() }

function resetDiscussion() {
  isDiscussing.value = false
  isFinished.value = false
  messages.length = 0
  proposal.value = ''
  completedPhases.clear()
  currentPhase.value = ''
  gameBus.emit('reset')
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
.card {
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: 16px;
}

.game-canvas-wrapper {
  width: 100%;
  aspect-ratio: 800 / 500;
  border-radius: 16px;
  overflow: hidden;
}

.game-canvas-wrapper :deep(canvas) {
  border-radius: 16px;
  width: 100% !important;
  height: 100% !important;
}

.prose-content :deep(h1), .prose-content :deep(h2), .prose-content :deep(h3) {
  color: var(--text-heading);
  margin-top: 0.8em; margin-bottom: 0.4em;
}
.prose-content :deep(h2) { font-size: 1.05em; }
.prose-content :deep(h3) { font-size: 0.95em; }
.prose-content :deep(ul), .prose-content :deep(ol) { padding-left: 1.5em; margin: 0.5em 0; }
.prose-content :deep(strong) { color: var(--text-heading); }
.prose-content :deep(table) { width: 100%; border-collapse: collapse; margin: 0.5em 0; font-size: 0.85em; }
.prose-content :deep(th), .prose-content :deep(td) { padding: 4px 8px; border: 1px solid var(--border-default); }
.prose-content :deep(th) { background: var(--bg-surface); font-weight: 600; color: var(--text-heading); }

.prose-sm :deep(p) { margin: 0.3em 0; }
</style>
