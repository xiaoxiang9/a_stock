<script setup>
/*
 * 首页视图。
 *
 * 职责：
 * - 展示项目定位、能力模块入口和服务在线状态。
 * - 读取 ETF 决策模块快照，作为首页预览。
 *
 * 边界：
 * - 首页只做轻量预览，不展示完整指标解释和投资规则细节。
 */
import { onMounted, ref } from 'vue'
import { apiUrl } from '../config/project.js'

const serviceStatus = ref('connecting')
const moduleData = ref(null)

onMounted(async () => {
  // 首页只做轻量探活和模块快照预览，完整决策明细放到模块页。
  try {
    const [healthResponse, moduleResponse] = await Promise.all([
      fetch(apiUrl('/health')),
      fetch(apiUrl('/modules/etf-buy-decision')),
    ])
    serviceStatus.value = healthResponse.ok ? 'online' : 'offline'
    if (moduleResponse.ok) moduleData.value = await moduleResponse.json()
  } catch {
    serviceStatus.value = 'offline'
  }
})
</script>

<template>
  <section class="home-hero content-width">
    <div class="eyebrow"><span></span> INVESTMENT INTELLIGENCE</div>
    <h1>把市场噪音，<br><em>变成决策信号。</em></h1>
    <p class="lead">面向专业投资团队的模块化决策平台。每一个结论，都由明确规则、官方数据与可追溯方法支撑。</p>
    <a class="primary hero-cta" href="#/etf-buy-decision">
      进入首个决策模块 <span aria-hidden="true">→</span>
    </a>
    <div class="service-line" :class="serviceStatus">
      <i></i>
      {{ serviceStatus === 'online' ? '决策引擎在线' : '等待决策引擎' }}
      <span>FastAPI · Official market data</span>
    </div>
  </section>

  <section class="module-section content-width">
    <div class="section-heading">
      <div>
        <p class="section-label">CAPABILITY MODULES</p>
        <h2>投资能力模块</h2>
      </div>
      <span class="module-count">01 / BUILDING</span>
    </div>

    <a class="module-entry" href="#/etf-buy-decision">
      <div class="module-index">01</div>
      <div class="module-copy">
        <div class="module-meta"><span>US MARKET</span><span>ETF</span><span>DAILY</span></div>
        <h3>美股 ETF 买入决策</h3>
        <p>综合 VIX、CNN Fear & Greed 与 QQQ RSI，在极端恐慌环境中识别纪律化买入时点。</p>
        <div class="rule-preview">
          <code>VIX &gt; 28</code><b>AND</b><code>CNN &lt; 18</code><b>AND</b><code>QQQ RSI &lt; 12</code>
        </div>
        <div class="module-snapshot" aria-label="当前指标概要">
          <div v-for="indicator in moduleData?.indicators || []" :key="indicator.key">
            <span>{{ indicator.name }}</span>
            <strong>{{ indicator.value === null ? '—' : indicator.value.toFixed(2) }}</strong>
            <small :class="indicator.deviation_pct >= 0 ? 'reached' : 'unreached'">
              {{ indicator.deviation_pct >= 0 ? '+' : '' }}{{ indicator.deviation_pct?.toFixed(1) ?? '—' }}%
              <em>距目标</em>
            </small>
          </div>
          <div v-if="!moduleData" v-for="item in 3" :key="`placeholder-${item}`" class="snapshot-placeholder">
            <span>LOADING</span><strong>—</strong><small>数据加载中</small>
          </div>
        </div>
      </div>
      <div class="module-arrow" aria-hidden="true">↗</div>
    </a>
  </section>

  <section class="principles content-width">
    <p class="section-label">OPERATING PRINCIPLES</p>
    <div class="principle-grid">
      <article><span>01</span><h3>规则先行</h3><p>先定义触发条件，再观察市场，降低情绪与叙事偏差。</p></article>
      <article><span>02</span><h3>来源可溯</h3><p>优先采用官方数据接口，每项指标都保留来源与时间戳。</p></article>
      <article><span>03</span><h3>模块演进</h3><p>将研究能力沉淀为独立模块，持续验证、复盘与迭代。</p></article>
    </div>
  </section>
</template>
