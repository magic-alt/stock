# Tests - 测试套件

本目录包含项目的所有测试代码。

## 🧪 测试结构

```
tests/
├── test_data_portal.py          # 数据门户测试
├── test_db_name_feature.py      # 数据库名称功能测试
├── test_integration_simulation.py # 集成仿真测试
├── test_objects.py              # 核心对象测试
├── test_phase4_integration.py   # Phase 4集成测试
├── test_simulation.py           # 仿真测试
├── test_sqlite_caching.py       # SQLite缓存测试
├── test_sqlite_v2_integration.py # SQLite V2集成测试
├── test_sqlite_v2_schema.py     # SQLite V2架构测试
└── test_strategy_template.py    # 策略模板测试
```

## 🚀 运行测试

### 运行所有测试
```bash
pytest tests/ -v
```

### 运行特定测试文件
```bash
pytest tests/test_data_portal.py -v
```

### 运行特定测试函数
```bash
pytest tests/test_data_portal.py::test_function_name -v
```

### 查看测试覆盖率
```bash
pytest tests/ --cov=src --cov-report=html
```

## 📊 测试分类

### 单元测试 (Unit Tests)
- `test_objects.py` - 核心数据对象
- `test_strategy_template.py` - 策略模板

### 集成测试 (Integration Tests)
- `test_integration_simulation.py` - 端到端集成
- `test_phase4_integration.py` - Phase 4功能集成
- `test_sqlite_v2_integration.py` - 数据库集成

### 功能测试 (Feature Tests)
- `test_data_portal.py` - 数据门户功能
- `test_db_name_feature.py` - 数据库名称功能
- `test_sqlite_caching.py` - 缓存功能
- `test_sqlite_v2_schema.py` - 数据库架构

## 🔧 测试配置

### pytest.ini
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

### 环境要求
```bash
pip install pytest pytest-cov pytest-xdist
```

## 📝 编写测试

### 测试模板
```python
import pytest
from src.module import YourClass

class TestYourClass:
    def test_basic_functionality(self):
        obj = YourClass()
        assert obj.method() == expected_value
    
    def test_edge_case(self):
        obj = YourClass()
        with pytest.raises(ValueError):
            obj.method(invalid_input)
```

### 最佳实践
1. **命名清晰**: `test_<功能>_<场景>`
2. **独立性**: 每个测试互不依赖
3. **覆盖率**: 核心功能 >80%
4. **快速**: 单个测试 <5秒
5. **文档**: 添加docstring说明测试目的

## 🐛 持续集成

测试会在GitHub Actions中自动运行：
- 每次push到main/develop分支
- 每次创建Pull Request
- 支持Python 3.8-3.11
- 支持Ubuntu和Windows

查看CI状态: `.github/workflows/ci.yml`

## 📚 相关文档

- **开发指南**: `docs/DEVELOPMENT.md`
- **贡献指南**: `docs/CONTRIBUTING.md`
- **CI/CD配置**: `.github/workflows/`

---

**提示**: 提交代码前请确保所有测试通过 ✅
