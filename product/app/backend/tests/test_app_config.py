"""后端应用配置测试。

职责：
- 验证 FastAPI 应用元信息来自共享项目配置。
- 验证 CORS 中间件已按表达层需要装配。
"""

import unittest

from product.app.backend.app.main import app


class BackendAppConfigTests(unittest.TestCase):
    """后端应用配置装配测试。"""

    def test_fastapi_app_uses_shared_project_config(self) -> None:
        """验证后端应用读取了全局配置中的标题、描述和版本。"""
        self.assertEqual(app.title, "A Stock API")
        self.assertEqual(app.description, "Python + Vue starter API")
        self.assertEqual(app.version, "0.1.0")

        middleware_classes = [middleware.cls.__name__ for middleware in app.user_middleware]
        self.assertIn("CORSMiddleware", middleware_classes)


if __name__ == "__main__":
    unittest.main()
