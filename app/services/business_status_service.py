"""
Chef business status helpers.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from app.models.user import User

TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
DEFAULT_SERVICE_START_TIME = "09:00"
DEFAULT_SERVICE_END_TIME = "21:00"


def normalize_service_time(value: Optional[str], fallback: str) -> str:
    """Normalize HH:MM strings and fall back to a safe default."""
    if not value:
        return fallback

    normalized = value.strip()
    if not TIME_PATTERN.fullmatch(normalized):
        return fallback
    return normalized


def service_time_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def is_time_in_service_window(target_time: str, start_time: str, end_time: str) -> bool:
    target_minutes = service_time_to_minutes(target_time)
    start_minutes = service_time_to_minutes(start_time)
    end_minutes = service_time_to_minutes(end_time)
    return start_minutes <= target_minutes < end_minutes


def get_chef_service_window(chef: User) -> tuple[str, str]:
    return (
        normalize_service_time(getattr(chef, "service_start_time", None), DEFAULT_SERVICE_START_TIME),
        normalize_service_time(getattr(chef, "service_end_time", None), DEFAULT_SERVICE_END_TIME),
    )


def build_chef_business_status(chef: User, delivery_time: Optional[datetime] = None) -> dict:
    """Build a frontend-friendly business status payload."""
    start_time, end_time = get_chef_service_window(chef)
    is_open = bool(getattr(chef, "is_open", True))
    rest_notice = (getattr(chef, "rest_notice", None) or "").strip() or None

    accepting_orders = is_open
    if is_open and delivery_time is not None:
        accepting_orders = is_time_in_service_window(
            delivery_time.strftime("%H:%M"),
            start_time,
            end_time,
        )

    if not is_open:
        status_text = rest_notice or "休息中"
    elif delivery_time is not None and not accepting_orders:
        status_text = f"当前仅支持 {start_time}-{end_time} 的配送时间"
    else:
        status_text = f"营业中 · {start_time}-{end_time} 可接单"

    return {
        "is_open": is_open,
        "service_start_time": start_time,
        "service_end_time": end_time,
        "rest_notice": rest_notice,
        "accepting_orders": accepting_orders,
        "status_text": status_text,
    }


def get_chef_order_unavailable_reason(chef: User, delivery_time: datetime) -> Optional[str]:
    """Return a clear reason when the chef cannot accept the order."""
    status = build_chef_business_status(chef, delivery_time)
    if status["accepting_orders"]:
        return None

    if not status["is_open"]:
        return status["rest_notice"] or "大厨当前休息中，暂不接单"

    return (
        f"大厨当前仅支持 {status['service_start_time']}-{status['service_end_time']} 的配送时间，"
        "请重新选择配送时间"
    )
