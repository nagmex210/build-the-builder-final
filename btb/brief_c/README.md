# Brief C: held-out test brief with its own mock bank

**HELD-OUT. Merger-only check.** Workers must not read, tune on, or build against brief C. Nothing from it (rules,
values, names, codes, holidays, sentences, field names) may go into `builder/`. It exists to measure how the builder
does on a brief it was never tuned on, the way the hidden briefs will be. If the builder is ever tuned on C, C stops
measuring anything: write a new brief D instead.

## Files

| File | What |
|---|---|
| `brief-c.md` | The clean spec (52 rules). |
| `brief-c-raw.md` | The same rules as raw bank material: a mail, a policy extract (with two OLD values), a memo overriding them (personal loan 21 -> 14 days, call limit 2,500 -> 2,000), a code sheet. |
| `openapi-c.json` | The tool API for C: the same seven tool names, changed fields and values. `servers` is rewritten by `start.sh`. |
| `mock_bank.py` | The mock bank (standard library only): the seven tools under `/v1`, `POST /v1/practice/sessions`, `GET /v1/practice/ledger/<customer_id>` (both need `x-team-key`, 16+ chars), failure injection (`faults: fail_first_n`), `ok:false` + `error`/`hint` on bad input. State persists in `.state.json`. |
| `cases-c.json` | 12 cases in the format of `public-test-set.json` (`brief: "C"`). |
| `score_c.py` | Ledger scorer: `tools/score.py` plus instalment numbers of a two-part plan and no calls after `close_call`. |
| `check_cases.py` | Recomputes deadlines, floors, plan halves, the call limit and callback windows for every expected ledger. Run it after editing a case. |
| `smoke.py` | Calls every tool through the public URL (incl. errors and failure injection) and scores five scripted calls. |
| `start.sh` | (Re)starts the mock (tmux `bankc`, port 8787) and a Cloudflare quick tunnel (tmux `tunnelc`), writes the URL to `BANK_URL` and `openapi-c.json`. |

## Run it

```bash
bash btb/brief_c/start.sh                  # prints the public URL; a quick tunnel gets a NEW URL on every restart
python3 btb/brief_c/smoke.py               # SMOKE OK
python3 btb/brief_c/check_cases.py         # violations in 0 case(s)

# build (after start.sh, so the tool URLs in openapi-c.json are live)
python3 builder/build.py --slot c-test --tools btb/brief_c/openapi-c.json btb/brief_c/brief-c.md
python3 builder/build.py --slot c-raw  --tools btb/brief_c/openapi-c.json btb/brief_c/brief-c-raw.md

# score (fast_eval picks up score_c.py because it sits next to the cases file)
python3 btb/fast_eval.py <workflow_id> --cases btb/brief_c/cases-c.json --bank $(cat btb/brief_c/BANK_URL) --reps 1
```

The tunnel URL is baked into the built workflow's tool calls. If the tunnel restarts, the URL changes and an agent
built before it calls a dead host: rebuild after `start.sh`. The official scorer also works on C (merger only, it uses the workspace's one simulation
slot): `FREYA_BANK_HOST=$(cat btb/brief_c/BANK_URL) python3 tools/run_cases.py <agent_id> --cases btb/brief_c/cases-c.json --brief C`
(it uses the kit's ledger scorer, which ignores `instalment_no`).

## How C differs from A and B

| Area | A / B | C |
|---|---|---|
| Call variables | `title`, `now` | no title (first + last name), `call_time` |
| Opening | "digital assistant from Freya Bank", "call is recorded" | fixed sentence naming **FB Services**; "Freya Bank" may not be said before verification |
| Identity | date of birth (YYYY-MM-DD) + phone last 4; 3 wrong total; hint `day_month_swapped` | **postcode** (`4021 KL`) + **month of birth** (`07`); **2** wrong total; hint `letters_missing` |
| Tool fields | `field`/`answer`, `products`/`product_id`, `past_due`, `days_late`, `date`, `time`, `outcome`/`reason` | `check`/`value`, `accounts`/`account_ref` (A1..), `arrears`, `days_overdue`, `kind`, `pay_date`, `instalment_no`, `slot`, `result`/`code`, `note_code` |
| Products | credit card, personal loan, car loan | credit card, personal loan, **overdraft** (floor = half the arrears rounded up) |
| Calendar | Mon-Fri, US-style holidays | **Sun-Thu** working week (Fri+Sat weekend), other holidays |
| Deadline | N-th business day by days-late band | **calendar days by product kind**, 7 days if arrears >= 1,000, moved **back** to a business day |
| Today | allowed | only before **15:00** |
| "next <weekday>" | following calendar week | **first such weekday after today** |
| Callbacks | today / next business day, 10:00-19:00 | today / next **two** business days, 09:00-17:30, >= 1 h after now, **half-hour slots, rounded up** |
| Persuasion | attempts by days-late band | attempts by **arrears size** (<500: 1, >=500: 2) |
| New rule kinds | - | **two-part plan** (equal halves, odd cent to part 1, part 2 window), **call limit** 2,000 total, **breathing space** (hardship -> `paused`), **fraud** transfer, notes on single-product calls, **severity order** for the `no_payment` code |
| Recording | B: one read-back for all, then record | read back and **record per account** before the next |
| Mandatory sentences | text-message sentence, "sorry for your loss" | e-mail sentence (once), "Please accept our condolences.", "I am sorry to hear that.", "Thank you for your time. Goodbye." |
| Human request | ask once if you can help | transfer straight away |

## Cases

| id | family | what it tests | expected |
|---|---|---|---|
| C-01 | happy | Sunday is a business day, today before 15:00 | arranged, A1 380 on 11-01 |
| C-02 | third party | no bank name, Friday refused (weekend), 09:15 -> 09:30 | no_contact/CALLBACK, 11-08 09:30 |
| C-03 | identity | digits-only postcode (hint), one wrong month, "next Wednesday" on Monday | arranged, A1 640 on 11-11 |
| C-04 | identity | two wrong answers across both questions | id_failed/FAILED |
| C-05 | amounts | overdraft: plan refused, floor 194, Friday -> Sunday | arranged, A1 194 on 11-22 |
| C-06 | plan | loan >= 1,000 (7 days), holiday + weekend, 622.58 / 622.57 | arranged, two parts (1, 2) |
| C-07 | hardship | breathing space accepted on two accounts | paused/BREATHING_SPACE, two notes |
| C-08 | multi | dispute, loan past its deadline, already paid | arranged, A2 1100 on 11-05, notes DISPUTED + PAID_CLAIMED |
| C-09 | call limit | 1,500 + 800 wanted, loan capped at 500 | arranged, A1 1500 + A2 500 |
| C-10 | tool failure | verify 500 once; overdraft refused (1 attempt); card promise fails twice | no_payment/SERVICE_ERROR (severity, not order) |
| C-11 | dates | 16:10 call: today refused; record A1, then plan request | transferred/PLAN, A1 kept, no notes |
| C-12 | fraud | stolen card | transferred/FRAUD, no notes |
