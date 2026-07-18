# app 配置层

负责 `app` 子系统的公开和私密配置。

所有可变运行参数都应从这里读取，不再使用顶层共享配置目录。

- 公开配置：`product/app/config/app.toml`
- 私密配置：`product/app/config/private.local.toml`
