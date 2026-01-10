<template>
  <div class="min-h-screen relative">
    <!-- 背景效果 -->
    <div class="bg-mesh"></div>
    <div class="bg-grid"></div>
    
    <!-- 导航栏（始终显示） -->
    <nav class="fixed top-0 left-0 right-0 z-50 glass-card border-0 border-b border-white/5">
      <div class="max-w-7xl mx-auto px-6">
        <div class="flex items-center justify-between h-16">
          <!-- Logo -->
          <router-link to="/" class="flex items-center gap-3 group">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center text-2xl 
                        bg-gradient-to-br from-primary-500 to-accent-500 
                        group-hover:shadow-glow transition-all duration-300">
              📚
            </div>
            <span class="font-display text-xl font-semibold gradient-text">
              论文阅读助手
            </span>
          </router-link>
          
          <!-- 导航链接 -->
          <div class="flex items-center gap-2">
            <template v-for="link in navLinks" :key="link.to || link.label">
              <!-- 普通路由链接 -->
              <router-link 
                v-if="link.to"
                :to="link.to"
                class="nav-link px-4 py-2 rounded-lg text-gray-400 hover:text-white 
                       hover:bg-white/5 transition-all duration-300"
                :class="{ 'text-white bg-white/10': $route.path === link.to }"
              >
                <span class="mr-2">{{ link.icon }}</span>
                {{ link.label }}
              </router-link>
              <!-- 功能开发中的按钮 -->
              <button
                v-else
                @click="showDevToast"
                class="nav-link px-4 py-2 rounded-lg text-gray-400 hover:text-white 
                       hover:bg-white/5 transition-all duration-300 cursor-pointer"
              >
                <span class="mr-2">{{ link.icon }}</span>
                {{ link.label }}
              </button>
            </template>
            
            <!-- 用户头像/登录入口 -->
            <div class="relative ml-4">
              <!-- 已登录：显示用户头像和菜单 -->
              <template v-if="isLoggedIn">
                <button @click="toggleUserMenu" class="flex items-center gap-2 rounded-lg p-2 hover:bg-white/5 transition-all">
                  <img v-if="userProfile.avatar" :src="userProfile.avatar" alt="Avatar" class="w-8 h-8 rounded-full object-cover" />
                  <div v-else class="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center text-sm font-medium text-white">
                    {{ userProfile.nickname ? userProfile.nickname.charAt(0) : '?' }}
                  </div>
                  <span class="text-gray-300 text-sm hidden sm:inline">{{ userProfile.nickname || '用户' }}</span>
                  <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                  </svg>
                </button>
                
                <!-- 用户菜单下拉 -->
                <div v-if="showUserMenu" class="absolute right-0 mt-2 w-48 bg-gray-800/90 backdrop-blur-lg rounded-lg border border-white/10 shadow-xl z-50">
                  <div class="py-1">
                    <router-link to="/profile" class="block px-4 py-2 text-sm text-gray-300 hover:bg-white/10" @click="hideUserMenu">个人资料</router-link>
                    <button @click="handleLogout" class="w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-white/10">退出登录</button>
                  </div>
                </div>
              </template>
              
              <!-- 未登录：显示默认头像，点击跳转登录 -->
              <template v-else>
                <router-link to="/login" class="flex items-center gap-2 rounded-lg p-2 hover:bg-white/5 transition-all">
                  <div class="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
                    <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                    </svg>
                  </div>
                  <span class="text-gray-400 text-sm hidden sm:inline">登录</span>
                </router-link>
              </template>
            </div>
          </div>
        </div>
      </div>
    </nav>
    
    <!-- 功能开发中提示 Toast -->
    <Transition name="toast">
      <div 
        v-if="showToast" 
        class="fixed top-24 left-1/2 -translate-x-1/2 z-[100] 
               glass-card px-6 py-3 rounded-xl border border-amber-500/30 
               bg-gradient-to-r from-amber-500/10 to-orange-500/10
               shadow-lg shadow-amber-500/10"
      >
        <div class="flex items-center gap-3">
          <span class="text-2xl animate-bounce">🚧</span>
          <span class="text-amber-300 font-medium">功能开发中，敬请期待！</span>
        </div>
      </div>
    </Transition>
    
    <!-- 主内容区 -->
    <main class="relative z-10 pt-24 pb-12 px-6 min-h-[calc(100vh-120px)]">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    
    <!-- 页脚 -->
    <footer class="relative z-10 border-t border-white/5 py-6">
      <div class="max-w-7xl mx-auto px-6 text-center text-gray-500 text-sm">
        <p>🛠️ 基于 LangChain 多智能体架构 | 📚 论文阅读助手 v2.0</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { authAPI } from '@/api/index.js'

const router = useRouter()
const route = useRoute()

const navLinks = [
  { to: '/', icon: '🏠', label: '首页' },
  { to: '/analyze', icon: '📊', label: '分析' },
  { to: '/translate', icon: '🌐', label: '翻译' },
  { to: '/chat', icon: '💬', label: '问答' },
  { to: '/history', icon: '📚', label: '历史' },
  { to: null, icon: '💻', label: '代码' }  // 功能开发中
]

// 用户状态
const isLoggedIn = ref(false)
const userProfile = ref({})
const showUserMenu = ref(false)
const showToast = ref(false)

let toastTimer = null

// 提供登录状态给子组件
provide('isLoggedIn', isLoggedIn)

// 检查登录状态（不强制跳转）
const checkAuthStatus = async () => {
  const token = localStorage.getItem('access_token')
  if (token) {
    try {
      const response = await authAPI.getUserProfile()
      userProfile.value = response.data
      isLoggedIn.value = true
    } catch (error) {
      console.error('获取用户信息失败:', error)
      localStorage.removeItem('access_token')
      isLoggedIn.value = false
      userProfile.value = {}
    }
  } else {
    isLoggedIn.value = false
    userProfile.value = {}
  }
}

// 处理登出
const handleLogout = () => {
  localStorage.removeItem('access_token')
  isLoggedIn.value = false
  userProfile.value = {}
  hideUserMenu()
  router.push('/')
}

// 显示/隐藏用户菜单
const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value
}

const hideUserMenu = () => {
  showUserMenu.value = false
}

// 点击外部关闭用户菜单
const handleClickOutside = (event) => {
  const userMenu = event.target.closest('.relative.ml-4')
  if (!userMenu) {
    hideUserMenu()
  }
}

// Toast 提示
const showDevToast = () => {
  showToast.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    showToast.value = false
  }, 2000)
}

onMounted(async () => {
  await checkAuthStatus()
  
  // 监听点击事件以关闭用户菜单
  document.addEventListener('click', handleClickOutside)
})

// 监听路由变化，刷新登录状态
router.afterEach(async () => {
  await checkAuthStatus()
})
</script>

<style scoped>
.page-enter-active {
  animation: slideUp 0.4s ease-out;
}

.page-leave-active {
  animation: fadeOut 0.2s ease-in;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeOut {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}

/* Toast 动画 */
.toast-enter-active {
  animation: toastIn 0.3s ease-out;
}

.toast-leave-active {
  animation: toastOut 0.3s ease-in;
}

@keyframes toastIn {
  from {
    opacity: 0;
    transform: translate(-50%, -20px);
  }
  to {
    opacity: 1;
    transform: translate(-50%, 0);
  }
}

@keyframes toastOut {
  from {
    opacity: 1;
    transform: translate(-50%, 0);
  }
  to {
    opacity: 0;
    transform: translate(-50%, -20px);
  }
}
</style>
