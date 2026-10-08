from typing import Any


class ExamplePlugin:
    def generate(self, ctx: Any, options: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": options.get("title", "Example outline"),
            "sections": [
                {
                    "title": "Related Work",
                    "points": ["Compare the selected papers"],
                    "citations": [paper["id"] for paper in ctx.papers],
                }
            ],
            "notes": ["Reading suggestions; verify every claim against the source papers."],
        }
