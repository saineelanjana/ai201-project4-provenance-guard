# System Design & Planning: Provenance Guard

## 🗺️ Architecture

### System Flow Narrative
When a creator uploads a piece of text via `POST /submit`, the content is evaluated in parallel by a semantic LLM-as-judge classifier (via Groq) and a local structural stylometric analysis module. Their scores are mathematically fused into a unified confidence score (0.0 to 1.0) representing AI likelihood, which is mapped to a non-technical transparency label, committed to an append-only audit log, and returned as a JSON payload. If a creator challenges this result via `POST /appeal`, the system verifies the transaction details, updates the lifecycle status to `"under_review"`, appends the creator's written reasoning to the log record, and flags the content for a human moderator's verification queue.

### Architecture Diagram
```text
User Content Submission
          │
          ▼
    POST /submit  ────> [Flask API Endpoint & Rate Limiter]
                                │
                                ├──> Signal 1: Groq LLM (Semantic Coherence) ──> [Score 0.0 - 1.0] ──┐
                                └──> Signal 2: Stylometrics (Structural Metrics) ──> [Score 0.0 - 1.0] ─┴─> [Weighted Scoring Engine]
                                                                                                                     │
                                                                                                                     ▼
                                                                                                           Calibrated Confidence
                                                                                                                     │
                                                                                                                     ▼
    Response to User <─── [JSON Payload] <─── [Transparency Label Mapping] <─── log_interaction() <─── [Audit Log Commit]

[APPEALS WORKFLOW]
POST /appeal ──> [Validate original creator_id] ──> Mutate Status to "under_review" ──> Append Reasoning ──> Reviewer Queue View
```

## 🧠 Core Specifications

### 1. Detection Signals
*   **Signal 1: LLM-Based Classification (Groq / `llama-3.3-70b-versatile`)**
    *   **What it measures:** Semantic fluidity, macro-structural transitions, and holistic writing smoothness.
    *   **Why it differs:** Large language models predictably minimize perplexity, yielding standard transitions and textbook-perfect grammar, whereas human writers introduce idiosyncratic logic leaps, asymmetric pacing, and unconventional phrasing.
    *   **Blind spots:** Highly edited, formal professional copy or academic papers can look like low-perplexity text; adversarial prompting engineered to intentionally inject minor human-like errors can slip past it.
    *   **Output format:** A floating-point value between `0.0` (confident human) and `1.0` (confident AI).
*   **Signal 2: Stylometric Heuristics (Pure Python)**
    *   **What it measures:** Sentence length variance (standard deviation), punctuation density, and Type-Token Ratio (TTR) for lexical diversity.
    *   **Why it differs:** AI text defaults to a highly uniform, balanced sentence length and a standardized vocabulary pool. Human prose fluctuates aggressively between quick fragments, lengthy run-on structures, and wide, creative vocabulary pools.
    *   **Blind spots:** Short text snippets (under 100 words) where statistical variance cannot establish a stable sample size; tightly bounded traditional poetry.
    *   **Output format:** A normalized floating-point value between `0.0` (high variance/human) and `1.0` (zero variance/uniform AI).

### 2. Uncertainty Representation & Scoring Logic
*   **Combination Strategy:** A weighted ensemble model that prioritizes semantic nuance over raw statistics:
    $$\text{Confidence Score} = (0.65 \times \text{LLM Score}) + (0.35 \times \text{Stylometric Score})$$
*   **Score Calibrations & Thresholds:**
    *   `0.00` to `0.40`: **Likely Human** (Low structural matching)
    *   `0.41` to `0.70`: **Uncertain** (Asymmetric defense range protecting human creators from false positive flags)
    *   `0.71` to `1.00`: **Likely AI** (High structural and semantic signature alignment)
*   **Interpretation of a 0.60 Score:** A score of `0.60` represents an ambiguous or borderline classification where the signals conflict (e.g., the text has the rigid sentence structures typical of an LLM, but uses rare, highly diverse vocabulary words typical of a human). Rather than forcing a harsh binary flip that punishes unique human writing styles, a `0.60` safely falls back to the "Unverified" buffer zone to protect the creator's platform visibility while signaling tracking limits to the ecosystem.

### 3. Transparency Label Design
The system dynamically maps confidence evaluations into plaintext strings intended for non-technical platform readers:

*   **High-Confidence Human:** `"Verified Original: This text matches patterns consistent with human authorship."`
*   **Uncertain:** `"Unverified Attribution: Stylistic markers are mixed. Content authenticity cannot be definitively proven."`
*   **High-Confidence AI:** `"AI-Generated Content: Structural signatures indicate this text was generated using automated linguistic models."`

### 4. Appeals Workflow
*   **Authorized Submitter:** Content creators whose incoming request matches the original `creator_id` logged during the initial `/submit` classification lifecycle.
*   **Payload Collected:** `content_id`, `creator_id`, and `creator_reasoning`.
*   **System Actions:** Mutates the database record's lifecycle status attribute from `"classified"` to `"under_review"`, logs an explicit append operation in the audit trail, and attaches the `creator_reasoning` string to the entry.
*   **Reviewer Queue View:** A moderation dashboard sorting active `"under_review"` records chronologically. Human moderators see the original raw text snippet, individual signal margins (LLM vs Heuristic breakdown), the system's generated confidence score, and the creator's written justification side-by-side.

### 5. Anticipated Edge Cases
*   **Scenario 1 (Complex Poetry):** Contemporary poetry utilizing intense structural repetition, short iterative line breaks, and minimalist vocabulary. This triggers a false positive on the pure Python stylometrics due to a very low Type-Token Ratio (TTR) and low sentence length variance, causing the system to flag it as AI-uniform.
*   **Scenario 2 (Non-Native Academic/Formal Text):** Academic papers or professional translations authored by non-native English speakers. Writers often rely tightly on rigid, formal sentence templates and perfectly optimized grammatical transitions, which mimic the exact low-perplexity distributions found in automated LLM generation.
* 
---

## 🛠️ AI Tool Plan

### Milestone 3: Submission Endpoint & First Signal
*   **Context Sections Provided:** `## Architecture`, `### 1. Detection Signals (Signal 1)`
*   **Prompt Request:** Generate a Flask application skeleton containing a stubbed `POST /submit` route, alongside the independent execution logic for the Groq LLM parsing function.
*   **Verification:** Execute direct function tests with sample inputs before tying into route handlers.

### Milestone 4: Second Signal & Confidence Scoring
*   **Context Sections Provided:** `## Architecture`, `### 1. Detection Signals`, `### 2. Uncertainty Representation`
*   **Prompt Request:** Generate the stylometric heuristic evaluation functions and the unified scoring compiler matching the defined thresholds.
*   **Verification:** Validate using the 4 canonical baseline text blocks to guarantee diverse score tiers.

### Milestone 5: Production Layer
*   **Context Sections Provided:** `### 3. Transparency Label Design`, `### 4. Appeals Workflow`
*   **Prompt Request:** Generate the final text mapping logic for labels and assemble the `POST /appeal` data persistence workflow.
*   **Verification:** Assert that status changes correctly flag in the audit trail.