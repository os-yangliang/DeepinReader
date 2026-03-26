import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import 'highlight.js/styles/github-dark.min.css'

// 亮色主题 hljs 覆盖（动态注入）
const lightHljsStyles = document.createElement('style')
lightHljsStyles.textContent = `
  [data-theme="light"] .hljs {
    background: #f6f8fa !important;
    color: #24292e !important;
    border: 1px solid rgba(0,0,0,0.08);
    border-radius: 8px;
  }
  [data-theme="light"] .hljs-keyword,
  [data-theme="light"] .hljs-selector-tag { color: #d73a49 !important; }
  [data-theme="light"] .hljs-string,
  [data-theme="light"] .hljs-addition { color: #032f62 !important; }
  [data-theme="light"] .hljs-comment { color: #6a737d !important; }
  [data-theme="light"] .hljs-function,
  [data-theme="light"] .hljs-title { color: #6f42c1 !important; }
  [data-theme="light"] .hljs-number,
  [data-theme="light"] .hljs-literal { color: #005cc5 !important; }
  [data-theme="light"] .hljs-built_in { color: #e36209 !important; }
`
document.head.appendChild(lightHljsStyles)

// 路由配置
const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('./views/Home.vue')
  },
  {
    path: '/analyze',
    name: 'Analyze',
    component: () => import('./views/Analyze.vue')
  },
  {
    path: '/translate',
    name: 'Translate',
    component: () => import('./views/Translate.vue')
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('./views/Chat.vue')
  },
  {
    path: '/codegen',
    name: 'CodeGen',
    component: () => import('./views/CodeGen.vue')
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('./views/History.vue')
  },
  {
    path: '/search',
    name: 'Search',
    component: () => import('./views/Search.vue')
  },
  {
    path: '/mindmap',
    name: 'MindMap',
    component: () => import('./views/MindMap.vue')
  },
  {
    path: '/compare',
    name: 'Compare',
    component: () => import('./views/Compare.vue')
  },
  {
    path: '/lab',
    name: 'ResearchLab',
    component: () => import('./views/ResearchLab.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const app = createApp(App)
app.use(router)
app.mount('#app')
