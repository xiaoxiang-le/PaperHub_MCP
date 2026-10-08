from difflib import SequenceMatcher
from itertools import combinations
from typing import Any


def find_duplicates(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs = []
    for left, right in combinations(papers, 2):
        reasons = []
        if left["file_hash"] == right["file_hash"]:
            reasons.append("sha256")
        if left.get("doi") and left["doi"].casefold() == right.get("doi", "").casefold():
            reasons.append("doi")
        if (
            SequenceMatcher(None, left["title"].casefold(), right["title"].casefold()).ratio()
            >= 0.92
        ):
            reasons.append("title_similarity")
        if reasons:
            pairs.append({"paper_ids": [left["id"], right["id"]], "reasons": reasons})
    return pairs
