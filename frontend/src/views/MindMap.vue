<template>
  <div class="h-[calc(100vh-80px)] flex flex-col">
    <!-- 顶部工具栏 -->
    <div class="h-14 toolbar-glass px-6 flex items-center justify-between z-20">
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <Network :size="20" class="text-violet-400" />
          <h1 class="text-lg font-semibold text-white">思维导图</h1>
        </div>
        <div v-if="store.documentInfo" class="flex items-center gap-2 text-gray-400 text-sm border-l border-white/10 pl-4">
          <FileText :size="14" />
          <span class="max-w-[200px] truncate">{{ store.documentInfo.filename }}</span>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button v-if="store.pdfUrl && !isGenerating" @click="generate" class="btn-glow px-5 py-2 text-sm flex items-center gap-2">
          <Sparkles :size="16" />
          {{ hasData ? '重新生成' : '生成思维导图' }}
        </button>
        <div v-if="isGenerating" class="flex items-center gap-2 text-violet-400 text-sm">
          <Loader2 :size="16" class="animate-spin" />
          <span>正在生成...</span>
        </div>
        <button v-if="hasData" @click="downloadPng" class="action-btn">
          <Download :size="13" />
          下载 PNG
        </button>
      </div>
    </div>

    <!-- 主体 -->
    <div class="flex-1 overflow-hidden relative">
      
      <!-- 未加载文档 -->
      <div v-if="!store.pdfUrl" class="absolute inset-0 flex items-center justify-center">
        <div class="text-center max-w-md">
          <div class="empty-icon-wrapper mx-auto mb-6">
            <Network :size="36" class="text-violet-400/60" />
          </div>
          <h3 class="text-xl font-bold text-white mb-2">尚未加载文档</h3>
          <p class="text-gray-400 mb-8 text-sm">请先上传并分析论文。</p>
          <router-link to="/analyze" class="btn-glow px-6 py-2.5 text-sm inline-flex items-center gap-2">
            <Upload :size="16" /> 去上传
          </router-link>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!hasData && !isGenerating && !error" class="absolute inset-0 flex items-center justify-center">
        <div class="text-center">
          <div class="empty-icon-wrapper mx-auto mb-6">
            <Network :size="36" class="text-violet-400/40" />
          </div>
          <h3 class="text-lg font-semibold text-white mb-2">交互式思维导图</h3>
          <p class="text-gray-400 text-sm mb-6">可拖拽、缩放的力导向图 · 基于论文结构生成</p>
          <button @click="generate" class="btn-glow px-6 py-2.5 text-sm inline-flex items-center gap-2">
            <Sparkles :size="16" /> 开始生成
          </button>
        </div>
      </div>

      <!-- 错误 -->
      <div v-if="error" class="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-2 rounded-xl">
        {{ error }}
      </div>

      <!-- D3 画布 -->
      <div ref="svgContainer" class="w-full h-full"></div>

      <!-- 提示 -->
      <div v-if="hasData" class="absolute bottom-4 right-4 text-[11px] text-gray-600">
        拖拽节点 · 滚轮缩放 · 按住拖动画布
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as d3 from 'd3'
import api from '../api'
import { store } from '../store'
import { 
  Network, FileText, Sparkles, Loader2, Upload, Download, RefreshCw
} from 'lucide-vue-next'

const svgContainer = ref(null)
const isGenerating = ref(false)
const hasData = ref(false)
const error = ref('')
let simulation = null

// 颜色方案
const COLORS = [
  '#8b5cf6', '#6366f1', '#3b82f6', '#0ea5e9', '#06b6d4',
  '#14b8a6', '#10b981', '#f59e0b', '#ef4444', '#ec4899',
]

const getDepthColor = (depth, index) => {
  if (depth === 0) return '#8b5cf6'
  if (depth === 1) return COLORS[index % COLORS.length]
  return COLORS[index % COLORS.length] + 'cc'
}

const getNodeRadius = (depth) => {
  if (depth === 0) return 35
  if (depth === 1) return 22
  return 14
}

// 将树形数据展平为 nodes + links
const flattenTree = (tree) => {
  const nodes = []
  const links = []
  let id = 0

  const walk = (node, depth, parentId, branchIndex) => {
    const nodeId = id++
    nodes.push({
      id: nodeId,
      name: node.name,
      depth,
      branchIndex,
      children: node.children?.length || 0,
    })
    if (parentId !== null) {
      links.push({ source: parentId, target: nodeId })
    }
    if (node.children) {
      node.children.forEach((child, i) => {
        walk(child, depth + 1, nodeId, depth === 0 ? i : branchIndex)
      })
    }
  }

  walk(tree, 0, null, 0)
  return { nodes, links }
}

const generate = async () => {
  isGenerating.value = true
  error.value = ''
  
  try {
    const res = await api.generateMindmap()
    const tree = res.tree
    if (!tree || !tree.name) throw new Error('返回数据格式错误')
    
    hasData.value = true
    await nextTick()
    renderGraph(tree)
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    isGenerating.value = false
  }
}

const renderGraph = (tree) => {
  const container = svgContainer.value
  if (!container) return

  // 清除旧图
  d3.select(container).selectAll('*').remove()
  if (simulation) simulation.stop()

  const width = container.clientWidth
  const height = container.clientHeight
  const { nodes, links } = flattenTree(tree)

  // 创建 SVG
  const svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', [0, 0, width, height])

  // 定义滤镜（发光效果）
  const defs = svg.append('defs')
  
  const glow = defs.append('filter').attr('id', 'glow')
  glow.append('feGaussianBlur').attr('stdDeviation', '4').attr('result', 'coloredBlur')
  const feMerge = glow.append('feMerge')
  feMerge.append('feMergeNode').attr('in', 'coloredBlur')
  feMerge.append('feMergeNode').attr('in', 'SourceGraphic')

  // 渐变背景
  const bgGrad = defs.append('radialGradient').attr('id', 'bg-grad')
  bgGrad.append('stop').attr('offset', '0%').attr('stop-color', 'rgba(139,92,246,0.05)')
  bgGrad.append('stop').attr('offset', '100%').attr('stop-color', 'transparent')
  
  svg.append('circle')
    .attr('cx', width / 2).attr('cy', height / 2).attr('r', Math.min(width, height) * 0.4)
    .attr('fill', 'url(#bg-grad)')

  // 缩放容器
  const g = svg.append('g')
  const zoom = d3.zoom()
    .scaleExtent([0.3, 3])
    .on('zoom', (event) => g.attr('transform', event.transform))
  svg.call(zoom)
  svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2))

  // 力仿真
  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(d => {
      const srcDepth = d.source.depth !== undefined ? d.source.depth : 0
      return srcDepth === 0 ? 160 : srcDepth === 1 ? 100 : 70
    }))
    .force('charge', d3.forceManyBody().strength(d => d.depth === 0 ? -800 : -300))
    .force('center', d3.forceCenter(0, 0))
    .force('collision', d3.forceCollide().radius(d => getNodeRadius(d.depth) + 20))

  // 绘制连线
  const link = g.append('g')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', d => {
      const src = nodes[d.source.id !== undefined ? d.source.id : d.source]
      return getDepthColor(1, src?.branchIndex || 0)
    })
    .attr('stroke-opacity', 0.3)
    .attr('stroke-width', d => {
      const src = nodes[d.source.id !== undefined ? d.source.id : d.source]
      return src?.depth === 0 ? 3 : 2
    })

  // 绘制节点组
  const node = g.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .call(d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended)
    )
    .style('cursor', 'grab')

  // 节点光晕
  node.append('circle')
    .attr('r', d => getNodeRadius(d.depth) + 8)
    .attr('fill', d => getDepthColor(d.depth, d.branchIndex))
    .attr('opacity', 0)
    .transition().duration(800).delay((d, i) => i * 50)
    .attr('opacity', d => d.depth === 0 ? 0.15 : 0.08)

  // 节点圆
  node.append('circle')
    .attr('r', 0)
    .attr('fill', d => {
      const col = getDepthColor(d.depth, d.branchIndex)
      return d.depth === 0 ? col : col + '20'
    })
    .attr('stroke', d => getDepthColor(d.depth, d.branchIndex))
    .attr('stroke-width', d => d.depth === 0 ? 3 : 2)
    .attr('filter', d => d.depth <= 1 ? 'url(#glow)' : null)
    .transition().duration(600).delay((d, i) => i * 40)
    .attr('r', d => getNodeRadius(d.depth))

  // 节点文字
  node.append('text')
    .text(d => d.name)
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'central')
    .attr('fill', d => d.depth === 0 ? 'white' : '#e2e8f0')
    .attr('font-size', d => d.depth === 0 ? '13px' : d.depth === 1 ? '11px' : '10px')
    .attr('font-weight', d => d.depth <= 1 ? '600' : '400')
    .attr('dy', d => getNodeRadius(d.depth) + 16)
    .attr('opacity', 0)
    .transition().duration(500).delay((d, i) => i * 50 + 300)
    .attr('opacity', 1)

  // 悬浮效果
  node.on('mouseenter', function(event, d) {
    d3.select(this).select('circle:nth-child(2)')
      .transition().duration(200)
      .attr('r', getNodeRadius(d.depth) + 4)
      .attr('stroke-width', 3)
    d3.select(this).select('circle:nth-child(1)')
      .transition().duration(200)
      .attr('opacity', 0.25)
  }).on('mouseleave', function(event, d) {
    d3.select(this).select('circle:nth-child(2)')
      .transition().duration(200)
      .attr('r', getNodeRadius(d.depth))
      .attr('stroke-width', d.depth === 0 ? 3 : 2)
    d3.select(this).select('circle:nth-child(1)')
      .transition().duration(200)
      .attr('opacity', d.depth === 0 ? 0.15 : 0.08)
  })

  // 力仿真 tick
  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)
    
    node.attr('transform', d => `translate(${d.x},${d.y})`)
  })

  function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart()
    d.fx = d.x
    d.fy = d.y
    d3.select(this).style('cursor', 'grabbing')
  }

  function dragged(event, d) {
    d.fx = event.x
    d.fy = event.y
  }

  function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0)
    d.fx = null
    d.fy = null
    d3.select(this).style('cursor', 'grab')
  }
}

const downloadPng = () => {
  const svgEl = svgContainer.value?.querySelector('svg')
  if (!svgEl) return
  
  const clone = svgEl.cloneNode(true)
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  
  const svgData = new XMLSerializer().serializeToString(clone)
  const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(svgBlob)
  
  const img = new Image()
  img.onload = () => {
    const canvas = document.createElement('canvas')
    const scale = 2
    canvas.width = img.width * scale
    canvas.height = img.height * scale
    const ctx = canvas.getContext('2d')
    ctx.scale(scale, scale)
    ctx.fillStyle = '#0f172a'
    ctx.fillRect(0, 0, img.width, img.height)
    ctx.drawImage(img, 0, 0)
    
    canvas.toBlob((blob) => {
      const a = document.createElement('a')
      const name = (store.documentInfo?.filename || 'paper').replace(/\.[^.]+$/, '')
      a.href = URL.createObjectURL(blob)
      a.download = `${name}_mindmap.png`
      a.click()
    }, 'image/png')
    URL.revokeObjectURL(url)
  }
  img.src = url
}

onBeforeUnmount(() => {
  if (simulation) simulation.stop()
})
</script>

<style scoped>
.toolbar-glass {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.empty-icon-wrapper {
  width: 80px;
  height: 80px;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(139, 92, 246, 0.08);
  border: 1px solid rgba(139, 92, 246, 0.12);
}

.btn-glow {
  display: inline-flex;
  align-items: center;
  font-weight: 600;
  color: white;
  border-radius: 12px;
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
  transition: all 0.3s;
}
.btn-glow:hover {
  box-shadow: 0 8px 25px rgba(139, 92, 246, 0.4);
  transform: translateY(-2px);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(148, 163, 184, 0.8);
  font-size: 12px;
  transition: all 0.2s;
  cursor: pointer;
}
.action-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}
</style>
