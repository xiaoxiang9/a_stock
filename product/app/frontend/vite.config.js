/*
 * Vite 前端构建配置。
 *
 * 职责：
 * - 从项目全局配置读取前端开发服务器和后端代理参数。
 * - 将非密钥类项目配置注入浏览器端，供页面运行时读取。
 *
 * 边界：
 * - 本文件只处理构建期配置，不写业务逻辑和投资判断。
 */
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { loadProjectConfig } from './scripts/project-config.js'

const frontendDir = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(frontendDir, '../../..')
// 前端端口、API 代理目标等统一读取全局配置，避免前后端各配一套。
const projectConfig = loadProjectConfig(path.resolve(projectRoot, 'product/app/config/app.toml'))

export default defineConfig({
  plugins: [vue()],
  server: {
    host: projectConfig.frontend.dev_host,
    port: projectConfig.frontend.dev_port,
    proxy: {
      '/api': {
        target: projectConfig.backend.public_base_url,
        changeOrigin: true,
      },
    },
  },
  define: {
    // 把构建期配置安全注入浏览器端，只暴露非密钥类配置。
    __ASTOCK_PROJECT_CONFIG__: JSON.stringify(projectConfig),
  },
})
