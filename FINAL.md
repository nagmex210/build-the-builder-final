# FINAL: Sunday 11 Oct submission checklist

Window: briefs open **17:00 UTC** (20:00 UTC+3), submit by **20:00 UTC** (23:00 UTC+3).
Rehearsed on Sat 10 Oct: `runs/submit_rehearsal.md`.

## Champion and known weaknesses

(The merger fills this in at the freeze: champion commit, official scores on A/B/raw A/raw B/C, known weaknesses.)

## 16:30 UTC — freeze

- [ ] All workers and the merger stop. `main` is the submission builder. No more merges.
- [ ] `git -C /home/ubuntu/btb/repo log -1` — note the commit hash: this is "the code" we submit.
- [ ] `python3 builder/build.py --help` and `python3 -m py_compile builder/*.py btb/*.py` pass on main.
- [ ] **Remove the "Builder login" section (the SSM line with the Claude token) from `btb/program.md`** and commit
      that (it must not be in the submitted code). Do not remove it before the freeze: workers need it.
- [ ] Check nothing secret is committed: `git grep -nE 'fak_|sk-|eyJ[A-Za-z0-9_-]{10,}\.'` returns nothing relevant.
- [ ] Workspace has room: fewer than ~195 workflows (each new slot name creates one workflow).
- [ ] Keys present in the shell or in Parameter Store (`/btb/freya_api_key`, `/btb/bank_team_key`, `/btb/azure_key`,
      `/video-iq/claude_token`); `btb/submit.sh` fetches missing ones itself.
- [ ] Claude subscription: no other agent running (the builder's Claude would compete for the rate limit).

## 17:00 UTC — get the briefs

- [ ] Download both final briefs and their tool API files into `briefs/final/` (e.g. `final-1.md`, `final-1.json`,
      `final-2.md`, `final-2.json`). Do not open them in any agent that can edit `builder/`.
- [ ] If a brief comes as several files (mail, memo, code list), pass them all: build.py takes several briefs
      (`--slot`, see below); submit.sh takes one, so concatenate them into one `.md` in the given order first.

## ~17:05 UTC — run both builds in parallel, no manual step

```bash
cd /home/ubuntu/btb/repo
bash btb/submit.sh briefs/final/final-1.md briefs/final/final-1.json final-1 &
bash btb/submit.sh briefs/final/final-2.md briefs/final/final-2.json final-2 &
wait
```

(Run inside tmux/nohup: each build takes ~22-26 min.) Each run writes:

| What | Where |
|---|---|
| printed build log = **the trace we submit** (start/end, every model call, Freya ids, tests) | `traces/<name>.log` |
| detailed machine trace | `runs/traces/<name>-<time>.jsonl` |
| **the phone agent file we submit** (`freya.export_workflow`) | `submission/<name>.workflow.json` |

The last block of each log is the summary: workflow_id, agent_id, export path, trace paths, builder commit, build
seconds and "under 30 min: yes/no". submit.sh exits non-zero if the build failed, the export does not load, or a
key is still in the log.

## Verify (~17:35 UTC)

- [ ] Both summaries: exit code 0, export loads with nodes, under 30 min: yes.
- [ ] `python3 -c "import json;d=json.load(open('submission/final-1.workflow.json'));print(d['workflow_id'],len(d['workflow']['nodes']))"`
- [ ] No key in the files: `python3 btb/scrub.py traces/*.log runs/traces/final-*.jsonl` prints 0 (it scrubs in place
      if not).
- [ ] Optional sanity, not tuning: one chat turn on each workflow returns no 500
      (`freya.api('POST','/api/v2/chat/message', ...)` as in the skill). Do not change anything because of how it talks.
- [ ] Submit: the two `submission/*.workflow.json`, the code (commit hash / repo, see open question), the two
      `traces/*.log` (and the `.jsonl` traces if they accept more than one file per brief).

## What may be fixed after 17:00 UTC

- Allowed: a **crash** of the builder on the new input (a parser that dies on an unexpected table, a missing field,
  a timeout). Fix it generically, commit it with a message saying what crashed, log it below, and rerun the build
  (the rerun reuses the same slot, so it updates the same workflow). Submit the rerun's trace.
- Not allowed: anything from a final brief in code or prompts (no rule, value, name, date, holiday, outcome code),
  no tuning to how the agent handles the new briefs, no hand edit of a phone agent after it is created.
- If both runs are fine: change nothing. A rerun only if a run failed or went over 30 min.

Post-17:00 change log (time UTC, commit, what crashed, fix):

-

## After the submission

- [ ] Rotate every key that was on the box: Freya workspace API key(s) (`FREYA_API_KEY`, `FREYA_API_KEY_2`), the
      Azure key, the bank team key, the Claude OAuth token (log out / revoke), and update Parameter Store.
- [ ] Stop the brief C mock bank and tunnel (`tmux kill-session -t bankc; tmux kill-session -t tunnelc`).

## Open question for the organisers

The rules say we submit "the phone agents it created, your code and the builder's trace", and the form asks for
**one commit**. Does that mean a commit hash on our repo (the frozen `main`, e.g. a tag `final`) or one single squashed
commit containing the whole builder? Until answered: tag the freeze commit (`git tag final <hash>`), and be ready
to produce a squashed single-commit branch (`git checkout --orphan submission && git commit -m "builder"`) without
`runs/`, `out/` and anything key-related.
