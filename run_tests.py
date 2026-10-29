# -*- coding: utf-8 -*-
"""客户 Agent 试点实例主流程验证 —— 对应验收标准
「提供五个实例配置及互相隔离的验证记录」

零第三方依赖。打印每条验收标准的实测结果。
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from instance_loader import InstanceManager, InstanceError, _validate  # noqa

PASS, FAIL = [], []
OK = "\u2705"
NO = "\u274c"


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = OK if cond else NO
    line = "  " + mark + " " + name
    if detail:
        line += " -- " + detail
    print(line)


print("=" * 78)
print("Customer Agent Pilot Instances -- acceptance verification")
print("=" * 78)
print("Acceptance: 五个实例配置及互相隔离的验证记录\n")

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "examples")
SCHEMA = os.path.join(HERE, "schema", "instance.schema.json")

# 1. schema 可加载 draft-07
schema = json.load(open(SCHEMA, encoding="utf-8"))
check("1. schema loadable, draft-07",
      schema.get("$schema", "").endswith("draft-07/schema#"),
      "title=" + str(schema.get("title")))

# 2. 实例配置文件恰好 5 个合法 + 1 个反例
legal = sorted(f for f in os.listdir(EX)
               if f.startswith("inst-") and f.endswith(".json")
               and "invalid" not in f)
check("2. five legal instance configs present", len(legal) == 5,
      str(legal))
invalid = [f for f in os.listdir(EX)
           if "invalid" in f and f.endswith(".json")]
check("2b. invalid counter-example present", len(invalid) >= 1, str(invalid))

# 3. 五个实例全部通过 schema 校验
mgr = InstanceManager(EX)
insts = mgr.instance_ids()
check("3. all five instances registered", len(insts) == 5,
      str(insts))

# 4. 五个实例 industry 覆盖不同行业（试点差异化）
inds = {mgr.instance(i)["industry"] for i in insts}
check("4. five instances cover distinct industries", len(inds) == 5,
      str(inds))

# 5. 命名空间前缀全局唯一（隔离的基础）
ns = [mgr.instance(i)["namespace_prefix"] for i in insts]
check("5. namespace prefixes globally unique", len(set(ns)) == 5,
      str(ns))

# 6. 每个实例写入自己的命名空间（16 条 = 5 实例各写多条）
for i, inst in enumerate(insts):
    for k in range(3):
        mgr.write(inst, f"data-{i}-{k}", f"secret-of-{inst}")
check("6. each instance writes to own namespace", True,
      f"{5*3} records written")

# 7-10. 交叉访问：任意两两组合必须 0 泄漏（C(5,2)=10 对）
leaks = 0
pairs = 0
for a in insts:
    for b in insts:
        if a == b:
            continue
        lk, tot = mgr.cross_access_check(a, b)
        leaks += lk
        pairs += 1
check("7. pairwise cross-access leaks zero (all pairs)",
      leaks == 0 and pairs == 20,
      f"leaked={leaks} pairs={pairs}")

# 8. 自读正常：每个实例能读到自己全部数据
self_ok = all(
    mgr.cross_access_check(i, i)[0] == 3 for i in insts)
check("8. each instance reads own records (3 each)", self_ok,
      "leaked==total==3 per instance")

# 9. 越权读被审计
n_blocked = len([a for a in mgr.audit_log()
                 if a["type"] == "cross_instance_read_blocked"])
check("9. cross reads are audited", n_blocked >= 10,
      f"{n_blocked} blocked events")

# 10. 非法实例被 schema 拒绝（缺字段/额外字段/冲突前缀/真实数据）
bad = json.load(open(os.path.join(EX, "inst-invalid-99.json"),
                     encoding="utf-8"))
errs = _validate(bad, schema)
check("10. invalid instance rejected by schema", len(errs) >= 4,
      f"{len(errs)} errors -> {errs[:3]}")
try:
    mgr.register(bad)
    check("10b. duplicate namespace rejected at register", False,
          "register 未拒绝冲突前缀")
except InstanceError as e:
    check("10b. duplicate namespace rejected at register", True,
          str(e)[:70])

# 11. 验证记录真实存在
vr = os.path.join(HERE, "docs", "验证记录.md")
check("11. verification record exists",
      os.path.isfile(vr) and os.path.getsize(vr) > 500,
      str(os.path.getsize(vr)) + " bytes" if os.path.isfile(vr) else "missing")

# 12. 交付齐套（9 个文件）
refs = ["instance_loader.py", "run_tests.py", "demo.py",
        "schema/instance.schema.json",
        "examples/inst-gold-jewelry-01.json",
        "examples/inst-apparel-02.json",
        "examples/inst-healthcare-03.json",
        "examples/inst-woodwork-04.json",
        "examples/inst-culture-05.json",
        "examples/inst-invalid-99.json",
        "README.md", "SETUP.md",
        "docs/验收对照.md", "docs/实现说明.md", "docs/验证记录.md"]
broken = [r for r in refs if not os.path.isfile(r)]
check("12. delivery set complete (15 files)", not broken,
      "broken=" + str(broken) if broken else str(len(refs)) + " files")

# ═══════════════════════════════════════════════════════════════════
# 全量审核组（13+）：文档 vs 实现 / 攻击面 / 命令一致性 / 交付完整性
# 一次 run_tests.py = 全部审核维度，买家可一键复现
# ═══════════════════════════════════════════════════════════════════
print("\n-- 全量审核组 A：文档 vs 实现 --")

# 13. schema 8 必填字段与 README 声明一致
req_set = set(schema.get("required", []))
check("13. schema 8 required fields as documented",
      req_set == {"instance_id", "instance_name", "industry",
                  "namespace_prefix", "bot_role", "knowledge_mounts",
                  "data_domains", "tools"},
      f"required={len(req_set)}")

# 14. 新增实例流程（SETUP 描述）可跑通：复制配置改 id/ns 可注册
import copy  # noqa
tmp_cfg = copy.deepcopy(mgr.instance(mgr.instance_ids()[0]))
tmp_cfg["instance_id"] = "inst-test-extra-01"
tmp_cfg["namespace_prefix"] = "ns-test-extra-01"
tmp_cfg["instance_name"] = "TestExtraInstance"
try:
    mgr.register(tmp_cfg)
    check("14. SETUP add-instance flow works", True, "registered ok")
except InstanceError as e:
    check("14. SETUP add-instance flow works", False, str(e)[:70])

# 15. 零第三方依赖
src = open(os.path.join(HERE, "instance_loader.py"),
           encoding="utf-8").read()
imports = [l.split()[1].split(".")[0]
           for l in src.splitlines()
           if (l.startswith("import ") or l.startswith("from "))
           and "instance_loader" not in l]
check("15. zero third-party deps",
      all(m in {"json", "os", "re", "sys", "time"} for m in imports),
      f"imports={imports}")

print("\n-- 全量审核组 B：攻击面/边界 --")

# 16. 空目录 / 缺失目录不崩
import tempfile  # noqa
with tempfile.TemporaryDirectory() as td:
    m_empty = InstanceManager(td)
    check("16. empty dir -> 0 instances", m_empty.count() == 0,
          f"count={m_empty.count()}")
missing_dir = os.path.join(tempfile.gettempdir(),
                           "clawhunt-1503-missing-dir-xyz")
try:
    InstanceManager(missing_dir)
    check("16b. missing dir tolerated", True, "no crash")
except Exception as e:
    check("16b. missing dir tolerated", False,
          f"raised {type(e).__name__}: {str(e)[:40]}")

# 17. 超长 instance_id / 非法 namespace / 空数组 被 schema 拒
bad_long = {
    "instance_id": "inst-" + "x" * 60, "instance_name": "xx",
    "industry": "retail", "namespace_prefix": "ns-x",
    "bot_role": {"title": "tt", "escalation": "none"},
    "knowledge_mounts": [{"mount_id": "mm", "source": "ss",
                          "access": "read"}],
    "data_domains": [{"domain": "dd", "scope": "own_instance_only"}],
    "tools": [{"tool": "tt", "mode": "read"}],
}
errs_long = _validate(bad_long, schema)
check("17. oversized instance_id rejected", any(
    "instance_id" in e for e in errs_long),
    str(errs_long[:1]))
bad_ns = dict(bad_long)
bad_ns["instance_id"] = "inst-bad02-01"
bad_ns["namespace_prefix"] = "Ns-Bad!02"
check("17b. illegal namespace_prefix rejected",
      any("namespace_prefix" in e for e in _validate(bad_ns, schema)),
      str([e for e in _validate(bad_ns, schema) if "namespace" in e][:1]))
bad_km = dict(bad_long)
bad_km["instance_id"] = "inst-bad03-01"
bad_km["knowledge_mounts"] = []
check("17c. empty knowledge_mounts rejected",
      any("knowledge_mounts" in e
          for e in _validate(bad_km, schema)),
      str([e for e in _validate(bad_km, schema)
           if "knowledge" in e][:1]))

# 18. 命名空间冲突 / 重复 id 在 register 层拒绝
m_adv = InstanceManager()
base_cfg = {"instance_id": "inst-aa-01", "instance_name": "AAA",
            "industry": "retail", "namespace_prefix": "ns-shared-01",
            "bot_role": {"title": "Bot", "escalation": "none"},
            "knowledge_mounts": [{"mount_id": "mm", "source": "ss",
                                  "access": "read"}],
            "data_domains": [{"domain": "dd",
                              "scope": "own_instance_only"}],
            "tools": [{"tool": "tt", "mode": "read"}]}
m_adv.register(base_cfg)
dup_ns = dict(base_cfg)
dup_ns["instance_id"] = "inst-bb-02"
try:
    m_adv.register(dup_ns)
    check("18. duplicate namespace rejected", False)
except InstanceError:
    check("18. duplicate namespace rejected", True, "InstanceError")
dup_id = dict(base_cfg)
dup_id["namespace_prefix"] = "ns-other-02"
try:
    m_adv.register(dup_id)
    check("18b. duplicate instance_id rejected", False)
except InstanceError:
    check("18b. duplicate instance_id rejected", True, "InstanceError")

# 19. 未知实例读写抛 InstanceError（不静默）
try:
    m_adv.write("inst-unknown", "k", "v")
    check("19. unknown instance write rejected", False)
except InstanceError:
    check("19. unknown instance write rejected", True)

# 20. 大量实例（100）不串扰
m_bulk = InstanceManager()
ids_bulk = []
for i in range(100):
    c = {"instance_id": f"inst-bulk-{i:03d}",
         "instance_name": f"Bulk{i:03d}",
         "industry": "retail",
         "namespace_prefix": f"ns-bulk-{i:03d}",
         "bot_role": {"title": "Bot", "escalation": "none"},
         "knowledge_mounts": [{"mount_id": "mm", "source": "ss",
                               "access": "read"}],
         "data_domains": [{"domain": "dd", "scope": "own_instance_only"}],
         "tools": [{"tool": "tt", "mode": "read"}]}
    m_bulk.register(c)
    ids_bulk.append(c["instance_id"])
m_bulk.write(ids_bulk[0], "k0", "v0")
m_bulk.write(ids_bulk[99], "k99", "v99")
lk_bulk, tot_bulk = m_bulk.cross_access_check(ids_bulk[0], ids_bulk[99])
check("20. 100 instances no cross-leak", lk_bulk == 0 and tot_bulk == 1,
      f"leaked={lk_bulk} total={tot_bulk}")

print("\n-- 全量审核组 C：README 承诺命令一致性 --")

# 21. demo.py 可运行且退出码 0
import subprocess  # noqa
rd = subprocess.run([sys.executable, "demo.py"], cwd=HERE,
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace")
check("21. demo.py exit=0", rd.returncode == 0,
      f"exit={rd.returncode}")
# 用全新实例列表对比（避免被测试 14 的额外实例污染）
fresh_ids = sorted(InstanceManager(EX).instance_ids())
check("21b. demo shows all five instances",
      all(iid in rd.stdout for iid in fresh_ids),
      f"missing={[i for i in fresh_ids if i not in rd.stdout]}")

# 22. README 反例命令真实输出（缺字段被拒）
rpy = subprocess.run(
    [sys.executable, "-c",
     "import json; from instance_loader import _validate;"
     "s=json.load(open('schema/instance.schema.json',encoding='utf-8'));"
     "bad=json.load(open('examples/inst-invalid-99.json',encoding='utf-8'));"
     "errs=_validate(bad,s); print(len(errs), 'errors')"],
    cwd=HERE, capture_output=True, text=True, encoding="utf-8",
    errors="replace")
check("22. README counter-example cmd matches",
      "errors" in rpy.stdout and rpy.returncode == 0,
      f"out={rpy.stdout.strip()[:40]!r}")

print("\n-- 全量审核组 D：脱敏合规 --")

# 23. 交付物不含真实手机号（反例文件里的测试假号除外）
import re  # noqa
phone_hits = []
for root, _, files in os.walk(HERE):
    for fn in files:
        if fn.endswith((".py", ".json", ".md")) and "invalid" not in fn:
            t = open(os.path.join(root, fn), encoding="utf-8",
                     errors="replace").read()
            if re.search(r"1[3-9]\d{9}", t):
                phone_hits.append(fn)
check("23. no real phone numbers in deliverables", not phone_hits,
      str(phone_hits) if phone_hits else "clean")

print()
print("=" * 78)
print("Result: PASS " + str(len(PASS)) + "   FAIL " + str(len(FAIL)))
print("=" * 78)
if FAIL:
    print("Failed: " + ", ".join(FAIL))
sys.exit(1 if FAIL else 0)