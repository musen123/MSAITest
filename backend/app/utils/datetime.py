"""
日期时间工具函数
"""

from datetime import datetime, timedelta
from typing import Optional


def now() -> datetime:
    """
    获取当前时间

    Returns:
        datetime: 当前时间
    """
    return datetime.now()


def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    获取格式化的当前时间字符串

    Args:
        fmt: 时间格式

    Returns:
        str: 格式化的时间字符串
    """
    return datetime.now().strftime(fmt)


def add_days(days: int) -> datetime:
    """
    获取 N 天后的时间

    Args:
        days: 天数

    Returns:
        datetime: N 天后的时间
    """
    return datetime.now() + timedelta(days=days)


def add_hours(hours: int) -> datetime:
    """
    获取 N 小时后的时间

    Args:
        hours: 小时数

    Returns:
        datetime: N 小时后的时间
    """
    return datetime.now() + timedelta(hours=hours)


def add_minutes(minutes: int) -> datetime:
    """
    获取 N 分钟后的时间

    Args:
        minutes: 分钟数

    Returns:
        datetime: N 分钟后的时间
    """
    return datetime.now() + timedelta(minutes=minutes)


def timestamp() -> int:
    """
    获取当前时间戳（秒）

    Returns:
        int: 时间戳
    """
    return int(datetime.now().timestamp())


def timestamp_ms() -> int:
    """
    获取当前时间戳（毫秒）

    Returns:
        int: 时间戳（毫秒）
    """
    return int(datetime.now().timestamp() * 1000)


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化日期时间

    Args:
        dt: 日期时间对象
        fmt: 格式字符串

    Returns:
        str: 格式化的字符串
    """
    return dt.strftime(fmt)


def parse_datetime(dt_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
    """
    解析日期时间字符串

    Args:
        dt_str: 日期时间字符串
        fmt: 格式字符串

    Returns:
        Optional[datetime]: 解析后的日期时间，失败返回 None
    """
    try:
        return datetime.strptime(dt_str, fmt)
    except (ValueError, TypeError):
        return None


def get_age(birth_date: datetime) -> int:
    """
    根据出生日期计算年龄

    Args:
        birth_date: 出生日期

    Returns:
        int: 年龄
    """
    today = datetime.now()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age
