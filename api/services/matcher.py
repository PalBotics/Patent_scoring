"""Keyword matching service for patent classification.

Matches patent text against keyword patterns with wildcard support.
Used for fast pre-filtering before LLM scoring.
"""

import re
from typing import List, Dict, Optional


def normalize_text(text: str) -> str:
    """Normalize text for matching: lowercase, collapse whitespace."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.lower().strip())


def wildcard_to_regex(pattern: str) -> re.Pattern:
    """Convert wildcard pattern to regex.
    
    Supports:
    - * for any characters
    - ? for single character
    - Word boundaries for exact word matching
    
    Examples:
        "mine*" matches "mine", "miner", "mineral"
        "detect*" matches "detect", "detection", "detector"
    """
    # Escape special regex chars except * and ?
    escaped = re.escape(pattern)
    # Replace escaped wildcards with regex equivalents
    regex_pattern = escaped.replace(r'\*', '.*').replace(r'\?', '.')
    # Add word boundaries - but only at start for prefix matching`n    # This allows "detect*" to match "detector" but not "undetected"`n    regex_pattern = r'\b' + regex_pattern
    return re.compile(regex_pattern, re.IGNORECASE)


def match_keywords(
    text: str,
    keyword_map: Dict[str, List[str]],
    min_matches: int = 1
) -> Dict[str, List[str]]:
    """Match text against keyword mapping.
    
    Args:
        text: Patent title + abstract to search
        keyword_map: Dict mapping subsystem names to keyword patterns
            Example: {
                "Detection": ["sensor*", "detect*", "radar", "lidar"],
                "Mobility": ["track*", "wheel*", "propul*"]
            }
        min_matches: Minimum keyword matches required per subsystem
    
    Returns:
        Dict mapping matched subsystem names to matched keywords
        Example: {"Detection": ["sensor", "detection"], "Mobility": ["tracked"]}
    """
    normalized_text = normalize_text(text)
    matches: Dict[str, List[str]] = {}
    
    for subsystem, patterns in keyword_map.items():
        subsystem_matches: List[str] = []
        
        for pattern in patterns:
            regex = wildcard_to_regex(pattern)
            found = regex.findall(normalized_text)
            if found:
                # Add unique matches
                subsystem_matches.extend([m for m in found if m not in subsystem_matches])
        
        if len(subsystem_matches) >= min_matches:
            matches[subsystem] = subsystem_matches
    
    return matches


def classify_relevance(
    title: str,
    abstract: str,
    keyword_map: Dict[str, List[str]],
    high_threshold: int = 3,
    medium_threshold: int = 1
) -> tuple[str, List[str]]:
    """Classify patent relevance based on keyword matches.
    
    Args:
        title: Patent title
        abstract: Patent abstract
        keyword_map: Subsystem -> keywords mapping
        high_threshold: Min matches for "High" relevance
        medium_threshold: Min matches for "Medium" relevance
    
    Returns:
        Tuple of (relevance, subsystems)
        - relevance: "High" | "Medium" | "Low"
        - subsystems: List of matched subsystem names
    """
    combined_text = f"{title} {abstract}"
    matches = match_keywords(combined_text, keyword_map, min_matches=1)
    
    subsystems = list(matches.keys())
    total_keyword_matches = sum(len(kw_list) for kw_list in matches.values())
    
    if total_keyword_matches >= high_threshold:
        relevance = "High"
    elif total_keyword_matches >= medium_threshold:
        relevance = "Medium"
    else:
        relevance = "Low"
    
    return relevance, subsystems


# Default keyword mapping for demining robot project
DEFAULT_KEYWORD_MAP = {
    "Detection": [
        "sensor*", "detect*", "radar", "lidar", "ultrasonic",
        "metal detect*", "gpr", "ground penetrat*", "imaging",
        "thermal", "infrared", "camera*", "vision"
    ],
    "Mobility": [
        "track*", "wheel*", "propul*", "locomot*", "terrain",
        "navigation", "path*", "obstacle", "chassis", "suspension",
        "drive*", "motor*", "actuator*"
    ],
    "Manipulation": [
        "arm", "gripper", "manipulat*", "end effector",
        "pick*", "grasp*", "tool*", "excavat*", "dig*"
    ],
    "Control": [
        "autonom*", "control*", "algorithm*", "ai", "machine learning",
        "neural", "computer vision", "slam", "localization",
        "remote*", "teleoperat*", "wireless"
    ],
    "Safety": [
        "safety", "protect*", "shield*", "armor*", "blast",
        "explo*", "hazard*", "risk*", "emergency"
    ],
    "Power": [
        "battery", "power", "energy", "fuel", "solar",
        "charging", "electrical", "voltage", "current"
    ]
}
