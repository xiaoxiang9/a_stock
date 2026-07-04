<script setup>
/*
 * 迷你折线图组件。
 *
 * 职责：
 * - 将后端趋势点绘制为 SVG 折线和面积阴影。
 * - 提供鼠标悬浮时的日期和值提示。
 *
 * 边界：
 * - 本组件只处理坐标映射和视觉交互，不解释趋势含义。
 */
import { computed, ref } from 'vue'

const props = defineProps({
  trend: { type: Array, default: () => [] },
  accent: { type: String, default: 'green' },
  chartId: { type: String, required: true },
})

const width = 320
const height = 112
const padding = 5
const hoveredIndex = ref(null)

// 将后端返回的趋势点映射为 SVG 坐标；组件只画图，不解释趋势。
const coordinates = computed(() => {
  if (!props.trend.length) return []
  const values = props.trend.map((point) => point.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  return props.trend.map((point, index) => ({
    x: padding + (index / Math.max(props.trend.length - 1, 1)) * (width - padding * 2),
    y: height - padding - ((point.value - min) / range) * (height - padding * 2),
  }))
})

const linePoints = computed(() => coordinates.value.map((point) => `${point.x},${point.y}`).join(' '))
const areaPath = computed(() => {
  // 面积阴影跟随折线，用于提升趋势图可读性。
  if (!coordinates.value.length) return ''
  const first = coordinates.value[0]
  const last = coordinates.value[coordinates.value.length - 1]
  return `M ${first.x} ${height} L ${linePoints.value.replaceAll(',', ' ')} L ${last.x} ${height} Z`
})
const hoveredPoint = computed(() => {
  if (hoveredIndex.value === null) return null
  return {
    ...props.trend[hoveredIndex.value],
    ...coordinates.value[hoveredIndex.value],
  }
})
const tooltipX = computed(() => Math.min(Math.max(hoveredPoint.value?.x || 0, 42), width - 42))
const tooltipY = computed(() => (hoveredPoint.value?.y || 0) < 42
  ? (hoveredPoint.value?.y || 0) + 10
  : (hoveredPoint.value?.y || 0) - 38)

function updateHover(event) {
  // 根据鼠标横向位置吸附到最近的数据点，方便查看具体日期和值。
  if (!props.trend.length) return
  const bounds = event.currentTarget.getBoundingClientRect()
  const ratio = Math.min(Math.max((event.clientX - bounds.left) / bounds.width, 0), 1)
  hoveredIndex.value = Math.round(ratio * (props.trend.length - 1))
}
</script>

<template>
  <div class="sparkline-wrap" :class="accent">
    <svg
      v-if="trend.length"
      :viewBox="`0 0 ${width} ${height}`"
      role="img"
      aria-label="最近一个月变化趋势，可移动鼠标查看具体值"
      @pointermove="updateHover"
      @pointerleave="hoveredIndex = null"
    >
      <defs>
        <linearGradient :id="`area-${chartId}`" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="currentColor" stop-opacity=".18" />
          <stop offset="100%" stop-color="currentColor" stop-opacity="0" />
        </linearGradient>
      </defs>
      <line v-for="row in 3" :key="row" x1="0" :y1="row * 28" :x2="width" :y2="row * 28" class="chart-grid" />
      <path :d="areaPath" :fill="`url(#area-${chartId})`" />
      <polyline :points="linePoints" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
      <circle v-if="coordinates.length" :cx="coordinates.at(-1).x" :cy="coordinates.at(-1).y" r="3.5" fill="currentColor" />
      <g v-if="hoveredPoint" class="chart-tooltip">
        <line :x1="hoveredPoint.x" y1="0" :x2="hoveredPoint.x" :y2="height" />
        <circle :cx="hoveredPoint.x" :cy="hoveredPoint.y" r="4.5" />
        <rect :x="tooltipX - 38" :y="tooltipY" width="76" height="31" rx="6" />
        <text :x="tooltipX" :y="tooltipY + 12">{{ hoveredPoint.date.slice(5) }}</text>
        <text :x="tooltipX" :y="tooltipY + 24" class="tooltip-value">{{ hoveredPoint.value.toFixed(2) }}</text>
      </g>
    </svg>
    <span v-else>暂无趋势数据</span>
  </div>
</template>
