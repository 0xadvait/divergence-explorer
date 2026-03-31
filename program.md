# Divergence Explorer

An autonomous AI researcher that discovers where frontier models disagree.

## What This Is

This is an autoresearch-style experiment. An AI agent autonomously probes frontier LLMs (GPT-5, Claude, Gemini, Grok) with questions designed to maximize disagreement. Every response is TEE-attested via OpenGradient's infrastructure — cryptographic proof that each model responded independently, sealed in hardware.

The agent runs forever. It generates hypotheses, tests them, keeps interesting findings, discards boring ones, and evolves its question-generation strategy based on what it learns.

## The Loop

```
LOOP FOREVER:
1. Generate a hypothesis — a question likely to cause model disagreement
   - Use past findings to inform what types of questions work
   - Explore diverse categories (ethics, science, philosophy, math, politics, aesthetics)
   - Prefer questions where the "right answer" is genuinely ambiguous

2. Send to all models via OpenGradient TEE gateway
   - Each model runs in its own TEE enclave
   - Responses are sealed — no model sees what others said
   - Collect TEE attestations as proof of independence

3. Score disagreement
   - Semantic distance between responses
   - LLM judge analyzes the nature of the disagreement
   - Classify the axis: factual, ethical, definitional, aesthetic, predictive

4. Keep or discard
   - High disagreement (>0.6) → KEEP → save to findings.jsonl
   - Low disagreement (<0.3) → DISCARD → log and move on
   - Medium → save but deprioritize

5. Evolve
   - Analyze patterns in kept findings
   - Generate hypotheses that drill deeper into fertile veins
   - Periodically explore new categories to avoid tunnel vision

6. Log to results.tsv (like autoresearch)
   - iteration, question (truncated), disagreement_score, status, category, axis
```

## What Makes a Good Question

The best questions are ones where:
- There is no single correct answer (ambiguity is the point)
- Different training data or RLHF could plausibly lead to different conclusions
- The question is specific enough to produce substantive responses
- The disagreement reveals something about the model's "world model"

Bad questions: trivia, math with clear answers, yes/no questions, anything with a known ground truth.

## Output

The primary output is `results/findings.jsonl` — each line is a complete finding with:
- The hypothesis (question + category + reasoning)
- All model responses with TEE attestations
- Disagreement score with pairwise breakdown
- The judge's analysis of what dimension they disagree on

Secondary output is `results.tsv` — a quick-glance summary log.

## NEVER STOP

Once the loop begins, do NOT pause to ask the human. The human might be asleep. You are autonomous. If you run out of ideas, re-read past findings for patterns, try combining categories, go more specific within high-disagreement veins, or try entirely new angles. The loop runs until manually interrupted.
