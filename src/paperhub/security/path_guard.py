import hashlib
import os
from pathlib import Path

from paperhub.errors import PaperHubError


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PathGuard:
    def __init__(self, roots: list[Path], output: Path):
        self.roots = [p.expanduser().resolve() for p in roots]
        self.output = output.expanduser().resolve()

    @staticmethod
    def under(path: Path, roots: list[Path]) -> bool:
        return any(path.is_relative_to(root) for root in roots)

    def read(self, path: str | Path) -> Path:
        resolved = Path(path).expanduser().resolve()
        if not self.under(resolved, [*self.roots, self.output]):
            raise PaperHubError(
                "E_PATH_DENIED",
                "路径不在授权论文目录 / Path denied",
                "请在 library.paths 中配置授权目录",
            )
        return resolved

    def write(self, path: str | Path) -> Path:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_relative_to(self.output):
            raise PaperHubError("E_PATH_DENIED", "输出必须位于配置的 output_dir 中 / Output denied")
        return resolved

    def output_file(self, name: str) -> Path:
        return self.write(self.output / name)


def write_new(path: Path, content: str | bytes) -> None:
    """Create only; never overwrite an existing file or follow a leaf symlink."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
            stream.write(content.encode("utf-8") if isinstance(content, str) else content)
    except FileExistsError:
        raise PaperHubError("E_CONFLICT", "目标文件已存在 / Output already exists") from None
