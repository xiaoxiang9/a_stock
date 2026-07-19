<script setup>
/*
 * 首页视图。
 *
 * 职责：
 * - 展示项目定位、能力模块入口和服务在线状态。
 * - 读取 ETF 决策模块快照，作为首页预览。
 * - 提供手动触发每日复盘邮件的入口与轻量表单。
 *
 * 边界：
 * - 首页只做轻量预览和手动触发，不展示完整指标解释和投资规则细节。
 */
import { onMounted, ref } from 'vue'
import { apiUrl } from '../config/project.js'

const serviceStatus = ref('connecting')
const moduleData = ref(null)
const manualMailDefaultsLoading = ref(false)
const manualMailSubmitting = ref(false)
const manualMailOpen = ref(false)
const manualMailError = ref('')
const manualMailFeedback = ref('')
const manualMailResult = ref(null)
const manualMailTrace = ref([])
const manualMailForm = ref({
  report_date: '',
  recipient: '',
})

function buildShanghaiDate() {
  // 默认日期按上海时区计算，避免浏览器本地时区和后端日期口径不一致。
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  const parts = formatter.formatToParts(new Date())
  const values = Object.fromEntries(parts.filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

async function loadManualMailDefaults() {
  // 默认值来自后端配置，前端只做展示和用户确认，不维护收件人口径。
  manualMailDefaultsLoading.value = true
  try {
    const response = await fetch(apiUrl('/reports/muyuan/daily/defaults'))
    if (response.ok) {
      const payload = await response.json()
      manualMailForm.value.report_date = manualMailForm.value.report_date || payload.report_date || buildShanghaiDate()
      manualMailForm.value.recipient = manualMailForm.value.recipient || payload.recipient || ''
      return
    }
  } catch {
    // 兜底到本地计算日期与空收件人，避免接口不可用时阻断首页。
  } finally {
    manualMailDefaultsLoading.value = false
  }
  manualMailForm.value.report_date = manualMailForm.value.report_date || buildShanghaiDate()
}

async function loadHomeData() {
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
}

function openManualMailDialog() {
  manualMailError.value = ''
  manualMailFeedback.value = ''
  manualMailResult.value = null
  manualMailTrace.value = []
  manualMailOpen.value = true
  if (!manualMailForm.value.report_date) {
    manualMailForm.value.report_date = buildShanghaiDate()
  }
  if (!manualMailForm.value.recipient && !manualMailDefaultsLoading.value) {
    void loadManualMailDefaults()
  }
}

async function sendManualMail() {
  // 手动发送只负责把用户选择提交给后端，分析和发信仍由后端工作流完成。
  manualMailError.value = ''
  manualMailFeedback.value = ''
  manualMailSubmitting.value = true
  try {
    const response = await fetch(apiUrl('/reports/muyuan/daily/send'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        report_date: manualMailForm.value.report_date,
        recipient: manualMailForm.value.recipient,
      }),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(payload.detail || `HTTP ${response.status}`)
    }
    manualMailResult.value = {
      report_date: payload.report_date || manualMailForm.value.report_date,
      recipient: payload.recipient || manualMailForm.value.recipient,
      subject: payload.subject || '',
      valuation_rounds: payload.valuation_rounds ?? null,
      valuation_termination_reason: payload.valuation_termination_reason || '',
      output_path: payload.output_path || '',
    }
    manualMailTrace.value = Array.isArray(payload.valuation_trace) ? payload.valuation_trace : []
    manualMailFeedback.value = `已触发 ${manualMailResult.value.report_date} 的复盘邮件，发送至 ${manualMailResult.value.recipient}。`
    manualMailOpen.value = false
  } catch (error) {
    manualMailError.value = error instanceof Error ? error.message : '手动发送失败'
  } finally {
    manualMailSubmitting.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadHomeData(), loadManualMailDefaults()])
})
</script>

<template>
  <section class="home-hero content-width">
    <div class="eyebrow"><span></span> INVESTMENT INTELLIGENCE</div>
    <h1>把市场噪音，<br><em>变成决策信号。</em></h1>
    <p class="lead">面向专业投资团队的模块化决策平台。每一个结论，都由明确规则、官方数据与可追溯方法支撑。</p>
    <div class="hero-actions">
      <a class="primary hero-cta" href="#/etf-buy-decision">
        进入首个决策模块 <span aria-hidden="true">→</span>
      </a>
      <button class="secondary hero-cta" type="button" @click="openManualMailDialog">
        <span aria-hidden="true">✉</span>
        手动发送复盘邮件
      </button>
    </div>
    <p v-if="manualMailFeedback" class="hero-feedback">{{ manualMailFeedback }}</p>
    <div v-if="manualMailResult" class="manual-mail-result" aria-live="polite">
      <div class="manual-mail-result__header">
        <div>
          <p class="section-label">LATEST TRIGGER</p>
          <h3>最近一次发送结果</h3>
        </div>
        <span class="manual-mail-result__status">已触发</span>
      </div>
      <div class="manual-mail-result__grid">
        <div>
          <span>报告日期</span>
          <strong>{{ manualMailResult.report_date }}</strong>
        </div>
        <div>
          <span>收件人</span>
          <strong>{{ manualMailResult.recipient }}</strong>
        </div>
        <div>
          <span>邮件主题</span>
          <strong>{{ manualMailResult.subject || '—' }}</strong>
        </div>
        <div>
          <span>估值循环</span>
          <strong>{{ manualMailResult.valuation_rounds ?? '—' }}</strong>
        </div>
        <div>
          <span>终止原因</span>
          <strong>{{ manualMailResult.valuation_termination_reason || '—' }}</strong>
        </div>
        <div>
          <span>输出路径</span>
          <strong>{{ manualMailResult.output_path || '—' }}</strong>
        </div>
      </div>
      <div class="manual-mail-trace" v-if="manualMailTrace.length">
        <div class="manual-mail-trace__header">
          <p class="section-label">DATA PATH</p>
          <h4>数据获取轮次与路径明细</h4>
        </div>
        <div v-for="round in manualMailTrace" :key="round.round_index" class="manual-mail-trace__round">
          <div class="manual-mail-trace__round-head">
            <strong>第 {{ round.round_index }} 轮</strong>
            <span>{{ round.valuation_status || '—' }}</span>
          </div>
          <p class="manual-mail-trace__summary">{{ round.valuation_summary || '—' }}</p>
          <div class="manual-mail-trace__meta">
            <span v-if="round.prefill_notes?.length">预填：{{ round.prefill_notes.join('；') }}</span>
            <span v-if="round.data_needs?.length">数据诉求：{{ round.data_needs.join('、') }}</span>
            <span v-if="round.notes?.length">本轮备注：{{ round.notes.join('；') }}</span>
          </div>
          <div v-if="round.acquisition_attempts?.length" class="manual-mail-trace__attempts">
            <div v-for="attempt in round.acquisition_attempts" :key="`${round.round_index}-${attempt.need_title}-${attempt.provider_name}`" class="manual-mail-trace__attempt">
              <div class="manual-mail-trace__attempt-top">
                <strong>{{ attempt.need_title }}</strong>
                <span>{{ attempt.provider_name }}</span>
              </div>
              <div class="manual-mail-trace__attempt-body">
                <span>状态：{{ attempt.status }}</span>
                <span>证据数：{{ attempt.evidence_count }}</span>
                <span v-if="attempt.query">查询：{{ attempt.query }}</span>
                <span v-if="attempt.message">说明：{{ attempt.message }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
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

  <div v-if="manualMailOpen" class="dialog-mask" @click.self="manualMailOpen = false">
    <section class="dialog-card" role="dialog" aria-modal="true" aria-labelledby="manual-mail-title">
      <header class="dialog-header">
        <div>
          <p class="section-label">MANUAL REVIEW</p>
          <h3 id="manual-mail-title">手动发送每日复盘邮件</h3>
        </div>
        <button class="dialog-close" type="button" aria-label="关闭" @click="manualMailOpen = false">×</button>
      </header>

      <p class="dialog-intro">选择报告日期和收件人后，后端会重新生成当日复盘并发送邮件。</p>

      <div class="dialog-form">
        <label>
          <span>报告日期</span>
          <input v-model="manualMailForm.report_date" type="date" />
        </label>
        <label>
          <span>收件人</span>
          <input v-model="manualMailForm.recipient" type="email" placeholder="默认收件人" />
        </label>
      </div>

      <div v-if="manualMailError" class="dialog-alert error">{{ manualMailError }}</div>

      <div class="dialog-actions">
        <button class="secondary" type="button" @click="manualMailOpen = false">取消</button>
        <button class="primary" type="button" :disabled="manualMailSubmitting || manualMailDefaultsLoading" @click="sendManualMail">
          <span v-if="manualMailSubmitting" class="spinning">↻</span>
          {{ manualMailSubmitting ? '发送中' : (manualMailDefaultsLoading ? '加载默认值' : '确认发送') }}
        </button>
      </div>
    </section>
  </div>
</template>
