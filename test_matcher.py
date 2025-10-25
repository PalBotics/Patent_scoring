"""Quick test of matcher service functionality."""
import sys
sys.path.insert(0, '.')

from api.services.matcher import (
    normalize_text,
    wildcard_to_regex,
    match_keywords,
    classify_relevance,
    DEFAULT_KEYWORD_MAP
)

# Test data
test_title = "Autonomous Mine Detection Robot with Sensor Array"
test_abstract = """
This patent describes an autonomous robot for detecting landmines using
a combination of metal detectors, ground-penetrating radar (GPR), and
thermal imaging sensors. The robot features tracked mobility for rough
terrain navigation and includes safety shields for blast protection.
"""

print("=" * 60)
print("Matcher Service Test")
print("=" * 60)

print(f"\nTitle: {test_title}")
print(f"Abstract: {test_abstract[:100]}...")

# Test normalize_text
print("\n--- Test: normalize_text ---")
normalized = normalize_text(test_title)
print(f"Normalized: '{normalized}'")

# Test wildcard_to_regex
print("\n--- Test: wildcard_to_regex ---")
pattern = "detect*"
regex = wildcard_to_regex(pattern)
matches = regex.findall(normalized)
print(f"Pattern '{pattern}' matches: {matches}")

# Test match_keywords
print("\n--- Test: match_keywords ---")
combined = f"{test_title} {test_abstract}"
matches = match_keywords(combined, DEFAULT_KEYWORD_MAP, min_matches=1)
print(f"Matched subsystems: {list(matches.keys())}")
for subsystem, keywords in matches.items():
    print(f"  {subsystem}: {keywords[:5]}")  # Show first 5 matches

# Test classify_relevance
print("\n--- Test: classify_relevance ---")
relevance, subsystems = classify_relevance(
    test_title,
    test_abstract,
    DEFAULT_KEYWORD_MAP,
    high_threshold=3,
    medium_threshold=1
)
print(f"Relevance: {relevance}")
print(f"Subsystems: {subsystems}")

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
