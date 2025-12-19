import re
from typing import List, Tuple, Optional
try:
    from rapidfuzz import process, fuzz
except Exception:
    process = None
    fuzz = None
    import difflib

class LocationMatcher:
    def __init__(self):
        self._standard_locations = set()

    def set_standards(self, locations: List[str]):
        """
        Set the list of known standard locations.
        """
        self._standard_locations = set(locations)

    def normalize(self, text: str) -> str:
        """
        Basic normalization:
        - Convert full-width parens to half-width
        - Strip whitespace
        """
        if not text:
            return ""
        text = text.replace("（", "(").replace("）", ")")
        text = text.strip()
        # Remove extra spaces inside parens? e.g. ( 103 ) -> (103)
        # Maybe not strictly necessary if rapidfuzz handles it, but good for consistency.
        return text

    def match(self, query: str, threshold: float = 90.0) -> Tuple[str, float]:
        """
        Find best match for query in standard locations.
        Returns (best_match, score).
        If no match found or score < threshold, returns (query, score).
        """
        query_norm = self.normalize(query)
        
        # 1. Exact match check (fastest)
        if query_norm in self._standard_locations:
            return query_norm, 100.0
            
        # 2. Fuzzy match
        if not self._standard_locations:
            return query_norm, 0.0
            
        if process and fuzz:
            best = process.extractOne(
                query_norm,
                self._standard_locations,
                scorer=fuzz.token_set_ratio
            )
            if best:
                match_str, score, _ = best
                if score >= threshold:
                    return match_str, score
            return query_norm, 0.0

        best_match: Optional[str] = None
        best_score = 0.0
        for cand in self._standard_locations:
            s = difflib.SequenceMatcher(None, query_norm, cand).ratio() * 100.0
            if s > best_score:
                best_score = s
                best_match = cand
        if best_match and best_score >= threshold:
            return best_match, best_score
        return query_norm, best_score

matcher = LocationMatcher()
