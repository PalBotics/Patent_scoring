from typing import Dict, List


def keyword_score(text: str = '', title: str = '', abstract: str = '', keywords: List[str] = None, mapping: Dict[str, List[str]] = None) -> Dict:
    content = f"{title} {abstract} {text}".lower()
    subsystems = []
    total_matches = 0
    if mapping:
        for subsystem, kws in mapping.items():
            count = sum(content.count(k) for k in kws)
            if count > 0:
                subsystems.append(subsystem)
                total_matches += count
    else:
        if keywords:
            total_matches = sum(content.count(k) for k in keywords)

    if total_matches >= 3:
        relevance = 'High'
    elif total_matches >= 1:
        relevance = 'Medium'
    else:
        relevance = 'Low'

    return {'Relevance': relevance, 'Subsystem': subsystems}
