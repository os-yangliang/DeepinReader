/**
 * Character — 角色系统
 * 
 * 使用纯色方块作为占位符，支持行走、坐下、发言动画
 */
export default class Character {
  constructor(scene, config) {
    this.scene = scene
    this.id = config.id
    this.name = config.name
    this.emoji = config.emoji
    this.color = config.color       // 0xRRGGBB
    this.seatX = config.seatX       // 座位坐标
    this.seatY = config.seatY
    this.podiumX = config.podiumX   // 发言位坐标
    this.podiumY = config.podiumY

    // 角色大小
    this.width = 28
    this.height = 40

    // 创建角色精灵（纯色方块占位符）
    this.container = scene.add.container(this.seatX, this.seatY)
    this.container.setDepth(10)

    // 身体
    this.body = scene.add.rectangle(0, 0, this.width, this.height, this.color)
    this.body.setStrokeStyle(2, this._darken(this.color, 0.3))
    this.container.add(this.body)

    // 头部（圆形）
    this.head = scene.add.circle(0, -this.height / 2 - 8, 12, this.color)
    this.head.setStrokeStyle(2, this._darken(this.color, 0.3))
    this.container.add(this.head)

    // 名字标签
    this.nameText = scene.add.text(0, this.height / 2 + 6, this.name, {
      fontSize: '11px',
      fontFamily: '"Microsoft YaHei", sans-serif',
      color: '#ffffff',
      align: 'center',
    }).setOrigin(0.5)
    this.container.add(this.nameText)

    // Emoji 标签（头顶）
    this.emojiText = scene.add.text(0, -this.height / 2 - 28, this.emoji, {
      fontSize: '16px',
    }).setOrigin(0.5)
    this.container.add(this.emojiText)

    // 状态
    this.isSpeaking = false
    this.isWalking = false
    this.breathTween = null
    this.glowCircle = null

    // 启动呼吸动画
    this._startBreathing()
  }

  /**
   * 走到发言位
   */
  walkToPodium() {
    return new Promise(resolve => {
      if (this.isWalking) return resolve()
      this.isWalking = true

      // 行走动画
      this.scene.tweens.add({
        targets: this.container,
        x: this.podiumX,
        y: this.podiumY,
        duration: 800,
        ease: 'Power2',
        onUpdate: () => {
          // 走路摇摆
          this.body.setRotation(Math.sin(Date.now() / 80) * 0.08)
        },
        onComplete: () => {
          this.body.setRotation(0)
          this.isWalking = false
          resolve()
        }
      })
    })
  }

  /**
   * 回到座位
   */
  walkToSeat() {
    return new Promise(resolve => {
      this.isSpeaking = false
      this._stopSpeakingEffect()

      this.scene.tweens.add({
        targets: this.container,
        x: this.seatX,
        y: this.seatY,
        duration: 600,
        ease: 'Power2',
        onComplete: () => resolve()
      })
    })
  }

  /**
   * 开始发言效果（发光 + 弹跳）
   */
  startSpeaking() {
    this.isSpeaking = true

    // 发光圆圈
    if (!this.glowCircle) {
      this.glowCircle = this.scene.add.circle(0, 0, 30, this.color, 0.2)
      this.container.addAt(this.glowCircle, 0)
    }

    // 脉冲动画
    this.scene.tweens.add({
      targets: this.glowCircle,
      scaleX: 1.5,
      scaleY: 1.5,
      alpha: 0,
      duration: 1000,
      repeat: -1,
      yoyo: true,
    })

    // 弹跳
    this.scene.tweens.add({
      targets: this.container,
      y: this.container.y - 3,
      duration: 400,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    })
  }

  /**
   * 停止发言效果
   */
  _stopSpeakingEffect() {
    this.scene.tweens.killTweensOf(this.container)
    if (this.glowCircle) {
      this.scene.tweens.killTweensOf(this.glowCircle)
      this.glowCircle.destroy()
      this.glowCircle = null
    }
    this._startBreathing()
  }

  /**
   * 显示工具使用动画
   */
  showToolUse(toolNames) {
    const toolIcon = this.scene.add.text(
      20, -this.height / 2 - 10, '🔧', { fontSize: '14px' }
    ).setOrigin(0.5)
    this.container.add(toolIcon)

    this.scene.tweens.add({
      targets: toolIcon,
      y: toolIcon.y - 20,
      alpha: 0,
      duration: 1500,
      onComplete: () => toolIcon.destroy()
    })
  }

  /**
   * 呼吸动画（待机状态）
   */
  _startBreathing() {
    if (this.breathTween) return
    this.breathTween = this.scene.tweens.add({
      targets: this.body,
      scaleY: 1.03,
      duration: 2000,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    })
  }

  /**
   * 获取头顶坐标（用于气泡定位）
   */
  getHeadPosition() {
    return {
      x: this.container.x,
      y: this.container.y - this.height / 2 - 35
    }
  }

  /**
   * 颜色加深
   */
  _darken(color, amount) {
    const r = Math.max(0, ((color >> 16) & 0xFF) * (1 - amount)) | 0
    const g = Math.max(0, ((color >> 8) & 0xFF) * (1 - amount)) | 0
    const b = Math.max(0, (color & 0xFF) * (1 - amount)) | 0
    return (r << 16) | (g << 8) | b
  }

  getX() { return this.container.x }
  getY() { return this.container.y }

  destroy() {
    if (this.breathTween) {
      this.breathTween.stop()
    }
    this._stopSpeakingEffect()
    this.container.destroy()
  }
}
