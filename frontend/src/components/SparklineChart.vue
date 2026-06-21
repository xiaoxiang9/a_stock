<script setup>
import { computed } from 'vue'

const props = defineProps({
  trend: { type: Array, default: () => [] },
  accent: { type: String, default: 'green' },
  chartId: { type: String, required: true },
})

const width = 320
const height = 112
const padding = 5

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
  if (!coordinates.value.length) return ''
  const first = coordinates.value[0]
  const last = coordinates.value[coordinates.value.length - 1]
  return `M ${first.x} ${height} L ${linePoints.value.replaceAll(',', ' ')} L ${last.x} ${height} Z`
})
</script>

<template>
  <div class="sparkline-wrap" :class="accent">
    <svg v-if="trend.length" :viewBox="`0 0 ${width} ${height}`" role="img" aria-label="最近一个月变化趋势">
      <defs>
        <linearGradient :id="`area-${chartId}`" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="currentColor" stop-opacity=".25" />
          <stop offset="100%" stop-color="currentColor" stop-opacity="0" />
        </linearGradient>
      </defs>
      <line v-for="row in 3" :key="row" x1="0" :y1="row * 28" :x2="width" :y2="row * 28" class="chart-grid" />
      <path :d="areaPath" :fill="`url(#area-${chartId})`" />
      <polyline :points="linePoints" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
      <circle v-if="coordinates.length" :cx="coordinates.at(-1).x" :cy="coordinates.at(-1).y" r="3.5" fill="currentColor" />
    </svg>
    <span v-else>暂无趋势数据</span>
  </div>
</template>
