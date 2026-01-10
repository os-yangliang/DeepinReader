<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 to-gray-800 p-4">
    <div class="glass-card w-full max-w-md p-8 rounded-2xl border border-white/10 shadow-2xl">
      <div class="text-center mb-8">
        <div class="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl 
                    bg-gradient-to-br from-primary-500 to-accent-500 mx-auto mb-4">
          📚
        </div>
        <h1 class="text-2xl font-bold text-white">论文阅读助手</h1>
        <p class="text-gray-400 mt-2">{{ showRegister ? '创建新账户' : '登录您的账户' }}</p>
      </div>

      <!-- 登录表单 -->
      <form @submit.prevent="handleLogin" v-if="!showRegister">
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">手机号</label>
            <input
              v-model="loginForm.phone"
              type="tel"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 
                     text-white placeholder-gray-500 focus:outline-none focus:ring-2 
                     focus:ring-primary-500 focus:border-transparent transition-all"
              placeholder="请输入手机号"
              required
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">密码</label>
            <input
              v-model="loginForm.password"
              type="password"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 
                     text-white placeholder-gray-500 focus:outline-none focus:ring-2 
                     focus:ring-primary-500 focus:border-transparent transition-all"
              placeholder="请输入密码"
              required
            />
          </div>
        </div>

        <button
          type="submit"
          class="w-full mt-6 py-3 px-4 rounded-xl bg-gradient-to-r from-primary-500 to-accent-500
                 text-white font-semibold hover:shadow-glow transition-all duration-300
                 disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="loading"
        >
          <span v-if="!loading">登录</span>
          <span v-else class="flex items-center justify-center">
            <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            登录中...
          </span>
        </button>

        <div class="mt-4 text-center">
          <button
            type="button"
            @click="showRegister = true"
            class="text-primary-400 hover:text-primary-300 text-sm font-medium"
          >
            还没有账号？立即注册
          </button>
        </div>
      </form>

      <!-- 注册表单（简化版：用户名、手机号、密码） -->
      <form @submit.prevent="handleRegister" v-else>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">用户名</label>
            <input
              v-model="registerForm.nickname"
              type="text"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 
                     text-white placeholder-gray-500 focus:outline-none focus:ring-2 
                     focus:ring-primary-500 focus:border-transparent transition-all"
              placeholder="请输入用户名"
              required
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">手机号</label>
            <input
              v-model="registerForm.phone"
              type="tel"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 
                     text-white placeholder-gray-500 focus:outline-none focus:ring-2 
                     focus:ring-primary-500 focus:border-transparent transition-all"
              placeholder="请输入手机号"
              required
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">密码</label>
            <input
              v-model="registerForm.password"
              type="password"
              maxlength="50"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 
                     text-white placeholder-gray-500 focus:outline-none focus:ring-2 
                     focus:ring-primary-500 focus:border-transparent transition-all"
              placeholder="请输入密码（至少6位）"
              required
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">确认密码</label>
            <input
              v-model="registerForm.confirmPassword"
              type="password"
              maxlength="50"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 
                     text-white placeholder-gray-500 focus:outline-none focus:ring-2 
                     focus:ring-primary-500 focus:border-transparent transition-all"
              placeholder="请再次输入密码"
              required
            />
          </div>
        </div>

        <button
          type="submit"
          class="w-full mt-6 py-3 px-4 rounded-xl bg-gradient-to-r from-primary-500 to-accent-500
                 text-white font-semibold hover:shadow-glow transition-all duration-300
                 disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="loading"
        >
          <span v-if="!loading">注册</span>
          <span v-else class="flex items-center justify-center">
            <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            注册中...
          </span>
        </button>

        <div class="mt-4 text-center">
          <button
            type="button"
            @click="showRegister = false"
            class="text-primary-400 hover:text-primary-300 text-sm font-medium"
          >
            ← 返回登录
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { authAPI } from '@/api/index.js'

const router = useRouter()

// 登录表单
const loginForm = reactive({
  phone: '',
  password: ''
})

// 注册表单（简化版）
const registerForm = reactive({
  nickname: '',
  phone: '',
  password: '',
  confirmPassword: ''
})

// 状态
const loading = ref(false)
const showRegister = ref(false)

// 处理登录
const handleLogin = async () => {
  if (loginForm.password.length < 6) {
    alert('密码长度不能少于6位')
    return
  }

  loading.value = true
  try {
    const response = await authAPI.login(loginForm)
    const { access_token } = response.data
    localStorage.setItem('access_token', access_token)
    router.push('/')
  } catch (error) {
    console.error('登录失败:', error)
    alert('登录失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

// 处理注册
const handleRegister = async () => {
  if (registerForm.password !== registerForm.confirmPassword) {
    alert('两次输入的密码不一致')
    return
  }

  if (registerForm.password.length < 6) {
    alert('密码长度不能少于6位')
    return
  }

  if (!registerForm.phone || !registerForm.nickname) {
    alert('请填写所有必填项')
    return
  }

  loading.value = true
  try {
    const response = await authAPI.register({
      phone: registerForm.phone,
      password: registerForm.password,
      nickname: registerForm.nickname
    })
    const { access_token } = response.data
    localStorage.setItem('access_token', access_token)
    router.push('/')
  } catch (error) {
    console.error('注册失败:', error)
    alert('注册失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.glass-card {
  background: rgba(30, 30, 40, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
</style>
