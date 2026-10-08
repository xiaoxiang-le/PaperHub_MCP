import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from paperhub.core.db import Database
from paperhub.errors import PaperHubError

TaskRunner = Callable[["TaskContext", dict[str, Any]], Awaitable[dict[str, Any]]]


class TaskContext:
    def __init__(self, manager: "TaskService", task_id: str):
        self.manager, self.id = manager, task_id

    def check(self) -> None:
        if self.manager.status(self.id).get("cancel_requested"):
            raise PaperHubError("E_TASK_CANCELLED", "任务已取消 / Task cancelled")

    def progress(self, completed: int, total: int) -> None:
        self.check()
        self.manager.update(
            self.id, progress=completed / max(1, total), completed=completed, total=total
        )


class TaskService:
    def __init__(self, db: Database):
        self.db = db
        self.runners: dict[str, TaskRunner] = {}
        self.active: dict[str, asyncio.Task[None]] = {}
        for task in db.list("task"):
            if task["status"] in ("pending", "running"):
                self.update(task["id"], status="interrupted", cancel_requested=False)

    def status(self, task_id: str) -> dict[str, Any]:
        task = self.db.get("task", task_id)
        if task is None:
            raise PaperHubError("E_NOT_FOUND", "任务不存在 / Task not found")
        return task

    def update(self, task_id: str, **fields: Any) -> None:
        with self.db.lock:
            task = self.status(task_id)
            task.update(fields, updated_at=time.time())
            self.db.put("task", task_id, task)

    def submit(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        self.db.put(
            "task",
            task_id,
            {
                "id": task_id,
                "type": kind,
                "payload": payload,
                "status": "pending",
                "progress": 0,
                "cancel_requested": False,
                "created_at": time.time(),
                "updated_at": time.time(),
            },
        )
        self._launch(task_id)
        return {"task_id": task_id, "status": "pending"}

    def _launch(self, task_id: str) -> None:
        self.active[task_id] = asyncio.create_task(self._run(task_id))

    async def _run(self, task_id: str) -> None:
        task = self.status(task_id)
        self.update(task_id, status="running")
        try:
            result = await self.runners[task["type"]](TaskContext(self, task_id), task["payload"])
            TaskContext(self, task_id).check()
            self.update(task_id, status="done", progress=1, result=result)
        except PaperHubError as exc:
            self.update(
                task_id,
                status="cancelled" if exc.code == "E_TASK_CANCELLED" else "failed",
                result=exc.as_dict(),
            )
        except asyncio.CancelledError:
            self.update(task_id, status="interrupted")
        except Exception as exc:
            # Never persist exception bodies: providers may echo request content or keys.
            self.update(
                task_id,
                status="failed",
                result={
                    "ok": False,
                    "error": {
                        "code": "E_INTERNAL",
                        "message": f"任务失败 / Task failed ({type(exc).__name__})",
                    },
                },
            )
        finally:
            self.active.pop(task_id, None)

    def cancel(self, task_id: str) -> dict[str, Any]:
        task = self.status(task_id)
        if task["status"] in ("pending", "running"):
            self.update(task_id, cancel_requested=True)
        return self.status(task_id)

    def resume(self, task_id: str) -> dict[str, Any]:
        task = self.status(task_id)
        if task_id in self.active or task["status"] not in ("failed", "cancelled", "interrupted"):
            raise PaperHubError("E_TASK_STATE", "该任务当前不可恢复 / Task cannot be resumed")
        self.update(task_id, status="pending", cancel_requested=False)
        self._launch(task_id)
        return {"task_id": task_id, "status": "pending"}

    async def close(self) -> None:
        running = list(self.active.values())
        for task in list(self.active):
            self.cancel(task)
        if running:
            await asyncio.gather(*running, return_exceptions=True)
