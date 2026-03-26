/**
 * DialogBubble — 对话气泡系统
 * 
 * 在角色头顶显示逐字出现的对话文本
 */
export default class DialogBubble {
  constructor(scene, x, y) {
    this.scene = scene
    this.x = x
    this.y = y
    this.fullText = ''
    this.displayedText = ''
    this.charIndex = 0
    this.isActive = false
    this.typeTimer = null

    // 气泡最大宽度
    this.maxWidth = 280
    this.padding = 12
    this.fontSize = 13

    // 创建气泡容器
    this.container = scene.add.container(x, y)
    this.container.setDepth(100)

    // 背景 (圆角矩形)
    this.bg = scene.add.graphics()
    this.container.add(this.bg)

    // 文本
    this.text = scene.add.text(this.padding, this.padding, '', {
      fontSize: `${this.fontSize}px`,
      fontFamily: '"Microsoft YaHei", "PingFang SC", sans-serif',
      color: '#1a1a2e',
      wordWrap: { width: this.maxWidth - this.padding * 2 },
      lineSpacing: 4,
    })
    this.container.add(this.text)

    // 说话者标签
    this.nameLabel = scene.add.text(this.padding, 4, '', {
      fontSize: '11px',
      fontFamily: '"Microsoft YaHei", sans-serif',
      fontStyle: 'bold',
      color: '#6366f1',
    })
    this.container.add(this.nameLabel)

    // 小三角（指向角色）
    this.arrow = scene.add.graphics()
    this.container.add(this.arrow)

    this.container.setVisible(false)
  }

  /**
   * 显示气泡并开始逐字打字效果
   */
  show(speakerName, speakerEmoji, text, color = '#6366f1') {
    this.fullText = text.slice(0, 150) // 气泡只显示前 150 字
    if (text.length > 150) this.fullText += '...'
    this.displayedText = ''
    this.charIndex = 0
    this.isActive = true

    this.nameLabel.setText(`${speakerEmoji} ${speakerName}`)
    this.nameLabel.setColor(color)
    this.nameLabel.setY(4)
    this.text.setY(22)
    this.text.setText('')

    this.container.setVisible(true)
    this._drawBg(this.maxWidth, 50) // 初始高度

    // 开始打字效果
    this._startTyping()
  }

  /**
   * 追加文本（流式更新）
   */
  appendText(chunk) {
    this.fullText += chunk
    // 截断
    if (this.fullText.length > 150) {
      this.fullText = this.fullText.slice(-150)
      this.displayedText = this.fullText
      this.charIndex = this.fullText.length
      this.text.setText(this.displayedText)
      this._updateSize()
    }
  }

  /**
   * 隐藏气泡
   */
  hide() {
    this.isActive = false
    if (this.typeTimer) {
      this.typeTimer.remove()
      this.typeTimer = null
    }
    // 渐隐动画
    this.scene.tweens.add({
      targets: this.container,
      alpha: 0,
      duration: 300,
      onComplete: () => {
        this.container.setVisible(false)
        this.container.setAlpha(1)
      }
    })
  }

  /**
   * 更新位置（跟随角色）
   */
  setPosition(x, y) {
    this.container.setPosition(x, y - 60)
  }

  _startTyping() {
    if (this.typeTimer) this.typeTimer.remove()

    this.typeTimer = this.scene.time.addEvent({
      delay: 30,
      callback: () => {
        if (this.charIndex < this.fullText.length) {
          this.displayedText += this.fullText[this.charIndex]
          this.charIndex++
          this.text.setText(this.displayedText)
          this._updateSize()
        } else {
          if (this.typeTimer) this.typeTimer.remove()
        }
      },
      loop: true,
    })
  }

  _updateSize() {
    const textHeight = this.text.height
    const totalHeight = textHeight + 30 + this.padding
    const width = Math.min(this.text.width + this.padding * 2, this.maxWidth)
    this._drawBg(Math.max(width, 120), Math.max(totalHeight, 45))
  }

  _drawBg(width, height) {
    this.bg.clear()

    // 阴影
    this.bg.fillStyle(0x000000, 0.15)
    this.bg.fillRoundedRect(3, 3, width, height, 10)

    // 主体
    this.bg.fillStyle(0xffffff, 0.95)
    this.bg.fillRoundedRect(0, 0, width, height, 10)

    // 边框
    this.bg.lineStyle(1.5, 0x6366f1, 0.3)
    this.bg.strokeRoundedRect(0, 0, width, height, 10)

    // 底部小三角
    this.arrow.clear()
    this.arrow.fillStyle(0xffffff, 0.95)
    this.arrow.fillTriangle(
      width / 2 - 6, height,
      width / 2 + 6, height,
      width / 2, height + 8
    )
    this.arrow.lineStyle(1.5, 0x6366f1, 0.3)
    this.arrow.lineBetween(width / 2 - 6, height, width / 2, height + 8)
    this.arrow.lineBetween(width / 2, height + 8, width / 2 + 6, height)

    // 居中气泡
    this.container.setX(this.x - width / 2)
  }

  destroy() {
    if (this.typeTimer) this.typeTimer.remove()
    this.container.destroy()
  }
}
