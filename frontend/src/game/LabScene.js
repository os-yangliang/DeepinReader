/**
 * LabScene — 课题组会议室 Phaser 场景
 * 
 * 使用纯色方块作为占位符的实验室/会议室场景
 * 支持：角色行走、发言气泡、阶段切换动画
 */
import Phaser from 'phaser'
import Character from './Character.js'
import SpriteCharacter from './SpriteCharacter.js'
import DialogBubble from './DialogBubble.js'
import { gameBus } from './GameBridge.js'

// LPC 精灵表资源路径 — 赵同学 (master, folder 1)
import masterWalkDown from '../assets/lab/1/sheets/walk_down.png'
import masterWalkLeft from '../assets/lab/1/sheets/walk_left.png'
import masterWalkRight from '../assets/lab/1/sheets/walk_right.png'
import masterWalkUp from '../assets/lab/1/sheets/walk_up.png'
import masterIdleDown from '../assets/lab/1/sheets/idle_down.png'
import masterIdleLeft from '../assets/lab/1/sheets/idle_left.png'
import masterIdleRight from '../assets/lab/1/sheets/idle_right.png'
import masterIdleUp from '../assets/lab/1/sheets/idle_up.png'
import masterSitDown from '../assets/lab/1/sheets/sit_down.png'
import masterSitLeft from '../assets/lab/1/sheets/sit_left.png'
import masterSitRight from '../assets/lab/1/sheets/sit_right.png'
import masterSitUp from '../assets/lab/1/sheets/sit_up.png'

// 李教授 (advisor, folder 2)
import advisorWalkDown from '../assets/lab/2/sheets/walk_down.png'
import advisorWalkLeft from '../assets/lab/2/sheets/walk_left.png'
import advisorWalkRight from '../assets/lab/2/sheets/walk_right.png'
import advisorWalkUp from '../assets/lab/2/sheets/walk_up.png'
import advisorIdleDown from '../assets/lab/2/sheets/idle_down.png'
import advisorIdleLeft from '../assets/lab/2/sheets/idle_left.png'
import advisorIdleRight from '../assets/lab/2/sheets/idle_right.png'
import advisorIdleUp from '../assets/lab/2/sheets/idle_up.png'
import advisorSitDown from '../assets/lab/2/sheets/sit_down.png'
import advisorSitLeft from '../assets/lab/2/sheets/sit_left.png'
import advisorSitRight from '../assets/lab/2/sheets/sit_right.png'
import advisorSitUp from '../assets/lab/2/sheets/sit_up.png'

// 王博士 (phd_junior, folder 3)
import juniorWalkDown from '../assets/lab/3/sheets/walk_down.png'
import juniorWalkLeft from '../assets/lab/3/sheets/walk_left.png'
import juniorWalkRight from '../assets/lab/3/sheets/walk_right.png'
import juniorWalkUp from '../assets/lab/3/sheets/walk_up.png'
import juniorIdleDown from '../assets/lab/3/sheets/idle_down.png'
import juniorIdleLeft from '../assets/lab/3/sheets/idle_left.png'
import juniorIdleRight from '../assets/lab/3/sheets/idle_right.png'
import juniorIdleUp from '../assets/lab/3/sheets/idle_up.png'
import juniorSitDown from '../assets/lab/3/sheets/sit_down.png'
import juniorSitLeft from '../assets/lab/3/sheets/sit_left.png'
import juniorSitRight from '../assets/lab/3/sheets/sit_right.png'
import juniorSitUp from '../assets/lab/3/sheets/sit_up.png'

// 张博士 (phd_senior, folder 4)
import seniorWalkDown from '../assets/lab/4/sheets/walk_down.png'
import seniorWalkLeft from '../assets/lab/4/sheets/walk_left.png'
import seniorWalkRight from '../assets/lab/4/sheets/walk_right.png'
import seniorWalkUp from '../assets/lab/4/sheets/walk_up.png'
import seniorIdleDown from '../assets/lab/4/sheets/idle_down.png'
import seniorIdleLeft from '../assets/lab/4/sheets/idle_left.png'
import seniorIdleRight from '../assets/lab/4/sheets/idle_right.png'
import seniorIdleUp from '../assets/lab/4/sheets/idle_up.png'
import seniorSitDown from '../assets/lab/4/sheets/sit_down.png'
import seniorSitLeft from '../assets/lab/4/sheets/sit_left.png'
import seniorSitRight from '../assets/lab/4/sheets/sit_right.png'
import seniorSitUp from '../assets/lab/4/sheets/sit_up.png'

// 精灵资源映射（所有角色）
function buildSheetMap(w_d,w_l,w_r,w_u, i_d,i_l,i_r,i_u, s_d,s_l,s_r,s_u) {
  return {
    walk_down: {src:w_d,frames:9}, walk_left: {src:w_l,frames:9},
    walk_right:{src:w_r,frames:9}, walk_up:   {src:w_u,frames:9},
    idle_down: {src:i_d,frames:2}, idle_left: {src:i_l,frames:2},
    idle_right:{src:i_r,frames:2}, idle_up:   {src:i_u,frames:2},
    sit_down:  {src:s_d,frames:3}, sit_left:  {src:s_l,frames:3},
    sit_right: {src:s_r,frames:3}, sit_up:    {src:s_u,frames:3},
  }
}

const ALL_SPRITE_SHEETS = {
  master:     buildSheetMap(masterWalkDown,masterWalkLeft,masterWalkRight,masterWalkUp,masterIdleDown,masterIdleLeft,masterIdleRight,masterIdleUp,masterSitDown,masterSitLeft,masterSitRight,masterSitUp),
  advisor:    buildSheetMap(advisorWalkDown,advisorWalkLeft,advisorWalkRight,advisorWalkUp,advisorIdleDown,advisorIdleLeft,advisorIdleRight,advisorIdleUp,advisorSitDown,advisorSitLeft,advisorSitRight,advisorSitUp),
  phd_junior: buildSheetMap(juniorWalkDown,juniorWalkLeft,juniorWalkRight,juniorWalkUp,juniorIdleDown,juniorIdleLeft,juniorIdleRight,juniorIdleUp,juniorSitDown,juniorSitLeft,juniorSitRight,juniorSitUp),
  phd_senior: buildSheetMap(seniorWalkDown,seniorWalkLeft,seniorWalkRight,seniorWalkUp,seniorIdleDown,seniorIdleLeft,seniorIdleRight,seniorIdleUp,seniorSitDown,seniorSitLeft,seniorSitRight,seniorSitUp),
}

// 所有角色都使用精灵
const SPRITE_ROLES = new Set(['master', 'advisor', 'phd_junior', 'phd_senior'])

// 场景尺寸
const SCENE_W = 800
const SCENE_H = 500

// 角色配置（颜色 + 座位 + 发言位）
const CHARACTERS = {
  advisor: {
    id: 'advisor', name: '李教授', emoji: '🧑‍🏫',
    color: 0x3b82f6, // 蓝色
    seatX: 400, seatY: 200,   // 桌子上方中间
    podiumX: 200, podiumY: 160, // 白板前
  },
  phd_senior: {
    id: 'phd_senior', name: '张博士', emoji: '🎓',
    color: 0x10b981, // 绿色
    seatX: 280, seatY: 320,
    podiumX: 200, podiumY: 160,
  },
  phd_junior: {
    id: 'phd_junior', name: '王博士', emoji: '💡',
    color: 0xf59e0b, // 橙色
    seatX: 520, seatY: 320,
    podiumX: 200, podiumY: 160,
  },
  master: {
    id: 'master', name: '赵同学', emoji: '📚',
    color: 0xa855f7, // 紫色
    seatX: 400, seatY: 390,
    podiumX: 200, podiumY: 160,
  },
}

// 阶段标签
const PHASE_LABELS = {
  paper_review: '📄 论文解读',
  brainstorm: '💡 头脑风暴',
  advisor_review: '🧑‍🏫 导师点评',
  deep_dive: '🔬 深入讨论',
  final_plan: '📋 终审与分工',
}

export default class LabScene extends Phaser.Scene {
  constructor() {
    super({ key: 'LabScene' })
    this.characters = {}
    this.currentBubble = null
    this.currentSpeakerId = null
    this.phaseText = null
    this.statusText = null
  }

  preload() {
    // 加载所有角色的 LPC 精灵表
    for (const [roleId, sheets] of Object.entries(ALL_SPRITE_SHEETS)) {
      for (const [key, info] of Object.entries(sheets)) {
        this.load.spritesheet(`${roleId}_sprite_${key}`, info.src, {
          frameWidth: 64,
          frameHeight: 64,
        })
      }
    }
  }

  create() {
    this.cameras.main.setBackgroundColor('#0f172a')

    // ===== 绘制会议室 =====
    this._drawRoom()

    // ===== 创建角色 =====
    for (const [id, config] of Object.entries(CHARACTERS)) {
      if (SPRITE_ROLES.has(id)) {
        // 精灵角色
        this.characters[id] = new SpriteCharacter(this, {
          ...config,
          spriteKey: `${id}_sprite`,
        })
      } else {
        // 占位符角色
        this.characters[id] = new Character(this, config)
      }
    }

    // ===== 创建气泡 =====
    this.currentBubble = new DialogBubble(this, 400, 100)

    // ===== 阶段标题 =====
    this.phaseText = this.add.text(SCENE_W / 2, 25, '', {
      fontSize: '16px',
      fontFamily: '"Microsoft YaHei", sans-serif',
      fontStyle: 'bold',
      color: '#e2e8f0',
      backgroundColor: '#1e293b',
      padding: { x: 16, y: 8 },
    }).setOrigin(0.5).setAlpha(0).setDepth(50)

    // ===== 状态文字 =====
    this.statusText = this.add.text(SCENE_W / 2, SCENE_H - 20, '', {
      fontSize: '11px',
      fontFamily: '"Microsoft YaHei", sans-serif',
      color: '#64748b',
    }).setOrigin(0.5).setDepth(50)

    // ===== 注册事件处理 =====
    this._registerEvents()
  }

  /**
   * 绘制会议室（纯几何占位符）
   */
  _drawRoom() {
    const g = this.add.graphics()

    // 地板
    g.fillStyle(0x1e293b, 1)
    g.fillRect(0, 0, SCENE_W, SCENE_H)

    // 地板格子
    g.lineStyle(1, 0x334155, 0.3)
    for (let x = 0; x < SCENE_W; x += 40) {
      g.lineBetween(x, 0, x, SCENE_H)
    }
    for (let y = 0; y < SCENE_H; y += 40) {
      g.lineBetween(0, y, SCENE_W, y)
    }

    // 墙壁（上方）
    g.fillStyle(0x334155, 1)
    g.fillRect(0, 0, SCENE_W, 60)
    g.lineStyle(2, 0x475569, 1)
    g.lineBetween(0, 60, SCENE_W, 60)

    // 白板（左上）
    g.fillStyle(0xf1f5f9, 0.9)
    g.fillRoundedRect(100, 8, 200, 45, 4)
    g.lineStyle(2, 0x94a3b8, 1)
    g.strokeRoundedRect(100, 8, 200, 45, 4)

    // 白板文字
    this.add.text(200, 30, '📋 课题组会议', {
      fontSize: '13px',
      fontFamily: '"Microsoft YaHei", sans-serif',
      fontStyle: 'bold',
      color: '#1e293b',
    }).setOrigin(0.5).setDepth(2)

    // 投影屏幕（右上）
    g.fillStyle(0x0f172a, 0.8)
    g.fillRoundedRect(500, 8, 220, 45, 4)
    g.lineStyle(2, 0x6366f1, 0.5)
    g.strokeRoundedRect(500, 8, 220, 45, 4)

    this.screenText = this.add.text(610, 30, '⏳ 等待开始...', {
      fontSize: '11px',
      fontFamily: '"Microsoft YaHei", sans-serif',
      color: '#94a3b8',
    }).setOrigin(0.5).setDepth(2)

    // 会议桌（中间椭圆）
    g.fillStyle(0x78350f, 0.6)
    g.fillEllipse(400, 280, 300, 100)
    g.lineStyle(2, 0x92400e, 0.8)
    g.strokeEllipse(400, 280, 300, 100)

    // 桌面纹理
    g.fillStyle(0x92400e, 0.3)
    g.fillEllipse(400, 280, 260, 80)

    // 椅子（4 个位置的椅子）
    const chairPositions = [
      { x: 400, y: 195 }, // 上
      { x: 275, y: 315 }, // 左下
      { x: 525, y: 315 }, // 右下
      { x: 400, y: 385 }, // 下
    ]
    for (const pos of chairPositions) {
      g.fillStyle(0x475569, 0.7)
      g.fillCircle(pos.x, pos.y, 15)
      g.lineStyle(1, 0x64748b, 0.5)
      g.strokeCircle(pos.x, pos.y, 15)
    }

    // 装饰：左边书架
    g.fillStyle(0x78350f, 0.4)
    g.fillRect(15, 80, 50, 100)
    g.fillStyle(0xef4444, 0.5)
    g.fillRect(20, 85, 15, 20)
    g.fillStyle(0x3b82f6, 0.5)
    g.fillRect(38, 85, 12, 25)
    g.fillStyle(0x10b981, 0.5)
    g.fillRect(20, 110, 18, 18)
    g.fillStyle(0xf59e0b, 0.5)
    g.fillRect(40, 115, 10, 22)

    // 装饰：右边植物
    g.fillStyle(0x78350f, 0.5)
    g.fillRect(745, 160, 20, 40)
    g.fillStyle(0x10b981, 0.6)
    g.fillCircle(755, 150, 20)
    g.fillCircle(745, 140, 15)
    g.fillCircle(765, 140, 15)

    // 装饰：底部门
    g.fillStyle(0x475569, 0.5)
    g.fillRoundedRect(680, SCENE_H - 90, 60, 85, { tl: 8, tr: 8, bl: 0, br: 0 })
    g.fillStyle(0xf59e0b, 0.6)
    g.fillCircle(730, SCENE_H - 45, 4)
  }

  /**
   * 注册 GameBridge 事件
   */
  _registerEvents() {
    gameBus.on('phase_start', (data) => this._onPhaseStart(data))
    gameBus.on('speaking', (data) => this._onSpeaking(data))
    gameBus.on('tool_done', (data) => this._onToolDone(data))
    gameBus.on('chunk', (data) => this._onChunk(data))
    gameBus.on('phase_end', (data) => this._onPhaseEnd(data))
    gameBus.on('proposal_start', () => this._onProposalStart())
    gameBus.on('proposal_chunk', (data) => this._onProposalChunk(data))
    gameBus.on('done', () => this._onDone())
    gameBus.on('reset', () => this._onReset())
  }

  // ==================== 事件处理 ====================

  async _onPhaseStart(data) {
    const label = PHASE_LABELS[data.phase] || data.phase_label || data.phase
    this.phaseText.setText(label)
    this.phaseText.setAlpha(0)

    // 屏幕更新
    this.screenText.setText(label)

    // 阶段标题动画
    this.tweens.add({
      targets: this.phaseText,
      alpha: 1,
      scaleX: { from: 0.8, to: 1 },
      scaleY: { from: 0.8, to: 1 },
      duration: 500,
      ease: 'Back.easeOut',
    })

    this.statusText.setText(`当前阶段：${label}`)
  }

  async _onSpeaking(data) {
    const agentId = data.agent
    const char = this.characters[agentId]
    if (!char) return

    // 前一个说话者回到座位
    if (this.currentSpeakerId && this.currentSpeakerId !== agentId) {
      const prevChar = this.characters[this.currentSpeakerId]
      if (prevChar) {
        this.currentBubble.hide()
        await prevChar.walkToSeat()
      }
    }

    this.currentSpeakerId = agentId

    // 走到发言位
    await char.walkToPodium()
    char.startSpeaking()

    // 显示气泡
    const headPos = char.getHeadPosition()
    this.currentBubble.setPosition(headPos.x, headPos.y)
    const colorHex = typeof char.color === 'number'
      ? '#' + char.color.toString(16).padStart(6, '0')
      : '#a855f7'
    this.currentBubble.show(data.agent_name, data.agent_emoji, '', colorHex)

    this.statusText.setText(`${data.agent_emoji} ${data.agent_name} 正在发言...`)
  }

  _onToolDone(data) {
    const char = this.characters[data.agent]
    if (char) {
      char.showToolUse(data.tools_used || [])
    }
    this.statusText.setText(`🔧 ${data.agent_name} 使用了工具`)
  }

  _onChunk(data) {
    if (this.currentBubble && this.currentBubble.isActive) {
      this.currentBubble.appendText(data.content)
    }
  }

  async _onPhaseEnd(data) {
    // 隐藏阶段标题
    this.tweens.add({
      targets: this.phaseText,
      alpha: 0,
      duration: 300,
    })

    // 当前说话者回到座位
    if (this.currentSpeakerId) {
      const char = this.characters[this.currentSpeakerId]
      if (char) {
        this.currentBubble.hide()
        await char.walkToSeat()
      }
      this.currentSpeakerId = null
    }
  }

  _onProposalStart() {
    this.screenText.setText('📝 生成研究提案...')
    this.statusText.setText('📝 正在生成研究提案...')

    // 屏幕发光效果
    const glow = this.add.rectangle(610, 30, 230, 55, 0x6366f1, 0.1).setDepth(1)
    this.tweens.add({
      targets: glow,
      alpha: 0.3,
      scaleX: 1.05,
      scaleY: 1.05,
      duration: 800,
      yoyo: true,
      repeat: -1,
    })
  }

  _onProposalChunk(data) {
    // 提案内容在 Vue 侧显示, 这里只更新屏幕文字
    const preview = (data.content || '').slice(0, 20)
    if (preview.includes('#')) {
      this.screenText.setText('📝 ' + preview.replace(/[#\n]/g, '').trim())
    }
  }

  _onDone() {
    this.screenText.setText('✅ 讨论完成！')
    this.statusText.setText('🎉 课题组讨论完成')

    // 庆祝动画：所有角色弹跳
    for (const char of Object.values(this.characters)) {
      this.tweens.add({
        targets: char.container,
        y: char.seatY - 15,
        duration: 300,
        yoyo: true,
        repeat: 2,
        ease: 'Bounce.easeOut',
        delay: Math.random() * 500,
      })
    }
  }

  _onReset() {
    // 重置所有角色位置
    for (const [id, char] of Object.entries(this.characters)) {
      const config = CHARACTERS[id]
      char.container.setPosition(config.seatX, config.seatY)
    }
    this.currentBubble.hide()
    this.currentSpeakerId = null
    this.phaseText.setAlpha(0)
    this.screenText.setText('⏳ 等待开始...')
    this.statusText.setText('')
  }

  shutdown() {
    gameBus.clear()
    for (const char of Object.values(this.characters)) {
      char.destroy()
    }
    if (this.currentBubble) {
      this.currentBubble.destroy()
    }
  }
}
