# 设置与运行

零第三方依赖，无需安装任何包。

## 环境要求

- Python 3.8+（标准库：json / os / sys / time / re）

## 快速验证

```bash
# 在项目根目录
python run_tests.py        # 31 项验收断言，期望 PASS 31 / FAIL 0
python demo.py             # 五实例隔离演示，期望退出码 0
```

## 在自己的代码中使用

```python
from instance_loader import InstanceManager

# 加载目录下全部 inst-*.json 实例（自动 schema 校验 + 注册）
mgr = InstanceManager("examples")

# 写数据到某实例命名空间
mgr.write("inst-gold-jewelry-01", "order-001", "private")

# 交叉访问探测：A 读 B -> (leaked, total)，leaked 必须恒 0
leaked, total = mgr.cross_access_check("inst-gold-jewelry-01",
                                       "inst-apparel-02")
assert leaked == 0   # 完全隔离

# 自读
leaked, total = mgr.cross_access_check("inst-gold-jewelry-01",
                                       "inst-gold-jewelry-01")

# 审计
print(mgr.audit_log())
```

## 新增一个实例

1. 复制任意 `examples/inst-*.json`
2. 改 `instance_id`（全局唯一）、`namespace_prefix`（全局唯一）、
   `industry`（枚举内）、知识挂载/数据域/工具权限
3. 放入 `examples/`（文件名 `inst-*.json`），下次 `InstanceManager`
   加载即自动校验注册

## 常见问题

- **命名空间前缀冲突会怎样？** 注册时抛 `InstanceError`（测试 10b），
  保证五个实例绝不共享前缀，这是隔离的硬保证。
- **跨实例读取返回空集而非报错？** 设计如此——返回空不泄露对方
  "存在数据"这个事实，配合审计即可追踪，又不形成侧信道。
- **Windows 中文乱码？** 脚本已内置 UTF-8 重配置。