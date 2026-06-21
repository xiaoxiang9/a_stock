<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import EtfDecisionView from './views/EtfDecisionView.vue'
import HomeView from './views/HomeView.vue'

const route = ref(window.location.hash || '#/')

const currentView = computed(() => (
  route.value === '#/etf-buy-decision' ? EtfDecisionView : HomeView
))

const updateRoute = () => {
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
