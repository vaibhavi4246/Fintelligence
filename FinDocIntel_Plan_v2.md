# FinDocIntel — Financial Document Intelligence Engine + LLM Eval Harness

*Implementation Plan v2.1 — Internal Sprint Document*

**Team:** Sanyam (Full-Stack + ML) · Vaibhavi (Full-Stack + ML)
**Duration:** 4 weeks · Target companies: BlackRock, Goldman Sachs, Microsoft

---

## Team Ownership Summary

| Member | Domain | Deliverables |
|---|---|---|
| **Sanyam** | Backend ML + UI | LangGraph DAG, contradiction classifier (3-way taxonomy), GraphRAG claim graph + entity resolution, hybrid pgvector retrieval, `/analyze` + `/retrieve` endpoints, factuality + calibration eval metrics + Wilson CIs, adversarial test set generator, error analysis, contradiction viewer UI, confidence visualization |
| **Vaibhavi** | Infra + ML + UI | Dual-path ingestion (EDGAR HTML/XBRL + pdfplumber), section-aware chunker, risk signal extractor, Pydantic output schema, cross-model dual LLM-as-judge harness, 8-K restatement benchmark, cost/latency accounting, eval dashboard + leaderboard, Docker/CI/CD, deployment |

---

# 1. System Architecture

Two integrated layers. Neither is optional.

**Layer 1 — Intelligence Engine:** Processes SEC filings, 10-K/10-Q documents, and earnings transcripts. Distinguishes genuine cross-period contradictions from legitimate business changes (three-way taxonomy: factual / explained-change / restatement), extracts risk signals mapped to a hardcoded taxonomy, and returns confidence-scored structured JSON with per-claim source citations — backed by a GraphRAG claim graph for entity resolution and multi-hop retrieval.

**Layer 2 — LLM Eval Harness:** Automated quality pipeline running on every commit. Measures factuality, citation accuracy, contradiction precision/recall, and confidence calibration. Tracks regression across model versions. This is what makes the project scientifically defensible — not another RAG wrapper.

### 1.1 What This Is Not

- Not a "chat with PDF" interface. No free-form Q&A.
- Not sentiment analysis. Output is structured JSON with per-claim confidence scores and cited source chunks.
- Not a prototype. The eval harness produces a precision metric — reported with a Wilson 95% confidence interval, never a bare number — benchmarked against companies' own 8-K restatements and corrective disclosures as authoritative, fully public ground truth. That number goes on the resume.

### 1.2 System Layers

| Layer | Components |
|---|---|
| **Ingestion** | Two parsing paths: EDGAR HTML/XBRL parser (filings by ticker) + pdfplumber (manual PDF uploads — broker notes, transcripts) → section-aware chunker → pgvector embeddings + claim graph → PostgreSQL metadata store |
| **Intelligence Engine** | LangGraph DAG: hybrid retrieval agent (vector + claim graph) → contradiction classifier (FACTUAL / EXPLAINED_CHANGE / RESTATEMENT) → risk signal extractor → structured output assembler → IntelligenceReport JSON |
| **Eval Harness** | Adversarial test set (200 cases) → factuality scorer → citation verifier → calibration (Brier score) → cross-model dual LLM-as-judge (agreement κ) → Wilson confidence intervals → error analysis → regression detector → benchmark vs. 8-K restatements |
| **Frontend** | Next.js 14: document upload → intelligence report viewer (contradiction cards + citation highlights) → eval dashboard + model leaderboard |

---

# 2. Technology Stack

| Layer | Choice | Rationale | Owner |
|---|---|---|---|
| Backend API | FastAPI | Async, OpenAPI autodocs, native LangGraph integration | Sanyam |
| LLM Orchestration | LangGraph | DAG-based agent state, first-class tool calling, controllable execution graph | Sanyam |
| LLM (local-first) | **Qwen2.5-14B-Instruct** (extractor) + **Qwen2.5-VL** (multimodal table/figure parsing) + **Llama-3.1-8B / Mistral** (independent judge) | Runs locally via Ollama/vLLM — near-zero marginal cost, 128K context, and no financial data leaves the box (a real selling point for finance reviewers). Judge is a *different* family from the extractor to avoid self-grading. Hosted GPT-4o kept optional as an external tie-breaker only. | Sanyam |
| Vector Store | pgvector (PostgreSQL extension) | Single DB for vectors + metadata; no Pinecone dependency; SQL joins on fiscal period filters | Sanyam |
| Claim Graph | Apache AGE (PostgreSQL graph extension) / networkx | GraphRAG layer: entity→metric→period claim graph for multi-hop retrieval and entity resolution (segment renames); no separate Neo4j infra | Sanyam |
| Relational DB | PostgreSQL (Supabase or self-hosted) | Document metadata, structured outputs, eval results, model version tracking | Vaibhavi |
| Document Parsing | EDGAR HTML/XBRL parser (selectolax/BeautifulSoup) + pdfplumber | Two paths: EDGAR serves HTML/XBRL (not PDF) so it gets a dedicated structured parser; pdfplumber reserved for manual PDF uploads (broker notes, transcripts) | Vaibhavi |
| Embeddings (local) | bge-base-en-v1.5 / Qwen3-Embedding | Local embeddings (768/1024-dim) served alongside the LLM — no API dependency, no data egress; strong retrieval on financial text. Hosted `text-embedding-3-small` remains a drop-in fallback. | Vaibhavi |
| Frontend | Next.js 14 (App Router) | Server components, streaming UI for long LLM responses, API routes for BFF pattern | Both |
| Eval Runner | Python + PostgreSQL | Custom domain-specific metrics; cross-model LLM-as-judge (extractor ≠ judge); Wilson CIs via statsmodels; cost/latency per stage; results persisted per eval_run | Vaibhavi |
| Containerization | Docker + Docker Compose | One-command local stack; dev/demo environment parity | Vaibhavi |
| CI/CD | GitHub Actions | Eval harness runs on every push; regression alerts fail the PR; score summary posted to PR comment | Vaibhavi |

---

# 3. PostgreSQL Schema

All tables have indexes. Schema supports both intelligence engine and eval harness. Each member owns migrations for their domain.

### Core Tables

| Table | Key Fields | Owner |
|---|---|---|
| **documents** | id, ticker, filing_type (10-K/10-Q/transcript), fiscal_period, fiscal_year, source_url, ingested_at, chunk_count, processing_status | Vaibhavi |
| **chunks** | id, document_id, chunk_index, content (text), embedding (vector N — sized to the local embedding model: 768 for bge-base, 1024 for Qwen3-Embedding), section_label, page_number | Vaibhavi |
| **intelligence_reports** | id, query_id, document_ids (array), model_version, generated_at, structured_output (jsonb), overall_confidence, contradiction_count, risk_signal_count | Sanyam |
| **claims** | id, report_id, claim_text, claim_type (fact/risk/contradiction), confidence_score, supporting_chunk_ids (array), cited_document_ids (array), verified (bool) | Sanyam |
| **contradictions** | id, report_id, claim_a_id, claim_b_id, document_a_id, document_b_id, period_a, period_b, contradiction_type (FACTUAL_CONTRADICTION/EXPLAINED_CHANGE/RESTATEMENT), stated_cause (text, nullable), restatement_source (8-K url, nullable), severity (low/medium/high), explanation | Sanyam |
| **risk_signals** | id, report_id, signal_text, taxonomy_category, severity, source_chunk_id, confidence_score | Vaibhavi |
| **claim_nodes** | id, ticker, subject (entity), predicate (metric), object (value), period, claim_id, canonical_entity_id (resolves segment renames) | Sanyam |
| **claim_edges** | id, source_node_id, target_node_id, edge_type (SAME_METRIC/CONTRADICTS/EXPLAINS/RESTATES/ALIAS_OF), weight, period_delta | Sanyam |
| **eval_runs** | id, model_version, run_at, test_set_id, factuality_score, citation_accuracy, calibration_score, contradiction_precision, contradiction_recall, precision_ci_low, precision_ci_high (Wilson 95%), extractor_model, judge_model, judge_agreement_rate, inter_judge_kappa, cost_usd, gpu_seconds, p50_latency_ms, p95_latency_ms, notes | Vaibhavi |
| **eval_test_cases** | id, test_set_id, input_query, input_document_ids, expected_output (jsonb), adversarial (bool), created_by (human/model), created_at | Sanyam |
| **eval_results** | id, eval_run_id, test_case_id, model_output (jsonb), factuality_pass (bool), citation_pass (bool), llm_judge_score, llm_judge_reasoning | Vaibhavi |

### Schema Design Decisions

- `structured_output` stored as JSONB — enables SQL queries on nested claim fields without ORM overhead.
- `embedding` column uses `vector(N)` via pgvector, where `N` matches the local embedding model (768 for bge-base, 1024 for Qwen3-Embedding). Index: `ivfflat` with `lists=100` for approximate nearest-neighbor search.
- `eval_runs` enables regression detection: compare `factuality_score` across `model_version` with a single `GROUP BY` query. It also stores `extractor_model` and `judge_model` separately so it is always provable that the judge differed from the extractor.
- `contradictions` stores both claim IDs and document IDs explicitly — contradiction detection is the differentiator and is first-class in the schema.
- `contradiction_type` is an explicit enum (`FACTUAL_CONTRADICTION` / `EXPLAINED_CHANGE` / `RESTATEMENT`) so the headline metric measures *distinguishing real contradictions from legitimate business evolution*, not raw flagging. `stated_cause` and `restatement_source` capture the evidence for that classification.
- `claim_nodes` + `claim_edges` form the GraphRAG layer. `canonical_entity_id` resolves renamed segments after a reorg to the same node — directly preventing the most common contradiction false-positive class.

---

# 4A. Intelligence Engine — Detailed Design

## LangGraph Agent DAG

```
[Input: ticker + period range]
        |
        v
[Hybrid Retrieval Agent]                        ← Sanyam
  - pgvector cosine similarity search (dense recall)
  - Claim-graph traversal: walk (entity)-(metric)-(period) edges to pull
    all periods of the same metric, even across renamed segments (GraphRAG)
  - Filters by fiscal_period metadata
  - Returns top-k chunks + linked claim nodes per document
        |
        v
[Contradiction Classifier]                      ← Sanyam  ← CORE DIFFERENTIATOR
  - Extracts atomic claims: {claim, subject, predicate, object, period, stated_cause}
  - Resolves entities via claim graph (canonical_entity_id) — renamed segments collapse to one node
  - Groups by (canonical subject, predicate) across fiscal periods
  - Semantic diff: cosine similarity on aligned claim pairs flags CANDIDATES (not verdicts)
  - LLM CLASSIFIES each candidate into:
      FACTUAL_CONTRADICTION — same claim, conflicting numbers, no stated cause
      EXPLAINED_CHANGE      — different numbers, filing attributes a cause (input costs, FX)
      RESTATEMENT           — explicit correction, usually disclosed in an 8-K
  - Severity applies ONLY to FACTUAL_CONTRADICTION:
      HIGH (numerical conflict), MEDIUM (directional), LOW (framing shift)
        |
        v
[Risk Signal Extractor]                         ← Vaibhavi
  - Maps chunks to hardcoded 5-category taxonomy (Python Enum)
  - LLM prompted to classify within taxonomy only — no free-form categories
  - Confidence score per signal
        |
        v
[Structured Output Assembler]                   ← Vaibhavi
  - Compiles claims, contradictions, risk signals into validated Pydantic schema
  - Per-claim citation: chunk_id + document_id + page_number
  - overall_confidence = weighted average of per-claim scores
        |
        v
[Output: IntelligenceReport JSON]
```

## Contradiction Detection — Technical Approach

**Owner: Sanyam**

The core insight — and the reason this is a differentiator rather than embedding-diffing — is that **a quarter-over-quarter change is not automatically a contradiction.** The hard problem is separating a company genuinely contradicting itself from a company whose situation legitimately changed, or one quietly correcting a prior error. We make that distinction explicit with a three-way taxonomy instead of a binary flag.

1. **Claim extraction:** Each chunk → atomic claims as `{claim, subject, predicate, object, period, stated_cause}` via structured LLM output (Qwen2.5). `stated_cause` captures any reason the filing itself gives for a change ("due to input cost pressure", "FX headwinds").
2. **Entity resolution (graph):** Map each `subject` to a `canonical_entity_id` via the claim graph so a segment renamed in a reorg (e.g. "Devices" → "Hardware") aligns to the same node rather than registering as a spurious change.
3. **Cross-period alignment:** Group claims by `(canonical_subject, predicate)` across fiscal periods for the same ticker.
4. **Semantic diff:** Cosine similarity on aligned claim pairs surfaces *candidates*. Low similarity + same subject/predicate = candidate for classification — **not yet a contradiction.**
5. **LLM classification:** The model assigns each candidate to exactly one category:

   | Category | Definition | Resume-relevant signal |
   |---|---|---|
   | `FACTUAL_CONTRADICTION` | Same claim, conflicting numbers, **no stated cause** | A real inconsistency |
   | `EXPLAINED_CHANGE` | Different numbers, but the filing **attributes a cause** | Normal business evolution — *not* a contradiction |
   | `RESTATEMENT` | Explicit correction of a prior figure, usually disclosed in an 8-K | Self-documented contradiction with authoritative source |

6. **Severity** (FACTUAL_CONTRADICTION only): HIGH = numerical conflict, MEDIUM = directional, LOW = framing shift.

**Worked example — the distinction in action:**

- *Not a contradiction (EXPLAINED_CHANGE):* Q2 10-Q "gross margin expanded 200bps YoY" → Q3 10-Q "gross margin contracted **due to input cost pressure**." The filing states the cause → legitimate business evolution, and the system must **not** flag it as a contradiction.
- *A real contradiction (FACTUAL_CONTRADICTION):* Q2 10-Q "no material pending litigation" → Q3 10-Q "we are party to a material lawsuit filed in [a date preceding the Q2 filing]." Same subject, conflicting facts, no reconciling cause → HIGH.
- *A restatement (RESTATEMENT):* 8-K "we are restating Q1 revenue from \$4.2B to \$3.9B." The company documents its own contradiction → authoritative ground truth.

The headline claim therefore becomes: *"the system correctly distinguishes real contradictions from legitimate business evolution X% of the time"* — far more defensible than raw contradiction-flagging, and it shows domain understanding rather than just diffing embeddings.

## GraphRAG Layer — Claim Graph

**Owner: Sanyam**

Vector retrieval alone treats each chunk independently, which is exactly why naive contradiction detection over-fires: it has no notion that "Devices margin" in 2022 and "Hardware margin" in 2023 are the same line, or that a Q3 claim *explains* a Q2 claim. We add a lightweight property graph over extracted claims and retrieve over both.

**Graph construction (during ingestion):**
- **Nodes** = claim atoms: `(canonical_entity, metric, value, period, claim_id)`.
- **Edges:**
  - `SAME_METRIC` — same `(entity, metric)` across periods (the backbone for cross-period diffing).
  - `ALIAS_OF` — links a renamed segment to its canonical entity (entity resolution).
  - `CONTRADICTS` / `EXPLAINS` / `RESTATES` — written by the contradiction classifier as typed edges, so the graph itself records *why* two claims relate.

**How it beats plain RAG:**
1. **Multi-hop assembly** — to analyze "gross margin," traverse `SAME_METRIC` edges to pull *every* period of that metric in one hop, instead of hoping top-k vector search surfaces all of them.
2. **Entity resolution** — `ALIAS_OF` edges collapse reorg renames, removing the single largest source of contradiction false positives.
3. **Explainable paths** — a contradiction is a typed subgraph (`claim_A —CONTRADICTS→ claim_B`), so the report viewer renders the actual evidence path, not just two cards.
4. **Cross-company reasoning** (Tier 1) — connect GS and BLK claims about the same sector to surface *cross-issuer* disagreement, which a vector query cannot express.

**Implementation (kept lean, local-first):** no separate graph database and no cloud dependency. Use **Apache AGE** (a PostgreSQL extension speaking openCypher over the same Postgres instance) or an in-process **networkx** graph rebuilt from the `claim_nodes` / `claim_edges` tables. Hybrid retrieval = `pgvector` dense recall + graph traversal for structural recall, fused before the contradiction classifier. Single Postgres container, genuine GraphRAG story.

## Risk Signal Taxonomy

**Owner: Vaibhavi**

| Category | Signals Detected |
|---|---|
| Liquidity | Cash burn rate changes, covenant breaches, revolving credit mentions |
| Legal | Ongoing litigation material changes, regulatory investigation language, SEC inquiry mentions |
| Macro | Interest rate exposure, FX headwind escalation, inflation impact language |
| Operational | Supply chain disruption, workforce reduction, capacity constraint language |
| Competitive | Market share loss language, pricing power commentary, new entrant mentions |

Taxonomy is a hardcoded Python Enum. LLM is constrained to classify within it — no generative category invention.

## Structured Output Schema

**Owner: Vaibhavi**

```json
{
  "ticker": "AAPL",
  "periods_analysed": ["Q2-2023", "Q3-2023", "Q4-2023"],
  "overall_confidence": 0.82,
  "contradictions": [
    {
      "claim_a": "...", "period_a": "Q2-2023",
      "claim_b": "...", "period_b": "Q3-2023",
      "severity": "HIGH",
      "explanation": "...",
      "citations": [{"document_id": "...", "page": 14}]
    }
  ],
  "risk_signals": [
    {
      "signal": "...", "category": "Liquidity",
      "confidence": 0.91,
      "citation": {"document_id": "...", "chunk_id": "..."}
    }
  ],
  "claims": [
    {
      "claim": "...", "confidence": 0.88,
      "citations": [{"document_id": "...", "page": 7}]
    }
  ]
}
```

---

# 4B. LLM Eval Harness — Detailed Design

Runs on every commit via GitHub Actions. Makes the intelligence engine scientifically defensible.

## Metrics

All proportion metrics are reported as a point estimate **with a Wilson 95% confidence interval** — `81% (CI 74–86%)` — never a bare number. This signals you understand the difference between "we measured this" and "we measured this and know how much to trust it."

| Metric | Definition | Owner |
|---|---|---|
| **Factuality Score** | % of claims in output supported by cited source chunk. Verified by an independent (cross-model) LLM judge. | Sanyam |
| **Citation Accuracy** | % of citations where cited chunk actually contains the claimed information. Catches hallucinated page numbers. | Sanyam |
| **Contradiction Precision (taxonomy-aware)** | % of flagged `FACTUAL_CONTRADICTION`s that are genuine — i.e. the system did **not** misfile a legitimate `EXPLAINED_CHANGE` as a contradiction. The headline number. | Vaibhavi |
| **Explained-Change Discrimination** | Of pairs where the filing states a cause, % the system correctly labels `EXPLAINED_CHANGE` rather than `FACTUAL_CONTRADICTION`. Directly measures the core differentiator. | Sanyam |
| **Contradiction Recall** | % of ground-truth contradictions (incl. 8-K restatements) the system detected. | Vaibhavi |
| **Calibration (Brier Score)** | How well does `confidence_score` predict actual factual correctness? Well-calibrated at 0.9 confidence → correct ~90% of the time. Reported **per category** (calibration degrades on sparse categories like Legal). | Sanyam |
| **Dual-Judge Agreement** | Two independent judges (Llama-3.1 + Mistral, neither is the extractor) score each case; we report (a) each judge's agreement with human labels on a 50-case subset and (b) inter-judge agreement (Cohen's κ). Disagreement routes to human review. | Vaibhavi |
| **Cost per call** | \$ / GPU-seconds per `/analyze` and per full eval run, broken out by agent (retrieval / contradiction / risk). | Vaibhavi |
| **Latency P50/P95** | Per-stage wall-clock, not just end-to-end. | Vaibhavi |
| **Regression Flag** | Fails CI if factuality or contradiction_precision drops by more than the CI half-width vs. previous eval_run. Posts warning to PR comment. | Vaibhavi |

## Adversarial Test Set Generator

**Owner: Sanyam**

No off-the-shelf benchmarks (MMLU etc.) — financial domain requires domain-specific test cases. Two design rules guard against correlated blind spots: (a) the **generator model is different from the model under test** (cases generated with a separate model — e.g. GPT-4o or a different local family — while extraction is done by Qwen), and (b) every case is human-reviewed before it counts.

1. Pull real SEC filing chunks (AAPL, MSFT, GS, BLK 10-Ks, 2021–2024).
2. Prompt the generator for **three** case types, so the set tests the *distinction*, not just detection:
   - a plausible-but-false claim (factuality negative),
   - a genuine `FACTUAL_CONTRADICTION` pair with the following quarter,
   - a **hard negative**: a real quarter-over-quarter change *with a stated cause* that must be labelled `EXPLAINED_CHANGE`, not a contradiction.
3. **Mine real 8-K restatements** for a subset of `RESTATEMENT` cases — ground-truth contradictions the company documented itself (see benchmark below).
4. Sanyam reviews and labels each generated case — accept/reject before storing.
5. Store in `eval_test_cases` with `adversarial=true` and the gold `contradiction_type`.
6. Target: 200 human-reviewed cases across 5 tickers, 3 years each, with a deliberate share of `EXPLAINED_CHANGE` hard negatives.

## LLM-as-Judge Protocol

**Owner: Vaibhavi**

**No self-grading.** The model that extracts claims (Qwen) is never the sole judge of its own output. Judging is done by *different* families (Llama-3.1 / Mistral), and for the headline metrics we run **two independent judges** and report their agreement (Cohen's κ) as its own number — pre-empting the obvious "isn't this the model grading its own homework?" interview question.

```
System: You are a financial fact-checker. Given a claim and the source text it cites,
        determine if the claim is factually supported by the source.
        Respond ONLY in JSON: {"verdict": "SUPPORTED"|"UNSUPPORTED"|"PARTIAL", "reasoning": "..."}

User:   Claim: [claim_text]
        Cited source: [chunk_content]
```

- **Judge model ≠ extractor model**, recorded explicitly in `eval_runs.extractor_model` / `eval_runs.judge_model`.
- **Two judges** score the labelled subset; we report each judge's agreement with human labels *and* inter-judge κ (`eval_runs.inter_judge_kappa`).
- Cases where the two judges disagree are routed to human review rather than silently averaged.

## Benchmark Against 8-K Restatements (Authoritative Ground Truth)

**Owner: Vaibhavi (data collection) + Sanyam (metric computation)**

Paywalled analyst reports were the weakest link in v1 — hard to access, hard to cite, hard to defend ("where did the ground truth come from?"). We replace them with a fully public, authoritative source: **companies' own 8-K restatements and corrective disclosures.**

A company that restates earnings is, by definition, documenting its own contradiction — with an authoritative source and a timestamp. So:

1. Pull 8-K filings flagged as **Item 4.02** (non-reliance on previously issued financials) and other corrective disclosures across the benchmark tickers + a wider universe to get enough positives.
2. The restated figure vs. the originally reported figure is a **gold `RESTATEMENT` contradiction** — no human guesswork.
3. Run the intelligence engine over the original + restating filings; measure recall (did it catch the documented contradiction?) and precision (with Wilson CI).
4. This is the headline resume metric — free, reproducible, and a more interesting story than "we eyeballed some bank reports."

*Optional secondary benchmark:* if accessible, a small set of free public analyst notes (broker free research) as a softer risk-signal cross-check — clearly labelled secondary, never the headline.

---

# 4C. Error Analysis — Where It Breaks and Why

A score alone reads as a school project. For every benchmark run we categorize the failure cases, not just count them. The eval runner buckets each false positive / false negative by cause and emits a table that ships in the README **and** as its own dashboard view.

| Bucket | Example | Likely fix |
|---|---|---|
| Renamed segment (reorg) | "Devices" → "Hardware" read as a metric change | `ALIAS_OF` graph edges / entity resolution |
| Stated-cause missed | Filing gave a cause in an adjacent sentence the chunker split off | Chunk boundary / wider context window |
| Restatement vs. contradiction | Genuine 8-K correction labelled `FACTUAL_CONTRADICTION` | Cross-reference 8-K Item 4.02 |
| Sparse-category calibration | Legal signals over/under-confident (few examples) | Per-category calibration; flag low-support |
| Citation drift | Right claim, off-by-one page number | Citation verifier hard gate |

The deliverable is a sentence like *"62% of contradiction false positives came from renamed business segments after a reorg, addressed by entity-resolution edges in the claim graph"* — the difference between "we built X and got a number" and "we built X, characterized where it breaks, and can explain why." Interviewers remember the second kind.

---

# 4D. Cost & Latency Accounting

Production awareness most portfolio projects skip. We instrument every pipeline stage and persist per-run figures in `eval_runs`.

| Tracked | Granularity |
|---|---|
| **\$ / GPU-seconds per `/analyze` call** | total + per agent (retrieval / contradiction / risk / assembler) |
| **Cost per full eval run** | 200-case set, by model |
| **Token usage** | input/output tokens per stage |
| **Latency P50 / P95** | per agent, not just end-to-end |
| **Model trade-off** | same metrics for Qwen (local) vs. a hosted model — ties into the model-comparison story |

Because inference is **local Qwen**, marginal API cost is ~\$0 — the story is "this runs on one box for the price of electricity," which is exactly the cost-at-scale answer finance and Microsoft interviewers probe for. We still report a hosted-model column so the trade-off (latency/quality vs. \$/token) is explicit.

---

# 4E. Limitations (Stated, Not Hidden)

Openly stating where the system is weak reads as *more* credible than a page implying it is flawless. Reviewers trust people who know where their system breaks. The README carries this verbatim:

- **Taxonomy edge cases:** the `FACTUAL_CONTRADICTION` / `EXPLAINED_CHANGE` boundary is genuinely fuzzy when a filing states a *partial* cause; we report the share of such ambiguous cases rather than hiding them.
- **Calibration on sparse categories:** confidence is well-calibrated on Liquidity/Macro (many examples) and degrades on Legal (few). Reported per-category, not just in aggregate.
- **Recall ceiling from chunking:** a contradiction split across a chunk boundary can be missed; recall is bounded by retrieval, not just reasoning.
- **8-K coverage:** restatement ground truth covers *explicit* corrections; subtler unacknowledged contradictions have no gold label and rely on human review.
- **Local-model ceiling:** Qwen2.5-14B trades some extraction accuracy vs. a frontier hosted model; we quantify the gap in the model-comparison table rather than assuming parity.
- **Single-language, US-GAAP only:** no IFRS / non-US filings in scope.

---

# 4F. Demo Principle — Show It Failing Safely

The most convincing 30 seconds of the demo is **not** "look, it found a contradiction." It is the eval harness doing its job: a regression caught by CI and failing a PR, or a low-confidence claim correctly flagged as uncertain instead of confidently wrong, or an `EXPLAINED_CHANGE` correctly *not* flagged. That is the actual value proposition of an eval harness, so the walkthrough leads with safe failure, then shows the happy path.

---

# 5. Document Ingestion Pipeline

**Owner: Vaibhavi (HTML/XBRL + pdfplumber parsers + chunker + EDGAR fetch) + Sanyam (embedding + pgvector store + claim graph builder)**

```
[SEC EDGAR REST API]  →  fetch by ticker + form type + period      [Vaibhavi]
[PDF upload (manual)] →  drag-drop in Next.js UI                   [Vaibhavi]
        |
        v
[Two parsing paths — same downstream chunk schema]                 [Vaibhavi]
  ┌─ EDGAR path → HTML/XBRL parser
  │    - EDGAR serves HTML + XBRL, NOT PDF — so it gets a dedicated parser
  │    - Structured financial facts read directly from XBRL tags
  │    - Section labels from HTML headings: MD&A, Risk Factors, Financial Statements
  └─ Upload path → pdfplumber (+ Qwen2.5-VL for complex tables/figures)
       - Layout-aware extraction for manual PDFs (broker notes, transcripts)
       - Qwen2.5-VL (multimodal) reads scanned tables / charts pdfplumber can't
       - Tables extracted as structured JSON separately
        |
        v
[Chunker]                                                          [Vaibhavi]
  - Section-aware (not fixed token windows)
  - MD&A: 512-token chunks, 50-token overlap
  - Risk Factors: one chunk per risk item
  - Financial tables: kept as single atomic chunks with metadata
  - Metadata per chunk: section_label, page_number, fiscal_period
        |
        v
[Embedder]                                                         [Sanyam]
  - text-embedding-3-small via OpenAI API
  - Batch embed: 100 chunks per API call
  - Store in chunks.embedding (pgvector column)
        |
        v
[PostgreSQL / pgvector]                                            [Sanyam]
  - Document metadata → documents table
  - Chunk text + embeddings → chunks table
  - IVFFlat index on embedding column
        |
        v
[Claim Graph Builder]                                              [Sanyam]
  - Extract claim atoms → claim_nodes (canonical_entity, metric, value, period)
  - Write SAME_METRIC / ALIAS_OF edges → claim_edges (GraphRAG layer)
```

---

# 6. GitHub Hygiene

This section is non-negotiable. A messy repo signals to reviewers that the team can't be trusted with a production codebase.

## Repository Structure

```
findocint/
├── backend/
│   ├── app/
│   │   ├── agents/          # LangGraph agents (retrieval, contradiction, risk, assembler)
│   │   ├── api/             # FastAPI routers (ingest, analyze, retrieve, eval)
│   │   ├── db/              # SQLAlchemy models + Alembic migrations
│   │   ├── eval/            # Eval harness: runner, metrics, judge, generator
│   │   ├── ingestion/       # EDGAR fetcher, pdfplumber parser, chunker
│   │   ├── schemas/         # Pydantic models (IntelligenceReport, Claim, etc.)
│   │   └── main.py
│   ├── tests/
│   │   ├── unit/            # Agent logic, metric calculations
│   │   └── integration/     # /analyze end-to-end, eval runner
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── dashboard/       # Eval runs table
│   │   ├── eval/leaderboard/
│   │   ├── report/[id]/     # Contradiction cards + citation viewer
│   │   └── upload/
│   ├── components/
│   └── Dockerfile
├── infra/
│   ├── docker-compose.yml
│   └── migrations/          # Alembic migration files (versioned)
├── .github/
│   └── workflows/
│       ├── eval.yml         # Eval harness on every push
│       └── deploy.yml       # Deploy on merge to main
├── .env.example             # ALL required env vars listed, no real values
├── .gitignore
└── README.md
```

## Branch Strategy

| Branch | Purpose | Merge Policy |
|---|---|---|
| `main` | Production-ready only. Deploys automatically. | PR required. Eval CI must pass. |
| `dev` | Integration branch. Both members merge feature branches here first. | PR required. No merge if tests fail. |
| `sanyam/feature-name` | Sanyam's feature branches | Merge to `dev` only |
| `vaibhavi/feature-name` | Vaibhavi's feature branches | Merge to `dev` only |

## Commit Message Convention

Format: `type(scope): short description`

```
feat(agents): add cross-period contradiction detection with LLM verification
fix(ingestion): handle missing section labels in EDGAR HTML filings
test(eval): add 20 adversarial test cases for liquidity risk signals
chore(ci): add regression alert to GitHub Actions eval workflow
docs(readme): add eval harness setup walkthrough
```

Types: `feat`, `fix`, `test`, `chore`, `docs`, `refactor`, `perf`

No vague commits. No `"fix stuff"`, `"wip"`, or `"asdfasdf"`. Every commit message should tell a reviewer exactly what changed and why.

## Pull Request Rules

- Every PR must have a description explaining **what** changed and **why**
- No PR merges to `dev` or `main` without at least one review from the other member
- PRs touching eval metrics must include before/after benchmark numbers in the description
- No secrets, API keys, or `.env` files ever committed — use `.env.example` with dummy values
- PR titles follow the same `type(scope): description` convention as commits

## `.gitignore` — Required Entries

```gitignore
# Environment
.env
.env.local
.env.*.local

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/

# Node
node_modules/
.next/
.vercel/

# Local data
*.pdf
data/
filings/

# IDE
.vscode/
.idea/
*.DS_Store

# Docker
*.log
```

Never commit raw PDF filings, embedding caches, or local database dumps.

## `.env.example` — Required Template

Every environment variable the project needs must be listed here with placeholder values and a comment explaining where to get the real value:

```env
# OpenAI
OPENAI_API_KEY=sk-...            # platform.openai.com/api-keys

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...     # console.anthropic.com

# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/findocint

# App
NEXT_PUBLIC_API_URL=http://localhost:8000
API_SECRET_KEY=your-api-key-here
```

## CI — GitHub Actions Workflows

**`eval.yml` — runs on every push to `dev` or `main`:**

```yaml
name: Eval Harness
on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run eval harness
        run: python backend/eval/runner.py --test-set-id latest
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      - name: Post score summary to PR
        if: github.event_name == 'pull_request'
        # Posts factuality + precision + calibration scores to PR comment
```

**Regression detection logic** (in `runner.py`):
```python
prev_run = db.query(EvalRun).order_by(EvalRun.run_at.desc()).offset(1).first()
if prev_run:
    if current_factuality < prev_run.factuality_score - 0.02:
        raise RegressionError(f"Factuality dropped: {prev_run.factuality_score:.2%} → {current_factuality:.2%}")
    if current_precision < prev_run.contradiction_precision - 0.02:
        raise RegressionError(f"Contradiction precision dropped")
```

## README Minimum Requirements

The README must let a new person run the full stack locally in under 15 minutes. Required sections:

1. **What it does** — 3 sentences, no hype
2. **Architecture diagram** — ASCII or image (show the two parsing paths + GraphRAG layer)
3. **Quickstart** — `git clone` → `cp .env.example .env` → fill vars → pull local Qwen via Ollama → `docker compose up`
4. **EDGAR ingestion walkthrough** — how to ingest AAPL 10-K for 2023 (HTML/XBRL path)
5. **Eval harness guide** — how to run the harness, what each metric means, why judge ≠ extractor
6. **Benchmark results table** — filled with measured values **and Wilson 95% CIs** from Week 4
7. **Error analysis** — failure buckets with the dominant cause called out
8. **Limitations** — the honest section from 4E, verbatim

---

# 7. Project Timeline — Week Overview

| Week | Sanyam | Vaibhavi | End-of-Week Gate |
|---|---|---|---|
| **1 — Foundation** | FastAPI + LangGraph scaffold; claim extraction agent (single doc); batch embedding pipeline | EDGAR ingestion + pdfplumber; section-aware chunker; all 9 DB migrations; Next.js upload UI | 3 filings ingested → chunked → embedded in pgvector. Single-doc claim extraction returns valid JSON. Upload UI live. |
| **2 — Core Engine** | Contradiction detection agent; `/retrieve` endpoint; full 4-agent LangGraph DAG; factuality + citation eval metrics | Risk signal extractor (5-category taxonomy); Pydantic IntelligenceReport schema; output assembler; eval dashboard + GitHub Actions CI | `/analyze` returns full IntelligenceReport with ≥1 contradiction and ≥3 risk signals. Eval harness runs factuality + citation metrics in CI on every push. |
| **3 — Eval Harness** | Adversarial test set generator (LLM-prompted, 200 cases, human reviewed); Brier score calibration metric; contradiction viewer UI + citation highlight | LLM-as-judge protocol; contradiction precision + recall; regression alert in CI; eval leaderboard UI; analyst report data collection (3 tickers) | 200 test cases in DB. All 7 metrics computed. Regression detection tested with intentional score drop. Both UI components render. |
| **4 — Benchmarks + Demo** | Final benchmark run (all metrics, 200-case set); precision vs. analyst reports (3 tickers); UI polish (confidence bars, streaming, risk cards) | Production deployment (FastAPI + Next.js + DB); README; demo video (3 min, rehearsed 2×) | All benchmark values measured. App publicly deployed. Demo recorded. Resume bullet drafted with real precision figure. |

### Critical Path

| Task | Depends On | Risk if Late |
|---|---|---|
| pgvector embedding pipeline live (W1 EOW) | Schema migrations, EDGAR ingestion | Blocks all retrieval — `/retrieve` and contradiction detection cannot run |
| Full LangGraph DAG wired (W2 EOW) | `/retrieve` endpoint live | Blocks `/analyze` — nothing to eval without output |
| 200 eval test cases seeded (W3 EOW) | Adversarial generator + Sanyam review | Harness metrics not statistically meaningful under 50 cases |
| Contradiction precision measured (W3 EOW) | Human-labelled ground truth | Cannot compute precision/recall without labels |
| Benchmark vs. analyst report (W4) | Analyst data collected by Vaibhavi in W3 | Headline resume metric is missing |
| LLM judge agreement rate (W3 EOW) | Human-labelled 50-case subset | Cannot validate judge reliability without agreement rate |

---

# 8. Day-by-Day Execution Plan

> Work days are Mon–Fri. Each day has a concrete deliverable, not a goal. If the deliverable isn't done, it carries over as Day 1 of the next day — no silent slippage.

---

## Week 1 — Foundation

### Sanyam

| Day | Deliverable |
|---|---|
| **Mon W1** | FastAPI project scaffolded. `docker-compose.yml` starts FastAPI + PostgreSQL in one command. `/health` endpoint returns 200. |
| **Tue W1** | `/ingest` endpoint accepts ticker + period, calls EDGAR fetch (stub ok), returns `document_id`. LangGraph installed and wired with a single no-op agent. |
| **Wed W1** | Claim extraction agent: given a single chunk, returns list of `Claim` objects `{claim, subject, predicate, object, period, confidence}` via structured LLM output. Tested on 3 hand-picked chunks. |
| **Thu W1** | Batch embedding pipeline: `text-embedding-3-small` called in batches of 100, embeddings written to `chunks.embedding`. IVFFlat index created post-load. |
| **Fri W1** | 20 manual eval test cases written and stored in `eval_test_cases`. Integration test: ingest AAPL Q2 filing → chunk → embed → query returns non-empty chunks. EOW checkpoint passed. |

### Vaibhavi

| Day | Deliverable |
|---|---|
| **Mon W1** | All 9 PostgreSQL tables created via Alembic migrations. IVFFlat index on `chunks.embedding`. Local DB seeds with 1 test document without errors. |
| **Tue W1** | SEC EDGAR REST API fetch working: pulls 10-K and 10-Q by ticker + form type + period. AAPL, GS, BLK 10-Ks fetched and raw text stored. |
| **Wed W1** | pdfplumber parser extracts text with section labels preserved (MD&A, Risk Factors, Financial Statements). Tables extracted as structured JSON separately. |
| **Thu W1** | Section-aware chunker live: MD&A at 512 tokens/50 overlap, Risk Factors at natural boundaries, tables as atomic chunks. Metadata (section_label, page_number, fiscal_period) per chunk confirmed in DB. |
| **Fri W1** | Next.js 14 project initialized. Document upload page renders. File sent to FastAPI `/ingest`. Ingestion status indicator shown in UI. EOW checkpoint passed. |

---

## Week 2 — Core Engine

### Sanyam

| Day | Deliverable |
|---|---|
| **Mon W2** | `POST /retrieve`: accepts `{query, ticker, fiscal_period, top_k}`. Returns top-k chunks by cosine similarity with scores. Response time <500ms on 10k chunks verified. |
| **Tue W2** | Contradiction detection: cross-document claim alignment by `(subject, predicate)`. Semantic diff computes cosine similarity on aligned pairs. Outputs `Contradiction` candidates. |
| **Wed W2** | LLM verification step added to contradiction agent. Claude called with structured prompt. Returns `{verdict, severity, explanation}` as JSON. Tested on AAPL Q2 vs Q3 — at least 1 real contradiction found. |
| **Thu W2** | Full LangGraph DAG wired: Retrieval → Contradiction → RiskSignal → Assembler. `/analyze` called with 2-document input returns complete `IntelligenceReport` JSON. |
| **Fri W2** | `eval_runner.py`: computes `factuality_score` and `citation_accuracy` against 20-case test set. Results stored in `eval_runs`. Runs in <5 minutes. EOW checkpoint passed. |

### Vaibhavi

| Day | Deliverable |
|---|---|
| **Mon W2** | Risk signal extractor: LangGraph agent maps chunks to 5-category taxonomy via Pydantic Enum. Tested on 5 EDGAR chunks, returns `RiskSignal` objects with confidence. No free-form categories in output. |
| **Tue W2** | Pydantic schema complete: `IntelligenceReport`, `Claim`, `Contradiction`, `RiskSignal`. Confidence scores constrained to 0.0–1.0. Schema rejection tested on deliberately invalid output. |
| **Wed W2** | Structured output assembler: compiles all agent outputs into `IntelligenceReport`. `overall_confidence` = weighted mean of per-claim scores. Pydantic validation runs before returning. |
| **Thu W2** | GitHub Actions CI: workflow triggers on push to `dev`. Runs eval harness. Posts factuality + citation score summary to PR comment. Failing harness fails the PR. |
| **Fri W2** | Next.js `/eval` dashboard: renders table of all `eval_runs` (model_version, run_at, factuality_score, citation_accuracy). Data fetched from FastAPI. EOW checkpoint passed. |

---

## Week 3 — Eval Harness

### Sanyam

| Day | Deliverable |
|---|---|
| **Mon W3** | Adversarial test set generator: Claude prompted with real filing chunks, produces plausible-but-false claims and genuine contradiction pairs. Generator script outputs valid `eval_test_cases` rows. |
| **Tue W3** | Sanyam reviews all generated test cases — accept/reject each one. 100 cases confirmed in DB by EOD. `adversarial=true` flag set on all generated cases. |
| **Wed W3** | Remaining 100 test cases reviewed and stored. 200 total in DB. Brier score calibration metric implemented in eval runner. Target <0.15 on current model. |
| **Thu W3** | Next.js `/report/[id]` page: contradiction pairs as side-by-side cards. LEFT: Claim A + period + citation. RIGHT: Claim B + period + citation. Severity badge (HIGH/MEDIUM/LOW). |
| **Fri W3** | Citation highlight in report viewer: source chunk text rendered with cited sentences highlighted. Clicking a claim scrolls to the citation panel. EOW checkpoint passed. |

### Vaibhavi

| Day | Deliverable |
|---|---|
| **Mon W3** | LLM-as-judge prompt implemented. Claude scores each claim as SUPPORTED/UNSUPPORTED/PARTIAL with reasoning. Results stored in `eval_results.llm_judge_score`. |
| **Tue W3** | 50-case human-labelled subset used to measure judge agreement rate. Agreement rate stored in `eval_runs`. Target >80%. |
| **Wed W3** | Contradiction precision and recall computed against human-labelled contradiction test cases. Both metrics stored in `eval_runs`. |
| **Thu W3** | Regression alert in GitHub Actions: workflow fails and posts PR warning if `factuality_score` or `contradiction_precision` drops >2% vs previous run. Tested with intentional score drop — alert fires correctly. |
| **Fri W3** | Next.js `/eval/leaderboard`: `eval_runs` grouped by `model_version`, bar chart of factuality score per version. Regression runs highlighted in red. Analyst report data (AAPL, GS, BLK — 2 reports each) collected and risk signals manually labelled. EOW checkpoint passed. |

---

## Week 4 — Benchmarks, Deployment, Demo

### Sanyam

| Day | Deliverable |
|---|---|
| **Mon W4** | Final benchmark run on full 200-case test set with production model version. All 7 metric columns in benchmark table filled with measured values. No blanks. |
| **Tue W4** | Precision and recall of detected risk signals vs. analyst report ground truth computed for all 3 tickers. Headline precision figure confirmed and ready for resume bullet. |
| **Wed W4** | Next.js UI polish: risk signal cards grouped by taxonomy category. Confidence bars: green >0.85, amber 0.65–0.85, red <0.65. Streaming loader for `/analyze` response. |
| **Thu W4** | End-to-end integration test: EDGAR ingest → `/analyze` → eval run → regression check. All green. Benchmark table verified — no estimated values. |
| **Fri W4** | Resume bullet drafted with measured precision figure. Repo audit: clean commit history, no secrets, `.env.example` accurate. Final submission checklist signed off. |

### Vaibhavi

| Day | Deliverable |
|---|---|
| **Mon W4** | FastAPI deployed on Railway/Fly.io. PostgreSQL provisioned on Supabase. Environment variables configured. FastAPI `/health` returns 200 on public URL. |
| **Tue W4** | Next.js deployed on Vercel, connected to production FastAPI. Full end-to-end flow tested on public deployment: ingest → analyze → report renders. |
| **Wed W4** | README written: setup, architecture diagram, EDGAR ingestion walkthrough, eval harness guide, benchmark results table (filled). |
| **Thu W4** | Demo video: 3-minute screen recording covering document ingest → `/analyze` call → contradiction detected → risk signals → eval dashboard. Rehearsed twice before recording. |
| **Fri W4** | Final integration test with Sanyam. All systems green on production URL. Submission checklist signed off. |

---

# 9. API Contract

| Endpoint | Method | Auth | Description | Owner |
|---|---|---|---|---|
| `/ingest` | POST | API key | Accepts ticker + filing_type + period. Fetches from EDGAR, parses, chunks, embeds, stores. Returns `document_id`. | Sanyam |
| `/ingest/upload` | POST | API key | Accepts PDF file upload. Same pipeline as `/ingest`. | Sanyam |
| `/analyze` | POST | API key | Accepts `{document_ids: [], query_config: {}}`. Runs full LangGraph DAG. Returns `IntelligenceReport` JSON. | Sanyam |
| `/retrieve` | POST | API key | Accepts `{query, ticker, fiscal_period, top_k}`. Returns matching chunks with cosine scores. | Sanyam |
| `/reports/{id}` | GET | API key | Returns stored `IntelligenceReport` by ID. | Vaibhavi |
| `/eval/run` | POST | API key | Triggers eval harness on `test_set_id` + `model_version`. Returns `eval_run_id`. | Vaibhavi |
| `/eval/runs` | GET | API key | Lists all `eval_runs` with metrics. Supports `?model_version=` filter. | Vaibhavi |
| `/eval/runs/{id}/results` | GET | API key | Returns per-test-case results for an eval run. | Vaibhavi |
| `/eval/test-cases` | GET | API key | Lists eval test cases. Supports `?adversarial=true` filter. | Sanyam |

---

# 10. Benchmark Table

All values from actual eval runs in Week 4. No estimated values anywhere.

| Metric | Target | Measured | 95% CI |
|---|---|---|---|
| **Factuality Score (200-case test set)** | >80% | ___% | ___ |
| **Citation Accuracy** | >85% | ___% | ___ |
| **Contradiction Precision (FACTUAL, taxonomy-aware)** | >75% | ___% | ___ |
| **Explained-Change Discrimination** | >80% | ___% | ___ |
| **Contradiction Recall (incl. 8-K restatements)** | >60% | ___% | ___ |
| **Calibration Brier Score** | <0.15 | ___ | — |
| **Judge–Human Agreement (per judge)** | >80% | ___% | ___ |
| **Inter-Judge Agreement (Cohen's κ)** | >0.6 | ___ | — |
| **Recall vs. 8-K Restatement Ground Truth** | >70% | ___% | ___ |
| **Cost per /analyze call (2 docs, local Qwen)** | ~\$0 | \$___ | — |
| **Cost per full eval run (200 cases)** | <\$10 | \$___ | — |
| **Regression Detection Latency (CI)** | <5 min | ___min | — |
| **/analyze P50 latency (2 documents)** | <30s | ___s | — |
| **/analyze P95 latency (2 documents)** | <60s | ___s | — |
| **Contradiction-agent P50 latency** | <12s | ___s | — |
| **pgvector retrieval P50 (10k chunks)** | <500ms | ___ms | — |
| **Eval harness full run time (200 cases)** | <30 min | ___min | — |
| **Adversarial test set size** | 200 cases | ___ | — |

---

# 11. Build Priority

## Tier 0 — Must Ship

| Item | Owner | Week |
|---|---|---|
| SEC EDGAR ingestion + section-aware chunker | Vaibhavi | 1 |
| Batch embedding pipeline (OpenAI → pgvector) | Sanyam | 1 |
| Single-document claim extraction agent + Pydantic schema | Sanyam + Vaibhavi | 1–2 |
| pgvector retrieval endpoint (`/retrieve`) | Sanyam | 2 |
| Contradiction classifier — 3-way taxonomy (factual / explained-change / restatement) | Sanyam | 2 |
| Claim graph + entity resolution (GraphRAG retrieval) | Sanyam | 2 |
| Risk signal extractor (5-category taxonomy) | Vaibhavi | 2 |
| Structured output assembler (IntelligenceReport) | Vaibhavi | 2 |
| Full LangGraph DAG end-to-end | Sanyam | 2 |
| Eval runner (factuality + citation metrics) | Sanyam | 2 |
| Cross-model dual LLM-as-judge + κ agreement (extractor ≠ judge) | Vaibhavi | 3 |
| 200-case adversarial test set (incl. EXPLAINED_CHANGE hard negatives, human reviewed) | Sanyam | 3 |
| Contradiction precision + recall metrics (taxonomy-aware) | Vaibhavi | 3 |
| Wilson confidence intervals on all proportion metrics | Sanyam | 3 |
| Calibration metric (Brier score, per-category) | Sanyam | 3 |
| Regression detection in GitHub Actions | Vaibhavi | 3 |
| Contradiction viewer UI (typed evidence path from claim graph) | Sanyam | 3 |
| Eval leaderboard UI | Vaibhavi | 3 |
| Benchmark vs. 8-K restatements (gold contradictions) | Both | 3–4 |
| Error-analysis bucketing + per-category calibration | Both | 4 |
| Cost & latency per pipeline stage | Vaibhavi | 4 |
| All benchmark metrics measured with CIs (no estimates) | Both | 4 |
| Production deployment | Vaibhavi | 4 |
| UI polish (confidence bars, streaming, risk cards) | Sanyam | 4 |

## Tier 1 — Ship if Tier 0 Done by W3 EOW

- Model head-to-head on same test set — public leaderboard (local Qwen vs. Llama vs. hosted), reframing the eval harness as a transferable, model-agnostic skill rather than tied to one vendor
- Financial table extraction as structured JSON (balance sheets, income statements) with separate eval metrics
- Multi-ticker cross-company contradiction detection via the claim graph (GS bullish on sector, BLK bearish same quarter) — a cross-issuer query plain vector RAG cannot express
- Local Qwen vs. hosted model head-to-head on the same test set — quantifies the local-model quality/cost trade-off
- Confidence calibration plot (reliability diagram) in eval dashboard
- Streaming output in Next.js UI — show claims as they are generated

## Tier 2 — Roadmap

- Fine-tuned embedding model on financial terminology (SEC EDGAR vocabulary)
- Temporal trend analysis: risk signal frequency per category across 4 quarters
- Webhook: POST structured report to Slack when new filing detected for watched ticker
- Export to structured Excel: one row per claim with confidence + citation columns

---

# 12. Submission Checklist

| | Item | Owner |
|---|---|---|
| ☐ | All Tier 0 items functional (manually tested) | Both |
| ☐ | `/analyze` returns valid IntelligenceReport JSON for 3 benchmark tickers | Sanyam |
| ☐ | Contradiction detection tested on AAPL Q2 vs Q3 — ≥1 genuine contradiction found | Sanyam |
| ☐ | Risk signals cover all 5 taxonomy categories across benchmark filings | Vaibhavi |
| ☐ | 200 eval test cases in DB (human-reviewed) | Sanyam |
| ☐ | LLM-as-judge agreement rate measured against human labels | Vaibhavi |
| ☐ | Regression detection fires correctly (tested with intentional score drop) | Vaibhavi |
| ☐ | Calibration Brier score measured on full test set | Sanyam |
| ☐ | Benchmark table fully populated — zero estimated values | Both |
| ☐ | Contradiction viewer renders side-by-side cards with citations | Sanyam |
| ☐ | Eval leaderboard shows model version comparison with regression highlighting | Vaibhavi |
| ☐ | App deployed publicly (FastAPI + Next.js + DB) | Vaibhavi |
| ☐ | UI polish complete (confidence bars, risk cards, streaming loader) | Sanyam |
| ☐ | README covers setup, architecture, eval harness guide, and benchmark results | Vaibhavi |
| ☐ | Demo rehearsed ≥2× without errors | Both |
| ☐ | Resume bullet drafted with measured precision figure | Both |
| ☐ | Repo clean: no secrets committed, `.gitignore` correct, `.env.example` accurate | Both |
| ☐ | All commits follow `type(scope): description` convention | Both |
| ☐ | No branch merged to `main` without review from the other member | Both |

---

# 13. Resume Bullet (Fill After Week 4)

> **Sanyam:** "Built a financial document intelligence engine over SEC 10-K/10-Q filings with a LangGraph + GraphRAG agent DAG that distinguishes genuine cross-period contradictions from legitimate business changes via a three-way taxonomy (factual / explained-change / restatement) — running on local Qwen models, evaluated with a custom LLM eval harness (factuality, Brier calibration, cross-model dual LLM-as-judge) achieving **\_\_\_% precision (95% CI \_\_–\_\_%)** at separating real contradictions from explained changes, benchmarked against companies' own 8-K restatements as authoritative ground truth."

> **Vaibhavi:** "Designed and deployed the dual-path ingestion pipeline (EDGAR HTML/XBRL + PDF), cross-model LLM eval harness, and CI regression detection for a financial document intelligence engine — processing SEC filings into pgvector + claim-graph indexes, running factuality, calibration, and cost/latency metrics (with Wilson confidence intervals) on every commit over local Qwen models, and benchmarking against 8-K restatements with **\_\_\_% citation accuracy (95% CI \_\_–\_\_%)**."

Fill the blanks with measured values from the benchmark table.

---

*Internal document — not for distribution.*
*v2.1 — Contradiction taxonomy (factual / explained-change / restatement), GraphRAG claim graph, local-first Qwen stack (incl. Qwen2.5-VL multimodal parsing), cross-model dual judge, 8-K restatement ground truth, Wilson confidence intervals, plus error-analysis, limitations, and cost/latency sections.*
