/*
 * 前端应用入口。
 *
 * 职责：
 * - 创建 Vue 应用实例。
 * - 挂载根组件 App.vue。
 * - 引入全局样式。
 */
import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

createApp(App).mount('#app')
