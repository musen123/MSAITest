"""
Celery 任务配置

定义 Celery Beat 定时任务配置
"""

from celery.schedules import crontab

# Celery Beat 定时任务配置
beat_schedule = {
    # 每天凌晨 2 点清理过期日志
    "cleanup-old-logs": {
        "task": "app.tasks.system.cleanup_old_logs",
        "schedule": crontab(hour=2, minute=0),
    },
    # 每 5 分钟检查失败任务
    "check-failed-tasks": {
        "task": "app.tasks.system.check_failed_tasks",
        "schedule": 300.0,  # 5 分钟
    },
    # 每小时同步外部系统数据
    "sync-external-data": {
        "task": "app.tasks.system.sync_external_data",
        "schedule": crontab(minute=0),  # 每小时
    },
    # TODO: 添加更多定时任务
}
