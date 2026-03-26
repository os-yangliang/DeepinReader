/**
 * WebSocket 连接管理器
 * 
 * 单连接多路复用 — 所有流式操作共享一个 WebSocket 连接
 * 支持：自动重连、心跳检测、请求取消、SSE 降级
 * 
 * 协议:
 *   Client → Server: { type, request_id, data }
 *   Server → Client: { type, request_id, data }
 *   type: "analyze" | "chat" | "translate" | "code_generate" | "compare" | "cancel" | "ping"
 *   response type: "stream" | "done" | "error" | "cancelled" | "pong"
 */
// 构建 WebSocket URL
function buildWsUrl() {
  const apiBase = import.meta.env.VITE_API_BASE_URL || '/api'
  
  if (apiBase.startsWith('http')) {
    // 绝对路径: http://host:port/api → ws://host:port/ws
    return apiBase.replace(/^http/, 'ws').replace(/\/api\/?$/, '/ws')
  }
  // 相对路径（dev proxy 模式）: 直接用当前 host
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}/ws`
}

const WS_URL = buildWsUrl()

let _ws = null
let _reconnectTimer = null
let _heartbeatTimer = null
let _reconnectAttempts = 0
const MAX_RECONNECT = 5
const HEARTBEAT_INTERVAL = 30000

// 请求回调映射: request_id -> { onStream, onDone, onError, onCancelled }
const _listeners = new Map()

// 连接状态
let _isConnecting = false
let _manualClose = false

/**
 * 获取或建立 WebSocket 连接
 */
function getConnection() {
  return new Promise((resolve, reject) => {
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      resolve(_ws)
      return
    }
    if (_isConnecting) {
      // 等待现有连接完成
      const check = setInterval(() => {
        if (_ws && _ws.readyState === WebSocket.OPEN) {
          clearInterval(check)
          resolve(_ws)
        } else if (!_isConnecting) {
          clearInterval(check)
          reject(new Error('WebSocket 连接失败'))
        }
      }, 100)
      return
    }

    _isConnecting = true
    _manualClose = false
    const ws = new WebSocket(WS_URL)

    ws.onopen = () => {
      _ws = ws
      _isConnecting = false
      _reconnectAttempts = 0
      console.log('[WS] 连接成功')
      startHeartbeat()
      resolve(ws)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        const { type, request_id, data } = msg
        const listener = _listeners.get(request_id)
        if (!listener) return

        switch (type) {
          case 'stream':
            listener.onStream?.(data)
            break
          case 'done':
            listener.onDone?.(data)
            _listeners.delete(request_id)
            break
          case 'error':
            listener.onError?.(data.message || '未知错误')
            _listeners.delete(request_id)
            break
          case 'cancelled':
            listener.onCancelled?.(data)
            _listeners.delete(request_id)
            break
          case 'pong':
            break
          default:
            console.warn('[WS] 未知消息类型:', type)
        }
      } catch (e) {
        console.warn('[WS] 解析消息失败:', e)
      }
    }

    ws.onclose = (event) => {
      _ws = null
      _isConnecting = false
      stopHeartbeat()

      if (!_manualClose && _reconnectAttempts < MAX_RECONNECT) {
        const delay = Math.min(1000 * Math.pow(2, _reconnectAttempts), 10000)
        console.log(`[WS] 断开，${delay}ms 后重连 (${_reconnectAttempts + 1}/${MAX_RECONNECT})`)
        _reconnectTimer = setTimeout(() => {
          _reconnectAttempts++
          getConnection().catch(() => {})
        }, delay)
      }

      // 通知所有活跃监听器
      for (const [rid, listener] of _listeners) {
        listener.onError?.('WebSocket 连接断开')
      }
      _listeners.clear()
    }

    ws.onerror = (error) => {
      _isConnecting = false
      console.error('[WS] 错误:', error)
      reject(new Error('WebSocket 连接失败'))
    }
  })
}

function startHeartbeat() {
  stopHeartbeat()
  _heartbeatTimer = setInterval(() => {
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify({ type: 'ping', request_id: '_hb', data: {} }))
    }
  }, HEARTBEAT_INTERVAL)
}

function stopHeartbeat() {
  if (_heartbeatTimer) {
    clearInterval(_heartbeatTimer)
    _heartbeatTimer = null
  }
}

/** 生成唯一请求 ID */
let _reqCounter = 0
function genRequestId(prefix = 'req') {
  return `${prefix}_${Date.now()}_${++_reqCounter}`
}

/**
 * 发送 WebSocket 请求并返回一个可取消的异步迭代器
 * 
 * @param {string} type - 任务类型
 * @param {object} data - 请求数据
 * @returns {{ stream: AsyncGenerator, cancel: Function, requestId: string }}
 */
export function wsRequest(type, data = {}) {
  const requestId = genRequestId(type)
  let cancelled = false

  // 创建可取消的异步迭代器
  const stream = (async function* () {
    const ws = await getConnection()

    // 使用 Promise 队列接收消息
    const queue = []
    let resolve = null
    let done = false
    let error = null

    _listeners.set(requestId, {
      onStream: (d) => {
        if (resolve) {
          const r = resolve
          resolve = null
          r({ value: d, done: false })
        } else {
          queue.push(d)
        }
      },
      onDone: (d) => {
        done = true
        if (resolve) {
          const r = resolve
          resolve = null
          // 包装 done 数据用特殊标记
          r({ value: { __done: true, ...d }, done: false })
        } else {
          queue.push({ __done: true, ...d })
        }
      },
      onError: (msg) => {
        error = msg
        done = true
        if (resolve) {
          const r = resolve
          resolve = null
          r({ value: undefined, done: true })
        }
      },
      onCancelled: (d) => {
        cancelled = true
        done = true
        if (resolve) {
          const r = resolve
          resolve = null
          r({ value: { __cancelled: true, ...d }, done: false })
        } else {
          queue.push({ __cancelled: true, ...d })
        }
      }
    })

    // 发送请求
    ws.send(JSON.stringify({ type, request_id: requestId, data }))

    // 迭代返回流式数据
    while (true) {
      if (queue.length > 0) {
        const item = queue.shift()
        if (item.__done || item.__cancelled) {
          yield item
          return
        }
        yield item
      } else if (done || cancelled) {
        if (error) throw new Error(error)
        return
      } else {
        // 等待下一个消息
        const result = await new Promise(r => { resolve = r })
        if (result.done) {
          if (error) throw new Error(error)
          return
        }
        const item = result.value
        if (item.__done || item.__cancelled) {
          yield item
          return
        }
        yield item
      }
    }
  })()

  const cancel = async () => {
    try {
      const ws = await getConnection()
      ws.send(JSON.stringify({ type: 'cancel', request_id: requestId, data: {} }))
    } catch (e) {
      console.warn('[WS] 取消请求失败:', e)
    }
  }

  return { stream, cancel, requestId }
}

/**
 * 检测 WebSocket 是否可用
 */
export async function isWsAvailable() {
  try {
    await getConnection()
    return true
  } catch {
    return false
  }
}

/**
 * 关闭 WebSocket 连接
 */
export function closeWs() {
  _manualClose = true
  if (_reconnectTimer) clearTimeout(_reconnectTimer)
  stopHeartbeat()
  if (_ws) {
    _ws.close()
    _ws = null
  }
  _listeners.clear()
}

export default { wsRequest, isWsAvailable, closeWs }
