# 自动化起步说明

## 当前目标

先把“每天 21:00 生成复盘底稿”自动化，后续再逐步接入实时数据抓取、校验、网页展示和定时任务。

项目级约定见：`records/project_conventions.md`

一句话原则：代码只做确定性流转与展示，所有分析、判断、决策都必须由模型驱动；当前阶段先模块化管理，不抽 skill。构建阶段默认用 Codex，运行阶段通过全局配置切换模型，默认生产路径优先外部模型。

运行时模型切换依赖环境变量：

全项目统一从 `product/config/project.toml` 读取：

- `runtime.python_path`：夜间脚本重启时使用的 Python
- `runtime.reexec_flag`：重启保护标记
- `model.profile=external`：默认外部模型
- `model.provider=deepseek`：外部默认模型提供方
- `model.profile=current`：切换到当前模型（Codex 路由）
- `model.name`：在需要时覆盖具体模型名（默认 `deepseek-v4-pro`）
- `model.api_key_env`：DeepSeek API Key 环境变量
- `model.base_url`：DeepSeek API 地址
- `model.thinking` / `model.reasoning_effort`：DeepSeek 思考模式
- `model.use_oss`：开启 OSS 路由
- `model.local_provider`：指定本地 provider
- `email.recipient`：默认收件人
- `launchd.label/hour/minute`：定时任务配置
- `tushare.token_env/ts_code/start_date/end_date`：Tushare 读取配置
- `report.output_dir`：日报输出目录

## 第一阶段已经落地的内容

- 复盘模板：`product/reports/daily/muyuan_21_template.md`
- 自动生成脚本：`product/jobs/muyuan_nightly.py`
- 输出目录：`product/reports/daily/`
- 邮件发送：复用本机 `msmtp` 默认账号
- 定时执行：`launchd` 每天 21:00
- 邮件格式：`multipart/alternative`，HTML 正文 + 纯文本兜底

## 建议执行顺序

### 阶段 1：模板自动生成

生成当日复盘文件，避免每天手工新建。

### 阶段 2：接入 Tushare 主数据

自动写入收盘价、PE(TTM)、PB、换手率、总市值等日频字段。

### 阶段 3：接入东方财富二次校验

自动补充校验结果和口径差异说明。

### 阶段 4：接入公告与公开网页补充

抓取公司公告、月度销售简报、行业公开数据。

### 阶段 5：服务网站前后端

把日复盘、主表、详情页和信号快照做成统一数据源，供前后端展示。

## 当前可执行命令

```bash
python3 product/jobs/muyuan_nightly.py --date 2026-06-27
```

```bash
python3 product/jobs/muyuan_nightly.py --date 2026-06-27 --send-email --recipient 376597874@qq.com
```

```bash
python3 product/jobs/muyuan_nightly.py --install-launchd --recipient 376597874@qq.com
```

## 当前安装状态

- LaunchAgent 标签：`com.astock.muyuan-nightly`
- 实际安装路径：`~/Library/LaunchAgents/com.astock.muyuan-nightly.plist`
- 日志文件：`product/jobs/muyuan_nightly.log`

## 当前邮件展示说明

- 邮件正文已改为 HTML，可直接阅读，不再依赖 Markdown 渲染
- 同时保留纯文本部分，兼容不支持 HTML 的邮件客户端
- 本地预览文件示例：`product/reports/daily/2026-06-27-muyuan-email-preview.html`
- 即使外部发信临时受限，本地也可以先打开 HTML 预览确认最终展示效果

## 当前信号补充能力

- 已纳入结构：
  - 公司公告摘要
  - 月度销售简报摘要
  - 生猪价格公开信号
  - 能繁母猪存栏公开信号
- 读取策略：
  - 优先实时抓取
  - 若实时抓取未拿到，则回退读取最近一次本地缓存结果
- 若当次抓取失败，日报会明确写出“本次未自动获取到”，不会静默留空
