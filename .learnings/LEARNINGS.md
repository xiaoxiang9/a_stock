# Learnings

## [LRN-20260630-001] best_practice

**Logged**: 2026-06-30T00:00:00+08:00
**Priority**: medium
**Status**: pending
**Area**: backend

### Summary
Python 模块级 docstring 需要放在 `from __future__` 导入之前，才能被 `ast.get_docstring` 识别。

### Details
本次按代码注释规范补齐 Python 文件说明时，最初把模块级说明放在 `from __future__ import annotations` 之后。虽然人眼能看到说明，但 `ast.get_docstring(module)` 不会把它识别为模块 docstring。正确做法是：模块 docstring 必须是文件中第一个语句；`from __future__` 导入应放在模块 docstring 之后。

### Suggested Action
后续为 Python 文件补充文件级说明时，统一把模块 docstring 放在文件顶部、shebang/编码声明之后、`from __future__` 之前，并用 AST 检查确认覆盖。

### Metadata
- Source: conversation
- Related Files: product/core/project_config.py, product/jobs/muyuan_nightly.py
- Tags: python, docstring, comments
- Pattern-Key: python.module_docstring_order
- Recurrence-Count: 1
- First-Seen: 2026-06-30
- Last-Seen: 2026-06-30

---
