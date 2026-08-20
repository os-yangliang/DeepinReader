import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import 'highlight.js/styles/github-dark.min.css'
import PageToolbar from './components/PageToolbar.vue'
import EmptyState from './components/EmptyState.vue'
import PdfReader from './components/PdfReader.vue'

// 路由配置
const routes = [
  { path: '/', name: 'Home', component: () => import('./views/Home.vue') },
  { path: '/analyze', name: 'Analyze', component: () => import('./views/Analyze.vue') },
  { path: '/translate', name: 'Translate', component: () => import('./views/Translate.vue') },
  { path: '/chat', name: 'Chat', component: () => import('./views/Chat.vue') },
  { path: '/history', name: 'History', component: () => import('./views/History.vue') },
  { path: '/search', name: 'Search', component: () => import('./views/Search.vue') },
  { path: '/compare', name: 'Compare', component: () => import('./views/Compare.vue') },
  { path: '/lab', name: 'ResearchLab', component: () => import('./views/ResearchLab.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const app = createApp(App)
app.component('PageToolbar', PageToolbar)
app.component('EmptyState', EmptyState)
app.component('PdfReader', PdfReader)
app.use(router)
app.mount('#app')