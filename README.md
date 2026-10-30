# 客户 Agent 试点实例 — 统一模板 × 五隔离实例

对应 ClawHunt 任务 **#1503**（企业 Agent 系统 16/50｜客户 Agent 试点实例）。

**验收标准**：提供**五个实例配置及互相隔离的验证记录**。

## 一条命令验证全部

```bash
python run_tests.py      # -> PASS 31 / FAIL 0
python demo.py           # -> 五个实例隔离演示
```

## 验收三要素（与验收标准逐条对应）

**① 核心实现（统一模板 + 实例注册/隔离）路径**
`instance_loader.py` —— `InstanceManager`：
- 统一模板 `schema/instance.schema.json`（draft-07，8 个必填字段）
- 加载目录下全部 `inst-*.json` 实例，先 schema 校验再注册
- **命名空间隔离**：每个实例全局唯一的 `namespace_prefix`，数据读写
  限定在 `{prefix}` 命名空间；跨实例读取 → 空集 + 审计

**② 五个实例配置文件路径**
- `examples/inst-gold-jewelry-01.json`（黄金珠宝）
- `examples/inst-apparel-02.json`（鞋服制造）
- `examples/inst-healthcare-03.json`（医疗健康）
- `examples/inst-woodwork-04.json`（硬木家具）
- `examples/inst-culture-05.json`（非遗文创）
- 反例 `examples/inst-invalid-99.json`（校验器拒绝路径）

**③ 隔离验证：运行命令 + 正/反例预期输出**

```bash
python run_tests.py
# ✅ 3. all five instances registered
# ✅ 5. namespace prefixes globally unique
# ✅ 7. pairwise cross-access leaks zero (all pairs) -- leaked=0 pairs=20
# ✅ 10. invalid instance rejected by schema -- 6 errors
# ✅ 10c. duplicate namespace rejected (real branch)
# Result: PASS 31   FAIL 0
```

反例（必须被拒）—— 缺少必填字段 / 冲突命名空间 / 额外字段 / 真实数据：

```bash
python -c "import json; from instance_loader import _validate;
s=json.load(open('schema/instance.schema.json',encoding='utf-8'));
bad=json.load(open('examples/inst-invalid-99.json',encoding='utf-8'));
errs=_validate(bad,s); print(len(errs), 'errors')"
# 输出: 6 errors      ← 非法实例被 schema 拒绝
```

## 快速开始

```bash
# 零第三方依赖（纯 Python 标准库）
python run_tests.py          # 全部验收验证
python demo.py               # 五实例隔离演示
```

## 目录

```
.
├── instance_loader.py       # 统一模板 + 实例注册/隔离（核心）
├── run_tests.py             # 验收验证（31 项断言）
├── demo.py                  # 五实例隔离演示
├── schema/
│   └── instance.schema.json # 统一实例模板（8 必填字段）
├── examples/
│   ├── inst-gold-jewelry-01.json   # 实例 1 黄金珠宝
│   ├── inst-apparel-02.json        # 实例 2 鞋服制造
│   ├── inst-healthcare-03.json     # 实例 3 医疗健康
│   ├── inst-woodwork-04.json       # 实例 4 硬木家具
│   ├── inst-culture-05.json        # 实例 5 非遗文创
│   └── inst-invalid-99.json        # 反例（校验拒绝路径）
├── docs/
│   ├── 验收对照.md           # 验收标准逐条对照
│   ├── 实现说明.md           # 设计与实现
│   └── 验证记录.md           # 真实执行输出
├── SETUP.md
└── README.md
```

## 设计要点

1. **统一模板**：`instance.schema.json` 定义实例结构（id/name/industry/
   namespace_prefix/bot_role/knowledge_mounts/data_domains/tools），
   五个实例同一模板、按行业差异化填充。
2. **命名空间隔离是核心**：每个实例全局唯一 `namespace_prefix`，数据
   读写限定在自己的前缀下；跨实例读取返回空集并审计（不泄露对方存在性）。
3. **5 个行业差异化**：黄金珠宝/鞋服/医疗健康/硬木家具/非遗文创——
   对应不同知识挂载、数据域、工具权限，证明"同一模板可配置化复用"。
4. **反例覆盖**：`inst-invalid-99.json` 故意带缺字段/冲突前缀/额外字段/
   真实联系方式，验证 schema 与注册器都会拒绝（测试 10/10b）。
5. **脱敏合规**：所有示例数据为脱敏/合成材料，无真实客户、患者、工厂机密。

## 环境

- Python 3.8+
- **零第三方依赖**（纯标准库）

## 边界说明

本单范围 = 基于统一模板配置五个隔离试点实例 + 隔离验证记录；
以下不在本单范围：
- 实例的实际运行时（会话隔离）—— 属拆分单 03（#1490）
- 多实例间的路由 —— 属拆分单 05（#1492）
- 真实客户数据接入 —— 按原文要求仅用脱敏材料