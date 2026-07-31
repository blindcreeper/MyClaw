import os
import json
import asyncio
import calendar
from datetime import datetime, timedelta
from .config import TASKS_FILE
from .tools.builtins import tasks_lock

async def pacemaker_loop(task_queue: asyncio.Queue, check_interval: int = 10):
    """
    后台心脏起搏器协程（带并发锁和循环任务续期功能）
    """
    while True:
        await asyncio.sleep(check_interval)

        if not os.path.exists(TASKS_FILE): continue

        now = datetime.now()
        pending_tasks = []
        triggered_tasks = []

        #线程锁，防止多线程/多协程同时读写任务文件导致的竞争条件和数据损坏
        with tasks_lock:
            try:
                with open(TASKS_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        continue
                    tasks = json.loads(content)
            except Exception:
                continue

            if not tasks:
                continue

            for t in tasks:
                try:
                    target_dt = datetime.strptime(t["time"], "%Y-%m-%d %H:%M:%S")
                    if now >= target_dt:
                        triggered_tasks.append(t) # 被记录为需要触发的任务

                        # 若是循环任务把循环次数减一，次数耗尽不再触发
                        repeat_freq = t.get("repeat")
                        if repeat_freq:
                            repeat_count = t.get("repeat_count")

                            if repeat_count is not None:
                                if repeat_count <= 1:
                                    continue
                                else:
                                    t["repeat_count"] = repeat_count - 1

                            if repeat_freq == "hourly":
                                    next_dt = target_dt + timedelta(hours=1)
                            elif repeat_freq == "daily":
                                    next_dt = target_dt + timedelta(days=1)
                            elif repeat_freq == "weekly":
                                    next_dt = target_dt + timedelta(days=7)
                            elif repeat_freq == "monthly":
                                    month = target_dt.month + 1
                                    year = target_dt.year
                                    if month > 12:
                                        month = 1
                                        year += 1
                                    last_day = calendar.monthrange(year, month)[1]
                                    day = min(target_dt.day, last_day)
                                    next_dt = target_dt.replace(year=year, month=month, day=day)
                            else:
                                continue

                            t["target_time"] = next_dt.strftime("%Y-%m-%d %H:%M:%S")
                            pending_tasks.append(t)
                except Exception:
                   pass

            # 将未触发的任务，循环的续期后的任务重新写入文件
            if triggered_tasks:
                try:
                    with open(TASKS_FILE, "w", encoding="utf-8") as f:
                        json.dump(pending_tasks, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

            for t in triggered_tasks:
                system_msg = (
                f"【系统内部心跳触发】\n"
                f"你设定的定时任务已到期，请立即主动提醒用户或执行动作。\n"
                f"任务内容：{t['description']}"
            )
                await task_queue.put(system_msg)

                    
                        
                    
        