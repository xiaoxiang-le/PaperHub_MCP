from typing import Any


class PaperHubError(Exception):
    def __init__(self, code: str, message: str, hint: str = "", **details: Any):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "hint": self.hint,
                **self.details,
            },
        }


def require(condition: bool, code: str, message: str, **details: Any) -> None:
    if not condition:
        raise PaperHubError(code, message, **details)
