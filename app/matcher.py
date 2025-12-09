import re
from rapidfuzz import process, fuzz
from typing import List, Tuple, Optional

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
            
        # extraction using rapidfuzz
        # process.extractOne returns (match, score, index)
        # We use token_set_ratio to handle subset strings like "Hello(103)" vs "Hello(Y1-103)"
        # token_set_ratio is good for intersection.
        # token_sort_ratio is good for reordering.
        # "Hello(103)" vs "Hello(Y1-103)" -> intersection is "Hello", "103".
        # Let's try partial_ratio too?
        # User example: PBL制造局(107) -> PBL制造局(Y8-107)
        # These share "PBL制造局" and "107".
        
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

matcher = LocationMatcher()
