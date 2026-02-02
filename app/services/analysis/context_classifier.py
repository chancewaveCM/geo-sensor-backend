"""
Context Classifier
F7: Classify AI response context (informational, comparative, recommendation)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
import re


class ContextType(Enum):
    """AI response context types"""
    INFORMATIONAL = "informational"  # General info, definitions
    COMPARATIVE = "comparative"      # Feature comparisons, vs. analysis
    RECOMMENDATION = "recommendation"  # Direct suggestions, "best for"
    TUTORIAL = "tutorial"            # How-to, step-by-step guides
    OPINION = "opinion"              # Subjective statements
    UNKNOWN = "unknown"


@dataclass
class ContextClassification:
    """Classification result for AI response"""
    primary_context: ContextType
    confidence: float  # 0.0 - 1.0
    secondary_contexts: List[ContextType]
    reasoning: str
    signals: List[str]  # Detected keywords/patterns

    def to_dict(self) -> dict:
        return {
            "primary_context": self.primary_context.value,
            "confidence": round(self.confidence, 3),
            "secondary_contexts": [c.value for c in self.secondary_contexts],
            "reasoning": self.reasoning,
            "signals": self.signals,
        }


class ContextClassifier:
    """
    Classify AI response context using keyword patterns

    Context types help understand:
    - Citation patterns by context
    - Brand mention strategies
    - Response positioning
    """

    # Keyword patterns for each context type
    PATTERNS = {
        ContextType.INFORMATIONAL: [
            r'\b(what is|definition of|refers to|means that|explanation)\b',
            r'\b(overview|introduction|background|history)\b',
            r'\b(types of|categories|classifications)\b',
            r'\b(generally|typically|commonly|usually)\b',
        ],
        ContextType.COMPARATIVE: [
            r'\b(compared to|versus|vs\.?|difference between)\b',
            r'\b(better than|worse than|similar to|unlike)\b',
            r'\b(pros and cons|advantages|disadvantages)\b',
            r'\b(while .+ offers|whereas|in contrast)\b',
            r'\b(alternative|competitor|competing)\b',
        ],
        ContextType.RECOMMENDATION: [
            r'\b(I recommend|we recommend|should use|best choice)\b',
            r'\b(ideal for|perfect for|great option|excellent)\b',
            r'\b(top pick|best .+ for|leading solution)\b',
            r'\b(consider using|try|opt for|go with)\b',
            r'\b(highly rated|most popular|widely used)\b',
        ],
        ContextType.TUTORIAL: [
            r'\b(step \d+|first|next|then|finally)\b',
            r'\b(how to|guide to|tutorial|walkthrough)\b',
            r'\b(follow these steps|here\'s how|instructions)\b',
            r'\b(install|setup|configure|implement)\b',
        ],
        ContextType.OPINION: [
            r'\b(I think|in my opinion|I believe|personally)\b',
            r'\b(seems like|appears to|feels like|looks like)\b',
            r'\b(probably|likely|might|could be)\b',
            r'\b(subjectively|arguably|debatable)\b',
        ],
    }

    # Weighting for signal strength
    WEIGHTS = {
        ContextType.RECOMMENDATION: 1.5,  # Strong signal
        ContextType.COMPARATIVE: 1.3,
        ContextType.TUTORIAL: 1.2,
        ContextType.OPINION: 1.1,
        ContextType.INFORMATIONAL: 1.0,
    }

    def classify(self, text: str) -> ContextClassification:
        """
        Classify the context type of AI response text

        Args:
            text: AI response text to classify

        Returns:
            ContextClassification with primary and secondary contexts
        """
        if not text or not text.strip():
            return ContextClassification(
                primary_context=ContextType.UNKNOWN,
                confidence=0.0,
                secondary_contexts=[],
                reasoning="Empty text",
                signals=[],
            )

        text_lower = text.lower()

        # Count pattern matches for each context type
        context_scores = {}
        context_signals = {}

        for context_type, patterns in self.PATTERNS.items():
            matches = []
            for pattern in patterns:
                found = re.findall(pattern, text_lower, re.IGNORECASE)
                matches.extend(found)

            if matches:
                weight = self.WEIGHTS.get(context_type, 1.0)
                context_scores[context_type] = len(matches) * weight
                context_signals[context_type] = matches[:5]  # Top 5 signals

        # No clear signals
        if not context_scores:
            return ContextClassification(
                primary_context=ContextType.INFORMATIONAL,  # Default
                confidence=0.3,
                secondary_contexts=[],
                reasoning="No strong context signals detected, defaulting to informational",
                signals=[],
            )

        # Sort by score
        sorted_contexts = sorted(
            context_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        primary = sorted_contexts[0][0]
        primary_score = sorted_contexts[0][1]

        # Calculate confidence based on score dominance
        total_score = sum(context_scores.values())
        confidence = min(primary_score / total_score, 1.0)

        # Secondary contexts (score > 30% of primary)
        threshold = primary_score * 0.3
        secondary = [
            ctx for ctx, score in sorted_contexts[1:]
            if score > threshold
        ]

        return ContextClassification(
            primary_context=primary,
            confidence=confidence,
            secondary_contexts=secondary,
            reasoning=self._generate_reasoning(primary, confidence, len(context_signals[primary])),
            signals=context_signals[primary],
        )

    def classify_with_override(
        self,
        text: str,
        override_context: Optional[ContextType] = None,
    ) -> ContextClassification:
        """
        Classify with manual override option

        Useful for:
        - Ground truth validation
        - Manual corrections
        - Test data labeling
        """
        if override_context:
            return ContextClassification(
                primary_context=override_context,
                confidence=1.0,
                secondary_contexts=[],
                reasoning="Manual override",
                signals=["[MANUAL]"],
            )

        return self.classify(text)

    def _generate_reasoning(
        self,
        context: ContextType,
        confidence: float,
        signal_count: int,
    ) -> str:
        """Generate human-readable reasoning"""
        confidence_level = "high" if confidence > 0.7 else "medium" if confidence > 0.4 else "low"

        return (
            f"Classified as {context.value} with {confidence_level} confidence "
            f"({confidence:.1%}) based on {signal_count} detected signals"
        )

    def batch_classify(self, texts: List[str]) -> List[ContextClassification]:
        """Classify multiple texts efficiently"""
        return [self.classify(text) for text in texts]
