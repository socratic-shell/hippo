"""Search functionality for Hippo insights."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Insight
from .constants import (
    RELEVANCE_WEIGHT_RECENCY,
    RELEVANCE_WEIGHT_FREQUENCY,
    RELEVANCE_WEIGHT_IMPORTANCE,
    RELEVANCE_WEIGHT_CONTEXT,
    MAX_REASONABLE_FREQUENCY,
    CONTENT_MATCH_THRESHOLD,
    SITUATION_MATCH_THRESHOLD,
)

# Configure logging for sentence transformers (can be noisy)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)


class SearchResult(BaseModel):
    """A single search result with computed relevance."""
    
    insight: Insight = Field(description="The matched insight")
    importance: float = Field(description="Current importance (with decay applied)")
    relevance: float = Field(description="Computed search relevance combining votes and semantic matching")
    content_match: bool = Field(description="Whether the insight content matches the query")
    situation_matches: List[str] = Field(
        default_factory=list,
        description="List of situation elements that match the filter"
    )
    


class SearchResults(BaseModel):
    """Complete search results with metadata."""
    
    insights: List[SearchResult] = Field(
        default_factory=list,
        description="List of search results ordered by relevance"
    )
    total_matching: int = Field(
        description="Total number of insights matching the search criteria"
    )
    relevance_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of relevance scores across all insights for the given query/filters"
    )
    
    @property
    def returned_count(self) -> int:
        """Number of results actually returned."""
        return len(self.insights)


class InsightSearcher:
    """Search engine for insights with semantic and fuzzy matching."""
    
    def __init__(self) -> None:
        """Initialize with sentence transformer model."""
        # Use a fast, lightweight model for local inference
        self._model: Optional[SentenceTransformer] = None
    
    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the sentence transformer model."""
        if self._model is None:
            # This downloads ~90MB on first run, then loads from cache
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._model
    
    def search(
        self,
        storage,  # HippoStorage instance
        query: str = "",
        situation_filter: Optional[List[str]] = None,
        relevance_range: Optional[Tuple[float, Optional[float]]] = None,
        limit: Optional[Tuple[int, int]] = None,
        record_access: bool = True,
    ) -> SearchResults:
        """
        Search insights with various filters.
        
        Args:
            storage: HippoStorage instance containing insights
            query: Text to search for in content
            situation_filter: Situation elements to match (partial matching)
            relevance_range: (min_relevance, max_relevance) tuple
            limit: (offset, count) tuple for pagination
            record_access: Whether to record access for returned insights
        """
        # Get current active day for temporal calculations
        current_active_day = storage.get_current_active_day()
        
        # Apply filters
        filtered = self._apply_filters(
            storage.insights, query, situation_filter, relevance_range, current_active_day
        )
        
        # Sort by relevance
        filtered.sort(key=lambda r: r.relevance, reverse=True)
        
        # Apply pagination
        offset, count = limit or (0, 10)
        paginated = filtered[offset:offset + count]
        
        # Record access for returned insights if requested
        if record_access:
            for result in paginated:
                result.insight.record_access(current_active_day)
        
        # Calculate relevance distribution for all insights using same query/filters
        distribution = self._calculate_relevance_distribution(
            storage.insights, current_active_day, query, situation_filter
        )
        
        return SearchResults(
            insights=paginated,
            total_matching=len(filtered),
            relevance_distribution=distribution,
        )
    
    def _apply_filters(
        self,
        insights: List[Insight],
        query: str,
        situation_filter: Optional[List[str]],
        relevance_range: Optional[Tuple[float, Optional[float]]],
        current_active_day: int,
    ) -> List[SearchResult]:
        """Apply all filters and return SearchResult objects."""
        results = []
        
        for insight in insights:
            # Step 1: Compute current importance (reinforcement with decay)
            current_importance = insight.compute_current_importance()
            
            # Step 2: Compute semantic relevance scores
            content_relevance = self._compute_content_relevance(insight.content, query) if query else 1.0
            situation_relevance, situation_matches = (
                self._compute_situation_relevance(insight.situation, situation_filter) 
                if situation_filter 
                else (1.0, [])
            )
            
            # Step 3: Compute temporal factors
            # 💡: Using research-based formula: 30% recency + 20% frequency + 35% importance + 15% context
            recency_score = insight.calculate_recency_score(current_active_day)
            frequency_score = insight.calculate_frequency(current_active_day)
            
            # Normalize frequency score to 0-1 range
            normalized_frequency = min(1.0, frequency_score / MAX_REASONABLE_FREQUENCY)
            
            # Step 4: Calculate final composite relevance using research formula
            final_relevance = (
                RELEVANCE_WEIGHT_RECENCY * recency_score +
                RELEVANCE_WEIGHT_FREQUENCY * normalized_frequency +
                RELEVANCE_WEIGHT_IMPORTANCE * current_importance +
                RELEVANCE_WEIGHT_CONTEXT * situation_relevance
            )
            
            # Step 5: Apply relevance range filtering on final computed relevance
            if relevance_range:
                min_relevance, max_relevance = relevance_range
                if final_relevance < min_relevance:
                    continue
                if max_relevance is not None and final_relevance > max_relevance:
                    continue
            
            # Step 6: Apply content/situation matching filters (separate from relevance)
            content_match = content_relevance > CONTENT_MATCH_THRESHOLD
            query_passes = not query or content_match
            situation_passes = not situation_filter or situation_relevance > SITUATION_MATCH_THRESHOLD
            
            if query_passes and situation_passes:
                results.append(SearchResult(
                    insight=insight,
                    importance=current_importance,
                    relevance=final_relevance,
                    content_match=content_match,
                    situation_matches=situation_matches,
                ))
        
        return results
    
    def _compute_content_relevance(self, content: str, query: str) -> float:
        """Compute semantic relevance between content and query."""
        if not query:
            return 1.0
        
        # Fallback to substring matching if content is very short
        if len(content.strip()) < 10:
            return 1.0 if query.lower() in content.lower() else 0.3
        
        try:
            # Compute semantic similarity using sentence transformers
            embeddings = self.model.encode([content, query])
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            
            # Cosine similarity ranges from -1 to 1:
            # 1 = identical meaning, 0 = unrelated, -1 = opposite meaning
            # For search relevance, we only care about positive similarity
            # (unrelated content should get 0 relevance, not 0.5)
            similarity = max(0.0, similarity)
            
            # Boost exact substring matches slightly
            if query.lower() in content.lower():
                similarity = min(1.0, similarity + 0.1)
            
            return similarity
        except Exception:
            # Fallback to substring matching on any error
            return 1.0 if query.lower() in content.lower() else 0.3
    
    def _matches_content(self, content: str, query: str) -> bool:
        """Check if content matches query (for backwards compatibility)."""
        relevance = self._compute_content_relevance(content, query)
        return relevance > 0.4  # Threshold for "matching"
    
    def _compute_situation_relevance(
        self,
        situation: List[str],
        filter_terms: Optional[List[str]]
    ) -> Tuple[float, List[str]]:
        """
        Compute situation relevance and find matching elements.
        
        Returns (relevance_score, matching_elements).
        """
        if not filter_terms:
            return 1.0, []
        
        matches = []
        relevance_scores = []
        
        for situation_elem in situation:
            best_match_score = 0.0
            
            for filter_term in filter_terms:
                # Exact substring match gets high score
                if filter_term.lower() in situation_elem.lower():
                    score = 0.9
                    if best_match_score < score:
                        best_match_score = score
                else:
                    # Semantic similarity for non-exact matches
                    try:
                        semantic_score = self._compute_semantic_similarity(
                            situation_elem, filter_term
                        )
                        if semantic_score > 0.5 and semantic_score > best_match_score:
                            best_match_score = semantic_score
                    except Exception:
                        pass
            
            if best_match_score > 0.4:  # Threshold for relevance
                matches.append(situation_elem)
                relevance_scores.append(best_match_score)
        
        # Overall situation relevance is the average of matching elements
        overall_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
        
        return overall_relevance, matches
    
    def _compute_semantic_similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity between two texts."""
        try:
            embeddings = self.model.encode([text1, text2])
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            # Cosine similarity ranges from -1 to 1, but for search relevance
            # we only want positive similarities (negative = irrelevant, not anti-relevant)
            return max(0.0, similarity)
        except Exception:
            return 0.0
    
    def _matches_situation(
        self,
        situation: List[str],
        filter_terms: Optional[List[str]]
    ) -> List[str]:
        """Find situation elements that match any filter term (backwards compatibility)."""
        _, matches = self._compute_situation_relevance(situation, filter_terms)
        return matches
    
    def _calculate_relevance_distribution(
        self,
        insights: List[Insight],
        current_active_day: int,
        query: str = "",
        situation_filter: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """Calculate distribution of relevance scores across all insights."""
        # 💡: Calculate relevance distribution to help clients understand what additional
        # data exists beyond their filtered results. Uses same composite relevance formula
        # as search filtering but without applying thresholds.
        distribution = {
            "below_0.2": 0,
            "0.2_to_0.4": 0,
            "0.4_to_0.6": 0,
            "0.6_to_0.8": 0,
            "0.8_to_1.0": 0,
            "above_1.0": 0,
        }
        
        for insight in insights:
            # Compute the same composite relevance score used in filtering
            current_importance = insight.compute_current_importance()
            
            # Compute semantic relevance scores
            content_relevance = self._compute_content_relevance(insight.content, query) if query else 1.0
            situation_relevance, _ = (
                self._compute_situation_relevance(insight.situation, situation_filter) 
                if situation_filter 
                else (1.0, [])
            )
            
            # Compute temporal factors
            recency_score = insight.calculate_recency_score(current_active_day)
            frequency_score = insight.calculate_frequency(current_active_day)
            normalized_frequency = min(1.0, frequency_score / MAX_REASONABLE_FREQUENCY)
            
            # Calculate final composite relevance using same formula as search
            relevance = (
                RELEVANCE_WEIGHT_RECENCY * recency_score +
                RELEVANCE_WEIGHT_FREQUENCY * normalized_frequency +
                RELEVANCE_WEIGHT_IMPORTANCE * current_importance +
                RELEVANCE_WEIGHT_CONTEXT * situation_relevance
            )
            
            # Bin by relevance score
            if relevance < 0.2:
                distribution["below_0.2"] += 1
            elif relevance < 0.4:
                distribution["0.2_to_0.4"] += 1
            elif relevance < 0.6:
                distribution["0.4_to_0.6"] += 1
            elif relevance < 0.8:
                distribution["0.6_to_0.8"] += 1
            elif relevance <= 1.0:
                distribution["0.8_to_1.0"] += 1
            else:
                distribution["above_1.0"] += 1
        
        return distribution