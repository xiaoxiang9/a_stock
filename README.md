# A Stock

一个围绕复盘展开的个人投资研究与执行系统。

项目目录规范见：`records/project_structure.md`。

## 项目结构

本项目长期分为四类资产：

- `product/`：项目产物，可独立部署运行的投资复盘系统
- `records/`：项目构建记录，包含建设日志、todo 和路线图
- `knowledge/`：项目构建经验沉淀，记录经验、踩坑、模式和重要决策
- `skills/`：项目构建 skill，记录候选或已抽取的可迁移能力

后续新增文件前，需要先按照 `records/project_structure.md` 确认目录归属。

当前仓库仍保留部分历史目录，后续会逐步按目录规范收敛。

## 一键启动

```bash
./product/scripts/start.sh
```

脚本会自动准备缺失的依赖并启动前后端。前端使用 Node.js 22 LTS；按 `Ctrl+C` 可同时停止两个服务。

## 启动后端

```bash
cd product/app/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

后端运行于 <http://127.0.0.1:8000>，API 文档位于 <http://127.0.0.1:8000/docs>。

## 启动前端

另开一个终端：

```bash
cd product/app/frontend
nvm use
npm install
npm run dev
```

前端使用 Node.js 22 LTS；首次运行时可先执行 `nvm install`。

打开 <http://localhost:5173> 查看欢迎页。开发服务器会将 `/api` 请求代理到 FastAPI。

## 投资模块

### 美股 ETF 买入决策

页面入口：<http://localhost:5173/#/etf-buy-decision>

策略仅在以下条件同时成立时触发买入信号：

```text
VIX > 28 AND CNN Fear & Greed < 18 AND QQQ RSI(14) < 12
```

数据来自 Cboe、CNN Business 与 Nasdaq 官方接口。QQQ RSI 使用 Nasdaq 日收盘价并按 Wilder 方法计算；接口响应缓存 5 分钟，可通过 `GET /api/modules/etf-buy-decision?refresh=true` 强制刷新。
