import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from paperhub.classify.cluster import ClassifyService
from paperhub.errors import PaperHubError, require
from paperhub.security.confirm import Confirmations
from paperhub.security.path_guard import PathGuard, file_hash


def move_new(src: Path, dst: Path) -> None:
    """Exclusive destination, hash-checked copy, then remove source; no clobbering."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        with src.open("rb") as incoming, dst.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        require(file_hash(src) == file_hash(dst), "E_SOURCE_CHANGED", "移动过程中源文件变化")
        shutil.copystat(src, dst)
        src.unlink()
    except FileExistsError:
        raise PaperHubError("E_CONFLICT", "移动目标已存在 / Destination exists") from None


class ClassificationApplier:
    def __init__(self, classifier: ClassifyService, guard: PathGuard, confirmations: Confirmations):
        self.classifier, self.guard, self.confirmations = classifier, guard, confirmations
        self.db = classifier.db

    def _destination(self, path: str | Path) -> Path:
        # Resolve parent only so undo can inspect a leaf symlink without following it.
        path = Path(path).absolute()
        self.guard.write(path.parent)
        return path

    def apply(self, plan_id: str, mode: str, token: str | None) -> dict[str, Any]:
        with self.classifier.lock:
            plan = self.classifier.get(plan_id)
            require(
                plan["status"] == "draft", "E_PLAN_STATE", "方案不在预览状态 / Plan is not a draft"
            )
            require(mode in ("index", "symlink", "move"), "E_ARGUMENT", "分类模式无效")
            operations = []
            for topic in plan["topics"]:
                name = re.sub(r"[^\w\- .]", "_", topic["name"])[:60].strip(" .") or "topic"
                for paper_id in topic["paper_ids"]:
                    snap = plan["snapshots"][paper_id]
                    src = self.guard.read(snap["path"])
                    require(
                        src.is_file() and file_hash(src) == snap["hash"],
                        "E_SOURCE_CHANGED",
                        "论文已变化，请重新扫描并生成方案",
                    )
                    dst = self.guard.output_file(
                        f"classified/{plan_id}/{name}-{topic['id'][:8]}/{paper_id[:8]}-{src.name}"
                    )
                    require(not os.path.lexists(dst), "E_CONFLICT", "分类目标已存在")
                    operations.append(
                        {
                            "src": str(src),
                            "dst": str(dst),
                            "hash": snap["hash"],
                            "paper_id": paper_id,
                            "mode": mode,
                            "state": "pending",
                        }
                    )
            if mode == "move":
                self.confirmations.verify(
                    "move",
                    {"plan": plan, "operations": operations},
                    token,
                    "将移动原论文文件，是否确认？ / Move original files?",
                    operations=operations,
                )
            journal = {
                "id": plan_id,
                "mode": mode,
                "operations": operations,
                "created_at": time.time(),
            }
            self.db.put("oplog", plan_id, journal)
            try:
                for op in operations:
                    src, dst = Path(op["src"]), Path(op["dst"])
                    if mode != "index":
                        self.guard.write(dst)
                        self.guard.read(src)
                        require(file_hash(src) == op["hash"], "E_SOURCE_CHANGED", "论文已变化")
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        if mode == "symlink":
                            dst.symlink_to(src)
                        else:
                            move_new(src, dst)
                            self._update_path(op["paper_id"], dst)
                    op["state"] = "done"
                    self.db.put("oplog", plan_id, journal)
            except Exception as exc:
                plan["status"] = "partial"
                self.db.put("plan", plan_id, plan)
                raise PaperHubError(
                    "E_APPLY_FAILED",
                    "分类应用中断，可调用 undo_classification 恢复",
                    type(exc).__name__,
                    plan_id=plan_id,
                ) from None
            plan.update(status="applied", mode=mode, applied_at=time.time())
            self.db.put("plan", plan_id, plan)
            return plan

    def _update_path(self, paper_id: str, path: Path) -> None:
        stat = path.stat()
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE paper SET file_path=?,file_mtime=?,file_size=?,updated_at=? WHERE id=?",
                (str(path), stat.st_mtime_ns, stat.st_size, time.time(), paper_id),
            )

    def undo(self, plan_id: str) -> dict[str, Any]:
        with self.classifier.lock:
            plan = self.classifier.get(plan_id)
            journal = self.db.get("oplog", plan_id)
            require(
                journal is not None and plan["status"] != "reverted",
                "E_PLAN_STATE",
                "没有可撤销的操作",
            )
            assert journal is not None
            for op in reversed(journal["operations"]):
                if op["state"] == "reverted" or op["mode"] == "index":
                    continue
                src, dst = self.guard.read(op["src"]), self._destination(op["dst"])
                # Recover a crash between the filesystem mutation and journal commit.
                if op["mode"] == "symlink":
                    if os.path.lexists(dst):
                        require(
                            dst.is_symlink() and dst.resolve() == src,
                            "E_CONFLICT",
                            "分类链接已被修改",
                        )
                        dst.unlink()
                elif dst.exists():
                    require(
                        file_hash(dst) == op["hash"], "E_CONFLICT", "移动后论文已修改，拒绝覆盖"
                    )
                    if src.exists():
                        require(
                            op["state"] == "pending" and file_hash(src) == op["hash"],
                            "E_CONFLICT",
                            "原路径已有文件，拒绝覆盖",
                        )
                        dst.unlink()
                    else:
                        move_new(dst, src)
                    self._update_path(op["paper_id"], src)
                elif op["state"] == "done":
                    require(
                        src.exists() and file_hash(src) == op["hash"],
                        "E_CONFLICT",
                        "源与目标文件丢失",
                    )
                    self._update_path(op["paper_id"], src)
                op["state"] = "reverted"
                self.db.put("oplog", plan_id, journal)
            plan["status"] = "reverted"
            self.db.put("plan", plan_id, plan)
            return plan
