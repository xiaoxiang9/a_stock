<script setup>
import { computed, onMounted, ref } from 'vue'
import MetricCard from '../components/MetricCard.vue'

const data = ref(null)
const loading = ref(true)
const error = ref('')
const refreshing = ref(false)

const generatedTime = computed(() => {
  if (!data.value?.generated_at) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(data.value.generated_at))
})

async function loadDecision(force = false) {
  error.value = ''
  if (force) refreshing.value = true
  else loading.value = true
  try {
    const response = await fetch(`/api/modules/etf-buy-decision${force ? '?refresh=true' : ''}`)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    data.value = await response.json()
  } catch {
    error.value = '无法连接决策引擎，请确认后端服务已经启动。'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

onMounted(() => loadDecision())
</script>

<template>
  <section class="decision-page content-width">
    <div class="module-breadcrumb"><a href="#/">首页</a><span>/</span><span>美股 ETF 买入决策</span></div>

    <header class="decision-header">
      <div>
        <p class="section-label">MODULE 01 · US ETF</p>
        <h1>美股 ETF<br>买入决策</h1>
        <p>用三项极端恐慌指标建立纪律化入场信号。</p>
      </div>
      <button class="refresh-button" :disabled="refreshing" @click="loadDecision(true)">
        <span :class="{ spinning: refreshing }">↻</span> {{ refreshing ? '刷新中' : '刷新数据' }}
      </button>
    </header>

    <div v-if="error" class="error-panel">
      <span>!</span><div><strong>数据加载失败</strong><p>{{ error }}</p></div>
      <button @click="loadDecision()">重试</button>
    </div>

    <template v-else-if="loading">
      <div class="decision-skeleton shimmer"></div>
      <div class="metric-grid"><div v-for="item in 3" :key="item" class="metric-skeleton shimmer"></div></div>
    </template>

    <template v-else-if="data">
      <section class="decision-result" :class="{ buy: data.decision.should_buy, pending: !data.decision.ready }">
        <div class="signal-orb"><span></span></div>
        <div class="decision-copy">
          <span class="decision-kicker">CURRENT DECISION</span>
          <h2>{{ data.decision.label }}</h2>
          <p>{{ data.decision.summary }}</p>
        </div>
        <div class="decision-score">
          <strong>{{ data.decision.met_count }}<small>/{{ data.decision.total_count }}</small></strong>
          <span>条件满足</span>
        </div>
        <div class="rule-bar">
          <span>策略规则</span>
          <code>VIX <b>&gt; 28</b></code><i>AND</i>
          <code>CNN <b>&lt; 18</b></code><i>AND</i>
          <code>QQQ RSI(14) <b>&lt; 12</b></code>
        </div>
      </section>

      <div class="data-meta">
        <div><i></i> OFFICIAL DATA</div>
        <span>聚合时间 {{ generatedTime }}</span>
      </div>

      <section class="metric-grid" aria-label="决策指标">
        <MetricCard v-for="indicator in data.indicators" :key="indicator.key" :indicator="indicator" />
      </section>

      <aside class="method-note">
        <span>i</span>
        <div><strong>模型说明</strong><p>{{ data.disclaimer }}</p></div>
        <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">查看 API 口径 ↗</a>
      </aside>
    </template>
  </section>
</template>
