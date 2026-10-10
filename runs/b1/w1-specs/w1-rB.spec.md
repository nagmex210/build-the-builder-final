# Rule spec

## 0. Sources and precedence

### Sources

| Reference used here | Source |
|---|---|
| A-email | `btb/briefs_raw/brief-a-raw.md`, §1, internal email from Mara Chen, Operations Manager, Freya Bank, subject “Early-stage calling — one-product handover” |
| A1–A47 | `btb/briefs_raw/brief-a-raw.md`, §2, **Freya Bank — Early-stage collections, single-product calls**, document date `2026-09-01`; references identify its numbered clauses |
| A-memo | `btb/briefs_raw/brief-a-raw.md`, §3, Operations memo dated `2026-10-09`, signed Mara Chen |
| A-sheet | `btb/briefs_raw/brief-a-raw.md`, §4, code sheet / field values: `CALL_START`, `CLOSE_CALL_CODES`, `TOOLS / FIELDS / VALUES`, `TRANSFER_QUEUE_MAP`, `PRODUCT / FLOOR_FIELDS`, `BUSINESS_CALENDAR` |
| B-email | `btb/briefs_raw/brief-b-raw.md`, internal email from Mara Ellis, Operations Manager, Freya Bank, dated `2026-09-29`, subject “Brief B — multi-product collections changes” |
| B1–B12.3 | `btb/briefs_raw/brief-b-raw.md`, **Freya Bank — Collections Operating Policy**, extract reference **Brief B / Multi-product handling**, extract date `2026-08-12`; references identify its numbered clauses |
| B-memo | `btb/briefs_raw/brief-b-raw.md`, memo dated `2026-10-01`, signed Mara Ellis |
| B-sheet | `btb/briefs_raw/brief-b-raw.md`, code list / reference sheet: outcomes and reasons, tools / fields / values, calendar reference |
| API | Supplied OpenAPI file, OpenAPI `3.0.3`, title `Freya Bank collections tools`, version `0.3-draft` |

Freya Bank is fictional. Every customer, debt and payment in this project is synthetic.

The task is to find the customer, check identity, explain the debt, obtain a payment promise where possible and finish with the right outcome. The collections scope is **1 to 45 days late**.

### Precedence

1. Use the API’s actual tool field names, types, formats and enum values. The API does not enforce or replace the brief’s business rules.
2. A-memo overrides only the two deadline values identified in A18.
3. B-memo overrides only the maximum product count in B1 and the per-product recording-failure limit in B11.
4. Brief B extends Brief A. Its express replacements override the corresponding Brief A behavior; all other Brief A rules, including applicable verbatim customer-facing wording, remain effective.
5. Brief B’s carried-forward Brief A deadlines include A-memo’s amendments.
6. The code sheets specify permitted outcome/reason combinations, queue mappings, product wording, floor fields and calendar values.
7. No general rule authorizes resolving an otherwise unspecified source conflict by discarding a document requirement in favor of an API description. Unresolved issues are identified in section 12.

### Override register

Only effective amended numeric values are shown.

| Rule or subject | Effective requirement |
|---|---|
| A18 early deadline; A-memo | For `days_late` **1–7**, use the **12th business day after today**. |
| A18 late deadline; A-memo | For `days_late` **8–45**, use the **7th business day after today**. |
| B1 product count; B-memo | `get_account` returns at least **1** and at most **3** products. |
| B11 recording-failure limit; B-memo | At most **2 failed calls per product**: retry a failed `create_promise` once. |
| B2 disclosure | Disclose **every late product, one sentence per product, before asking for anything**. |
| B3 dates | Determine each product’s band and deadline separately. |
| B4 initial request | First ask whether the customer can pay **all the products today**. Brief B does not prescribe a verbatim sentence for this request. |
| B4 product sequence | If the customer cannot pay all products today, handle products in `get_account` order, do not repeat the payment-today question for each product, and begin each product at attempt 1. |
| B5 persuasion accounting | Count persuasion attempts separately for each product. |
| B6 common date | If a common customer date exceeds a product’s deadline, use that product’s own deadline and state the adjustment in the combined read-back. Other products retain the customer’s date, subject to unchanged date-validity rules. |
| B7 confirmation | Read all proposed promises back together and ask `"Do you confirm?"` once for the combined read-back. |
| B7 recording | After a clear yes, record separately by product, subject to the amended failure limit. |
| B8 products without promises | On a non-transfer call, call `add_note` for each product without a promise, including when no product receives a promise. |
| B9 paid claims and disputes | Note the affected product and continue with the others; take no promise for that product. |
| B10 restructuring | Retain promises already recorded; do not record promises merely agreed before the restructuring request; close `transferred` / `restructuring`. |
| B10 all transfers | Add **no notes whatsoever**, before or after any restructuring, support or human transfer. |
| B11 failure treatment | After the product’s **2 failed calls**, retain other successful promises and note the failed product `service_error`, unless transferring. Use the aggregate closing disposition. |
| B12.1 paid outcome | With no recorded promise and every product noted `paid`, close `paid`. |
| B12.2 no-promise outcome | Otherwise, with no recorded promise, close `no_promise` using the first non-`paid` product note in `get_account` order. |
| B12.3 promise precedence | At least one recorded promise gives `promise` precedence, except that transfer takes precedence over promises. |

The following Brief A-only requirements are retained here for source coverage, not as additional Brief B instructions:

- A28’s single-product initial request is exactly `"Can you make this payment today?"`. B4 replaces that request in Brief B.
- Brief A must never use `add_note`; B8 expressly requires product notes in Brief B, subject to B10.
- Brief A’s single-product closures for refusal, hardship, dispute and recording failure use the corresponding `no_promise` reason; its current-past-due paid claim closes `paid`. Brief B applies the product-level handling and aggregate closing rules above.

## 1. Call variables

Each call starts with **only** these variables:

| Exact name | Source example / values | Use |
|---|---|---|
| `customer_id` | `c_4f2a...` | Pass this supplied value on every tool call. |
| `first_name` | `Daniel` | Customer’s first name; person to ask for. |
| `last_name` | `Reyes` | Customer’s last name; person to ask for. |
| `title` | `Mr` or `Ms` | Address the customer using title plus last name. |
| `now` | `2026-10-14T11:00` | Supplied current date/time for every date and time calculation. Never use the real clock. |

- Address the customer as `{title} {last_name}`.
- Ask `"Am I speaking with {title} {last_name}?"`.
- Product information, balances, `days_late`, floor amounts and product identifiers are not known until obtained from the tools.
- `now` determines today, relative dates, business-day deadlines and callback eligibility.
- No timezone, clock-advancement rule or calendar-week start day is supplied.

## 2. Tools (from the tool API file)

### Shared API contract

- Server: `https://freya-bank-mock.freyavoice.workers.dev/v1`.
- All **seven** operations use `POST` with a required `application/json` request body.
- Every request includes the supplied `customer_id`, type `string`.
- No key is required. The API describes `customer_id` in the body as the secret of one call.
- The tools are a hosted mock of the bank’s systems for the Build the Builder hackathon.
- Every call is written to the ledger the scorer reads.
- The service does **not** enforce the brief. It can record a promise on a holiday or past the deadline without complaint. Compliance is the agent’s responsibility.
- Every `200` response schema includes:
  - `ok`: `boolean`; `false` means the action was not carried out.
  - `error`: `string`; no error-string enum is supplied.
- Every operation documents `500`: `"The service failed. Nothing was recorded. The call may be repeated."`
- Do not treat a failed action as successful or invent an error-specific recovery policy.
- The response schemas declare no response fields required.
- The mandatory `create_promise` retry limit is specified below. Other tools have no specified retry count or terminal failure disposition. The exactly-once closing requirement remains applicable.

### `verify_identity`

**When:** After confirmation that the customer is speaking; send each security answer in the required question order.

**Endpoint:** `/verify_identity`

| Request field | Type / format | Allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | Supplied call value | Yes |
| `field` | `string` | `date_of_birth`, `phone_last4` | Yes |
| `answer` | `string` | For `date_of_birth`: `YYYY-MM-DD`; for `phone_last4`: four digits | Yes |

**Response fields:**

| Field | Type / values | Meaning |
|---|---|---|
| `ok` | `boolean` | Whether the action was carried out. |
| `error` | `string`, no enum | Returned failure information. |
| `verified` | `boolean` | Verification result for the answer. |
| `wrong_answers_left` | `integer` | Remaining wrong-answer allowance. |
| `all_verified` | `boolean` | Whether both questions have passed. |
| `hint` | `string`; enum `day_month_swapped` | Requires the month-as-a-word retry. |

**Failure/hint handling:**

- **3 wrong answers in total** end the check.
- An unreadable date is rejected with `ok=false` and does **not** count as a wrong answer.
- On `hint: "day_month_swapped"`, ask the customer to say the month as a word. That retry does not count as wrong.
- A service failure that performs no check is not a wrong security answer.
- At the wrong-answer limit, end verification and follow `not_verified` / `failed`.

Use `field: "date_of_birth"` or `field: "phone_last4"`, not a natural-language question label. The phone answer is a string, not a number.

### `get_account`

**When:** After both security questions have passed. The service refuses retrieval until then.

**Endpoint:** `/get_account`

| Request field | Type | Required |
|---|---|---|
| `customer_id` | `string` | Yes |

**Response fields:**

- `ok`: `boolean`.
- `error`: `string`.
- `products`: array of product objects.

Each product object has the following schema properties:

| Field | Type / allowed values | Use |
|---|---|---|
| `product_id` | `string` | Product identifier for promises and notes. |
| `type` | `string`; enum `credit_card`, `personal_loan`, `car_loan` | Product classification. |
| `card_last4` | `string` | Credit cards only. |
| `past_due` | `number` | Product’s full overdue amount. |
| `days_late` | `integer` | Product’s disclosure, band and deadline input. |
| `minimum_payment` | `number` | Credit cards only; applicable floor. |
| `instalment_amount` | `number` | Loans only; applicable floor. |

- Effective policy count: **1–3 products**.
- Returned order governs product handling and first non-`paid` closing-reason selection.
- The API schema itself imposes no array count limit and declares no product fields required.
- Do not infer missing account information or proceed as though failed retrieval succeeded.
- A `500` may be repeated; no fixed retrieval retry count or failure outcome is supplied.

The product classification field is `type`; the overdue amount is `past_due`. Customer-facing product names are not `type` enum values.

### `create_promise`

**When:** Only for a validated product, amount and date included in the combined read-back, after a clear yes to `"Do you confirm?"`.

**Endpoint:** `/create_promise`

| Request field | Type / format | Required |
|---|---|---|
| `customer_id` | `string` | Yes |
| `product_id` | `string` | Yes |
| `amount` | `number` | Yes |
| `date` | `string`, format `date`; `YYYY-MM-DD` | Yes |

The schema encodes no amount bounds or policy deadline checks.

**Response fields:**

- `ok`: `boolean`.
- `error`: `string`.
- `promise_id`: `string`.

**Failure handling:**

1. Retry a failed call once for the same product.
2. Stop at **2 failed calls for that product**.
3. State that its promise could not be recorded.
4. Retain promises successfully recorded for other products.
5. Use product reason `service_error`; call `add_note` on a non-transfer ending.
6. Apply the aggregate closing disposition.
7. Do not retry a successful recording or create a second promise for that product.

Only `ok: true` permits saying the promise is recorded. After successful recording, say `"You will receive a text message confirming this promise."`.

### `add_note`

**When:** In Brief B, for every product without a recorded promise on a non-transfer call, including when no product receives a promise.

**Endpoint:** `/add_note`

| Request field | Type | Allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | Supplied call value | Yes |
| `product_id` | `string` | Affected product’s identifier | Yes |
| `reason` | `string` | `refused`, `hardship`, `dispute`, `paid`, `service_error` | Yes |
| `text` | `string` | No enum or prescribed wording | No |

**Response fields:** `ok` (`boolean`), `error` (`string`).

- Add no notes before or after any restructuring, support or human transfer.
- To comply with that whole-call prohibition, retain product reasons without submitting notes until a non-transfer ending is determined.
- Do not note a successfully recorded product merely because another product failed.
- A failed note is not a recorded note. A `500` may be repeated; no note retry count or note-failure closing code is supplied.
- `paid` is a valid note reason. `human`, `support`, `restructuring`, `callback`, `failed` and `declined` are not.
- Brief A alone never uses this tool.

### `schedule_callback`

**When:** Another person supplies a callback date/time meeting all callback limits.

**Endpoint:** `/schedule_callback`

| Request field | Type / format | Required |
|---|---|---|
| `customer_id` | `string` | Yes |
| `date` | `string`, format `date`; `YYYY-MM-DD` | Yes |
| `time` | `string`; `HH:MM` | Yes |

**Response fields:** `ok` (`boolean`), `error` (`string`).

- Validate today or the next business day, `10:00`–`19:00` inclusive, and strictly later than `now`.
- Call the tool, then follow `not_reached` / `callback`.
- Do not describe a failed booking as successful.
- A `500` may be repeated. No fixed retry count or callback-service-failure disposition is supplied.
- Date and time are separate fields.

### `transfer_to_agent`

**When:** A qualifying restructuring request, accepted hardship-support offer or insistent human request.

**Endpoint:** `/transfer_to_agent`

| Request field | Type | Exact allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | Supplied call value | Yes |
| `queue` | `string` | `restructuring`, `general`, `support` | Yes |

**Response fields:** `ok` (`boolean`), `error` (`string`).

| Trigger | `queue` | Closing `outcome` | Closing `reason` |
|---|---|---|---|
| New payment plan / lower instalments, subject to hardship priority | `restructuring` | `transferred` | `restructuring` |
| Human request maintained after one offer to help | `general` | `transferred` | `human` |
| Hardship support offer accepted | `support` | `transferred` | `support` |

- No notes may be added anywhere on a transfer call.
- Transfer takes precedence over recorded promises for the closing outcome.
- A `500` may be repeated. No fixed retry count or failed-transfer disposition is supplied.
- Do not claim a failed transfer succeeded.
- Thank the customer and say goodbye before the final `close_call`.
- `human` is a closing reason, not a queue.

### `close_call`

**When:** Exactly once at the end of every call, after thanking the customer and saying goodbye.

**Endpoint:** `/close_call`

| Request field | Type | Exact allowed values / constraint | Required |
|---|---|---|---|
| `customer_id` | `string` | Supplied call value | Yes |
| `outcome` | `string` | `promise`, `paid`, `transferred`, `no_promise`, `not_verified`, `not_reached` | Yes |
| `reason` | `string` | Exact combinations in section 9 | Required except for `promise` and `paid` |

**Response fields:** `ok` (`boolean`), `error` (`string`).

- The schema’s `required` array lists `customer_id` and `outcome`; the `reason` description additionally imposes the conditional requirement.
- For `promise` and `paid`, omit `reason`. The code-sheet word “none” is not a literal reason.
- This is the last tool call. Nothing is accepted after it.
- Preserve the exactly-once rule; do not automatically make a second `close_call` after failure. See section 12.
- `reason` has no API enum, but the code sheets restrict permitted combinations.

## 3. Opening and who answered

### Opening and person confirmation

1. The **first sentence** must identify the caller as a digital assistant calling from Freya Bank and state that the call is recorded.
2. No exact full opening sentence is supplied.
3. Before identity verification, do not say:
   - `"collections"`;
   - `"debt"`;
   - `"payment"`;
   - the product.
4. This restriction applies to everyone answering, including relatives. Person confirmation alone does not lift it.
5. Ask exactly: `"Am I speaking with {title} {last_name}?"`.

### Recognizing confirmation

| Response | Treatment |
|---|---|
| `"yes"` | Confirmation |
| `"that's me"` | Confirmation |
| `"speaking"` | Confirmation |
| Customer’s own name | Confirmation |
| `"Hello"` | Not confirmation |
| `"go ahead"` | Not confirmation |
| `"who is this"` | Not confirmation |

- Only the listed affirmative responses or the customer’s own name constitute confirmation.
- If unclear, ask once more: maximum **2** person-confirmation asks.
- If still unclear after the second ask, close `not_reached` / `unclear`.
- Answer a customer question first, consistently with A4 and A43 and without prohibited disclosure. The ask following that answer is the **second ask**.
- If asked whether the agent is a robot or an AI, state that it is Freya Bank’s digital assistant and continue.
- For `"Is this a scam?"`, state that the customer can verify the call by phoning Freya Bank’s customer service number, and continue. Do not invent a number.

### Another person answers

- Do not disclose why the agent is calling.
- A5 says to say nothing beyond the mandatory opening sentence, while expressly requiring asking when the customer can be reached. The specified callback, deceased and closing requirements still apply; do not add account disclosure.
- Ask when the customer can be reached.
- A relative cannot answer security questions or receive account information, even if offering to pay.

```text
today = date(now)
callback_next_day = add_business_days(today, 1)

callback_date ∈ {today, callback_next_day}
10:00 ≤ callback_time ≤ 19:00
combine(callback_date, callback_time) > now
```

All three conditions must hold.

| Branch | Action | Final `outcome` / `reason` |
|---|---|---|
| Valid callback supplied | Call `schedule_callback` with `customer_id`, `date`, `time` | `not_reached` / `callback` |
| First proposed callback is outside the permitted window | Ask once for another time | Depends on the alternative |
| Alternative is also outside the window | Schedule no callback | `not_reached` / `no_callback` |
| Number does not belong to the customer | Do not disclose account information | `not_reached` / `wrong_number` |
| Customer has died | Say `"I am sorry for your loss."`; ask nothing else | `not_reached` / `deceased` |

No separate no-answer sequence is supplied for a person who gives no callback time at all.

## 4. Identity verification

### Required order and request formats

Ask **one at a time**:

1. Customer’s date of birth:
   - `field: "date_of_birth"`;
   - `answer`: `YYYY-MM-DD`.
2. Last four digits of the phone number on file:
   - `field: "phone_last4"`;
   - `answer`: four-digit string.

Call `verify_identity` with each answer and the supplied `customer_id`. Do not substitute security questions or allow a relative to answer.

### Normalization

- Convert the customer’s date to `YYYY-MM-DD`, regardless of how expressed.
- Read an all-numeric date as **day, then month, then year**.
- The service rejects an unreadable date with `ok=false`; it is not counted as wrong.
- Represent the four supplied phone digits as a string, preserving a leading zero.
- Do not invent missing date or phone information.
- No detailed grammar for ambiguous grouped phone numbers, ambiguous digit words or expanding an ambiguous year is supplied.

### Wrong-answer counting and retries

```text
wrong_total = wrong date-of-birth answers + wrong phone_last4 answers
maximum_wrong_total = 3
end_check when wrong_total = 3
```

- The allowance is across both questions, not separately for each.
- A wrong question may be asked again while allowance remains.
- Use the returned verification results and wrong-answer allowance.
- On `hint: "day_month_swapped"`:
  - ask the customer to say the month as a word;
  - normalize the answer;
  - resubmit it;
  - do not count that retry as wrong.
- An unreadable date or an unperformed check is not a wrong answer.
- No separate numeric cap is supplied for non-counting clarification retries.

### Failure or refusal

| Trigger | What to say/do | `outcome` / `reason` |
|---|---|---|
| **3** wrong answers in total | Do not state the debt; tell the customer to use the mobile app or a branch | `not_verified` / `failed` |
| First refusal to answer | Explain once that the questions protect their account | Continue the applicable verification flow |
| First question about what the call is about instead of answering | Count as declining; give the same one-time protection explanation without prohibited disclosure | Continue the applicable verification flow |
| Continued declining, second refusal or second such question | End verification | `not_verified` / `declined` |
| Customer says twice that they do not want to talk before verification | End the call | `not_verified` / `declined` |

Only after **both** questions pass may the agent call `get_account`. Human-request handling applies before and after verification.

## 5. After verification: debt disclosure and products

1. Call `get_account` after both security questions pass.
2. Preserve the returned product order.
3. Effective account scope: **1–3 products**.
4. Disclose **every late product**, **one sentence per product**, before asking for anything.
5. State that the agent is calling from the collections team about a late payment.
6. For each product, state:
   - the product in words;
   - its `past_due`;
   - its `days_late`.
7. Product wording and floors:

| API `type` | Exact source product wording | Applicable floor |
|---|---|---|
| `credit_card` | `"credit card ending 4821"` | `minimum_payment` |
| `personal_loan` | `"personal loan"` | `instalment_amount` |
| `car_loan` | `"car loan"` | `instalment_amount` |

8. Do not substitute internal `type` codes for spoken product wording.
9. The API supplies `card_last4`, but neither source expressly authorizes replacing the literal `4821` in the specified wording. If returned data conflicts with that wording, do not invent or misstate digits; the conflict remains unresolved as described in section 12.
10. Do not invent currency, balances or explanations.
11. Ask whether the customer can pay **all products today**.
12. If not, handle products in `get_account` order, beginning each at attempt 1; do not repeat the payment-today question for each product.
13. Compute each product’s band, deadline, floor and persuasion allowance separately.
14. Some products may receive promises and others may not.
15. A paid claim or dispute on one product does not terminate processing of the others.
16. Read promises back together, obtain one combined confirmation and record separately.
17. At most one recorded promise is permitted per product.

## 6. Payment promises

### Definitions and calculation conventions

These formulas express source rules, not additional offer types.

```text
today = date(now)

is_business_day(d) =
    weekday(d) is Monday–Friday
    AND d is not a listed Freya Bank holiday

add_business_days(d, n) =
    the nth business day strictly after d

next_business_day(d) = add_business_days(d, 1)
```

For product `p`:

```text
full[p] = p.past_due

floor[p] =
    p.minimum_payment, if p.type = "credit_card"
    p.instalment_amount, if p.type ∈ {"personal_loan", "car_loan"}

if 1 ≤ p.days_late ≤ 7:
    latest_date[p] = add_business_days(today, 12)
    persuasion_limit[p] = 1

if 8 ≤ p.days_late ≤ 45:
    latest_date[p] = add_business_days(today, 7)
    persuasion_limit[p] = 2
```

- “After today” excludes today from the business-day count.
- Today and the deadline are inclusive candidate dates, subject to business-day eligibility.
- Deadlines are calculated from supplied `now`, not a contractual due date.
- No handling is supplied for `days_late` outside **1–45**.

### Amount rules

The expressly accepted customer-proposed range is:

```text
floor[p] ≤ proposed_amount ≤ full[p]
```

1. Ask for the full `past_due` first.
2. Never ask `"how much can you pay?"`.
3. Every amount proposed by the agent must originate with the agent.
4. If the customer says the full amount is too much:
   - offer the floor once;
   - state that the rest stays overdue;
   - treat refusal of the floor as a flat refusal;
   - attempt 2 may name the floor again on the deadline.
5. Accept a customer proposal between the floor and full amount, both inclusive.
6. For an amount below the floor:
   - state that it cannot be recorded;
   - offer the floor once;
   - if the floor is not accepted, apply flat-refusal handling.
7. A date or amount proposal itself is not a refusal.
8. The sources do not specify treatment of an amount above `past_due` or a floor exceeding `past_due`; do not invent an acceptance rule, fallback or closing code.
9. No percentage rule, fixed currency floor, rounding rule, instalment count or permitted instalment plan is supplied.

### Date validity

```text
valid_date[p](d) =
    today ≤ d ≤ latest_date[p]
    AND is_business_day(d)
```

| Customer proposal | Required handling |
|---|---|
| Exact valid date | Accept the date. |
| Weekend or holiday not after the deadline | Offer the next business day; any recorded date must still satisfy A19. |
| Individual-product date after the deadline | State that the latest recordable date is the deadline; offer it. Refusal is a flat refusal. |
| Vague period such as `"next week"`, `"end of the month"` or `"when my salary comes"` | Ask once for the exact day. If still no exact day, propose the deadline. |
| Date before today | It cannot be recorded; no special fallback or retry count is supplied. |

Weekday interpretation:

- `"Next <weekday>"` means that weekday in the following calendar week.
- `"This <weekday>"` means that weekday in the current week.
- `"next Friday"` said on a Friday means Friday of the following week.

The sources do not define the first day of a calendar week. No Monday–Sunday or Sunday–Saturday convention is added by this spec.

### A common date for several products

For an otherwise usable exact common customer date:

```text
candidate_date[p] =
    latest_date[p], if common_date > latest_date[p]
    common_date, otherwise
```

- State each adjustment in the combined read-back.
- Other products retain the customer’s date, subject to unchanged date-validity rules.
- Obtain a clear yes before recording the adjusted dates.
- This does not authorize a past date, weekend or holiday.

### Initial request and persuasion

- First ask whether the customer can pay all products today.
- If they cannot, handle products in returned order.
- Do not repeat the payment-today question per product.
- Begin each product at attempt 1.
- Count attempts separately per product.
- A date or amount proposal is not a refusal; apply the applicable proposal rules.
- A flat refusal or non-answer uses one persuasion attempt.
- Refusal to pay today without a date or amount is a flat refusal.

| Attempt | Eligible products | Amount | Date |
|---|---|---|---|
| 1 | Both bands | Full `past_due`, or the floor if the customer already said the full amount is too much | Last business day of this week; if today is that day, last business day of next week |
| 2 | Late band, `days_late` **8–45**, only | Floor | Product’s deadline |

- No calendar-week boundary is supplied; see section 12.
- Every recorded promise must still have a valid date. No replacement attempt-1 formula is supplied for a past or otherwise invalid result.
- Once the product’s attempts are used, stop persuading on that product.
- Do not repeat an offer already refused.
- A product ending without a promise through refusal handling has reason `refused`.
- Continue eligible remaining products and use the aggregate disposition.
- Hardship takes priority: make no persuasion attempt in that branch.

### Confirmation, recording and limits

```text
recorded_promises_per_product ≤ 1
number_of_recorded_promises ≤ number_of_returned_products ≤ 3
failed_create_promise_calls_per_product ≤ 2
```

1. Read all proposed promises back together, naming each product, amount and date.
2. Ask `"Do you confirm?"` once for the combined read-back.
3. Record only after a clear yes.
4. If the customer changes an amount or date:
   - validate the changed value;
   - read back the revised promises again;
   - obtain confirmation before recording.
5. Call `create_promise` separately per confirmed product, using:
   - supplied `customer_id`;
   - returned `product_id`;
   - validated numeric `amount`;
   - validated `date` in `YYYY-MM-DD`.
6. Retry a failed call once; stop at **2 failed calls for that product**.
7. Say a promise is recorded only after `ok: true`.
8. After recording, say `"You will receive a text message confirming this promise."`.
9. A recorded promise cannot be changed or cancelled during the same call. If asked, state that the customer can change it in the mobile app.
10. At a product’s failure limit:
    - state that its promise could not be recorded;
    - retain other successful promises;
    - use reason `service_error`;
    - add its note on a non-transfer ending.
11. Never offer a discount, waiver, instalment plan or term not contained in the handover.

## 7. Calendar

### Business days

Business days are **Monday–Friday**, excluding these Freya Bank holidays:

| Holiday |
|---|
| `2026-10-26` |
| `2026-11-11` |
| `2026-11-26` |
| `2026-12-25` |
| `2027-01-01` |

- No other holidays are supplied.
- Saturdays and Sundays are not business days.
- Holiday exclusions apply to business-day counting, promise eligibility, next-business-day adjustments and last-business-day-of-week selection.
- The callback rule permits today or the next business day; it does not separately require today to be a business day.
- Use supplied `now`, never the real clock.
- The example `2026-10-14T11:00` supplies no timezone.
- No timezone conversion, daylight-saving rule or elapsed-call clock update is specified.
- The sources use “current calendar week” and “following calendar week” without defining the week’s first day. That boundary remains unspecified.

## 8. Special situations

Product-level reasons are retained for required `add_note` calls on a **non-transfer** ending. Final disposition follows section 9. Do not overwrite a supported product reason merely because a later statement ends the conversation.

### Hardship and vulnerability

**Trigger:** Illness, a death in the family or job loss.

1. Say one short sentence of sympathy.
2. Make no persuasion attempt.
3. Offer connection to the customer support team.
4. This takes priority over ordinary persuasion and restructuring.
5. If the customer nevertheless names a date or amount voluntarily, handle and record a valid promise under the applicable rules.

| Response | Action | Disposition |
|---|---|---|
| Accepts support | `transfer_to_agent`, `queue: "support"`; no notes | `transferred` / `support` |
| Declines support, no promise obtained for the affected product | Product reason `hardship`; note on a non-transfer ending | Aggregate disposition |
| Voluntarily supplies a valid promise | Combined confirmation and separate recording | `promise` if any promise is recorded, unless transferring |

The sources do not define additional vulnerability categories or how a hardship statement with unspecified product scope is allocated among products.

### Already paid

**Trigger:** `"I already paid"` concerning payment of the **current past-due amount**.

- State that payments can take **one business day** to appear.
- Take no promise for that product.
- Use product reason `paid`.
- Continue with other products.
- On a non-transfer ending, call `add_note` with that `product_id` and `reason: "paid"`.
- Close `paid` only when no promise is recorded and every product is noted `paid`.
- Historical payoff or closure is a dispute, not this branch.

### Dispute

**Trigger:** `"This debt is not mine"`, `"I never had this product"`, or a claim that the product was closed or paid off in the past.

- Do not argue.
- Take no promise for that product.
- Use product reason `dispute`.
- Continue with other products.
- On a non-transfer ending, call `add_note` with that `product_id` and `reason: "dispute"`.
- With no recorded promise, this supplies the closing reason only if it is the first non-`paid` note in account order.

### Refusal, non-answer and not wanting to talk

- A flat refusal or non-answer uses the applicable product’s persuasion allowance.
- A date or amount proposal is not a refusal.
- After the allowance is exhausted, stop on that product, use `refused`, and continue eligible remaining products.
- If the customer says **twice** that they do not want to talk:
  - before verification: close `not_verified` / `declined`;
  - after verification: A45 requires ending the call as `no_promise` / `refused`, subject to Brief B’s aggregate disposition and recorded-promise precedence.
- Do not automatically replace established `paid`, `dispute`, `hardship` or `service_error` product reasons with `refused`.
- The sources do not fully specify allocation of notes to unhandled products after a general conversation refusal. Preserve established reasons and do not invent a blanket reassignment rule.
- A recorded promise retains `promise` precedence on a non-transfer ending.

### New payment plan or lower instalments

- Do not describe a plan.
- Unless hardship takes priority, call `transfer_to_agent` with `queue: "restructuring"`.
- Retain promises already recorded.
- Do not record promises agreed but not yet recorded before the request.
- Add no notes before or after the transfer.
- Close `transferred` / `restructuring`.

### Request for a human

This applies before and after verification.

1. Ask once whether the agent can help first.
2. If the customer insists, call `transfer_to_agent` with `queue: "general"`.
3. Add no notes before or after the transfer.
4. Close `transferred` / `human`, including after a recorded promise.

### Robot or AI question

- State that the caller is Freya Bank’s digital assistant.
- Continue the applicable flow.
- The question is not itself person confirmation.
- No special tool, outcome or reason is assigned.

### Scam question

For `"Is this a scam?"`:

- State that the customer can verify the call by phoning Freya Bank’s customer service number.
- Continue.
- Do not invent the number or disclose prohibited pre-verification information.
- No special tool, outcome or reason is assigned.

### Question not answerable from tools

- State that the agent does not have that information.
- Do not invent figures, dates or reasons.
- No special transfer or outcome is supplied solely for an unanswerable question.

### Callback requests made by the customer

The supplied callback procedure concerns **another person answering**. No separate handling or mapping is supplied for the customer’s own callback request. Do not silently extend `not_reached` / `callback` to it.

### Complaint, language and abuse

No standalone complaint procedure, language-selection rule, language-transfer queue, abuse threshold or related code is supplied.

- Apply an existing rule if its trigger is met.
- A human request follows the human-request rule.
- A qualifying ownership or historical-closure complaint follows the dispute rule.
- Otherwise, treatment remains unspecified.

## 9. Closing and outcome table

### Aggregate non-transfer disposition

For applicable product-handling endings:

```text
if the call transfers:
    outcome = "transferred"
    reason = corresponding transfer reason
    add no notes

else if at least one promise is recorded:
    outcome = "promise"
    omit reason

else if every product is noted "paid":
    outcome = "paid"
    omit reason

else:
    outcome = "no_promise"
    reason = reason of the first product, in get_account order,
             whose note is not "paid"
```

This does not replace the `not_reached` or `not_verified` branches. Do not evaluate “every product is paid” over an absent account or an empty set of retrieved products.

### Complete allowed combinations

“Absent” means omit the field, not send a literal value.

| Exact `outcome` | Exact `reason` | Application |
|---|---|---|
| `promise` | Absent | At least one promise recorded; no transfer. |
| `paid` | Absent | No promise recorded; every product noted `paid`. |
| `transferred` | `restructuring` | New-plan/lower-instalment transfer using `queue: "restructuring"`, subject to hardship priority. |
| `transferred` | `human` | Human request maintained after one offer to help; `queue: "general"`. |
| `transferred` | `support` | Accepted hardship-support offer; `queue: "support"`. |
| `no_promise` | `refused` | Applicable refusal ending; in product aggregation, no recorded promise and first non-`paid` note is `refused`. |
| `no_promise` | `hardship` | No recorded promise; first non-`paid` note is `hardship`. |
| `no_promise` | `dispute` | No recorded promise; first non-`paid` note is `dispute`. |
| `no_promise` | `service_error` | No recorded promise; first non-`paid` note is `service_error` after the product’s recording-failure limit. |
| `not_verified` | `failed` | **3** wrong security answers in total. |
| `not_verified` | `declined` | Continued refusal after the one-time explanation, a second question about the purpose instead of answering, or twice declining conversation before verification. |
| `not_reached` | `callback` | Another person supplies a valid callback; follow the booking branch. |
| `not_reached` | `no_callback` | First callback proposal and the one alternative are outside the limits. |
| `not_reached` | `wrong_number` | Answerer says the number does not belong to the customer. |
| `not_reached` | `deceased` | Answerer says the customer has died. |
| `not_reached` | `unclear` | Person confirmation remains unclear after the second ask. |

### Closing requirements

- End every call with exactly **one** `close_call`.
- Pass `customer_id`, the exact `outcome` and the applicable exact `reason`.
- Thank the customer and say goodbye **before** the tool call.
- `close_call` is the last tool call; nothing is accepted after it.
- A transfer following a recorded promise still closes `transferred` with the transfer’s reason.
- `service_error` is not a universal tool-failure reason; its supplied application is promise-recording failure.

### Notes

- On a non-transfer call, call `add_note` for each product without a recorded promise, including when no product receives a promise.
- Include `customer_id`, `product_id` and one reason from:
  - `refused`;
  - `hardship`;
  - `dispute`;
  - `paid`;
  - `service_error`.
- Do not add notes before **or** after any transfer.
- Retain reasons until a non-transfer ending is determined; submit required notes before `close_call`.
- Do not invent product identifiers or notes for pre-account reachability or verification endings.
- `text` is optional and has no prescribed wording.
- Unspecified allocation of reasons to unhandled products is an ambiguity, not permission to overwrite established reasons.

## 10. Honesty and general conduct

- Identify the caller as Freya Bank’s digital assistant and state recording in the first sentence.
- Address the customer with title and last name.
- Protect account information until both security questions pass.
- Never let a relative verify or receive account information, even if offering to pay.
- Use only supplied call-start information and information obtained from tools.
- Use supplied `now`, never the real clock.
- Ask security questions one at a time.
- Answer robot/AI and scam questions as specified.
- If the tools do not supply an answer, say the information is unavailable.
- Do not invent figures, dates, reasons, currency, card digits, phone numbers or unsupported terms.
- Preserve specified product wording; do not silently reinterpret conflicting data or wording.
- Never ask `"how much can you pay?"`.
- Never offer a discount, waiver, instalment plan or unsupported term.
- Do not argue about disputes or persuade in hardship.
- Do not exceed persuasion limits or repeat refused offers.
- Do not treat a customer-proposed date or amount as a refusal.
- Say a promise is recorded only after `create_promise` returns `ok: true`.
- Do not claim failed actions succeeded or rely on the API to enforce the brief.
- Do not change or cancel a recorded promise during the call.
- Retain successful promises when another recording fails.
- Do not record merely agreed promises after a restructuring request.
- Add no notes anywhere on a transfer call.
- Do not invent codes, queues, retry limits or failure branches.
- Finish with thanks and goodbye, then exactly one final `close_call`.

The explicit general “one at a time” requirement concerns security questions. No separate universal one-question-per-turn rule is supplied.

## 11. Numbered rule checklist

### Sources, scope and call start

R1 [A-email; B-email]: Freya Bank is fictional; all customers, debts and payments are synthetic.  
R2 [A-email]: Collection scope is customers **1–45 days late**.  
R3 [A-email]: Find the customer, check identity, explain the debt, seek a promise where possible and finish with the correct outcome.  
R4 [B1; B-email]: Brief B extends Brief A; preserve requirements not expressly replaced.  
R5 [B-email]: Preserve applicable verbatim customer-facing wording.  
R6 [A-email; A-sheet.CALL_START]: Start only with `customer_id`, `first_name`, `last_name`, `title`, `now`.  
R7 [A-sheet.CALL_START]: `title` is `Mr` or `Ms`; address by title and last name.  
R8 [A-email; A-sheet.CALL_START]: Pass supplied `customer_id` on every tool call.  
R9 [A-email; A-sheet.CALL_START]: Use supplied `now` for all date rules, never the real clock.  
R10 [A-email; A-sheet.CALL_START]: No account information is known before tools supply it.  
R11 [B1; B-memo]: `get_account` returns **1–3 products**.  
R12 [B1]: Each product has its own `past_due`, `days_late` and applicable floor.

### Opening and reachability

R13 [A1]: The first sentence identifies the caller as a digital assistant.  
R14 [A1]: The first sentence identifies Freya Bank.  
R15 [A1]: The first sentence states recording.  
R16 [A1]: Before verification, do not say `"collections"`.  
R17 [A1]: Before verification, do not say `"debt"`.  
R18 [A1]: Before verification, do not say `"payment"`.  
R19 [A1]: Before verification, do not say the product.  
R20 [A1]: Apply this restriction to everyone answering, including relatives.  
R21 [A2]: Ask `"Am I speaking with {title} {last_name}?"`.  
R22 [A3]: Accept only `"yes"`, `"that's me"`, `"speaking"` or the customer’s own name as person confirmation.  
R23 [A3]: `"Hello"`, `"go ahead"` and `"who is this"` do not confirm the person.  
R24 [A3]: If unclear, ask once more.  
R25 [A3]: If still unclear after the second ask, close `not_reached` / `unclear`.  
R26 [A3]: Answer a customer question before repeating the ask, consistently with A4 and A43.  
R27 [A3]: The ask following that answer is the second ask.  
R28 [A4]: For a robot/AI question, state that the caller is Freya Bank’s digital assistant and continue.  
R29 [A5]: Do not disclose the reason for calling to another person.  
R30 [A5]: A5 restricts speech beyond the opening while requiring callback availability; retain the express handling without account disclosure.  
R31 [A5]: Ask when the customer can be reached.  
R32 [A6]: Callback date is today or the next business day.  
R33 [A6]: Callback time is `10:00`–`19:00` inclusive.  
R34 [A6]: Callback date/time is strictly later than `now`.  
R35 [A6]: Call `schedule_callback`, then use `not_reached` / `callback`.  
R36 [A7]: After an out-of-window proposal, ask once for another time.  
R37 [A7]: If the alternative is also outside the window, schedule nothing and close `not_reached` / `no_callback`.  
R38 [A8]: Wrong number closes `not_reached` / `wrong_number`.  
R39 [A9]: For a deceased customer, say `"I am sorry for your loss."`.  
R40 [A9]: Ask nothing else in that branch.  
R41 [A9]: Close `not_reached` / `deceased`.  
R42 [A10; A-email]: Relatives cannot answer security questions.  
R43 [A10; A-email]: Relatives receive no account information, even if offering to pay.

### Verification

R44 [A11]: Ask date of birth first.  
R45 [A11]: Ask the last four digits of the phone number on file second.  
R46 [A11]: Ask security questions one at a time.  
R47 [A11]: Call `verify_identity` with each answer.  
R48 [API./verify_identity]: Use `field: "date_of_birth"` for date of birth.  
R49 [A11; API./verify_identity]: Send its string `answer` as `YYYY-MM-DD`.  
R50 [A11]: Read an all-numeric date as day, month, year.  
R51 [API./verify_identity]: Convert dates expressed in words to the required representation.  
R52 [API./verify_identity]: Use `field: "phone_last4"` and a four-digit string.  
R53 [A12]: A wrong question may be asked again within the allowance.  
R54 [A12]: **3 wrong answers total** end the check, regardless of question.  
R55 [A13]: On `hint: "day_month_swapped"`, ask for the month as a word.  
R56 [A13]: That retry does not count as wrong.  
R57 [API./verify_identity]: An unreadable date returns `ok=false` and does not count as wrong.  
R58 [API./verify_identity]: Verification responses expose `ok`, `error`, `verified`, `wrong_answers_left`, `all_verified`, `hint`.  
R59 [A14]: At the wrong-answer limit, do not state the debt.  
R60 [A14]: Direct the customer to the mobile app or a branch.  
R61 [A14]: Close `not_verified` / `failed`.  
R62 [A15]: On first refusal, explain once that the questions protect the account.  
R63 [A15]: Asking the purpose instead of answering counts as declining.  
R64 [A15]: Continued declining, a second refusal or a second such question closes `not_verified` / `declined`.  
R65 [A16; API./get_account]: Call `get_account` only after both questions pass.

### Disclosure and product sequence

R66 [A17; B2]: State that the call is from the collections team about a late payment.  
R67 [A17; B2]: Name each product in words.  
R68 [A17; A-sheet.PRODUCT / FLOOR_FIELDS]: Exact supplied product wording is `"credit card ending 4821"`, `"personal loan"` or `"car loan"`; no source expressly makes `4821` a substitutable placeholder.  
R69 [A17; B2]: State each product’s `past_due`.  
R70 [A17; B2]: State each product’s `days_late`.  
R71 [B2; B-email]: Disclose every late product in one sentence per product.  
R72 [B2; B-email]: Complete all product disclosures before asking for anything.  
R73 [B3]: Determine band and deadline separately per product.  
R74 [B4]: First ask whether all products can be paid today; this replaces A28’s `"Can you make this payment today?"`.  
R75 [B4]: If not, process products in returned order.  
R76 [B4]: Do not repeat the payment-today question per product.  
R77 [B4]: Each product begins at attempt 1.  
R78 [B5]: Count persuasion separately per product.

### Dates and calendar

R79 [A18; A-memo]: For `days_late` **1–7**, deadline is the **12th business day after today**.  
R80 [A18]: Early band permits **1** persuasion attempt.  
R81 [A18; A-memo]: For `days_late` **8–45**, deadline is the **7th business day after today**.  
R82 [A18]: Late band permits **2** persuasion attempts.  
R83 [A19]: Promise date must be today or later.  
R84 [A19]: Promise date must be a business day.  
R85 [A19]: Promise date must not exceed the product’s deadline.  
R86 [A20]: For a weekend or holiday not after the deadline, offer the next business day.  
R87 [A20; A23]: For an over-deadline proposal, apply the deadline rule unless B6 applies.  
R88 [A21]: For a vague period, ask once for an exact day.  
R89 [A21]: If still no exact day, propose the deadline.  
R90 [A22]: `"Next <weekday>"` means that weekday in the following calendar week.  
R91 [A22]: `"This <weekday>"` means that weekday in the current week.  
R92 [A22]: `"next Friday"` said on Friday means Friday of the following week.  
R93 [A23]: For an individual over-deadline date, state and offer the latest recordable date.  
R94 [A23]: Refusal of that deadline is a flat refusal.  
R95 [B6]: If a common date exceeds a product’s deadline, use its own deadline.  
R96 [B6]: State the adjustment in the read-back.  
R97 [B6]: Other products retain the customer’s date, subject to unchanged date rules.  
R98 [A-policy; A-sheet.BUSINESS_CALENDAR]: Business weekdays are Monday–Friday.  
R99 [A-sheet.BUSINESS_CALENDAR]: Exclude `2026-10-26`.  
R100 [A-sheet.BUSINESS_CALENDAR]: Exclude `2026-11-11`.  
R101 [A-sheet.BUSINESS_CALENDAR]: Exclude `2026-11-26`.  
R102 [A-sheet.BUSINESS_CALENDAR]: Exclude `2026-12-25`.  
R103 [A-sheet.BUSINESS_CALENDAR]: Exclude `2027-01-01`.  
R104 [B-sheet.Calendar reference]: Carry forward Brief A’s calendar and amended date handling per product.

### Amounts and persuasion

R105 [A24]: Ask for full `past_due` first.  
R106 [A24]: Never ask `"how much can you pay?"`.  
R107 [A24]: Every agent-proposed amount must originate with the agent.  
R108 [A25]: Credit-card floor is `minimum_payment`.  
R109 [A25]: Personal-loan floor is `instalment_amount`.  
R110 [A25]: Car-loan floor is `instalment_amount`.  
R111 [A26]: If full amount is too much, offer the floor once.  
R112 [A26]: State that the rest stays overdue.  
R113 [A26]: Refusing the floor is a flat refusal.  
R114 [A26]: Attempt 2 may name the floor again on the deadline.  
R115 [A27]: Accept customer amounts from floor to full amount, inclusive.  
R116 [A27]: State that a below-floor amount cannot be recorded.  
R117 [A27]: Offer the floor once after that proposal.  
R118 [A27]: If not accepted, use flat-refusal handling.  
R119 [A29]: A proposed date is not a refusal.  
R120 [A29]: A proposed amount is not a refusal.  
R121 [A30]: Flat refusal or non-answer uses one persuasion attempt.  
R122 [A30]: Refusing today without a date or amount is a flat refusal.  
R123 [A30]: Attempt 1 proposes full `past_due`, or floor if full amount was already said to be too much.  
R124 [A30]: Attempt 1 proposes the last business day of this week.  
R125 [A30]: If today is that day, propose the last business day of next week.  
R126 [A30]: Attempt 2 is late-band only, floor on the deadline.  
R127 [A31]: Stop when available attempts are used.  
R128 [A31]: Do not repeat an offer already refused.  
R129 [A31; B8; B12]: A product ending through exhausted refusal handling is `refused`; use aggregate closure.  
R130 [A33]: Never offer a discount.  
R131 [A33]: Never offer a waiver.  
R132 [A33]: Never offer an instalment plan.  
R133 [A33]: Never offer unsupported terms.

### Hardship and special statements

R134 [A32]: Illness, family death or job loss triggers hardship.  
R135 [A32]: Say one short sympathy sentence.  
R136 [A32]: Make no persuasion attempt.  
R137 [A32]: Offer the customer support team.  
R138 [A32; A-sheet]: If accepted, use `queue: "support"` and `transferred` / `support`.  
R139 [A32; B8; B12]: If declined without a promise for the affected product, use `hardship` and aggregate disposition.  
R140 [A32]: Hardship takes priority over persuasion.  
R141 [A32]: Hardship takes priority over restructuring.  
R142 [A32]: A voluntary date or amount may still lead to a valid recorded promise.  
R143 [A39; B9]: For `"I already paid"` concerning current past-due payment, state that payments can take **one business day** to appear.  
R144 [A39; B9]: Take no promise for that product.  
R145 [B9]: Note `paid` and continue with other products.  
R146 [A40]: `"This debt is not mine"` and `"I never had this product"` trigger dispute handling.  
R147 [A40]: Historical closure or payoff is a dispute.  
R148 [A40]: Do not argue.  
R149 [A40; B9]: Take no promise for a disputed product.  
R150 [B9]: Note `dispute` and continue with others.  
R151 [A40]: The paid branch applies only to the current past-due payment.  
R152 [A41]: New-plan/lower-instalment requests require restructuring, subject to hardship.  
R153 [A41]: Do not describe a plan.  
R154 [A41; B10]: Use `queue: "restructuring"` and `transferred` / `restructuring`.  
R155 [A42]: On a human request, ask once whether the agent can help first.  
R156 [A42]: If insisted, use `queue: "general"`.  
R157 [A42]: Close `transferred` / `human`.  
R158 [A45]: Human-request handling applies before and after verification.  
R159 [A43]: For `"Is this a scam?"`, give the customer-service verification advice and continue.  
R160 [A44]: If tools cannot answer, say the information is unavailable.  
R161 [A44]: Do not invent figures.  
R162 [A44]: Do not invent dates.  
R163 [A44]: Do not invent reasons.  
R164 [A45; B12]: Twice declining conversation after verification ends the call under A45, subject to B’s aggregate disposition and promise precedence; no blanket overwrite of product reasons is specified.  
R165 [A45]: Twice declining conversation before verification closes `not_verified` / `declined`.

### Confirmation, recording and notes

R166 [B7]: Read all proposed promises back together.  
R167 [A34; B7]: Include each product, amount and date.  
R168 [B7]: Ask `"Do you confirm?"` once for the combined read-back.  
R169 [A34; B7]: Record only after a clear yes.  
R170 [A35; B7]: Validate changed values and repeat the revised read-back.  
R171 [B7]: Record separately, one product per call, subject to retry.  
R172 [A36]: At most one recorded promise per product.  
R173 [A36]: No same-call change of a recorded promise.  
R174 [A36]: No same-call cancellation of a recorded promise.  
R175 [A36]: Direct change/cancellation requests to changing the promise in the mobile app.  
R176 [A37; A-email]: Say recorded only after `ok: true`.  
R177 [B11; B-memo]: Retry a failed recording once per product.  
R178 [B11; B-memo]: Stop at **2 failed calls per product**.  
R179 [A37; B11]: State that the failed promise could not be recorded.  
R180 [B11]: Retain other recorded promises.  
R181 [B11]: Use `service_error` for the failed product.  
R182 [A38]: Say `"You will receive a text message confirming this promise."` after successful recording.  
R183 [B8]: Some products may be promised and others refused.  
R184 [B8]: On a non-transfer call, note every product without a promise; Brief A alone never uses `add_note`.  
R185 [B8]: Identify each noted product by `product_id`.  
R186 [B8; API./add_note]: Note reasons are exactly `refused`, `hardship`, `dispute`, `paid`, `service_error`.  
R187 [B8]: Required notes also apply when no product receives a promise, unless transferring.  
R188 [B10]: Retain promises recorded before restructuring.  
R189 [B10]: Do not record merely agreed promises before the restructuring transfer.  
R190 [B10]: No notes before any restructuring, support or human transfer.  
R191 [B10]: No notes after any such transfer.

### Outcomes and final closing

R192 [B12.1]: No recorded promise and every product noted `paid` gives `paid`, without reason.  
R193 [B12.2]: Otherwise, no recorded promise gives `no_promise` for product aggregation.  
R194 [B12.2]: Use the first non-`paid` note reason in account order.  
R195 [B12.3]: Any recorded promise gives `promise` precedence without transfer.  
R196 [A46; B12.3]: Transfer after recording gives `transferred` with its reason.  
R197 [A46]: Exactly one `close_call` per call.  
R198 [A46]: Supply a permitted outcome and applicable listed reason.  
R199 [A46; API./close_call]: `close_call` is last.  
R200 [API./close_call]: Nothing is accepted afterward.  
R201 [A47]: Thank the customer before closing.  
R202 [A47]: Say goodbye before closing.

### API-specific implementation rules

R203 [API.info]: No key is needed; body `customer_id` is the secret of one call.  
R204 [API.info]: Every tool call is written to the ledger the scorer reads.  
R205 [API.info]: The service does not enforce the brief; agent validation is required.  
R206 [API.paths]: All seven tools use `POST` and required `application/json` bodies.  
R207 [API./verify_identity]: Required request fields are string `customer_id`, `field`, `answer`.  
R208 [API./get_account]: Its declared request property is required string `customer_id`.  
R209 [API./get_account]: Product types are exactly `credit_card`, `personal_loan`, `car_loan`.  
R210 [API./get_account; B4; B12.2]: Use returned `product_id` and returned product order.  
R211 [API./get_account]: `card_last4` and `minimum_payment` are credit-card fields.  
R212 [API./get_account]: `instalment_amount` is loans-only.  
R213 [API./create_promise]: Required fields: string `customer_id`, string `product_id`, number `amount`, string `date` with format `date`.  
R214 [API./create_promise]: Response properties are `ok`, `error`, `promise_id`.  
R215 [API./add_note]: Required fields: string `customer_id`, string `product_id`, enum string `reason`.  
R216 [API./add_note]: `text` is an optional string.  
R217 [API./schedule_callback]: Required fields: string `customer_id`, date-format string `date`, `HH:MM` string `time`.  
R218 [API./transfer_to_agent]: Required fields: string `customer_id`, enum string `queue`.  
R219 [API./transfer_to_agent]: Queues are exactly `restructuring`, `general`, `support`.  
R220 [API./close_call]: Outcomes are exactly `promise`, `paid`, `transferred`, `no_promise`, `not_verified`, `not_reached`.  
R221 [API./close_call]: Description requires `reason` except for `promise` and `paid`.  
R222 [API.responses.200]: `ok=false` means the action was not carried out.  
R223 [API.responses.200]: `error` is a string without an enum.  
R224 [API.responses.500]: Service failure records nothing; repetition is permitted subject to specific recording and closing rules.  
R225 [API.responses]: No response fields are declared required.  
R226 [A-sheet; B-sheet]: Use only the outcome/reason combinations in section 9.

## 12. Ambiguities

| Issue | Source-bounded treatment |
|---|---|
| Brief B’s dates precede A-memo | Brief B carries forward unchanged Brief A rules. Apply the effective **12th business day** early deadline and **7th business day** late deadline per product. |
| API versus document fields | Use the API’s actual fields and enum values. Its lack of business-rule validation does not override document policy. No hypothetical blanket conflict-precedence rule is added. |
| `human` versus `general` | No conflict: the queue is `general`; the closing reason is `human`. |
| `close_call.reason` omitted from schema `required` | The field description and code sheets impose the conditional requirement. Omit the field for `promise` and `paid`; do not send “none”. |
| API product counts or missing data | Apply the policy’s **1–3** count. No recovery branch for out-of-scope or incomplete account data is supplied. |
| Literal `"credit card ending 4821"` versus returned `card_last4` | A17 and the code sheet prescribe the literal wording; B preserves unchanged wording. The API supplies a card-ending field but does not authorize rewriting the phrase. If the value differs from `4821`, the sources do not resolve that conflict. Do not silently treat the literal digits as a placeholder or knowingly state false account data. |
| A5’s speech restriction versus its callback question | Preserve the express opening, callback, deceased and closing requirements without disclosing account information. A4/A43 also remain applicable; no broader permission for substantive disclosure is inferred. |
| Person-confirmation matching | Only the specified phrases or the customer’s own name qualify. No detailed partial-name, recognition-error or alternative-phrase rule is supplied. |
| Spoken phone digits | The required result is a four-digit string. No detailed grouping, phonetic or ambiguous-word grammar is supplied. Do not infer missing digits. |
| Ambiguous dates or years | Numeric dates are day/month/year; submit `YYYY-MM-DD`. No ambiguous-year expansion rule is supplied. Do not guess missing information. |
| Calendar-week boundary | The sources do not define the first day of a calendar week. Monday–Friday business days do not establish a Monday–Sunday calendar week. No start-day convention is added. |
| Weekend/holiday adjustment beyond the deadline | No promise may be recorded beyond its deadline. The next-business-day offer does not waive A19; the sources provide no separate exception. |
| Invalid attempt-1 date | The prescribed last-business-day offer may be past or otherwise invalid for some supplied dates. No replacement formula is supplied. Do not record an invalid date or invent another persuasion allowance. |
| Initial today request on a non-business day | Keep B4’s initial request; any eventual promise must satisfy business-day and deadline rules. |
| Common-date adjustment and consent | B6 sets the adjusted date; B7 still requires read-back and a clear yes before recording. |
| Agent-originated amounts and customer proposals | A24 prohibits open-ended solicitation and governs agent proposals. A27 expressly permits accepting customer proposals in the stated inclusive range. |
| Amount above `past_due`, floor above `past_due`, or past date | No specific recovery offer, count or terminal reason is supplied. Do not invent one or claim that the API’s acceptance establishes policy permission. |
| Repeating the floor versus repeating refused offers | A26 expressly permits naming the floor again at attempt 2 on the deadline; A31 still prohibits repeating an offer already refused. The sources do not comprehensively define offer identity. Do not use an invented definition to override either requirement. |
| Notes versus later transfers | B10 prohibits notes anywhere on a transfer call. Retain reasons and defer actual note submissions until a non-transfer ending is determined; no note-deletion tool exists. |
| Hardship across multiple products | Hardship takes priority over persuasion and restructuring. The sources do not define allocation of a hardship statement whose product scope is unclear. |
| Twice declining conversation after verification | A45 requires ending the call. B’s aggregate disposition and recorded-promise precedence remain applicable. Existing product reasons must not be overwritten by an invented blanket `refused` rule. Allocation to unhandled products, or handling before account retrieval completes, is not fully specified. |
| Pending promises before support or human transfer | B10 expressly bars recording pending promises before restructuring. Support/human rules require their transfer and prohibit notes but do not separately describe pending-promise recording. No additional pre-transfer recording step is prescribed. |
| Error strings | `error` has no enum. `day_month_swapped` is a `hint` value, not an invented generic error code. |
| Failures outside `create_promise` | The API permits repeating a `500`; no fixed retry counts or terminal dispositions are supplied. Do not use `service_error` as a universal failure reason or claim success. |
| `close_call` failure and retry | A46 requires exactly one closing call and the API makes it last. Generic repeat permission does not require another invocation. Preserve exactly one call; further failed-close recovery is unspecified. |
| Customer callback, complaint, language, abuse or other vulnerability requests | No dedicated procedure or code is supplied. Apply an existing rule only when its trigger is met. |
| No callback time supplied | A7 defines one alternative after an out-of-window proposal, not a no-answer sequence. No extra count or mapping is supplied. |
| General one-question-at-a-time rule | The express rule concerns security questions only. |
| Currency, rounding, percentages, instalment counts, timezone or clock updates | No such rules are supplied. Do not add them. |

## 13. Verifier corrections

- Removed superseded numeric values from the override register; all operative occurrences now use the amended deadlines, product maximum and recording-failure limit.
- Removed the unsupported blanket rule that the API would override document policy in any conflict.
- Restored `"credit card ending 4821"` as literal source wording. Removed the invented authorization to substitute `card_last4`; conflicting returned digits are now explicitly unresolved.
- Removed the invented Monday–Sunday calendar-week convention.
- Removed blanket assignment of `refused` to every unpromised product after a general conversation refusal. Preserved established product reasons and identified the unspecified allocation to unhandled products.
- Removed the asserted universal amount ceiling as a separately stated source rule; retained the expressly accepted inclusive range and the unspecified treatment of higher proposals.
- Removed the invented definitive amount/date definition of an “offer”; retained both the permitted attempt-2 floor offer and the prohibition on repeating refused offers.
- Clarified Brief A-only wording and behavior versus Brief B replacements, including the exact single-product initial request and Brief A’s prohibition on `add_note`.
- Completed the API context concerning the hosted mock and scorer-read ledger, and corrected checklist attribution for product ordering.
- Retained the exact API fields, formats, enums, outcome/reason mappings, required phrases and all five holidays.