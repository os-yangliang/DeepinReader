/**
 * GameBridge — Vue ↔ Phaser 通信桥
 * 
 * WebSocket 事件通过 EventEmitter 传递给 Phaser 场景
 */
class GameEventBus {
  constructor() {
    this._listeners = new Map()
  }

  on(event, callback) {
    if (!this._listeners.has(event)) {
      this._listeners.set(event, [])
    }
    this._listeners.get(event).push(callback)
    return this
  }

  off(event, callback) {
    if (!this._listeners.has(event)) return
    if (!callback) {
      this._listeners.delete(event)
    } else {
      const cbs = this._listeners.get(event).filter(cb => cb !== callback)
      this._listeners.set(event, cbs)
    }
  }

  emit(event, data) {
    if (!this._listeners.has(event)) return
    for (const cb of this._listeners.get(event)) {
      cb(data)
    }
  }

  clear() {
    this._listeners.clear()
  }
}

// 全局单例
export const gameBus = new GameEventBus()

export default gameBus
