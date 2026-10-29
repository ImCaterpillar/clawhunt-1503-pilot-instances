# -*- coding: utf-8 -*-
"""演示：五个隔离的试点实例（验收标准直接演示）

运行：python demo.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from instance_loader import InstanceManager  # noqa

HERE = os.path.dirname(os.path.abspath(__file__))
mgr = InstanceManager(os.path.join(HERE, "examples"))

print("五个隔离试点实例演示\n")
for iid in mgr.instance_ids():
    cfg = mgr.instance(iid)
    print(f"  {iid:<22} industry={cfg['industry']:<18} "
          f"ns={cfg['namespace_prefix']}")

# 各实例写数据
for i, iid in enumerate(mgr.instance_ids()):
    for k in range(3):
        mgr.write(iid, f"secret-{k}", f"private-{iid}")

print("\n--- 交叉访问探测（实例 A 读实例 B，必须 0 条）---")
ids = mgr.instance_ids()
all_ok = True
for i in range(len(ids)):
    for j in range(len(ids)):
        if i == j:
            continue
        leaked, total = mgr.cross_access_check(ids[i], ids[j])
        if leaked != 0:
            all_ok = False
        print(f"  {ids[i]:<22} -> {ids[j]:<22}  leaked={leaked}/{total}")

print("\n--- 自读验证（实例读自己数据，必须 3 条）---")
self_ok = True
for iid in ids:
    leaked, total = mgr.cross_access_check(iid, iid)
    self_ok = self_ok and leaked == total == 3
    print(f"  {iid:<22} 自读 {leaked}/3")

print("\n" + "=" * 46)
print(f"验收结果: 5 实例互相隔离 -> "
      f"{'✅ 通过（交叉 0 泄漏，自读完整）' if all_ok and self_ok else '❌ 失败'}")
print("=" * 46)
sys.exit(0 if (all_ok and self_ok) else 1)