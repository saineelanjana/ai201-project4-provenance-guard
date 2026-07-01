import re
import math
import logging
from groq import Groq
import config

logger = logging.getLogger(__name__)

client = Groq(api_key=config.GROQ_API_KEY)

def get_llm_score(text: str) -> float:
    """Signal 1: LLM-as-judge scoring text on a spectrum from 0.0 to 1.0"""
    try:
        # System prompt should enforce returning exactly a float value or small JSON
        response = client.chat.completions.create(
            model=config.MODEL_NAME,
            messages=[
                {"role": "system", "content": "Analyze if the text is AI written. Output exactly a single float between 0.0 (Human) and 1.0 (AI)."},
                {"role": "user", "content": text}
            ],
            temperature=0.0
        )
        return float(response.choices[0].message.content.strip())
    except Exception as e:
        logger.error("Groq LLM signal failed: %s", e)
        return 0.5  # Neutral fallback on API error

def get_stylometric_score(text: str) -> float:
    """Signal 2: Pure Python heuristics — sentence variance, word length, punctuation density, TTR."""
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    words = re.findall(r'\b\w+\b', text.lower())

    if not sentences or not words:
        return 0.5

    # Metric 1: Sentence Length Variance
    # Continuous mapping: std_dev=0 → 1.0 (uniform/AI), std_dev≥12 → 0.0 (erratic/human)
    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(sentences)
    variance = sum((x - mean) ** 2 for x in lengths) / len(sentences)
    std_dev = math.sqrt(variance)
    sentence_score = max(0.0, min(1.0, 1.0 - (std_dev / 12.0)))

    # Metric 2: Average Word Length (vocabulary formality proxy)
    # AI formal prose uses longer, academic words (~6+ chars); human casual uses shorter (~4 chars)
    # Continuous mapping: 4.0 chars → 0.0, 7.0 chars → 1.0
    avg_word_len = sum(len(w) for w in words) / len(words)
    word_len_score = max(0.0, min(1.0, (avg_word_len - 4.0) / 3.0))

    # Metric 3: Punctuation Density (informal markers: !, ?, ;, —)
    # AI text uses clean sentence-ending punctuation; human writing has more expressive variety
    informal_punct = len(re.findall(r'[!?;—]', text))
    punct_density = informal_punct / max(len(words), 1)
    punct_score = 0.2 if punct_density > 0.03 else 0.8

    # Metric 4: Type-Token Ratio
    # For short texts (<300 words) TTR clusters high for all text types, limiting its signal.
    # Retained per spec; flags clearly repetitive text (TTR < 0.55) as human-like.
    ttr = len(set(words)) / len(words)
    ttr_score = 0.2 if ttr < 0.55 else 0.5

    return round(
        (sentence_score * 0.35)
        + (word_len_score * 0.35)
        + (punct_score   * 0.20)
        + (ttr_score     * 0.10),
        2
    )
