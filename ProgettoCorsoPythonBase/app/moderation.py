# app/moderation.py
import re
from dataclasses import dataclass
from typing import List
from flask import current_app as app

@dataclass
class ModResult:
    action: str   # 'approve' | 'pending' | 'reject'
    score: float  # 0..1

# elenco parole/insulti “hard block” (case-insensitive, word boundary, piccole varianti)
_HARD_PATTERNS: List[str] = [
    r"\b(vaf+ancul\w*)\b",
    r"\b(stronz\w*)\b",
    r"\b(coglion\w*)\b",
    r"\b(puttan\w*|troi\w*)\b",
    r"\b(merd\w*)\b",
    r"\b(muori|ammazzati|ucciditi|suicidati)\b",
    r"\b(negro|zingar\w*|froci\w*|lesbic\w*)\b",
    r"\b(cornut\w*|bastard\w*)\b",
    r"\b(deficient\w*|idiot\w*)\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _HARD_PATTERNS]

def _has_hard_abuse(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return any(p.search(t) for p in _COMPILED)

def _soft_score(text: str) -> float:
    """Heuristica semplice: più parole dalla softlist => score più alto (0..1)."""
    if not text:
        return 0.0
    t = text.lower()
    soft_words = [
        "stupido", "idiota", "cretino", "odioso", "schifo",
        "odi", "odio", "imbecille", "vergogna"
    ]
    hits = sum(t.count(w) for w in soft_words)
    # normalizza: 0 -> 0.0, >=3 -> ~1.0
    return min(1.0, hits / 3.0)

def assess(text: str) -> ModResult:
    """Regole:
    - hard list => reject (score=1.0)
    - altrimenti calcola soft score e confronta con soglie dal config:
      score < PENDING => approve
      PENDING <= score < REJECT => pending
      score >= REJECT => reject
    """
    if _has_hard_abuse(text):
        return ModResult(action="reject", score=1.0)

    score = _soft_score(text)
    pending_th = float(getattr(app.config, "TOXICITY_PENDING_THRESHOLD", 0.75))
    reject_th  = float(getattr(app.config, "TOXICITY_REJECT_THRESHOLD", 0.95))

    if score >= reject_th:
        return ModResult(action="reject", score=score)
    if score >= pending_th:
        return ModResult(action="pending", score=score)
    return ModResult(action="approve", score=score)


