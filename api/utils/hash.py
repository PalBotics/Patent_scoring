"""
Utility functions for hashing and deduplication.
"""
import hashlib


def compute_abstract_sha1(patent_id: str, abstract: str, prompt_version: str = "v1.0") -> str:
    """
    Compute SHA1 hash for a patent abstract to enable deduplication.
    
    Format: sha1(f"{patent_id}|{normalized_abstract}|{prompt_version}")
    
    Args:
        patent_id: Patent ID (e.g., US2023123456A1)
        abstract: Raw abstract text
        prompt_version: Scoring prompt version (default: v1.0)
    
    Returns:
        40-character hex SHA1 digest
    """
    # Normalize abstract: lowercase, collapse whitespace
    normalized = " ".join(abstract.lower().split())
    
    # Construct hash input
    hash_input = f"{patent_id}|{normalized}|{prompt_version}"
    
    # Compute SHA1
    return hashlib.sha1(hash_input.encode("utf-8")).hexdigest()
