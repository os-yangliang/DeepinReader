import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'

// 创建 axios 实例（用于普通 JSON/表单请求）
const apiClient = axios.create({
  baseURL,
  timeout: 30000,
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 从 localStorage 获取 token
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // 处理 401 错误（未授权）
    if (error.response && error.response.status === 401) {
      // 清除本地存储的 token
      localStorage.removeItem('access_token');
      // 可以在这里跳转到登录页面
      // router.push('/login'); // 如果使用了路由
    }
    return Promise.reject(error);
  }
);

// 认证相关 API
export const authAPI = {
  // 用户注册
  register: (data) => apiClient.post('/register', data),
  
  // 用户登录
  login: (data) => apiClient.post('/login', data),
  
  // 获取用户资料
  getUserProfile: () => apiClient.get('/user/profile'),
  
  // 更新用户资料
  updateUserProfile: (data) => apiClient.put('/user/profile', data),
};

function getAuthHeaders() {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * SSE 解析：后端以 `data: {json}\n\n` 形式发送，其中 json 可能包含：
 * - { chunk: "..." }
 * - { done: true }
 * - { error: "..." }
 */
async function* streamChat(message) {
  const res = await fetch(`${baseURL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ message }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `Stream request failed: ${res.status}`)
  }

  if (!res.body) return

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''

    for (const event of events) {
      const lines = event.split('\n')
      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        const payload = line.slice('data:'.length).trim()
        if (!payload) continue
        const data = JSON.parse(payload)
        if (data.error) throw new Error(data.error)
        if (data.done) return
        if (typeof data.chunk === 'string') yield data.chunk
      }
    }
  }
}

// 论文分析/问答相关 API（返回后端 JSON 数据，而不是 axios Response）
export const paperAPI = {
  uploadAndAnalyze: async (file, onProgress) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await apiClient.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt) => {
        if (!onProgress) return
        if (!evt.total) return
        onProgress(evt.loaded / evt.total)
      },
    })
    return res.data
  },
  getDocument: async () => {
    const res = await apiClient.get('/document')
    return res.data
  },
  chat: async (message) => {
    const res = await apiClient.post('/chat', { message })
    return res.data
  },
  chatStream: (message) => streamChat(message),
  getSuggestions: async () => {
    const res = await apiClient.get('/suggestions')
    return res.data
  },
  clearChat: async () => {
    const res = await apiClient.post('/clear')
    return res.data
  },
  clearDocument: async () => {
    const res = await apiClient.delete('/document')
    return res.data
  },
  getHistory: async () => {
    const res = await apiClient.get('/history')
    return res.data
  },
  loadHistory: async (historyId) => {
    const res = await apiClient.post(`/history/${historyId}/load`)
    return res.data
  },
  deleteHistory: async (historyId) => {
    const res = await apiClient.delete(`/history/${historyId}`)
    return res.data
  },
  getHistoryChat: async (historyId) => {
    const res = await apiClient.get(`/history/${historyId}/chat`)
    return res.data
  },
}

// 默认导出：给 views 直接使用的便捷 API
export default {
  ...paperAPI,
}
