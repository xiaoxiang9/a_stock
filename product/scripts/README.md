# 脚本层

负责人工执行脚本，例如安装、初始化、部署和迁移。

项目需要维护安装脚本，支持快速独立部署。

- 安装脚本：`product/scripts/install.sh`
- 启动脚本：`product/scripts/start.sh`

`start.sh` 会在启动前检测是否已有项目实例运行；如果发现旧实例，会先停止再重启，避免端口冲突。
