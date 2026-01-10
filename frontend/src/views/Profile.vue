<template>
  <div class="max-w-4xl mx-auto p-6">
    <div class="glass-card rounded-2xl border border-white/10 p-8">
      <h2 class="text-2xl font-bold text-white mb-6">个人资料</h2>
      
      <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        <!-- 头像区域 -->
        <div class="md:col-span-1 flex flex-col items-center">
          <div class="relative mb-6">
            <img 
              v-if="userProfile.avatar" 
              :src="userProfile.avatar" 
              alt="Avatar" 
              class="w-32 h-32 rounded-full object-cover border-4 border-white/10"
            />
            <div 
              v-else 
              class="w-32 h-32 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center text-3xl font-medium text-white"
            >
              {{ userProfile.nickname ? userProfile.nickname.charAt(0) : '?' }}
            </div>
            <button 
              @click="changeAvatar" 
              class="absolute bottom-2 right-2 bg-primary-500 hover:bg-primary-600 text-white rounded-full p-2 shadow-lg transition-colors"
              title="更换头像"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"></path>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"></path>
              </svg>
            </button>
          </div>
          <button 
            @click="logout" 
            class="w-full py-2 px-4 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors border border-red-500/30"
          >
            退出登录
          </button>
        </div>
        
        <!-- 个人信息表单 -->
        <div class="md:col-span-2">
          <form @submit.prevent="updateProfile" class="space-y-6">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">手机号</label>
              <input
                v-model="userProfile.phone"
                type="tel"
                class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 
                       text-white placeholder-gray-500 focus:outline-none focus:ring-2 
                       focus:ring-primary-500 focus:border-transparent transition-all
                       disabled:opacity-50"
                readonly
                disabled
              />
              <p class="text-xs text-gray-500 mt-1">手机号不可修改</p>
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">用户名 *</label>
              <input
                v-model="editForm.nickname"
                type="text"
                class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 
                       text-white placeholder-gray-500 focus:outline-none focus:ring-2 
                       focus:ring-primary-500 focus:border-transparent transition-all"
                placeholder="请输入用户名"
                required
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">头像URL</label>
              <input
                v-model="editForm.avatar"
                type="url"
                class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 
                       text-white placeholder-gray-500 focus:outline-none focus:ring-2 
                       focus:ring-primary-500 focus:border-transparent transition-all"
                placeholder="请输入头像URL"
              />
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">年龄</label>
                <input
                  v-model.number="editForm.age"
                  type="number"
                  min="1"
                  max="120"
                  class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 
                         text-white placeholder-gray-500 focus:outline-none focus:ring-2 
                         focus:ring-primary-500 focus:border-transparent transition-all"
                  placeholder="年龄"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">职业</label>
                <input
                  v-model="editForm.profession"
                  type="text"
                  class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 
                         text-white placeholder-gray-500 focus:outline-none focus:ring-2 
                         focus:ring-primary-500 focus:border-transparent transition-all"
                  placeholder="职业"
                />
              </div>
            </div>
            
            <div class="flex gap-4 pt-4">
              <button
                type="submit"
                class="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-primary-500 to-accent-500
                       text-white font-semibold hover:shadow-glow transition-all duration-300
                       disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="updating"
              >
                <span v-if="!updating">保存更改</span>
                <span v-else class="flex items-center justify-center">
                  <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  保存中...
                </span>
              </button>
              <button
                type="button"
                @click="resetForm"
                class="py-3 px-6 rounded-xl bg-white/10 text-gray-300 hover:bg-white/20
                       border border-white/20 transition-all duration-300"
              >
                取消
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { authAPI } from '@/api/index.js'

const router = useRouter()

// 用户资料
const userProfile = ref({})
const updating = ref(false)

// 编辑表单
const editForm = reactive({
  nickname: '',
  avatar: '',
  age: null,
  profession: ''
})

// 获取用户资料
const fetchUserProfile = async () => {
  try {
    const response = await authAPI.getUserProfile()
    userProfile.value = response.data
    // 初始化编辑表单
    editForm.nickname = response.data.nickname
    editForm.avatar = response.data.avatar || ''
    editForm.age = response.data.age || null
    editForm.profession = response.data.profession || ''
  } catch (error) {
    console.error('获取用户资料失败:', error)
    if (error.response?.status === 401) {
      router.push('/login')
    }
  }
}

// 更新用户资料
const updateProfile = async () => {
  if (!editForm.nickname.trim()) {
    alert('用户名不能为空')
    return
  }

  updating.value = true
  try {
    await authAPI.updateUserProfile({
      nickname: editForm.nickname.trim(),
      avatar: editForm.avatar.trim() || null,
      age: editForm.age || null,
      profession: editForm.profession.trim() || null
    })
    alert('资料更新成功')
    await fetchUserProfile() // 重新获取更新后的资料
  } catch (error) {
    console.error('更新资料失败:', error)
    alert('更新资料失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    updating.value = false
  }
}

// 更换头像
const changeAvatar = () => {
  const newAvatar = prompt('请输入新的头像URL:')
  if (newAvatar) {
    editForm.avatar = newAvatar
  }
}

// 重置表单
const resetForm = () => {
  editForm.nickname = userProfile.value.nickname
  editForm.avatar = userProfile.value.avatar || ''
  editForm.age = userProfile.value.age || null
  editForm.profession = userProfile.value.profession || ''
}

// 退出登录
const logout = () => {
  if (confirm('确定要退出登录吗？')) {
    localStorage.removeItem('access_token')
    router.push('/')
  }
}

onMounted(() => {
  fetchUserProfile()
})
</script>

<style scoped>
.glass-card {
  background: rgba(30, 30, 40, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
</style>
