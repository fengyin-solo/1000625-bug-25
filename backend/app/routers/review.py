"""结果复核接口：维护复核记录，覆盖开始复核、确认通过、发起重测等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.review import ReviewConflictError, ReviewService

router = APIRouter(prefix="/api/review", tags=["结果复核"])

service = ReviewService()

LIST_FIELDS = ["复核编号", "关联结果", "复核项目", "复核人", "复核意见", "复核时间", "差异说明", "复核状态"]
STATUSES = ["待复核", "复核中", "已通过", "需重测"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按复核编号检索"),
    status: str | None = Query(default=None, description="待复核、复核中、已通过、需重测"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按复核编号与状态过滤结果复核列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats")
def review_stats() -> dict[str, Any]:
    """复核统计卡片：待复核、本月通过、需重测，与列表共用同一个状态源。"""
    return {"items": service.stats()}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出结果复核清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "review", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条复核记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"复核记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条复核记录，缺字段或编号重复时说明原因而不是静默丢弃。"""
    entry, errors = service.create_entry(payload.values)
    if errors:
        return ActionResult(ok=False, message="；".join(errors))
    return ActionResult(ok=True, message="复核记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条复核记录执行动作；版本冲突返回 409，提示刷新后重试而不是互相覆盖。"""
    action = str(payload.values.get("action") or "").strip()
    try:
        entry, message = service.run_action(entry_id, action, payload.values)
    except ReviewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
