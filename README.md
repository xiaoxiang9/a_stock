# A Stock

一个基于 FastAPI 与 Vue 3 的前后端项目骨架。

## 一键启动

```bash
./start.sh
```

脚本会自动准备缺失的依赖并启动前后端。前端使用 Node.js 22 LTS；按 `Ctrl+C` 可同时停止两个服务。

## 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

后端运行于 <http://127.0.0.1:8000>，API 文档位于 <http://127.0.0.1:8000/docs>。

## 启动前端

另开一个终端：

```bash
cd frontend
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
