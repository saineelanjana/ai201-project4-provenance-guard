import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "llama-3.3-70b-versatile"

# Uncertainty Weightings & Thresholds
LLM_WEIGHT = 0.65
STYLO_WEIGHT = 0.35

HUMAN_THRESHOLD = 0.40
AI_THRESHOLD = 0.70

# Verbatim Transparency Labels
LABEL_HUMAN = "Verified Original: This text matches patterns consistent with human authorship."
LABEL_UNCERTAIN = "Unverified Attribution: Stylistic markers are mixed. Content authenticity cannot be definitively proven."
LABEL_AI = "Unverified Authenticity: Structural signatures are consistent with AI-generated text. This content has been flagged for review."
