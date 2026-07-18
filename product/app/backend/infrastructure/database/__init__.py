"""后端数据库基础设施包。

职责：
- 提供 MySQL 连接创建、连通性检查和关闭能力。
- 向应用层暴露一个确定性的数据库接入门面。

边界：
- 这里只处理连接与健康检查，不承载业务表、仓储和查询编排。
"""

from .mysql import MysqlClient, MysqlConnectionSettings, build_mysql_client, build_mysql_connection_settings

__all__ = ["MysqlClient", "MysqlConnectionSettings", "build_mysql_client", "build_mysql_connection_settings"]
