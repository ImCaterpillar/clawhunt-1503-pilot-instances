# -*- coding: utf-8 -*-
"""客户 Agent 试点实例：统一模板 + 五个隔离实例的加载与校验器

对应 ClawHunt 任务 #1503（企业 Agent 系统 16/50｜客户 Agent 试点实例），
验收标准：**提供五个实例配置及互相隔离的验证记录**。

设计：
  - 统一模板 `schema/instance.schema.json`（draft-07 必要子集校验，
    本文件内置，零第三方依赖）
  - 每个实例一个 JSON 配置（examples/inst-*.json），含全局唯一
    namespace_prefix —— 这是隔离的关键：所有数据读写都限定在
    `{namespace_prefix}::*` 命名空间
  - `InstanceManager`：load 全部实例 → 校验通过 → 建立隔离注册表
    （instance_id ↔ namespace_prefix 唯一映射），并提供交叉访问探测
  - 隔离验证：instance A 尝试读写 instance B 的命名空间 → 必须返回空
    + 审计；同模板但不同实例的数据互不可见
"""
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class InstanceError(Exception):
    pass


# ── 迷你 JSON Schema draft-07 必要子集（复制自 #1489 validate.py 风格）──
def _type_ok(value, t):
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "null":
        return value is None
    return True


def _validate(instance, schema, path="$"):
    errors = []
    if "type" in schema and not _type_ok(instance, schema["type"]):
        return [f"{path}: 期望 {schema['type']} 实为 {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: 值 {instance!r} 不在允许集合 {schema['enum']}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: 长度 {len(instance)} < {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: 长度 {len(instance)} > {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: 值 {instance!r} 不匹配模式 {schema['pattern']}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: 元素数 {len(instance)} < {schema['minItems']}")
        if "items" in schema:
            for i, item in enumerate(instance):
                errors += _validate(item, schema["items"], f"{path}[{i}]")
    if isinstance(instance, dict):
        if "required" in schema:
            for k in schema["required"]:
                if k not in instance:
                    errors.append(f"{path}: 缺少必填字段 {k!r}")
        if schema.get("additionalProperties") is False \
                and "properties" in schema:
            for k in instance:
                if k not in schema["properties"]:
                    errors.append(f"{path}: 不允许的额外字段 {k!r}")
        if "properties" in schema:
            for k, sub in schema["properties"].items():
                if k in instance:
                    errors += _validate(instance[k], sub, f"{path}.{k}")
    return errors


class InstanceManager:
    """加载并管理相互隔离的试点实例。"""

    SCHEMA = None

    def __init__(self, instances_dir=None):
        # 命名空间注册表：namespace_prefix -> set(instance 数据键)
        self._registry = {}
        self._instances = {}
        self._audit = []
        # 先加载 schema（register 校验需要它），再加载实例
        here = os.path.dirname(os.path.abspath(__file__))
        self.schema = json.load(open(
            os.path.join(here, "schema", "instance.schema.json"),
            encoding="utf-8"))
        if instances_dir:
            self.load_dir(instances_dir)

    # ── 加载 ─────────────────────────────────────────────────────────
    def load_dir(self, d):
        """加载目录下所有 inst-*.json 实例配置（按文件名排序）。

        跳过文件名含 'invalid' 的反例文件——反例只用于校验器的
        单元测试（拒绝路径），不进入正常注册流程。
        目录不存在/为空时优雅返回 0，不崩溃。
        """
        if not os.path.isdir(d):
            return 0
        files = sorted(f for f in os.listdir(d)
                       if f.startswith("inst-") and f.endswith(".json")
                       and "invalid" not in f)
        for fn in files:
            cfg = json.load(open(os.path.join(d, fn), encoding="utf-8"))
            self.register(cfg)
        return len(files)

    def register(self, cfg):
        """注册一个实例：先校验 schema + 命名空间唯一性，再入注册表。"""
        errs = _validate(cfg, self.schema)
        if errs:
            raise InstanceError("实例校验失败: " + "; ".join(errs[:5]))
        iid = cfg["instance_id"]
        ns = cfg["namespace_prefix"]
        if iid in self._instances:
            raise InstanceError(f"重复 instance_id: {iid}")
        if ns in self._registry:
            raise InstanceError(f"命名空间前缀冲突: {ns} "
                                f"(实例 {iid} 试图占用已用前缀)")
        self._registry[ns] = set()
        self._instances[iid] = cfg
        return iid

    # ── 数据读写（隔离核心）────────────────────────────────────────
    def write(self, instance_id, key, value, requester=None):
        """写数据到指定实例的命名空间；key 归属该实例。

        requester: 可选，调用方自称的身份（instance_id）。
        - requester 缺省（None）= 兼容原语模式：由上层保证可信；
        - requester 给定且 ≠ instance_id = 越权写，抛 InstanceError
          （与文档「数据读写限定在各自命名空间」一致）。
        """
        if requester is not None and requester != instance_id:
            self._audit.append({
                "ts": time.time(),
                "type": "cross_instance_write_blocked",
                "requester": requester,
                "target": instance_id,
            })
            raise InstanceError(
                f"写入方 {requester} 无权写入实例 {instance_id} 的命名空间")
        ns, cfg = self._ns_of(instance_id)
        self._registry[ns].add(key)
        return key

    def read(self, requester_id, target_id):
        """读取目标实例命名空间里的 key 集合。

        隔离规则：requester 只能读自己实例的数据。
        跨实例读取 → 返回空集 + 审计（不泄露目标实例的存在性）；
        目标实例不存在 → 同样返回空集 + 审计（消除存在性侧信道——
        「未知实例」与「有数据但不给你看」在外部观感上不可区分）。
        """
        try:
            r_ns, _ = self._ns_of(requester_id)
        except InstanceError:
            self._audit.append({
                "ts": time.time(), "type": "unknown_requester_read",
                "requester": requester_id, "target": target_id,
                "returned": 0})
            return set()
        # 目标实例不存在：不抛错，返回空并审计（防侧信道）
        t_cfg = self._instances.get(target_id)
        if t_cfg is None:
            self._audit.append({
                "ts": time.time(),
                "type": "cross_instance_read_blocked",
                "requester": requester_id,
                "requester_ns": r_ns,
                "target": target_id,
                "target_ns": "(unknown)",
                "returned": 0,
            })
            return set()
        t_ns = t_cfg["namespace_prefix"]
        if r_ns != t_ns:
            self._audit.append({
                "ts": time.time(),
                "type": "cross_instance_read_blocked",
                "requester": requester_id,
                "requester_ns": r_ns,
                "target": target_id,
                "target_ns": t_ns,
                "returned": 0,
            })
            return set()
        return set(self._registry.get(r_ns, set()))

    def _ns_of(self, instance_id):
        cfg = self._instances.get(instance_id)
        if not cfg:
            raise InstanceError(f"未知实例: {instance_id}")
        return cfg["namespace_prefix"], cfg

    # ── 隔离验证（验收核心）──────────────────────────────────────
    def cross_access_check(self, requester_id, target_id):
        """交叉访问探测：requester 试图读 target 的数据。

        返回 (leaked, total)：
          - total = target 实例实际写入的数据条数
          - leaked = requester 能读到的条数（必须恒为 0）
        """
        t_ns, _ = self._ns_of(target_id)
        total = len(self._registry.get(t_ns, set()))
        leaked = len(self.read(requester_id, target_id))
        return leaked, total

    def instance_ids(self):
        return sorted(self._instances)

    def instance(self, iid):
        return self._instances.get(iid)

    def audit_log(self):
        return list(self._audit)

    def count(self):
        return len(self._instances)