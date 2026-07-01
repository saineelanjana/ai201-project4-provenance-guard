# Provenance Guard

An AI-content attribution API that classifies submitted text as human-written or AI-generated, attaches a transparency label, logs every decision to an append-only audit trail, and supports creator appeals.

---

## Architecture Overview

A submission travels the following path from input to response:

```
POST /submit
    │
    ├── Input validation (text + creator_id required)
    │
    ├── Signal 1: Groq LLM (llama-3.3-70b-versatile)
    │       → floating-point score 0.0–1.0 (0 = human, 1 = AI)
    │
    ├── Signal 2: Stylometric Heuristics (pure Python)
    │       → floating-point score 0.0–1.0 (0 = high variance / human, 1 = uniform / AI)
    │
    ├── Weighted Scoring Engine
    │       confidence = (0.65 × LLM score) + (0.35 × stylometric score)
    │
    ├── Threshold Mapping
    │       ≤ 0.40 → likely_human
    │       0.41–0.70 → uncertain
    │       ≥ 0.71 → likely_ai
    │
    ├── Transparency Label Selection
    │
    ├── Audit Log Commit (logs/audit.jsonl)
    │
    └── JSON Response → { content_id, attribution, confidence, label }
```

Appeals go through `POST /appeal`, which validates the original `creator_id`, mutates the record's status to `under_review`, and appends the creator's reasoning to the log entry. A `GET /log` endpoint exposes the most recent 50 entries for audit visibility.

---

## Detection Signals

### Signal 1 — LLM-Based Classification (Groq / `llama-3.3-70b-versatile`)

**What it measures:** Semantic fluidity, macro-structural transitions, and holistic writing smoothness. The model is prompted to return a single float representing AI likelihood.

**Why this signal:** Large language models predictably minimize perplexity, yielding standard transitions and textbook-perfect grammar. Human writers introduce idiosyncratic logic leaps, asymmetric pacing, and unconventional phrasing that LLM classifiers are well-positioned to detect because they share the same underlying distributional space.

**What it misses:** Highly edited formal professional copy or academic papers can look like low-perplexity text and receive false-positive AI scores. Adversarial text engineered to inject minor human-like errors can also evade it.

**Output:** Float 0.0 (confident human) → 1.0 (confident AI).

---

### Signal 2 — Stylometric Heuristics (Pure Python)

Four metrics are computed and combined into a single score:

| Metric | AI pattern | Human pattern |
|---|---|---|
| **Sentence length std_dev** | Low variance — uniform sentence rhythm | High variance — fragments mixed with run-ons |
| **Average word length** | Longer, formal academic vocabulary (~6+ chars/word) | Shorter, everyday vocabulary (~4 chars/word) |
| **Punctuation density** | Clean sentence-ending punctuation only | Expressive informal markers (`!`, `?`, `;`, `—`) |
| **Type-Token Ratio** | Unreliable for short texts; retained as tie-breaker for repetitive text | TTR < 0.55 flags repetitive/casual writing |

Weights: sentence variance × 0.35, word length × 0.35, punctuation density × 0.20, TTR × 0.10.

**Why these metrics:** AI text defaults to a highly uniform, balanced sentence length and a formal, standardized vocabulary pool. Human prose fluctuates aggressively in sentence length and mixes formal with informal words depending on context.

**What it misses:** Short texts (under ~80 words) where statistical variance cannot establish a stable sample size. Contemporary poetry with intentional repetition and minimalist vocabulary triggers false positives. The TTR signal is compressed near 0.85–0.90 for all short texts and carries limited standalone weight.

**Output:** Float 0.0 (high variance / human-like) → 1.0 (uniform / AI-like).

---

## Confidence Scoring

### Formula

```
confidence = (0.65 × LLM score) + (0.35 × stylometric score)
```

The LLM signal carries higher weight because it captures semantic intent and writing coherence — properties that pure structural heuristics miss. The stylometric signal acts as a cross-check: if the LLM is uncertain, structural uniformity can tip the classification.

### Thresholds

| Range | Attribution | Reasoning |
|---|---|---|
| 0.00 – 0.40 | `likely_human` | Both signals lean strongly human |
| 0.41 – 0.70 | `uncertain` | Signals conflict or evidence is weak — protects creators from false positives |
| 0.71 – 1.00 | `likely_ai` | Both signals converge on AI-generated patterns |

The wide uncertain band (0.41–0.70) is intentional: formal human writing often scores 0.55–0.65 on the LLM signal because it resembles low-perplexity AI output. Forcing a hard binary flip at 0.50 would falsely flag academic writers and non-native English speakers.

### Example Submissions

**High-confidence AI (confidence = 0.82, label = `likely_ai`)**
```
Input: "Artificial intelligence represents a transformative paradigm shift in modern
society. It is important to note that while the benefits of AI are numerous, it is
equally essential to consider the ethical implications. Furthermore, stakeholders
across various sectors must collaborate to ensure responsible deployment."

LLM score:         0.90
Stylometric score: 0.66
Combined:          (0.65 × 0.90) + (0.35 × 0.66) = 0.585 + 0.231 = 0.82 → likely_ai
```

Stylometric breakdown: avg_word_len = 6.23 (formal vocabulary), std_dev = 5.44 (moderate but uniform rhythm), zero informal punctuation — all pointing to machine-generated structure.

**Low-confidence human (confidence = 0.20, label = `likely_human`)**
```
Input: "ok so i finally tried that new ramen place downtown and honestly?
underwhelming. the broth was fine but they put WAY too much sodium in it and i
was thirsty for like three hours after. my friend got the spicy version and said
it was better. probably won't go back unless someone drags me there"

LLM score:         0.10
Stylometric score: 0.38
Combined:          (0.65 × 0.10) + (0.35 × 0.38) = 0.065 + 0.133 = 0.20 → likely_human
```

Stylometric breakdown: avg_word_len = 4.18 (everyday casual vocabulary), std_dev = 6.72 (erratic sentence lengths from "underwhelming." as a one-word sentence), lowercase throughout — consistent human writing patterns.

These two cases show the scoring produces meaningful variation: 0.82 vs 0.20, separated by all four stylometric features moving in the same direction.

---

## Transparency Labels

The system maps confidence scores to one of three plaintext labels intended for non-technical platform readers:

**High-confidence human** (confidence ≤ 0.40):
> Verified Original: This text matches patterns consistent with human authorship.

**Uncertain** (confidence 0.41–0.70):
> Unverified Attribution: Stylistic markers are mixed. Content authenticity cannot be definitively proven.

**High-confidence AI** (confidence ≥ 0.71):
> Unverified Authenticity: Structural signatures are consistent with AI-generated text. This content has been flagged for review.

All three variants are reachable via the `/submit` endpoint. The test inputs in `test_signals.py` demonstrate scores of 0.20 (human), 0.57 (uncertain), and 0.82 (AI) across the four spec test cases.

---

## Rate Limiting

The `/submit` endpoint is limited to **10 requests per minute and 100 requests per day** per IP address.

**Reasoning:** A working writer submitting their own pieces for attribution review realistically sends 1–3 submissions per session. A burst of 10 per minute accommodates rapid iterative testing (submitting multiple drafts of the same piece) without enabling scripted flooding. The 100/day cap prevents a single IP from exhausting Groq API quota — at roughly $0.001 per Groq call, 100 submissions costs ~$0.10/day per user, which is sustainable.

**Evidence — rate limit enforcement (429 responses after 10th request):**
```
200
200
200
200
200
200
200
200
200
200
429
429
```

The implementation uses Flask-Limiter ≥ 3.x with `storage_uri="memory://"` for local development:
```python
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day"],
    storage_uri="memory://"
)

@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    ...
```

---

## Known Limitations

**Non-native English academic and formal writing** is the most likely source of false positives. Writers who rely on rigid formal sentence templates, perfectly optimized grammatical transitions, and low-perplexity phrasing — common patterns in academic papers or professional translations from non-native English speakers — will have their work score in the 0.55–0.75 range on the LLM signal. This happens because the LLM classifier and the human author are drawing from the same formal register: the classifier cannot distinguish between "this was generated by a model" and "this was written by someone who learned formal English as a second language and writes in the academic style they were trained on."

This is not a calibration error that can be fixed by adjusting thresholds — it is a fundamental property of the LLM-as-judge approach. The wide uncertain band (0.41–0.70) mitigates this by routing borderline cases to `uncertain` rather than `likely_ai`, but it does not eliminate it.

**Contemporary poetry** with intense structural repetition and minimalist vocabulary triggers false positives on the stylometric signal specifically. Low sentence-length variance and a restricted vocabulary pool (low avg word length, low TTR) match the same statistical patterns the system associates with AI uniformity. This is documented as a known edge case in `planning.md`.

---

## Spec Reflection

**One way the spec helped:** The planning document's explicit requirement to document each signal's blind spots before implementation prevented a common failure mode: building a signal and then reverse-engineering justifications for why it works. Writing "TTR is unreliable for short texts" in the spec before touching any code meant I noticed immediately during calibration testing that the original TTR threshold (0.45–0.58) returned the same score (0.38) for every one of the four spec test inputs — and had a documented reason to replace it rather than rationalize it.

**One way implementation diverged from the spec:** The spec describes TTR as one of three primary stylometric metrics alongside sentence length variance and punctuation density. During calibration, TTR proved essentially useless for texts under ~300 words: all four spec test inputs clustered in the 0.86–0.90 TTR range regardless of whether they were AI-generated or human-written. Rather than remove TTR (which would deviate from the documented spec), I added average word length as the primary lexical discriminator and retained TTR at a 10% weight as a tie-breaker for repetitive text. This preserved the spec's intent — measuring lexical diversity — while replacing the mechanism that was empirically broken for short texts.

---

## AI Usage

### Instance 1 — Flask Skeleton and First Signal (Milestone 3)

**Directed:** Provided the architecture diagram and Signal 1 specification from `planning.md`, then prompted the AI tool to generate a Flask app skeleton with a stubbed `POST /submit` route and the `get_llm_score` function.

**Produced:** A working Flask skeleton and a Groq API call that returned a raw completion string. The function signature matched the spec (returns a float), the endpoint structure matched the API contract (accepts `text` + `creator_id`, returns `content_id` + `attribution` + `confidence` + `label`).

**Revised:** The original system prompt in `get_llm_score` asked for a "structured assessment" rather than a bare float, which caused parsing failures when the model returned prose. Tightened the system prompt to "Output exactly a single float between 0.0 (Human) and 1.0 (AI)" to enforce the return format.

### Instance 2 — Stylometric Signal and Confidence Scoring (Milestone 4)

**Directed:** Provided the full Detection Signals and Uncertainty Representation sections from `planning.md` and asked the AI tool to generate the `get_stylometric_score` function and the confidence scoring logic combining both signals.

**Produced:** A stylometric function using sentence length variance and TTR, and the correct weighted formula `(0.65 × LLM) + (0.35 × stylometric)` with the right thresholds.

**Revised:** Running the generated function against the four spec test inputs revealed a critical calibration failure — it returned 0.38 for every input. The root cause was two compounding problems: the step-function thresholds for sentence variance never triggered (`std_dev` for real text consistently fell in the 4–7 middle range), and the TTR window (0.45–0.58) is never reached by short texts where TTR clusters above 0.85. Replaced the step functions with continuous mappings, added average word length as the primary lexical discriminator, and added punctuation density (which was listed in the spec but missing from the generated code). After the fix, scores ranged from 0.38 (human casual) to 0.66 (AI formal) — meaningful variation across all four test cases.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:
```
GROQ_API_KEY=your_key_here
```

Run the server:
```bash
python app.py
```

### Example: Submit text for classification
```bash
curl -s -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "The sun dipped below the horizon, painting the sky in hues of amber and rose. I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet.", "creator_id": "test-user-1"}' | python -m json.tool
```

### Example: File an appeal
```bash
curl -s -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "PASTE-CONTENT-ID-HERE", "creator_id": "test-user-1", "creator_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical."}' | python -m json.tool
```

### Example: View audit log
```bash
curl -s http://localhost:5000/log | python -m json.tool
```

### Example audit log entry
```json
{
  "content_id": "3f7a2b1e-...",
  "creator_id": "test-user-1",
  "timestamp": "2025-04-01T14:32:10.123Z",
  "attribution": "likely_ai",
  "confidence": 0.82,
  "llm_score": 0.90,
  "stylometric_score": 0.66,
  "status": "classified",
  "appeal_reasoning": null
}
```
