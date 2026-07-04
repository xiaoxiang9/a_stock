/*
 * 前端构建期项目配置读取工具。
 *
 * 职责：
 * - 读取 product/config/project.toml。
 * - 解析本项目使用到的简单 TOML 语法。
 *
 * 边界：
 * - 这是项目内轻量解析器，不是通用 TOML 实现。
 * - 仅供 Vite 配置和前端测试读取非密钥配置。
 */
import fs from 'node:fs'
import path from 'node:path'

// 前端构建期只需要读取本项目的简单 TOML 配置，
// 因此这里保留轻量解析器，避免额外引入运行时依赖。
function parseScalar(raw) {
  // 标量解析只覆盖当前配置需要的字符串、布尔值、数字和简单 JSON 字面量。
  const value = raw.trim()
  if (value === '') return ''
  if (value === 'true') return true
  if (value === 'false') return false
  try {
    return JSON.parse(value)
  } catch {
    return value.replace(/^"(.*)"$/, '$1').replace(/^'(.*)'$/, '$1')
  }
}

export function parseProjectToml(text) {
  // 仅解析 [section] + key = value 结构，和 Python 公共配置保持同源。
  const data = {}
  let current = null

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue
    if (line.startsWith('[') && line.endsWith(']')) {
      current = line.slice(1, -1).trim()
      if (!data[current]) data[current] = {}
      continue
    }
    if (!current || !line.includes('=')) continue
    const index = line.indexOf('=')
    const key = line.slice(0, index).trim()
    const rawValue = line.slice(index + 1)
    data[current][key] = parseScalar(rawValue)
  }

  return data
}

export function loadProjectConfig(configPath) {
  // Vite 启动时加载 product/config/project.toml，并注入浏览器端。
  const absolutePath = path.resolve(configPath)
  const text = fs.readFileSync(absolutePath, 'utf8')
  return parseProjectToml(text)
}
