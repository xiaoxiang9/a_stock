/*
 * 浏览器端项目配置访问工具。
 *
 * 职责：
 * - 读取 Vite 注入的全局项目配置。
 * - 提供 API 地址和文档地址的统一拼接方法。
 *
 * 边界：
 * - 本文件只暴露前端运行所需配置，不读取密钥类环境变量。
 */
export const projectConfig = __ASTOCK_PROJECT_CONFIG__

export const frontendConfig = projectConfig.frontend
export const backendConfig = projectConfig.backend

export function apiUrl(pathname) {
  // 页面只传业务路径，由这里统一拼接 API base path。
  const basePath = frontendConfig.api_base_path || '/api'
  const normalizedBase = basePath.endsWith('/') ? basePath.slice(0, -1) : basePath
  const normalizedPath = pathname.startsWith('/') ? pathname : `/${pathname}`
  return `${normalizedBase}${normalizedPath}`
}

export function docsUrl() {
  // API 文档地址由配置决定，便于本地和服务器部署切换。
  return frontendConfig.docs_url
}
