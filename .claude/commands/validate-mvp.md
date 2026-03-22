# /project:validate-mvp
# 
# 运行 MVP 核心场景的完整验证。
# 在 Claude Code 中使用：输入 /project:validate-mvp

## 执行步骤

1. 运行单元测试（无外部依赖）：
```bash
pytest tests/unit -v -m "not integration"
```

2. 检查类型（确保 Pydantic 模型正确）：
```bash
mypy relos/core/models.py relos/core/engine.py
```

3. 代码风格检查：
```bash
ruff check relos/ --select E,W,F
```

4. 检查 API 路由是否完整注册：
```bash
python -c "from relos.main import app; routes = [r.path for r in app.routes]; print('\n'.join(routes))"
```

5. 验证种子数据脚本语法：
```bash
python -m py_compile scripts/seed_neo4j.py scripts/simulate_alarm.py && echo "✓ Scripts OK"
```

## 成功标准

- 所有单元测试通过
- mypy 无 error（warning 可接受）  
- ruff 无 E/F 级别错误
- API 路由包含 /v1/health, /v1/relations, /v1/decisions/analyze-alarm
