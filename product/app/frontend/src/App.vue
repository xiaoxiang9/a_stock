<script setup>
/*
 * 前端根组件。
 *
 * 职责：
 * - 提供页面外壳、顶部导航和底部信息。
 * - 根据 hash 路由切换首页和 ETF 决策模块。
 *
 * 边界：
 * - 本组件只做轻量路由和布局，不直接获取投研数据。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import EtfDecisionView from './views/EtfDecisionView.vue'
import HomeView from './views/HomeView.vue'

const route = ref(window.location.hash || '#/')

// 根据当前 hash 选择展示页面，保持前端路由实现足够轻量。
const currentView = computed(() => (
  route.value === '#/etf-buy-decision' ? EtfDecisionView : HomeView
))

const updateRoute = () => {
  // hash 变化后同步视图，并把页面滚动回顶部，避免模块切换时停留在旧滚动位置。
  route.value = window.location.hash || '#/'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => window.addEventListener('hashchange', updateRoute))
onBeforeUnmount(() => window.removeEventListener('hashchange', updateRoute))
</script>

<template>
  <main class="page-shell">
    <nav class="topbar" aria-label="主导航">
      <a class="brand" href="#/" aria-label="A Stock 首页">
        <span class="brand-mark">A</span>
        <span>A Stock</span>
      </a>
      <div class="topbar-links">
        <a href="#/">首页</a>
        <a href="#/etf-buy-decision">投资模块</a>
        <span class="live-label"><i></i> DATA LIVE</span>
      </div>
    </nav>

    <component :is="currentView" />

    <footer>
      <span>A Stock Intelligence</span>
      <span>Professional decision support · Python + Vue</span>
    </footer>
  </main>
</template>
