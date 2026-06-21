<script setup>
import { computed } from 'vue'
import SparklineChart from './SparklineChart.vue'

const props = defineProps({ indicator: { type: Object, required: true } })

const change = computed(() => {
  const trend = props.indicator.trend || []
  if (trend.length < 2 || trend[0].value === 0) return null
  return ((trend.at(-1).value - trend[0].value) / Math.abs(trend[0].value)) * 100
})

const dateRange = computed(() => {
  const trend = props.indicator.trend || []
  if (!trend.length) return '最近一个月'
  const format = (value) => value.slice(5).replace('-', '/')
  return `${format(trend[0].date)} — ${format(trend.at(-1).date)}`
})
</script>

<template>
  <article class="metric-card" :class="{ met: indicator.met, unavailable: indicator.value === null }">
    <header>
      <div>
        <span class="metric-name">{{ indicator.name }}</span>
        <small>{{ indicator.subtitle }}</small>
      </div>
      <span class="condition-badge" :class="indicator.met ? 'met' : 'waiting'">
        {{ indicator.operator }} {{ indicator.threshold }}
      </span>
    </header>

    <div class="metric-value-row">
      <strong>{{ indicator.value === null ? '—' : indicator.value.toFixed(2) }}</strong>
      <div>
        <span v-if="indicator.value !== null" :class="indicator.met ? 'positive' : 'neutral'">
          {{ indicator.met ? '条件已满足' : '条件未满足' }}
        </span>
        <span v-else class="warning">数据暂不可用</span>
        <small>截至 {{ indicator.updated_at || '—' }}</small>
      </div>
    </div>

    <div class="trend-heading">
      <span>近一月趋势</span>
      <span v-if="change !== null" :class="change >= 0 ? 'up' : 'down'">
        {{ change >= 0 ? '+' : '' }}{{ change.toFixed(1) }}%
      </span>
    </div>
    <SparklineChart :trend="indicator.trend" :chart-id="indicator.key" :accent="indicator.met ? 'green' : 'blue'" />
    <div class="trend-range"><span>{{ dateRange }}</span><span>{{ indicator.trend.length }} 个数据点</span></div>

    <footer class="metric-footer">
      <div><span>口径</span><p>{{ indicator.methodology }}</p></div>
      <a :href="indicator.source.url" target="_blank" rel="noreferrer">
        {{ indicator.source.name }} <span aria-hidden="true">↗</span>
      </a>
    </footer>
  </article>
</template>
