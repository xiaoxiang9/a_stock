# A Stock 部署说明

本文说明如何在一台新机器上独立部署 A Stock，并保证启动前能够完成配置和依赖校验。

## 架构总览

- 公开配置：`product/app/config/app.toml`
- 私密配置：`product/app/config/private.local.toml`
- 本地 MySQL 编排：`product/app/config/mysql/docker-compose.yml`
- 安装脚本：`product/scripts/install.sh`
- 启动脚本：`product/scripts/start.sh`

原则如下：

1. 公开配置可提交 git，私密配置本地保留
2. 安装只检测、确认、安装和初始化，不自动填密钥
3. 启动前必须通过配置和依赖检查
4. 任一检查失败，直接阻断并返回原因
5. 业务代码只读配置中心，不依赖 shell 环境
6. 若发现已有项目实例，启动脚本会先暂停旧实例，再拉起新实例，避免端口冲突
7. MySQL 默认连接项目配置里的 `mysql.host`；如果它指向本机地址，启动脚本会优先探测 Homebrew MySQL，再回退到 Docker Compose；如果它指向群辉等远程数据库，则跳过本地数据库运行时检查
8. 后端启动时只装配 MySQL 客户端，不在生命周期里强制连库；数据库探活由 `/api/database/ping` 按需触发

## 1. 依赖清单

### 系统依赖

- Python 3.9+
- Node.js 22+
- npm
- git

### Python 依赖

- `fastapi`
- `httpx`
- `uvicorn[standard]`
- `akshare`
- `tushare`
- `MySQL 连接能力`：通过内置 MySQL 客户端和本地运行时完成连通性检查，不依赖外部 ORM 包

### 前端依赖

- `vue`
- `@vitejs/plugin-vue`
- `vite`

## 2. 配置中心

### 公开配置

文件：`product/app/config/app.toml`

可提交 git，内容只放非敏感参数，例如：

- 后端标题和描述
- 允许的前端来源
- 调度时间
- 报告输出目录
- 默认收件人
- SMTP 的 host / port / user / from_addr

### 私密配置

文件：`product/app/config/private.local.toml`

不提交 git，只放敏感参数，例如：

- SMTP 密码
- DeepSeek API key
- Tushare token
- MySQL 用户名和密码
- 如需手动复盘里启用 `agents` 子系统的补数链路，也可以在同一份文件里额外补 `mx_api_key` 和 `websearch_api_key`

安装脚本会初始化私密配置模板，启动脚本会在启动前检查值是否已填写。

## 3. 安装流程

运行：

```bash
./product/scripts/install.sh
```

安装脚本会做这些事：

1. 检测系统和项目依赖
2. 在用户确认后安装缺失依赖
3. 初始化 `product/app/config/private.local.toml`
4. 安装后端 Python 依赖
5. 安装前端 Node 依赖
6. 输出启动前需要补齐的配置项

注意：

- 脚本不会自动填写密钥
- 如果私密配置存在空值，安装脚本只提示，不会代填

## 4. 启动流程

运行：

```bash
./product/scripts/start.sh
```

启动脚本会先做以下校验：

1. 公开配置可读
2. 私密配置可读且必填项已填写
3. 后端 Python 依赖可导入
4. 前端依赖已安装
5. 本地 MySQL 运行时已在监听，或能通过本地运行时被拉起

若检测到已有项目实例，脚本会先回收旧实例，再启动新实例。任何一项不通过都会直接退出，并输出失败原因，不会启动服务。

## 5. 启动成功后的检查

- 前端：`http://127.0.0.1:5173`
- 后端文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/health`
- 数据库探活：`http://127.0.0.1:8000/api/database/ping`
- 数据库示例写入查询：`POST http://127.0.0.1:8000/api/database/demo`

## 6. 常见失败原因

- `product/app/config/app.toml` 缺少 SMTP 公共字段
- `product/app/config/private.local.toml` 缺少 SMTP 密码或 token 值
- `product/app/config/private.local.toml` 缺少 MySQL 用户名或密码
- 后端 `.venv` 尚未安装完成
- 前端 `node_modules` 尚未安装完成
- 本机未启动 MySQL，或 `mysql.host` 仍指向本机且 Homebrew MySQL / Docker Compose 不可用
- Node.js 版本过低

如果启动失败，优先查看脚本输出的第一条错误信息。
