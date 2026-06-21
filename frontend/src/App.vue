<script setup>
import { onMounted, ref } from 'vue'

const welcome = ref({
  title: '欢迎来到 A Stock',
  message: '正在连接 Python 服务…',
  status: 'connecting',
})

onMounted(async () => {
  try {
    const response = await fetch('/api/welcome')
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    welcome.value = await response.json()
  } catch (error) {
    welcome.value.message = '前端已经就绪，启动 Python 服务后即可完成连接。'
    welcome.value.status = 'offline'
  }
})
</script>

<template>
  <main class="page-shell">
    <nav class="topbar" aria-label="主导航">
      <a class="brand" href="#" aria-label="A Stock 首页">
        <span class="brand-mark">A</span>
        <span>A Stock</span>
      </a>
      <div class="stack-labels" aria-label="技术栈">
        <span>Python</span>
        <i></i>
        <span>Vue</span>
      </div>
    </nav>

    <section class="hero">
      <div class="eyebrow"><span></span> READY TO BUILD</div>
      <h1>{{ welcome.title }}</h1>
      <p class="lead">{{ welcome.message }}</p>

      <div class="actions">
        <a class="primary" href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
          查看 API 文档 <span aria-hidden="true">↗</span>
        </a>
        <a class="secondary" href="#architecture">了解项目结构 <span aria-hidden="true">↓</span></a>
      </div>

      <div class="connection-card" :class="welcome.status">
        <div class="pulse"><span></span></div>
        <div>
          <strong>{{ welcome.status === 'online' ? '服务连接正常' : '等待后端服务' }}</strong>
          <small>Vue :5173 <span>→</span> FastAPI :8000</small>
        </div>
        <code>{{ welcome.status }}</code>
      </div>
    </section>

    <section id="architecture" class="architecture">
      <p class="section-label">PROJECT FOUNDATION</p>
      <div class="feature-grid">
        <article>
          <span class="number">01</span>
          <h2>FastAPI 后端</h2>
          <p>清晰的 Python API、自动生成的接口文档，以及适合持续扩展的目录结构。</p>
        </article>
        <article>
          <span class="number">02</span>
          <h2>Vue 3 前端</h2>
          <p>使用 Composition API 与 Vite，获得轻量、快速且舒适的开发体验。</p>
        </article>
        <article>
          <span class="number">03</span>
          <h2>开发即连通</h2>
          <p>本地代理与跨域配置已经准备好，前后端服务可以立即协同工作。</p>
        </article>
      </div>
    </section>

    <footer>
      <span>A Stock Starter</span>
      <span>Built with Python + Vue</span>
    </footer>
  </main>
</template>
