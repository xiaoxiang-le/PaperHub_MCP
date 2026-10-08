import json
import re
from typing import Any


def bib_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "&": r"\&",
        "%": r"\%",
        "_": r"\_",
        "#": r"\#",
        "$": r"\$",
    }
    return "".join(replacements.get(c, c) for c in value)


def export_references(papers: list[dict[str, Any]], style: str) -> str:
    if style == "csl-json":
        return json.dumps(
            [
                {
                    "id": p["id"],
                    "type": "article-journal",
                    "title": p["title"],
                    "author": [{"literal": a} for a in p.get("authors", [])],
                    **({"issued": {"date-parts": [[p["year"]]]}} if p.get("year") else {}),
                    **({"DOI": p["doi"]} if p.get("doi") else {}),
                }
                for p in papers
            ],
            ensure_ascii=False,
            indent=2,
        )
    entries = []
    for p in papers:
        key = "paper" + re.sub(r"[^a-zA-Z0-9]", "", p["id"])
        fields = {
            "title": p["title"],
            "author": " and ".join(p.get("authors", [])),
            "year": str(p.get("year") or ""),
            "doi": p.get("doi", ""),
        }
        body = ",\n".join(f"  {k} = {{{bib_escape(v)}}}" for k, v in fields.items() if v)
        entries.append(f"@article{{{key},\n{body}\n}}")
    return "\n\n".join(entries)
