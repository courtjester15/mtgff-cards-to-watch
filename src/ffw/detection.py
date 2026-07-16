from __future__ import annotations

import re
from typing import Any

START_PATTERNS = (
    r"cards?\s+to\s+watch",
    r"picks?\s+of\s+the\s+week",
    r"watch\s*list",
)
END_PATTERNS = (
    r"(that(?:'s| is) all|wrap(?:s|ping)? up).{0,40}(cards?|picks?)",
    r"(thanks for listening|until next week|patreon|listener questions)",
)


def locate_cards_to_watch(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Locate the recurring section without performing recommendation extraction."""
    ordered = sorted(segments, key=lambda item: float(item.get("start", 0)))
    start_index = None
    for index, segment in enumerate(ordered):
        text = str(segment.get("text", ""))
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in START_PATTERNS):
            start_index = index
            break
    if start_index is None:
        return {
            "located": False,
            "start_seconds": None,
            "end_seconds": None,
            "label": "Cards to Watch",
            "confidence": "low",
            "review_reason": "No credible Cards to Watch section marker was found.",
            "segments": [],
        }
    end_index = len(ordered)
    explicit_end = False
    for index in range(start_index + 1, len(ordered)):
        text = str(ordered[index].get("text", ""))
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in END_PATTERNS):
            end_index = index + 1
            explicit_end = True
            break
    selected = ordered[start_index:end_index]
    return {
        "located": True,
        "start_seconds": int(float(selected[0].get("start", 0))),
        "end_seconds": int(float(selected[-1].get("end", selected[-1].get("start", 0)))),
        "label": "Cards to Watch",
        "confidence": "high" if explicit_end else "medium",
        "review_reason": None if explicit_end else "Section start found, but no explicit end marker was detected.",
        "segments": selected,
    }
