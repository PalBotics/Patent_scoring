"""OpenAI-based patent scoring service.

Uses LLM to analyze patent relevance and classify into subsystems.
"""

import os
import json
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# Check if openai is available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None


class ScoringService:
    """Service for scoring patents using OpenAI LLM."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """Initialize scoring service.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed. Run: pip install openai")
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided and OPENAI_API_KEY not set")
        
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
    
    def build_prompt(
        self,
        title: str,
        abstract: str,
        prompt_version: str = "v1.0",
        subsystems: Optional[List[str]] = None
    ) -> str:
        """Build scoring prompt for LLM.
        
        Args:
            title: Patent title
            abstract: Patent abstract
            prompt_version: Version identifier for prompt template
            subsystems: Available subsystem categories
        
        Returns:
            Formatted prompt string
        """
        if subsystems is None:
            subsystems = [
                "Detection", "Mobility", "Manipulation",
                "Control", "Safety", "Power"
            ]
        
        prompt = f"""Analyze this patent for relevance to a demining robot project.

**Patent Title:** {title}

**Patent Abstract:** {abstract}

**Task:**
1. Determine relevance level: High, Medium, or Low
   - High: Directly applicable to demining robot design/operation
   - Medium: Related technology that could be adapted
   - Low: Not relevant to demining robots

2. Identify applicable subsystems from: {', '.join(subsystems)}

**Output Format (JSON):**
{{
  "relevance": "High|Medium|Low",
  "subsystem": ["subsystem1", "subsystem2"],
  "reasoning": "Brief explanation of relevance and subsystem matches"
}}

Respond with valid JSON only."""
        
        return prompt
    
    def score_patent(
        self,
        title: str,
        abstract: str,
        prompt_version: str = "v1.0"
    ) -> Tuple[str, List[str], str]:
        """Score a patent using OpenAI LLM.
        
        Args:
            title: Patent title
            abstract: Patent abstract  
            prompt_version: Prompt template version
        
        Returns:
            Tuple of (relevance, subsystems, reasoning)
            - relevance: "High" | "Medium" | "Low"
            - subsystems: List of matched subsystem names
            - reasoning: LLM explanation
        
        Raises:
            Exception: If OpenAI API call fails or response is invalid
        """
        prompt = self.build_prompt(title, abstract, prompt_version)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a patent analysis expert specializing in robotics and demining technology."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            # Handle markdown code blocks if present
            if content.startswith("```"):
                # Extract JSON from markdown code block
                lines = content.split('\n')
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block or (not line.strip().startswith("```")):
                        json_lines.append(line)
                content = '\n'.join(json_lines)
            
            result = json.loads(content)
            
            relevance = result.get("relevance", "Low")
            subsystems = result.get("subsystem", [])
            reasoning = result.get("reasoning", "")
            
            # Validate relevance
            if relevance not in ["High", "Medium", "Low"]:
                relevance = "Low"
            
            # Ensure subsystems is a list
            if not isinstance(subsystems, list):
                subsystems = [subsystems] if subsystems else []
            
            return relevance, subsystems, reasoning
            
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse LLM response as JSON: {e}")
        except Exception as e:
            raise Exception(f"OpenAI API error: {e}")


# Convenience function for direct use
def score_with_llm(
    title: str,
    abstract: str,
    model: str = "gpt-4o-mini",
    prompt_version: str = "v1.0"
) -> Tuple[str, List[str], str]:
    """Score a patent using OpenAI (convenience function).
    
    Args:
        title: Patent title
        abstract: Patent abstract
        model: OpenAI model name
        prompt_version: Prompt template version
    
    Returns:
        Tuple of (relevance, subsystems, reasoning)
    """
    service = ScoringService(model=model)
    return service.score_patent(title, abstract, prompt_version)
