/**
 * SpriteCharacter — 使用 LPC 精灵表的角色
 * 
 * 支持 walk/idle/sit 动画，4 方向
 * LPC 帧目录结构: standard/{animation}/{direction}/{frame}.png
 */
export default class SpriteCharacter {
  constructor(scene, config) {
    this.scene = scene
    this.id = config.id
    this.name = config.name
    this.emoji = config.emoji
    this.color = config.color
    this.seatX = config.seatX
    this.seatY = config.seatY
    this.podiumX = config.podiumX
    this.podiumY = config.podiumY
    this.spriteKey = config.spriteKey // e.g. 'master_sprite'

    this.isSpeaking = false
    this.isWalking = false
    this.breathTween = null
    this.glowCircle = null
    this.currentDir = 'down'

    // 容器
    this.container = scene.add.container(this.seatX, this.seatY)
    this.container.setDepth(10)

    // 精灵
    this.sprite = scene.add.sprite(0, 0, `${this.spriteKey}_idle_down`, 0)
    this.sprite.setScale(1.2)
    this.container.add(this.sprite)

    // 名字标签
    this.nameText = scene.add.text(0, 32, this.name, {
      fontSize: '11px',
      fontFamily: '"Microsoft YaHei", sans-serif',
      color: '#ffffff',
      align: 'center',
    }).setOrigin(0.5)
    this.container.add(this.nameText)

    // Emoji
    this.emojiText = scene.add.text(0, -42, this.emoji, {
      fontSize: '16px',
    }).setOrigin(0.5)
    this.container.add(this.emojiText)

    // 创建动画
    this._createAnimations()

    // 播放 idle
    this.sprite.play(`${this.spriteKey}_idle_down`)
  }

  _createAnimations() {
    const key = this.spriteKey
    const directions = ['down', 'left', 'right', 'up']
    const anims = ['walk', 'idle']

    for (const anim of anims) {
      for (const dir of directions) {
        const animKey = `${key}_${anim}_${dir}`
        if (this.scene.anims.exists(animKey)) continue

        const texKey = `${key}_${anim}_${dir}`
        // 检查纹理是否存在
        if (!this.scene.textures.exists(texKey)) continue

        const frameCount = this.scene.textures.get(texKey).frameTotal - 1
        this.scene.anims.create({
          key: animKey,
          frames: this.scene.anims.generateFrameNumbers(texKey, { start: 0, end: frameCount - 1 }),
          frameRate: anim === 'walk' ? 10 : 4,
          repeat: -1,
        })
      }
    }

    // sit 动画（通常没有循环，只播放一次）
    for (const dir of directions) {
      const sitKey = `${key}_sit_${dir}`
      if (this.scene.anims.exists(sitKey)) continue
      if (!this.scene.textures.exists(sitKey)) continue

      const frameCount = this.scene.textures.get(sitKey).frameTotal - 1
      this.scene.anims.create({
        key: sitKey,
        frames: this.scene.anims.generateFrameNumbers(sitKey, { start: 0, end: frameCount - 1 }),
        frameRate: 6,
        repeat: 0,
      })
    }
  }

  /**
   * 根据目标位置决定朝向
   */
  _getDirection(targetX, targetY) {
    const dx = targetX - this.container.x
    const dy = targetY - this.container.y
    if (Math.abs(dx) > Math.abs(dy)) {
      return dx > 0 ? 'right' : 'left'
    }
    return dy > 0 ? 'down' : 'up'
  }

  walkToPodium() {
    return new Promise(resolve => {
      if (this.isWalking) return resolve()
      this.isWalking = true

      const dir = this._getDirection(this.podiumX, this.podiumY)
      this.currentDir = dir
      const walkAnim = `${this.spriteKey}_walk_${dir}`
      if (this.scene.anims.exists(walkAnim)) {
        this.sprite.play(walkAnim)
      }

      this.scene.tweens.add({
        targets: this.container,
        x: this.podiumX,
        y: this.podiumY,
        duration: 800,
        ease: 'Power2',
        onComplete: () => {
          this.isWalking = false
          // 到达后面向下方
          const idleAnim = `${this.spriteKey}_idle_down`
          if (this.scene.anims.exists(idleAnim)) {
            this.sprite.play(idleAnim)
          }
          resolve()
        }
      })
    })
  }

  walkToSeat() {
    return new Promise(resolve => {
      this.isSpeaking = false
      this._stopSpeakingEffect()

      const dir = this._getDirection(this.seatX, this.seatY)
      const walkAnim = `${this.spriteKey}_walk_${dir}`
      if (this.scene.anims.exists(walkAnim)) {
        this.sprite.play(walkAnim)
      }

      this.scene.tweens.add({
        targets: this.container,
        x: this.seatX,
        y: this.seatY,
        duration: 600,
        ease: 'Power2',
        onComplete: () => {
          const idleAnim = `${this.spriteKey}_idle_down`
          if (this.scene.anims.exists(idleAnim)) {
            this.sprite.play(idleAnim)
          }
          resolve()
        }
      })
    })
  }

  startSpeaking() {
    this.isSpeaking = true

    // 发光圆圈
    if (!this.glowCircle) {
      this.glowCircle = this.scene.add.circle(0, 0, 35, this.color, 0.2)
      this.container.addAt(this.glowCircle, 0)
    }

    this.scene.tweens.add({
      targets: this.glowCircle,
      scaleX: 1.5,
      scaleY: 1.5,
      alpha: 0,
      duration: 1000,
      repeat: -1,
      yoyo: true,
    })
  }

  _stopSpeakingEffect() {
    this.scene.tweens.killTweensOf(this.container)
    if (this.glowCircle) {
      this.scene.tweens.killTweensOf(this.glowCircle)
      this.glowCircle.destroy()
      this.glowCircle = null
    }
  }

  showToolUse(toolNames) {
    const toolIcon = this.scene.add.text(
      20, -30, '🔧', { fontSize: '14px' }
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

  getHeadPosition() {
    return {
      x: this.container.x,
      y: this.container.y - 45
    }
  }

  getX() { return this.container.x }
  getY() { return this.container.y }

  destroy() {
    this._stopSpeakingEffect()
    this.container.destroy()
  }
}
