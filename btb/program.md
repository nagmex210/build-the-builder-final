# Build the Builder: research program (workers + merger)

You are part of a team of Claude agents improving a **builder**: a program that reads a bank's brief and creates a
phone agent (a Freya workflow) for debt-collection calls. Read `README.md` (the kit) and `docs/` first.

```
layer 1  you (Claude Code, Opus 5.5)  ── improve ──▶  layer 2  builder/  (what we submit)
                                                        └─ builds ──▶ layer 3  phone agent on Freya (what is scored)
```

## The competition (facts from the kit; read README.md for all of them)

- Score = share of 60 hidden cases passed (2 hidden briefs × 30 customers, 1-3 products, several calendar days).
  Each case runs 3 times and must pass all 3. Pass = bank ledger right AND conversation inside the brief AND honest.
- **Hidden briefs open Sun 11 Oct 17:00 UTC; submit by 20:00 UTC.** One is a clean spec, the other is raw bank
  material (a mail, a policy extract, a memo that changes it, a code list). Each comes with its own tool API file:
  the seven tool names stay, fields and allowed values can change. Other identity questions, limits, deadlines,
  outcome table, calendar.
- Customers talk like people: numbers in two parts, corrections, small talk, questions back, amounts/dates in words.
- One builder run: one command, briefs (+ the tool API file) in, phone agent out, **at most 30 minutes** including
  any self-test, with a trace (start/end, every model call with model + one-line purpose, what it created, tests).
- The phone agent runs on Freya's fixed model (`freya.AGENT_LLM`). Never change it. The builder may use any model.
- Tie-breaks: total promised amount on passed cases, then shorter build time.

## The one rule that decides this run: GENERALISE

The builder will meet briefs it has never seen. Never write a rule, value, name, date, holiday or outcome code from
brief A or B into the builder's code or prompts. Everything specific must be *read from the brief at build time*.
Improvements must be about *how the builder reads and compiles any brief*: extraction, structure, code steps for
date/amount math, verification, self-testing. If an idea only helps because it knows brief A, it is cheating and
will score zero on Sunday. The merger rejects such changes.

## Layout

- `builder/` — THE BUILDER. Entry point: `python3 builder/build.py --slot <name> --tools <openapi.json> <brief.md>...`
  It must print `{"workflow_id": ..., "agent_id": ...}` on its last line and write the trace to
  `runs/traces/<slot>-<timestamp>.txt`. (If `builder/` does not exist yet, the first merger creates it from
  `examples/agent_builder.py` + `.claude/skills/build-phone-agent/`.)
- `btb/fast_eval.py <workflow_id> --brief A [--reps 2] [--style random]` — fast parallel eval (minutes): our own
  simulated customers through the chat endpoint, the kit's ledger scorer, our own judge. No queue.
- `tools/run_cases.py <agent_id> --brief A --reps 3` — the OFFICIAL scorer (Freya's simulator + judge). One
  simulation at a time per workspace, 3-11 min per run. **Only the merger runs it.**
- `btb/briefs_raw/` — held-out generalisation briefs: brief A/B rewritten as messy bank material (mails, memo
  overrides, code lists) with the SAME rules, so the same public cases score them. Never tune on their wording.
- `btb/llm.py` — Azure OpenAI models with fallback (`tier="strong"`: gpt-6-astra → gpt-6-luna → gpt-4.1-mini;
  `tier="fast"`: gpt-4.1-mini first). Logs every call to `$BTB_TRACE`. The builder may use these, or the Claude
  Agent SDK (Opus 5.5). Prefer Azure for heavy or repeated builder calls: the Claude subscription is shared by
  six agents.
- `results.tsv` (merger only), `journal.md`, `runs/<batch>/w<N>.md` (worker reports).

## Score of a builder version (the number we optimise)

`score = fast_eval passes on A (10 cases) + B (3 cases) + raw-A + raw-B, --reps 2 --style random`
(= cases that passed both reps, out of 26). The merger confirms with the official scorer on A and B.

## WORKER (you were started in a git worktree `wt<N>` on branch `idea/<batch>-<N>`)

1. Read: this file, `btb/ideas.md` (idea bank), `journal.md` (what was tried; do not repeat a discard unless the mechanism changes),
   the last batch's reports, `builder/`.
2. Your idea family is given in your prompt. Pick ONE concrete idea in it, the one you believe moves the score most.
3. Implement it in `builder/`. Commit.
4. Build with your own slot (never another worker's): `python3 builder/build.py --slot w<N>-A --tools tools/openapi.json briefs/brief-a.md`,
   `--slot w<N>-B ... briefs/brief-a.md briefs/brief-b.md`, and the raw variants (`w<N>-rA`, `w<N>-rB`).
   Builds of different slots can run in parallel (background them, then wait for all).
5. Score each with `btb/fast_eval.py` as defined above. Compare with the champion's score in `results.tsv`.
6. Read failing transcripts (`freya.get_call(call_id)["messages"]`) and fix within your idea. At most 2 iterations.
7. Write `runs/<batch>/w<N>.md`: idea, what changed (files), score per brief vs champion, build time, failures left,
   and whether the change is brief-agnostic (say why). Commit everything on your branch. Then stop.
- Hard limit: 75 minutes wall time. Never run `tools/run_cases.py`. Never touch `main`.

## MERGER (you run in the main repo after each batch)

1. Read the five reports and their diffs (`git diff main idea/<batch>-<N>`).
2. Reject any change that hard-codes something from brief A/B (rule, value, name, date, outcome code). Say so in the journal.
3. Combine the winners: start from the best-scoring branch, merge others whose ideas are independent and also
   improved. Resolve conflicts by hand. Re-run the builder + fast_eval on the merged result.
4. If the merged fast score beats the champion by ≥ 1 case (or ties with clearly shorter build time): run the
   official scorer on both briefs AT THE SAME TIME, one per Freya workspace (one simulation at a time per workspace):
   `python3 tools/run_cases.py <main-A agent_id> --brief A --reps 2 > runs/<batch>/official-A.txt &`
   `python3 btb/official_ws2.py main-B --brief B --reps 2 > runs/<batch>/official-B.txt &` then `wait`.
   (`official_ws2.py` copies the slot's workflow into our second workspace and scores it there.)
   Keep (commit to `main`, push) only if official A+B passes do not drop vs the champion.
5. Append a row to `results.tsv`: `batch	commit	fast_A	fast_B	fast_rawA	fast_rawB	official_A	official_B	build_s	status	description`.
6. Journal entry: what each worker tried, measured numbers, what was kept and why, hypotheses (marked) for next batch.
7. Assign the next batch's five idea families in `runs/next_families.txt` (one per line), covering different parts:
   brief extraction/normalisation, workflow structure/routing, code steps for dates/amounts/business days,
   prompt wording per node, tool-call robustness/honesty, multi-product handling, conversation robustness to the
   customer styles, the builder's own self-test within 30 min, speed of the build. At most 2 families in a row on
   the same part.

## Freeze

At **Sun 11 Oct 16:30 UTC** stop all work. `main` is the submission builder. Write `FINAL.md`: how to run it,
champion scores, known weaknesses.

## Builder login

If the builder's Claude is not logged in inside your shell: `export CLAUDE_CODE_OAUTH_TOKEN=$(aws ssm get-parameter --region eu-central-1 --name /video-iq/claude_token --with-decryption --query Parameter.Value --output text)`.
