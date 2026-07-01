"""
Standalone signal test — run before wiring signals into the endpoint.

Usage:
    python test_signals.py              # stylometric only (no API key needed)
    python test_signals.py --llm        # includes Groq LLM signal (requires GROQ_API_KEY)
"""

import sys
import signals
import config

LLM_W = config.LLM_WEIGHT
STY_W = config.STYLO_WEIGHT

HUMAN_T = config.HUMAN_THRESHOLD
AI_T    = config.AI_THRESHOLD

TEST_INPUTS = [
    (
        "AI formal",
        "Artificial intelligence represents a transformative paradigm shift in modern society. "
        "It is important to note that while the benefits of AI are numerous, it is equally "
        "essential to consider the ethical implications. Furthermore, stakeholders across "
        "various sectors must collaborate to ensure responsible deployment.",
    ),
    (
        "Human casual",
        "ok so i finally tried that new ramen place downtown and honestly? "
        "underwhelming. the broth was fine but they put WAY too much sodium in it and "
        "i was thirsty for like three hours after. my friend got the spicy version and "
        "said it was better. probably won't go back unless someone drags me there",
    ),
    (
        "Formal human (borderline)",
        "The relationship between monetary policy and asset price inflation has been "
        "extensively studied in the literature. Central banks face a fundamental tension "
        "between their mandate for price stability and the unintended consequences of "
        "prolonged low interest rates on equity and real estate valuations.",
    ),
    (
        "Lightly edited AI (borderline)",
        "I've been thinking a lot about remote work lately. There are genuine tradeoffs — "
        "flexibility and no commute on one side, isolation and blurred work-life boundaries "
        "on the other. Studies show productivity varies widely by individual and role type.",
    ),
]


def attribution_label(confidence: float) -> str:
    if confidence <= HUMAN_T:
        return "likely_human"
    if confidence >= AI_T:
        return "likely_ai"
    return "uncertain"


def run(use_llm: bool):
    print(f"\n{'='*60}")
    print(f"  Signal test  |  LLM={'ON' if use_llm else 'OFF (stylometric only)'}")
    print(f"{'='*60}\n")

    for name, text in TEST_INPUTS:
        print(f"[{name}]")
        stylo_score = signals.get_stylometric_score(text)

        if use_llm:
            llm_score = signals.get_llm_score(text)
        else:
            llm_score = None

        print(f"  stylometric : {stylo_score:.3f}")

        if llm_score is not None:
            print(f"  llm         : {llm_score:.3f}")
            confidence = round(LLM_W * llm_score + STY_W * stylo_score, 3)
            print(f"  combined    : {confidence:.3f}  ->  {attribution_label(confidence)}")
            agree = (llm_score > 0.5) == (stylo_score > 0.5)
            print(f"  signals agree: {'yes' if agree else 'NO — investigate divergence'}")
        else:
            print(f"  (LLM score skipped — pass --llm to enable)")
        print()


if __name__ == "__main__":
    use_llm = "--llm" in sys.argv
    run(use_llm)
