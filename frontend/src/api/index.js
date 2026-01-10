import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'

// 生成或获取 Session ID
function getSessionId() {
  let sessionId = localStorage.getItem('session_id');
  if (!sessionId) {
    sessionId = 'sess_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
    localStorage.setItem('session_id', sessionId);
  }
  return sessionId;
}

// 创建 axios 实例
const apiClient = axios.create({
  baseURL,
  timeout: 30000,
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 1. 添加认证 Token
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    
    // 2. 添加 Session ID (用于隔离未登录用户的文档状态)
    config.headers['X-Session-ID'] = getSessionId();
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token 过期，清除并跳转（生产环境建议实现无感刷新）
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

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

// 通用 SSE 流式请求 Helper
function createSSEStream(url, options = {}) {
  const token = localStorage.getItem('access_token');
  const sessionId = getSessionId();
  
  const headers = {
    'Content-Type': 'application/json',
    'X-Session-ID': sessionId
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return async function* () {
    const response = await fetch(`${baseURL}${url}`, {
      method: options.method || 'POST',
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '请求失败');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.error) throw new Error(data.error);
            if (data.done) return;
            if (data.chunk) yield data.chunk;
          } catch (e) {
            console.warn('解析 SSE 数据失败:', e);
          }
        }
      }
    }
  }();
}

// 获取 SSE 流式对话的 Helper
function streamChat(message) {
  return createSSEStream('/chat/stream', { body: { message } });
}

// 获取 SSE 流式翻译的 Helper
function streamTranslate() {
  return createSSEStream('/translate/stream', { method: 'POST' });
}

// 论文相关 API
export const paperAPI = {
  // 上传并分析
  uploadAndAnalyze: async (file, onProgress) => {
    const formData = new FormData()
    formData.append('file', file)
    
    const res = await apiClient.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 300000, // 5 分钟超时，PDF 分析需要多个 LLM 调用
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percentCompleted)
        }
      }
    })
    return res.data
  },

  // 获取文档信息
  getDocument: async () => {
    const res = await apiClient.get('/document')
    return res.data
  },

  // 普通问答
  chat: async (message) => {
    const res = await apiClient.post('/chat', { message })
    return res.data
  },
  
  // 流式问答
  chatStream: (message) => streamChat(message),
  
  // 流式翻译
  translateStream: () => streamTranslate(),

  // 获取建议问题
  getSuggestions: async () => {
    const res = await apiClient.get('/suggestions')
    return res.data
  },

  // 清除对话
  clearChat: async () => {
    const res = await apiClient.post('/clear')
    return res.data
  },

  // 清除文档
  clearDocument: async () => {
    const res = await apiClient.delete('/document')
    return res.data
  },
  
  // 获取历史记录列表
  getHistory: async () => {
    const res = await apiClient.get('/history')
    return res.data
  },
  
  // 获取历史记录详情
  getHistoryDetail: async (historyId) => {
    const res = await apiClient.get(`/history/${historyId}`)
    return res.data
  },
  
  // 加载历史记录
  loadHistory: async (historyId) => {
    const res = await apiClient.post(`/history/${historyId}/load`)
    return res.data
  },
  
  // 删除历史记录
  deleteHistory: async (historyId) => {
    const res = await apiClient.delete(`/history/${historyId}`)
    return res.data
  },
  
  // 获取历史记录的对话
  getHistoryChat: async (historyId) => {
    const res = await apiClient.get(`/history/${historyId}/chat`)
    return res.data
  }
}

export default {
  ...paperAPI
}
