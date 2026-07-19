# 已发布 skill

这里记录已经稳定抽取并可迁移复用的 skill。

本目录下的 skill 已经固化到仓库中，可随 Git 一起发布到服务器。代码侧优先读取这里的版本，只有在仓库副本缺失时才回退到本机全局安装态。

## 当前清单

- `tushare`：A 股、指数、ETF、财务、资金流等基础研究 skill
- `mx-finance-data`：东方财富妙想金融数据 skill
- `mx-finance-search`：东方财富妙想资讯搜索 skill

兼容说明：

- `mx-data`、`mx-search` 仍保留为迁移期兼容别名。
- 新代码应优先引用 `mx-finance-data` 和 `mx-finance-search`。
