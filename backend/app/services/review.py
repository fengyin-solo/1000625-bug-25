"""结果复核业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "review"
REQUIRED_FIELDS = ["复核编号", "关联结果", "复核项目"]
STATUS_ORDER = ["待复核", "复核中", "已通过", "需重测"]
ACTION_RULES = {"开始复核": "复核中", "确认通过": "已通过", "发起重测": "需重测"}
NEGATIVE_ACTIONS: list[str] = []
# 动作级必填：确认通过必须留复核意见，发起重测必须写差异说明
ACTION_REQUIRED_FIELDS = {"确认通过": ["复核意见"], "发起重测": ["差异说明"]}
# 长文本上限：差异说明、复核意见过长会把列表撑坏，提交入口统一拦住
FIELD_LIMITS = {"复核意见": 200, "差异说明": 200}
# 仍在复核流水线里的状态：列表统计与概览“待处理”共用这一口径
PENDING_STATUSES = {"待复核", "复核中"}
# 动作提交时允许回写到记录上的字段
ACTION_WRITABLE_FIELDS = ["复核人", "复核意见", "差异说明"]


class ReviewConflictError(Exception):
    """提交时版本对不上：这条复核记录刚被别人改过，不能静默覆盖。"""


class ReviewService:
    def _normalize(self, entry: dict[str, Any]) -> dict[str, Any]:
        """把展示字段对齐到唯一状态源，列表、详情、统计看到的才是同一个复核状态。"""
        status = str(entry.get("status") or STATUS_ORDER[0])
        if status not in STATUS_ORDER:
            status = STATUS_ORDER[0]
        entry["status"] = status
        entry["复核状态"] = status
        entry["pending"] = status in PENDING_STATUSES
        try:
            entry["version"] = int(entry.get("version") or 0)
        except (TypeError, ValueError):
            entry["version"] = 0
        return entry

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._normalize(row) for row in store.rows(MODULE)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("复核编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._normalize(entry)

    def stats(self) -> list[dict[str, Any]]:
        """统计卡片口径：全部从唯一状态源推导，不另存冗余计数，避免和列表对不上。"""
        rows = [self._normalize(row) for row in store.rows(MODULE)]
        month_prefix = date.today().strftime("%Y-%m")
        return [
            {"label": "待复核记录", "value": sum(1 for row in rows if row["status"] in PENDING_STATUSES)},
            {
                "label": "本月通过数",
                "value": sum(
                    1
                    for row in rows
                    if row["status"] == "已通过" and str(row.get("复核时间") or "").startswith(month_prefix)
                ),
            },
            {"label": "需重测项数", "value": sum(1 for row in rows if row["status"] == "需重测")},
        ]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, [f"缺少必填字段：{'、'.join(missing)}"]
        rows = store.rows(MODULE)
        code = str(values.get("复核编号") or "").strip()
        if any(str(row.get("复核编号") or "") == code for row in rows):
            return None, [f"复核编号 {code} 已存在，请勿重复登记"]
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: str(values.get(field)).strip() for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["abnormal"] = False
        entry["version"] = 0
        rows.append(self._normalize(entry))
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"复核记录 {entry_id} 不存在或已归档"
        self._normalize(entry)
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于结果复核可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        # 乐观并发锁：提交必须带上看到时的版本号，对不上就说明别人先改了
        try:
            expected_version = int(values.get("version"))
        except (TypeError, ValueError):
            return None, "提交缺少记录版本号，请刷新列表后重新操作"
        if expected_version != entry["version"]:
            raise ReviewConflictError(
                f"复核记录 {entry.get('复核编号') or entry_id} 刚被其他人更新"
                f"（当前状态：{entry['status']}），请刷新列表后重试"
            )
        # 动作级必填：确认通过要复核意见，发起重测要差异说明
        missing = [
            field
            for field in ACTION_REQUIRED_FIELDS.get(action, [])
            if not str(values.get(field) or "").strip()
        ]
        if missing:
            return None, f"「{action}」需要先填写：{'、'.join(missing)}"
        # 长文本上限：超长的差异说明会把列表撑坏
        for field, limit in FIELD_LIMITS.items():
            text = str(values.get(field) or "").strip()
            if len(text) > limit:
                return None, f"「{field}」最多 {limit} 字，当前 {len(text)} 字，请精简后再提交"
        for field in ACTION_WRITABLE_FIELDS:
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
        entry["status"] = target
        entry["复核时间"] = date.today().isoformat()
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        entry["version"] += 1
        self._normalize(entry)
        return entry, f"复核记录已{action}"
