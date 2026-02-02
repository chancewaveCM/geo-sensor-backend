"""
GEO Optimization Analyzer
F9: 5-trigger scoring system for content optimization
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class TriggerType(Enum):
    """GEO optimization trigger types"""
    CLEAR_DEFINITION = "clear_definition"
    STRUCTURED_INFO = "structured_info"
    STATISTICS = "statistics"
    AUTHORITY = "authority"
    SUMMARY = "summary"


class Grade(Enum):
    """GEO score grades"""
    A = "A"  # 90-100
    B = "B"  # 80-89
    C = "C"  # 70-79
    D = "D"  # 60-69
    F = "F"  # 0-59


@dataclass
class TriggerResult:
    """Result for a single trigger detection"""
    trigger_type: TriggerType
    detected: bool
    score: float  # 0-20 per trigger
    evidence: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "trigger_type": self.trigger_type.value,
            "detected": self.detected,
            "score": round(self.score, 1),
            "evidence": self.evidence,
        }


@dataclass
class GEOScore:
    """Complete GEO optimization score"""
    total_score: float  # 0-100
    grade: Grade
    triggers: List[TriggerResult] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_score": round(self.total_score, 1),
            "grade": self.grade.value,
            "triggers": [t.to_dict() for t in self.triggers],
            "suggestions": self.suggestions,
        }


class GEOOptimizationAnalyzer:
    """
    GEO Optimization Analyzer

    Analyzes content for 5 GEO triggers (20 points each = 100 total):

    1. CLEAR_DEFINITION (20pts) - Clear brand/product definition
       - Explicit "X is" or "X는" definitions
       - Category statements

    2. STRUCTURED_INFO (20pts) - Structured data presence
       - Lists (bulleted, numbered)
       - Tables
       - Key-value pairs

    3. STATISTICS (20pts) - Numerical data
       - Percentages
       - Numbers with units
       - Rankings

    4. AUTHORITY (20pts) - Expert/source citations
       - Quote marks
       - "According to" phrases
       - Expert names

    5. SUMMARY (20pts) - Concise summary
       - "In summary" phrases
       - Conclusion markers
       - TL;DR sections
    """

    MAX_SCORE_PER_TRIGGER = 20.0

    # Detection patterns
    DEFINITION_PATTERNS = [
        r'\b(\w+)\s+is\s+(a|an|the)\s+',  # "X is a/an/the"
        r'\b(\w+)\s+are\s+',  # "X are"
        r'(\w+)은\s+',  # Korean "X은"
        r'(\w+)는\s+',  # Korean "X는"
        r'defined\s+as\b',
        r'refers\s+to\b',
        r'known\s+as\b',
    ]

    STRUCTURE_PATTERNS = [
        r'^\s*[-•*]\s+',  # Bullet points
        r'^\s*\d+\.\s+',  # Numbered lists
        r'\|.*\|',  # Table indicators
        r':\s*\n',  # Key-value indicators
        r'^\s*-\s+\*\*',  # Markdown bold bullets
    ]

    STATISTICS_PATTERNS = [
        r'\d+%',  # Percentages
        r'\$[\d,]+',  # Currency
        r'\d+\s*(times|x|배)',  # Multipliers
        r'#\d+',  # Rankings
        r'\d+\s*(GB|MB|TB|KB)',  # Data sizes
        r'\d+\s*(hours?|minutes?|seconds?)',  # Time
        r'\d+\s*(users?|customers?)',  # Counts
        r'top\s*\d+',  # Top N
        r'\d+\s*점',  # Korean scores
    ]

    AUTHORITY_PATTERNS = [
        r'"[^"]{10,}"',  # Quoted text (10+ chars)
        r"'[^']{10,}'",
        r'according\s+to\b',
        r'experts?\s+say',
        r'\bstudy\b',
        r'\bresearch\b',
        r'\breport\b',
        r'전문가',  # Korean "expert"
        r'연구',  # Korean "research"
    ]

    SUMMARY_PATTERNS = [
        r'\bin\s+summary\b',
        r'\bto\s+summarize\b',
        r'\bin\s+conclusion\b',
        r'\boverall\b',
        r'\btl;?dr\b',
        r'\bbottom\s+line\b',
        r'결론',  # Korean "conclusion"
        r'요약',  # Korean "summary"
        r'정리하면',  # Korean "to summarize"
    ]

    def __init__(self):
        # Compile patterns
        self._definition_re = [
            re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.DEFINITION_PATTERNS
        ]
        self._structure_re = [re.compile(p, re.MULTILINE) for p in self.STRUCTURE_PATTERNS]
        self._statistics_re = [re.compile(p, re.IGNORECASE) for p in self.STATISTICS_PATTERNS]
        self._authority_re = [re.compile(p, re.IGNORECASE) for p in self.AUTHORITY_PATTERNS]
        self._summary_re = [re.compile(p, re.IGNORECASE) for p in self.SUMMARY_PATTERNS]

    def analyze(
        self,
        content: str,
        brand: Optional[str] = None,
    ) -> GEOScore:
        """
        Analyze content for GEO optimization triggers

        Args:
            content: Text content to analyze
            brand: Optional brand name for context

        Returns:
            GEOScore with total score, grade, triggers, and suggestions
        """
        triggers = [
            self._detect_clear_definition(content, brand),
            self._detect_structured_info(content),
            self._detect_statistics(content),
            self._detect_authority(content),
            self._detect_summary(content),
        ]

        total_score = sum(t.score for t in triggers)
        grade = self._calculate_grade(total_score)
        suggestions = self._generate_suggestions(triggers)

        return GEOScore(
            total_score=total_score,
            grade=grade,
            triggers=triggers,
            suggestions=suggestions,
        )

    def _detect_clear_definition(self, content: str, brand: Optional[str]) -> TriggerResult:
        """Detect clear definition triggers"""
        matches = []
        for pattern in self._definition_re:
            matches.extend(pattern.findall(content))

        # Bonus if brand is defined
        brand_defined = False
        if brand:
            brand_pattern = re.compile(rf'\b{re.escape(brand)}\s+(is|are|은|는)', re.IGNORECASE)
            brand_defined = bool(brand_pattern.search(content))

        match_count = len(matches)
        if brand_defined:
            match_count += 2  # Bonus for brand definition

        score = min(self.MAX_SCORE_PER_TRIGGER, match_count * 5)

        return TriggerResult(
            trigger_type=TriggerType.CLEAR_DEFINITION,
            detected=match_count > 0,
            score=score,
            evidence=(
                f"{len(matches)} definition patterns found"
                + (", brand defined" if brand_defined else "")
            ),
        )

    def _detect_structured_info(self, content: str) -> TriggerResult:
        """Detect structured information triggers"""
        matches = []
        for pattern in self._structure_re:
            matches.extend(pattern.findall(content))

        match_count = len(matches)
        score = min(self.MAX_SCORE_PER_TRIGGER, match_count * 4)

        return TriggerResult(
            trigger_type=TriggerType.STRUCTURED_INFO,
            detected=match_count > 0,
            score=score,
            evidence=f"{match_count} structure indicators found",
        )

    def _detect_statistics(self, content: str) -> TriggerResult:
        """Detect statistics triggers"""
        matches = []
        for pattern in self._statistics_re:
            matches.extend(pattern.findall(content))

        match_count = len(matches)
        score = min(self.MAX_SCORE_PER_TRIGGER, match_count * 5)

        return TriggerResult(
            trigger_type=TriggerType.STATISTICS,
            detected=match_count > 0,
            score=score,
            evidence=f"{match_count} statistical elements found",
        )

    def _detect_authority(self, content: str) -> TriggerResult:
        """Detect authority/citation triggers"""
        matches = []
        for pattern in self._authority_re:
            matches.extend(pattern.findall(content))

        match_count = len(matches)
        score = min(self.MAX_SCORE_PER_TRIGGER, match_count * 7)

        return TriggerResult(
            trigger_type=TriggerType.AUTHORITY,
            detected=match_count > 0,
            score=score,
            evidence=f"{match_count} authority indicators found",
        )

    def _detect_summary(self, content: str) -> TriggerResult:
        """Detect summary triggers"""
        matches = []
        for pattern in self._summary_re:
            matches.extend(pattern.findall(content))

        match_count = len(matches)
        score = min(self.MAX_SCORE_PER_TRIGGER, match_count * 10)

        return TriggerResult(
            trigger_type=TriggerType.SUMMARY,
            detected=match_count > 0,
            score=score,
            evidence=f"{match_count} summary indicators found",
        )

    def _calculate_grade(self, score: float) -> Grade:
        """Calculate grade from score"""
        if score >= 90:
            return Grade.A
        elif score >= 80:
            return Grade.B
        elif score >= 70:
            return Grade.C
        elif score >= 60:
            return Grade.D
        else:
            return Grade.F

    def _generate_suggestions(self, triggers: List[TriggerResult]) -> List[str]:
        """Generate improvement suggestions"""
        suggestions = []

        suggestion_map = {
            TriggerType.CLEAR_DEFINITION: "Add clear definitions - use 'X is a...' format",
            TriggerType.STRUCTURED_INFO: (
                "Add structured content - use bullet points, numbered lists, or tables"
            ),
            TriggerType.STATISTICS: "Include statistics - add percentages, numbers, or rankings",
            TriggerType.AUTHORITY: (
                "Add authority signals - include quotes, expert opinions, or research citations"
            ),
            TriggerType.SUMMARY: (
                "Add a summary section - include 'In summary' or 'To conclude' phrases"
            ),
        }

        for trigger in triggers:
            if trigger.score < self.MAX_SCORE_PER_TRIGGER * 0.5:  # Less than 50% of max
                suggestions.append(suggestion_map[trigger.trigger_type])

        return suggestions
