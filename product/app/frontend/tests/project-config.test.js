/*
 * 前端项目配置工具测试。
 *
 * 职责：
 * - 验证轻量 TOML 解析器能读取前后端配置段。
 * - 验证前端构建期可以读取共享项目配置文件。
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { loadProjectConfig, parseProjectToml } from '../scripts/project-config.js'

const frontendDir = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(frontendDir, '../../../..')

test('parseProjectToml reads frontend and backend sections', () => {
  // 使用最小配置样本保护 section 解析和基础标量解析。
  const data = parseProjectToml(`
[backend]
public_base_url = "http://127.0.0.1:8000"

[frontend]
dev_host = "0.0.0.0"
dev_port = 5173
api_base_path = "/api"
docs_url = "http://127.0.0.1:8000/docs"
`)

  assert.equal(data.backend.public_base_url, 'http://127.0.0.1:8000')
  assert.equal(data.frontend.dev_host, '0.0.0.0')
  assert.equal(data.frontend.dev_port, 5173)
  assert.equal(data.frontend.api_base_path, '/api')
})

test('loadProjectConfig reads the shared project config file', () => {
  // 直接读取仓库共享配置，确保 Vite 构建入口可用。
  const config = loadProjectConfig(path.resolve(projectRoot, 'product/app/config/app.toml'))

  assert.equal(config.frontend.dev_port, 5173)
  assert.equal(config.backend.public_base_url, 'http://127.0.0.1:8000')
  assert.equal(config.frontend.docs_url, 'http://127.0.0.1:8000/docs')
})
