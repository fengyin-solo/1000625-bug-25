"""结果复核业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "review"
REQUIRED_FIELDS = ["复核编号", "关联结果", "复核项目"]
OPTIONAL_FIELDS = ["复核人", "复核意见", "差异说明"]
STATUS_PENDING = "待复核"
STATUS_DOING = "复核中"
STATUS_PASSED = "已通过"
STATUS_RETEST = "需重测"
STATUS_ORDER = [STATUS_PENDING, STATUS_DOING, STATUS_PASSED, STATUS_RETEST]
DISPLAY_FIELD = "复核状态"
# 每个动作允许的起始状态、必填字段与长度上限，前端与接口共用同一套口径。
ACTION_RULES: dict[str, dict[str, Any]] = {
    "开始复核": {
        "target": STATUS_DOING,
        "from": {STATUS_PENDING},
        "required": {},
    },
    "确认通过": {
        "target": STATUS_PASSED,
        "from": {STATUS_DOING},
        "required": {"复核意见": "确认通过必须填写复核意见"},
    },
    "发起重测": {
        "target": STATUS_RETEST,
        "from": {STATUS_DOING},
        "required": {"差异说明": "发起重测必须填写差异说明"},
    },
}
FIELD_MAX_LENGTH = {"复核意见": 500, "差异说明": 500}


class ReviewVersionConflict(Exception):
    """提交时记录版本号已落后，说明已被其他人先提交。"""

    def __init__(self, current_version: int) -> None:
        self.current_version = current_version
        super().__init__(
            f"该复核记录刚被其他人更新过（当前版本 {current_version}），请刷新后重新提交"
        )


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    """以内部 status 为准同步展示用的「复核状态」。

    历史数据里「复核状态」可能是占位文本或上一轮动作的旧值，列表、详情、统计
    都经过这里，保证三处口径一致；不改动 pending/abnormal，避免影响其他模块的概览统计。
    """
    status = row.get("status")
    if status not in STATUS_ORDER:
        status = row.get(DISPLAY_FIELD) if row.get(DISPLAY_FIELD) in STATUS_ORDER else STATUS_PENDING
    row["status"] = status
    row[DISPLAY_FIELD] = status
    row.setdefault("version", 1)
    return row


class ReviewService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [_normalize(dict(row)) for row in store.rows(MODULE)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("复核编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def stats(self) -> dict[str, int]:
        """复核看板统计：待复核、本月通过、需重测，状态口径与列表完全一致。"""
        month_prefix = date.today().strftime("%Y-%m")
        rows = [_normalize(dict(row)) for row in store.rows(MODULE)]
        return {
            "pending": sum(1 for row in rows if row["status"] == STATUS_PENDING),
            "passed_month": sum(
                1
                for row in rows
                if row["status"] == STATUS_PASSED
                and str(row.get("复核时间", "")).startswith(month_prefix)
            ),
            "retest": sum(1 for row in rows if row["status"] == STATUS_RETEST),
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return _normalize(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
        entry["status"] = STATUS_PENDING
        entry[DISPLAY_FIELD] = STATUS_PENDING
        entry["pending"] = True
        entry["abnormal"] = False
        entry["version"] = 1
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
        expected_version: int | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"复核记录 {entry_id} 不存在或已归档"
        _normalize(entry)
        rule = ACTION_RULES.get(action)
        if rule is None:
            return None, f"动作「{action}」不属于结果复核可执行范围"
        current_status = entry["status"]
        current_version = int(entry.get("version", 1))
        # 乐观锁优先判定：两人同时提交时，版本落后的一方会被拦下，
        # 避免先校验当前状态而给出误导性提示，也不允许互相覆盖。
        if expected_version is not None and int(expected_version) != current_version:
            raise ReviewVersionConflict(current_version)
        if current_status not in rule["from"]:
            allowed = "、".join(rule["from"])
            return None, f"复核记录当前为「{current_status}」，仅{allowed}状态可执行「{action}」"
        updates: dict[str, str] = {}
        for field, message in rule["required"].items():
            # 只认本次动作提交的内容；不能让记录上的历史/占位字段替空输入兜底。
            text = str(values.get(field) or "").strip()
            if not text:
                return None, message
            limit = FIELD_MAX_LENGTH.get(field)
            if limit and len(text) > limit:
                return None, f"{field}过长（最多 {limit} 字，当前 {len(text)} 字），请精简后再提交"
            updates[field] = text
        target = rule["target"]
        entry["status"] = target
        entry[DISPLAY_FIELD] = target
        entry["pending"] = target in (STATUS_PENDING, STATUS_DOING, STATUS_RETEST)
        entry["abnormal"] = target == STATUS_RETEST
        entry["version"] = current_version + 1
        entry.update(updates)
        if action in ("确认通过", "发起重测"):
            entry["复核时间"] = date.today().isoformat()
        return entry, f"复核记录已{action}"
