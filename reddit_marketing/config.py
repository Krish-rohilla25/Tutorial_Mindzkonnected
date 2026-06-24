"""
Project brief configuration and environment loading.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ProjectBrief:
    """Reusable project config — swap this to market a different product."""

    brand_name: str = ""
    description: str = ""
    features: list = field(default_factory=list)
    target_audience: str = ""
    voice_tone: str = ""

    def to_prompt_str(self):
        """Format the brief as a string for LLM prompts."""
        features_str = "\n".join(f"  - {f}" for f in self.features) if self.features else "  (none specified)"
        return (
            f"Brand: {self.brand_name}\n"
            f"Description: {self.description}\n"
            f"Key Features:\n{features_str}\n"
            f"Target Audience: {self.target_audience}\n"
            f"Voice / Tone: {self.voice_tone}"
        )


def get_default_brief():
    """Return a sample brief to pre-fill the UI."""
    return ProjectBrief(
        brand_name="MindzKonnected",
        description="An AI-powered learning platform that helps students study smarter with personalized tutoring, flashcards, and practice tests.",
        features=[
            "AI tutor that adapts to learning style",
            "Auto-generated flashcards from any PDF",
            "Practice tests with instant feedback",
            "Progress tracking dashboard",
        ],
        target_audience="College students, self-learners, and professionals preparing for certifications",
        voice_tone="Helpful, casual, knowledgeable — like a smart friend, not a corporation",
    )


def get_tavily_api_key():
    """Load the Tavily API key from .env."""
    return os.getenv("TAVILY_API_KEY", "")


def get_groq_api_key():
    """Load the Groq API key from .env."""
    return os.getenv("GROQ_API_KEY", "")


def get_google_api_key():
    """Load the Google API key from .env."""
    return os.getenv("GOOGLE_API_KEY", "")
