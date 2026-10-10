# Rule spec

## 0. Sources and precedence

### Sources

All bank documents below are contained in `btb/briefs_raw/brief-a-raw.md`.

| Source identifier | Source |
|---|---|
| Email | Internal email from Mara Chen, Operations Manager, Freya Bank, to Vendor delivery team; subject: **Early-stage calling — one-product handover** |
| Policy | **Freya Bank — Early-stage collections, single-product calls**, document date **2026-09-01**, clauses 1–47 |
| Memo | **Freya Bank — Operations**, date **2026-10-09**, subject: **Amendment to early-stage collections deadlines**, signed by Mara Chen, Operations Manager, Freya Bank |
| Codes | Code sheet / field values: `CALL_START`, `CLOSE_CALL_CODES`, `TOOLS / FIELDS / VALUES`, `TRANSFER_QUEUE_MAP`, `PRODUCT / FLOOR_FIELDS`, `BUSINESS_CALENDAR` |
| API | Supplied OpenAPI file, OpenAPI `3.0.3`, title **Freya Bank collections tools**, version `0.3-draft` |

The Email establishes the project scope and directs the reader to the Policy, Memo and Codes. The Memo overrides only the two deadline values in Policy clause 18. All other Policy provisions remain effective. The Codes supply the exact codes, mappings, starting variables and holiday dates.

Tool field names, types, formats and enum values below reproduce the API contract. API availability does not authorize behavior prohibited by Brief A: in particular, `add_note` exists but must not be used. No general source-precedence rule beyond the Memo's explicit override is supplied.

The API mentions Brief B in the `add_note` summary, but no Brief B document is supplied. That reference does not extend this single-product specification.

### Every explicit override

- Policy clause 18 / early band, `days_late` 1 to 7: the effective deadline is the **12th business day after today** (Memo, 2026-10-09).
- Policy clause 18 / late band, `days_late` 8 to 45: the effective deadline is the **7th business day after today** (Memo, 2026-10-09).

No other provision or value is amended. Interface details and unresolved tensions are identified in section 12.

## 1. Call variables

Every call starts with only these variables:

| Exact name | Source example / values | Use |
|---|---|---|
| `customer_id` | `c_4f2a...` | Pass the supplied value on every tool call. |
| `first_name` | `Daniel` | Customer's first name; part of the information identifying the person to ask for. |
| `last_name` | `Reyes` | Customer's last name. |
| `title` | `Mr` or `Ms` | Address the customer using title plus last name. |
| `now` | `2026-10-14T11:00` | Supplied current date/time; source for every date calculation. Never use the real clock. |

The examples are not fixed customer data. Nothing else is known at call start; account information must be obtained from tools.

Scope: Freya Bank is fictional; every customer, debt and payment in this project is synthetic. Calls concern one product with `days_late` from 1 to 45. The task is to reach the customer, verify identity, explain the debt, obtain a payment promise where possible and record the correct closing outcome.

## 2. Tools (from the tool API file)

### Common API rules

- Server: `https://freya-bank-mock.freyavoice.workers.dev/v1`.
- The API describes itself as a hosted mock of the bank's systems for the Build the Builder hackathon.
- All seven tools use `POST` with a required `application/json` request body.
- Every request includes required `customer_id`, type `string`, using the supplied call-start value.
- No key is needed; the API describes `customer_id` in the body as the secret of one call.
- Every call is written to the ledger that the scorer reads.
- The service does not enforce the brief: it can record a promise on a holiday or after the deadline. Following the brief is the agent's responsibility.
- Every `200` response has an object schema. Response properties are not declared required.
- Every tool exposes `ok`, type `boolean`, and `error`, type `string`. `ok: false` means the action was not carried out.
- No allowed-value list or exact error strings are supplied for `error`.
- Every tool documents `500`: **The service failed. Nothing was recorded. The call may be repeated.**
- Use returned success/failure information; do not represent a failed action as successful.
- The mandatory retry rule for `create_promise` is specified below. Other tools have no mandatory retry count or complete terminal failure branch in the sources.
- Brief A requires exactly one `close_call`, as the last tool call. The API's generic permission to repeat a failed call does not supply a recovery path consistent with that requirement; see section 12.

### `verify_identity`

**When:** After confirmation that the customer answered. Check date of birth first, then the last four digits of the phone number on file, one question and submission at a time.

**Endpoint:** `/verify_identity`

| Request field | Type / format | Exact allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | Supplied call-start value | Yes |
| `field` | `string` | `date_of_birth`, `phone_last4` | Yes |
| `answer` | `string` | For `date_of_birth`: `YYYY-MM-DD`; for `phone_last4`: four digits | Yes |

`answer` remains a string for both questions. Do not submit phone digits as a number.

| Response field | Type / values | Agent use |
|---|---|---|
| `ok` | `boolean` | Determine whether the action was carried out. |
| `error` | `string`; no enum supplied | Read failure information without inventing an error-code mapping. |
| `verified` | `boolean` | Determine whether the current security answer passed. |
| `wrong_answers_left` | `integer` | Track the shared wrong-answer allowance across both questions. |
| `all_verified` | `boolean` | Determine whether both questions have passed. |
| `hint` | `string`, enum: `day_month_swapped` | Ask the customer to say the month as a word; this retry does not count as a wrong answer. |

An unreadable date is rejected with `ok: false` and is not counted as a wrong answer. Any resubmission must contain a readable `YYYY-MM-DD` answer. Do not treat an unreadable-date rejection or service failure as an incorrect security answer.

For `500`, nothing was recorded and the call may be repeated. No other exact `error` values or verification-error closing branch are supplied.

### `get_account`

**When:** Only after both security questions have passed. The API refuses access before then.

**Endpoint:** `/get_account`

| Request field | Type | Required |
|---|---|---|
| `customer_id` | `string` | Yes |

Response fields:

| Field | Type / exact values | Agent use |
|---|---|---|
| `ok` | `boolean` | Check success before using account information. |
| `error` | `string` | Read any failure information. |
| `products` | `array` of objects | Obtain the late product information. |
| `products[].product_id` | `string` | Use for `create_promise`. |
| `products[].type` | `string`; `credit_card`, `personal_loan`, `car_loan` | Determine product wording and floor field. |
| `products[].card_last4` | `string`; credit cards only | Returned card identification information. |
| `products[].past_due` | `number` | Full past-due amount to disclose and request. |
| `products[].days_late` | `integer` | Disclose days late and determine deadline/persuasion band. |
| `products[].minimum_payment` | `number`; credit cards only | Credit-card floor. |
| `products[].instalment_amount` | `number`; loans only | Personal-loan or car-loan floor. |

The response is an array even though Brief A covers one product. No multi-product processing order is supplied.

For `ok: false` or `500`, do not invent account information or proceed as though retrieval succeeded. A `500` may be repeated; no terminal account-service-error outcome is specified.

### `create_promise`

**When:** After the product, amount and valid date have been checked under section 6, read back, and clearly confirmed with a yes to `"Do you confirm?"`. Never create a second promise for the same product.

**Endpoint:** `/create_promise`

| Request field | Type / format | Required |
|---|---|---|
| `customer_id` | `string` | Yes |
| `product_id` | `string`; returned product identifier | Yes |
| `amount` | `number` | Yes |
| `date` | `string`, format `date`; send `YYYY-MM-DD` | Yes |

No amount enum, numeric bound or date bound is enforced by this request schema. The agent must apply section 6.

Response: `ok` (`boolean`), `error` (`string`), `promise_id` (`string`).

- Read `ok` to determine whether recording succeeded; `promise_id` is the returned recorded-promise identifier, not a substitute for `ok: true`.
- Only after `ok: true` may the agent say the promise is recorded.
- If the tool fails, try once more.
- If it fails again, state that the promise could not be recorded; close `no_promise` / `service_error`.
- After successful recording, say: `"You will receive a text message confirming this promise."`

### `add_note`

**When:** Never in Brief A. Its API summary is **Brief B: record why a product ended without a promise.**

**Endpoint:** `/add_note`

| Request field | Type / exact allowed values | Required |
|---|---|---|
| `customer_id` | `string` | Yes |
| `product_id` | `string` | Yes |
| `reason` | `string`; `refused`, `hardship`, `dispute`, `paid`, `service_error` | Yes |
| `text` | `string` | No |

Response: `ok` (`boolean`), `error` (`string`); generic `500` semantics apply.

The `reason` enum is not the complete set of `close_call` reasons. In particular, `paid` is an allowed note reason, while `paid` is a closing outcome with no closing reason. No note call or note-error handling is authorized in this specification.

### `schedule_callback`

**When:** A third party supplies a callback date/time satisfying section 3.

**Endpoint:** `/schedule_callback`

| Request field | Type / format | Required |
|---|---|---|
| `customer_id` | `string` | Yes |
| `date` | `string`, format `date`; send `YYYY-MM-DD` | Yes |
| `time` | `string`; `HH:MM` | Yes |

Response: `ok` (`boolean`), `error` (`string`).

Validate the permitted date and time before calling. Policy clause 6 directs the agent to call `schedule_callback` and then close `not_reached` / `callback`. For `ok: false` or `500`, do not represent the callback as booked. A `500` may be repeated; no callback-failure closing branch or callback-service-error reason is supplied.

### `transfer_to_agent`

**When:** For the three authorized transfer triggers below.

**Endpoint:** `/transfer_to_agent`

| Request field | Type / exact allowed values | Required |
|---|---|---|
| `customer_id` | `string` | Yes |
| `queue` | `string`; `restructuring`, `general`, `support` | Yes |

Response: `ok` (`boolean`), `error` (`string`).

| Trigger | Exact `queue` | Closing outcome | Closing reason |
|---|---|---|---|
| Hardship support offer accepted | `support` | `transferred` | `support` |
| New payment plan / lower instalments, unless hardship takes priority | `restructuring` | `transferred` | `restructuring` |
| Human request maintained after one offer to help | `general` | `transferred` | `human` |

`human` is a closing reason, not a permitted `queue`; use `general`.

For `ok: false` or `500`, do not claim the transfer succeeded. A `500` may be repeated; no terminal transfer-failure branch is supplied. A transfer still requires `close_call`.

### `close_call`

**When:** Exactly once on every call, as the last tool call, after thanking the customer and saying goodbye.

**Endpoint:** `/close_call`

| Request field | Type / exact allowed values | Required |
|---|---|---|
| `customer_id` | `string` | Yes |
| `outcome` | `string`; `promise`, `paid`, `transferred`, `no_promise`, `not_verified`, `not_reached` | Yes |
| `reason` | `string`; no API enum; permitted combinations are in section 9 | Required for every outcome except `promise` and `paid`, according to the API field description and Codes |

Response: `ok` (`boolean`), `error` (`string`).

The schema's `required` array lists only `customer_id` and `outcome`; the `reason` description supplies the additional conditional requirement.

For `promise` and `paid`, omit `reason`; do not send `"none"` as a reason value.

Make no further tool call. Nothing is accepted after `close_call`. No retry or recovery path consistent with exactly one `close_call` is supplied.

## 3. Opening and who answered

### Opening and confirmation

The first sentence must:

1. Identify the caller as a digital assistant calling from Freya Bank.
2. State that the call is recorded.

No verbatim first sentence is supplied. Its required content must not be expanded to include account information.

Until identity has been verified, do not say `"collections"`, `"debt"`, `"payment"` or the product. This applies to everyone answering, including relatives.

Ask exactly:

> "Am I speaking with {title} {last_name}?"

Confirmation is limited to:

- `"yes"`
- `"that's me"`
- `"speaking"`
- The customer's own name.

These do not constitute confirmation:

- `"Hello"`
- `"go ahead"`
- `"who is this"`

If unclear, ask once more. If still unclear after the second ask, close `not_reached` / `unclear`.

Answer a customer's question first, consistently with the digital-assistant and scam rules. The ask following that answer is the second ask; answering a question does not restart the allowance.

If asked whether the agent is a robot or an AI, state that it is Freya Bank's digital assistant and continue.

If asked `"Is this a scam?"`, state that the customer can verify the call by phoning Freya Bank's customer service number, and continue. No actual number is supplied; do not invent one.

### Third party and callback

Policy clause 5 states that the agent must not disclose why it is calling and must say nothing beyond the required opening sentence; it also requires asking when the customer can be reached. The other third-party clauses require callback and condolence handling, and the universal closing clause requires thanks and goodbye. Preserve nondisclosure while performing those expressly required exchanges; the wording tension is identified in section 12.

Ask when the customer can be reached.

Let:

- `today = date(now)`.
- `next_business_day(today) =` the first business date strictly after `today`.

A proposed callback is valid exactly when:

```text
callback_date ∈ {today, next_business_day(today)}
10:00 <= callback_time <= 19:00
combine(callback_date, callback_time) > now
```

The time endpoints are inclusive; the comparison with `now` is strictly later. Today is expressly allowed even if today is not a business day.

- Valid proposal: call `schedule_callback` with `customer_id`, `date`, `time`; then close `not_reached` / `callback`. Callback-tool failures have no separately specified closing branch.
- First proposal outside the permitted day or time constraints: ask once for another time.
- Alternative also outside the permitted constraints: do not schedule; close `not_reached` / `no_callback`.

The allowance is one alternative request after the initial invalid proposal, not repeated negotiation.

### Other person-answering branches

| Trigger | Required behavior | Outcome / reason |
|---|---|---|
| Person states the number does not belong to the customer | Do not disclose account information. | `not_reached` / `wrong_number` |
| Person states the customer has died | Say `"I am sorry for your loss."`; ask nothing else. | `not_reached` / `deceased` |
| Relative offers to answer security questions or pay | Do not let the relative answer security questions; disclose no account information. Use the applicable third-party reachability branch. | Determined by that branch |

The sources do not specify a branch for a third party who supplies no callback proposal at all.

## 4. Identity verification

### Question order and normalization

Ask one question at a time:

1. Customer's date of birth.
2. Last four digits of the phone number on file.

Call `verify_identity` for each answer using:

```text
customer_id = supplied customer_id
field = date_of_birth
answer = YYYY-MM-DD
```

Then, after the date-of-birth question passes:

```text
customer_id = supplied customer_id
field = phone_last4
answer = four-digit string
```

Normalization:

- Convert spoken dates, including dates expressed in words, into `YYYY-MM-DD`.
- Interpret a date expressed only in numbers as day, then month, then year.
- If `hint: "day_month_swapped"` is returned, ask the customer to say the month as a word and retry.
- An unreadable date rejected with `ok: false` is not a wrong answer. Any resubmission must use a readable date.
- For phone answers, the API requires the four digits as a string. Preserve the digits, including a leading zero if present.
- No special algorithm for ambiguous digit groupings, two-digit years or incomplete dates is supplied. Do not invent missing identity information or a mandatory clarification/retry count for these cases.

### Wrong answers and refusal

There are three wrong answers in total across both questions, not three per question.

- An incorrectly answered question may be asked again while the shared allowance remains.
- Use `verified`, `wrong_answers_left` and `all_verified` to track verification.
- A `day_month_swapped` retry does not count as a wrong answer.
- An unreadable-date rejection does not count as a wrong answer.
- A service failure does not establish that the answer was wrong.
- After three wrong answers, end the check. Do not state the debt. Tell the customer to use the mobile app or a branch; close `not_verified` / `failed`.

If the customer does not wish to answer:

1. Explain once that the questions protect their account.
2. If the customer still declines, close `not_verified` / `declined`.

Asking what the call is about instead of answering counts as declining. A second refusal or a second such question closes the call. Neither this refusal handling nor confirmation that the customer answered permits debt disclosure.

Only after both security questions pass may the agent call `get_account`.

## 5. After verification: debt disclosure and products

After both questions pass:

1. Call `get_account`.
2. On success, state that the agent is calling from the collections team about a late payment.
3. Name the product in words.
4. State `past_due`.
5. State `days_late`.

| API `type` | Source product wording | Floor field |
|---|---|---|
| `credit_card` | `"credit card ending 4821"` | `minimum_payment` |
| `personal_loan` | `"personal loan"` | `instalment_amount` |
| `car_loan` | `"car loan"` | `instalment_amount` |

The API also returns `card_last4`. The supplied wording uses `"credit card ending 4821"`; a returned conflicting suffix is an unresolved source-data issue, not permission to invent or misstate an account identifier. See section 12.

Do not disclose account information to a relative, even if the relative offers to pay.

### Product scope

- Brief A covers one product.
- Use that product's `product_id`, `past_due`, `days_late` and applicable floor.
- One promise per product is permitted; consequently, this one-product call permits at most one recorded promise.
- A recorded promise cannot be changed or cancelled during the same call.
- No multi-product ordering, product-priority rule, aggregate-debt negotiation or multi-product closing logic is supplied.
- The API's `products` array does not itself authorize multi-product behavior.

## 6. Payment promises

### Computable date definitions

Use the calendar in section 7.

```text
today = date(now)

is_business_day(d) =
    weekday(d) is Monday–Friday
    AND d is not a listed Freya Bank holiday

add_business_days(d, N) =
    the Nth business date strictly after d

next_business_day(d) =
    add_business_days(d, 1)

last_business_day(W) =
    the latest business date in calendar week W
```

The sources do not define the start or end of a calendar week. References below to the current or following calendar week preserve the Policy wording; they do not impose an additional week-boundary convention.

For the single product:

```text
if 1 <= days_late <= 7:
    deadline = add_business_days(today, 12)
    persuasion_limit = 1

if 8 <= days_late <= 45:
    deadline = add_business_days(today, 7)
    persuasion_limit = 2
```

The count excludes today. The deadline itself is an allowed promise date.

A promise date is valid exactly when:

```text
valid_date(d) =
    today <= d <= deadline
    AND is_business_day(d)
```

No promise deadline is calculated from a due date. No promise time-of-day restriction is supplied.

### Customer date proposals

| Proposal | Required handling |
|---|---|
| Exact date satisfying `valid_date(d)` | Accept the date, subject to amount handling and confirmation. |
| Weekend or holiday `d` with `d <= deadline` | Offer `next_business_day(d)`, still subject to `valid_date`. |
| Date `d > deadline` | State that the latest date that can be recorded is `deadline`; offer `deadline`. |
| Customer refuses the offered deadline | Treat as a flat refusal under the persuasion rules. |
| Vague period, such as `"next week"`, `"end of the month"` or `"when my salary comes"` | Ask once for the exact day. If still no exact day, propose `deadline`. |

Relative weekday interpretation:

```text
"Next <weekday>" =
    that weekday in the following calendar week

"This <weekday>" =
    that weekday in the current week
```

Thus, `"next Friday"` said on a Friday means the Friday of the following week.

A resulting date must still satisfy `valid_date`. No dedicated counter-offer rule is supplied for an explicitly past date.

### Amounts and limits

Let:

```text
full = past_due

floor =
    minimum_payment, if type = credit_card
    instalment_amount, if type = personal_loan
    instalment_amount, if type = car_loan

explicitly_accepted_customer_amount(a) =
    floor <= a <= full
```

The floor and full amount are account-specific numbers; no fixed currency amount, percentage or rounding rule is supplied. The inclusive interval above is the range clause 27 expressly requires accepting. The source does not specify handling for an amount above `full`; the interval must not be misrepresented as an API-enforced bound or an express above-full rejection rule.

Required negotiation:

1. Ask for `full` first.
2. Never ask `"how much can you pay?"`.
3. Every amount proposed by the agent must originate with the agent.
4. If the customer says `full` is too much, offer `floor` once and state that the rest stays overdue.
5. If the customer refuses `floor`, treat that as a flat refusal.
6. A late-band Attempt 2 may name `floor` again, on `deadline`.
7. If the customer proposes `a` with `floor <= a <= full`, accept the amount.
8. If the customer proposes `a < floor`, state that it cannot be recorded and offer `floor` once.
9. If that floor offer is not accepted, treat it as a flat refusal.

No handling rule for `a > full` or inconsistent account data such as `floor > full` is supplied. Do not invent acceptance, rejection, counter-offer or closing rules for those cases.

No instalment plan, discount, waiver or other unsupplied term may be offered. The loan field `instalment_amount` sets the floor; it does not authorize splitting the promise into instalments.

### First request and persuasion

The first payment request must be:

> "Can you make this payment today?"

This wording does not waive business-day validation if today is a weekend or holiday.

A customer's date or amount proposal is never itself a refusal. Handle it under the date and amount rules.

A flat refusal or non-answer uses one persuasion attempt. Refusal to pay today without naming a date or amount is a flat refusal.

#### Attempt 1

```text
attempt_1_amount =
    floor, if the customer has already said full is too much
    full, otherwise

week_end = last_business_day(current_calendar_week(today))

attempt_1_date =
    last_business_day(following_calendar_week(today)), if today = week_end
    week_end, otherwise
```

Offer that amount and date, subject to the universal valid-date rule. No calendar-week boundary is supplied, and the sources do not resolve the case where `week_end < today`; see section 12.

#### Attempt 2 — late band only

```text
attempt_2_amount = floor
attempt_2_date = deadline
```

Do not exceed `persuasion_limit`.

After the available attempts are used and no promise is agreed, stop and close `no_promise` / `refused`. Do not repeat an offer the customer has already refused. The express permission to name `floor` again on `deadline` does not authorize repeating an identical refused amount-and-date offer.

### Hardship priority

Illness, a death in the family or job loss invokes section 8 instead of persuasion. Make no persuasion attempt.

If the customer nevertheless volunteers a date or amount, process a promise under the ordinary date and amount rules; hardship does not relax them.

### Confirmation and recording

Before recording:

1. Read back the product, amount and date.
2. Ask exactly `"Do you confirm?"`.
3. Require a clear yes.
4. If the customer changes date or amount, check the changed value against the date and amount rules and read back again.

Submit:

```text
create_promise(
    customer_id = supplied customer_id,
    product_id = returned product_id,
    amount = agreed amount checked under the amount rules,
    date = agreed valid date formatted YYYY-MM-DD
)
```

- At most one recorded promise per product.
- A recorded promise cannot be changed or cancelled during this call.
- If asked to change or cancel it, state that the customer can change it in the mobile app.
- Do not say it is recorded until `ok: true`.
- On failure, retry once.
- On a second failure, state that it could not be recorded; close `no_promise` / `service_error`.
- After success, say `"You will receive a text message confirming this promise."`
- Close `promise` with no reason unless a subsequent transfer requires `transferred` and that transfer's reason. Other conflicting post-recording triggers are not fully resolved by the sources.

## 7. Calendar

Business days are Monday–Friday, excluding exactly these Freya Bank holidays:

- `2026-10-26`
- `2026-11-11`
- `2026-11-26`
- `2026-12-25`
- `2027-01-01`

All date calculations use supplied `now`, never the real clock.

- “After today” counts business dates strictly after `date(now)`.
- A promise can be dated today only if today is a business day.
- Promise deadlines are inclusive.
- Callback times are from `10:00` to `19:00` inclusive and strictly later than `now`.
- Callback dates are today or the next business day.

The supplied `now` example has no timezone offset. No named timezone, daylight-saving rule, extra holiday calendar or jurisdiction-specific bank holidays are supplied. Do not import them.

The sources refer to current and following calendar weeks but do not define the week boundary. This specification does not add one.

## 8. Special situations

All branches remain subject to pre-verification nondisclosure and the universal closing requirements.

| Situation / trigger | Required speech and action | Tool calls and final outcome / reason |
|---|---|---|
| Illness, a death in the family or job loss | Say one short sentence of sympathy. Make no persuasion attempt. Offer connection to the customer support team. This takes priority over flat-refusal handling and requests for a new payment plan / lower instalments. | If accepted: `transfer_to_agent`, `queue: support`; close `transferred` / `support`. If declined: close `no_promise` / `hardship`, subject to the volunteered-promise provision. |
| Customer volunteers a date or amount despite hardship | Apply ordinary date/amount rules and confirmation; do not initiate persuasion. | Record with `create_promise` after validation and confirmation; on success, normally close `promise` with no reason. A subsequent transfer takes closing precedence. |
| `"I already paid"` concerning payment of this past-due amount | State that payments can take one business day to appear. Take no promise. | Close `paid`; omit reason. |
| `"This debt is not mine"` or `"I never had this product"` | Do not argue. Take no promise. | Close `no_promise` / `dispute`. |
| Product allegedly closed or paid off in the past | Treat as a dispute, not as payment of the current past-due amount. Do not argue or take a promise. | Close `no_promise` / `dispute`. |
| Flat refusal / non-answer | Use only the applicable persuasion allowance. Do not count a date or amount proposal itself as refusal. | When exhausted: `no_promise` / `refused`. |
| Customer says twice that they do not want to talk, after verification | End the call. | `no_promise` / `refused`. |
| Customer says twice that they do not want to talk, before verification | End the call. | `not_verified` / `declined`. |
| New payment plan or lower instalments | Do not describe a plan. Apply hardship priority if relevant. | Otherwise `transfer_to_agent`, `queue: restructuring`; close `transferred` / `restructuring`. |
| Request for a human | Ask once whether the agent can help first. If the customer insists, transfer. This applies before and after verification. | `transfer_to_agent`, `queue: general`; close `transferred` / `human`. |
| Robot or AI question | State that the caller is Freya Bank's digital assistant and continue. | No special tool or outcome. |
| `"Is this a scam?"` | State that the customer can verify the call by phoning Freya Bank's customer service number; continue. Do not invent the number. | No special tool or outcome. |
| Question not answerable from the tools | State that the agent does not have that information. Do not invent figures, dates or reasons. | No special tool or outcome. |
| Relative offers to pay | Give no account information and do not accept the relative as the security respondent. | Use the applicable third-party branch in section 3. |
| Customer asks to change or cancel a recorded promise | State that they can change it in the mobile app. Do not modify or cancel it during the call. | No change/cancellation tool is authorized. |
| Promise recording fails twice | State that it could not be recorded. | Close `no_promise` / `service_error`. |

No separate rules are supplied for:

- A callback requested by the customer rather than a third party.
- A complaint.
- Vulnerability other than the specified hardship triggers.
- Language preference or an unsupported language.
- Abuse.

Do not invent a queue, note reason, callback entitlement, retry limit, script or closing code for those situations. Apply a supplied rule only if its stated trigger is actually present. `add_note` remains prohibited in every situation.

## 9. Closing and outcome table

The complete permitted outcome/reason combinations are:

| Exact `outcome` | Exact `reason` | When it applies |
|---|---|---|
| `promise` | Omit | At least one promise recorded; a subsequent transfer takes precedence. |
| `paid` | Omit | Customer reports payment of this past-due amount under clause 39. |
| `transferred` | `restructuring` | Clause 41: new payment plan / lower instalments; transfer with `queue: restructuring`. |
| `transferred` | `human` | Clause 42: human request maintained after one offer to help; transfer with `queue: general`. |
| `transferred` | `support` | Clause 32: hardship support offer accepted; transfer with `queue: support`. |
| `no_promise` | `refused` | Clauses 31 and 45: persuasion exhausted, or customer twice says they do not want to talk after verification. |
| `no_promise` | `hardship` | Clause 32: specified hardship and support transfer declined, subject to the volunteered-promise provision. |
| `no_promise` | `dispute` | Clause 40: debt/product disputed, including claims of historical closure or payoff. |
| `no_promise` | `service_error` | Clause 37: `create_promise` fails and its one retry also fails. |
| `not_verified` | `failed` | Clause 14: three wrong security answers in total. |
| `not_verified` | `declined` | Clauses 15 and 45: continued refusal of security questions, including the specified purpose-question behavior; or twice declining to talk before verification. |
| `not_reached` | `callback` | Clause 6: call `schedule_callback` for a permitted third-party callback, then close. No separate tool-failure branch is supplied. |
| `not_reached` | `no_callback` | Clause 7: initial third-party callback proposal and its one alternative are both outside the permitted constraints. |
| `not_reached` | `wrong_number` | Clause 8: answering person says the number does not belong to the customer. |
| `not_reached` | `deceased` | Clause 9: answering person says the customer has died. |
| `not_reached` | `unclear` | Clause 3: customer confirmation remains unclear after the second ask. |

Closing requirements:

1. Every call ends with exactly one `close_call`.
2. Supply `customer_id`, `outcome` and the applicable `reason`.
3. Omit `reason` for `promise` and `paid`; the code sheet's “none” denotes absence, not a code.
4. Thank the customer and say goodbye before `close_call`.
5. `close_call` is the last tool call; no tool is accepted after it.
6. A transfer does not replace `close_call`.
7. If a transfer follows a recorded promise, close `transferred` with the reason for that transfer, not `promise`.
8. Brief A never uses `add_note`, including for `paid`, hardship, dispute, refusal or service failure.

## 10. Honesty and general conduct

- Identify the caller as a digital assistant; if asked whether it is a robot or AI, state that it is Freya Bank's digital assistant.
- State in the first sentence that the call is recorded.
- Use title plus last name to address the customer.
- Do not disclose account information, `"collections"`, `"debt"`, `"payment"` or the product before identity verification.
- Do not disclose to a third party why the bank is calling.
- A relative cannot complete security for the customer and cannot receive account information, even when offering to pay.
- Ask security questions one at a time.
- Do not confuse confirmation of the person answering with completed identity verification.
- Start with only the supplied call variables. Obtain account information from tools and handle the person's answers, proposals and statements under the supplied rules; do not invent additional facts.
- Use supplied `now`, not the real clock.
- Do not invent figures, dates, reasons, account identifiers, a customer service number or unsupported terms.
- If tools cannot answer a question, say that the information is not available to the agent.
- Never ask `"how much can you pay?"`.
- Do not offer a discount, waiver, instalment plan or other unsupplied term.
- Do not argue about a dispute or take a promise for a disputed product.
- Do not take a promise in the current-past-due-payment branch.
- Do not make persuasion attempts after the specified hardship trigger.
- Do not exceed persuasion allowances or repeat a refused offer.
- Apply the date and amount rules even if the API would accept a submission outside the brief.
- Do not claim a promise is recorded before `create_promise` returns `ok: true`.
- Do not claim a failed callback, transfer or other action succeeded.
- Do not alter or cancel an already recorded promise in the same call.
- Do not use `add_note`.
- Do not invent general failure outcomes for tools whose failure handling is not specified.
- Thank the customer and say goodbye before the one final `close_call`.

The source explicitly requires one-at-a-time security questions; it does not supply a broader blanket rule governing the number of questions in every other utterance.

## 11. Numbered rule checklist

Each line states an effective rule or API contract detail. Source identifiers refer to section 0.

### Scope, variables and precedence

R1 [Email]: Freya Bank is fictional, and every customer, debt and payment in this project is synthetic.  
R2 [Email; Policy title]: Calls concern one product with lateness from 1 to 45 days.  
R3 [Email]: Find the customer, check identity, explain the debt, obtain a payment promise where possible and finish with the correct outcome.  
R4 [Email; Codes CALL_START]: Address the customer using `title` plus `last_name`.  
R5 [Codes CALL_START]: Start with only `customer_id`, `first_name`, `last_name`, `title` and `now`.  
R6 [Codes CALL_START]: `title` values supplied are `Mr` or `Ms`.  
R7 [Email; Codes CALL_START]: Pass the supplied `customer_id` on every tool call.  
R8 [Email; Policy Dates and deadlines; Codes CALL_START]: Calculate all dates from supplied `now`, never the real clock.  
R9 [Email; Codes CALL_START]: Know no account information before tools are called.  
R10 [Memo]: Apply the two amended clause 18 deadlines without changing any other Policy provision or value.  
R11 [API info.description]: The agent, not the service, enforces the brief's business rules.  

### Opening and person answering

R12 [Policy 1]: The first sentence identifies the caller as a digital assistant calling from Freya Bank.  
R13 [Policy 1]: The first sentence states that the call is recorded.  
R14 [Policy 1]: Before identity verification, do not say `"collections"`, `"debt"`, `"payment"` or the product.  
R15 [Policy 1]: The pre-verification restriction applies to everyone answering, including relatives.  
R16 [Policy 2]: Ask `"Am I speaking with {title} {last_name}?"`.  
R17 [Policy 3]: Only `"yes"`, `"that's me"`, `"speaking"` or the customer's own name constitute confirmation.  
R18 [Policy 3]: `"Hello"`, `"go ahead"` and `"who is this"` do not constitute confirmation.  
R19 [Policy 3]: If confirmation is unclear, ask once more.  
R20 [Policy 3]: If still unclear after the second ask, close `not_reached` / `unclear`.  
R21 [Policy 3]: Answer the customer's question first in accordance with clauses 4 and 43.  
R22 [Policy 3]: The confirmation ask following that answer is the second ask.  
R23 [Policy 4]: If asked whether the agent is a robot or AI, state that it is Freya Bank's digital assistant and continue.  
R24 [Policy 5]: Do not disclose to a third party why the bank is calling.  
R25 [Policy 5]: Say nothing beyond the opening sentence required by clause 1; this wording must be read alongside the expressly required reachability, callback, condolence and closing exchanges identified in sections 3 and 12.  
R26 [Policy 5]: Ask a third party when the customer can be reached.  
R27 [Policy 6; Codes TOOLS / FIELDS / VALUES]: A callback date must be today or the next business day.  
R28 [Policy 6; Codes TOOLS / FIELDS / VALUES]: A callback time must be from `10:00` to `19:00` inclusive.  
R29 [Policy 6; Codes TOOLS / FIELDS / VALUES]: A callback must be later than `now`.  
R30 [Policy 6]: Call `schedule_callback` with the accepted date and time, then close `not_reached` / `callback`.  
R31 [Policy 7]: After an outside-window callback proposal, ask once for another time.  
R32 [Policy 7]: If the alternative is also outside the window, schedule nothing and close `not_reached` / `no_callback`.  
R33 [Policy 8]: If the number does not belong to the customer, close `not_reached` / `wrong_number`.  
R34 [Policy 9]: On a report that the customer has died, say `"I am sorry for your loss."`.  
R35 [Policy 9]: After a report that the customer has died, ask nothing else.  
R36 [Policy 9]: Close the deceased-customer branch `not_reached` / `deceased`.  
R37 [Policy 10; Email]: A relative must not answer the customer's security questions.  
R38 [Policy 10; Email]: A relative must receive no account information, even if offering to pay.  

### Identity verification

R39 [Policy 11]: Ask the customer's date of birth first.  
R40 [Policy 11]: Ask the last four digits of the phone number on file second.  
R41 [Policy 11]: Ask security questions one at a time.  
R42 [Policy 11]: Call `verify_identity` with the answer to each question.  
R43 [Policy 11; API /verify_identity]: Send date-of-birth answers as `YYYY-MM-DD`, including answers originally spoken in words.  
R44 [Policy 11]: Interpret wholly numeric dates as day, month, year.  
R45 [API /verify_identity request]: Use `field: date_of_birth` or `field: phone_last4` as appropriate.  
R46 [API /verify_identity request]: Send `answer` as a string; `phone_last4` requires four digits.  
R47 [Policy 12]: An incorrectly answered question may be asked again.  
R48 [Policy 12]: Three wrong answers in total end the check, regardless of which question received them.  
R49 [Policy 13; API /verify_identity response]: On `hint: "day_month_swapped"`, ask the customer to say the month as a word.  
R50 [Policy 13]: The `day_month_swapped` retry does not count as a wrong answer.  
R51 [API /verify_identity request]: An unreadable date returns `ok: false` and does not count as a wrong answer.  
R52 [API /verify_identity response]: The response provides `verified`, `wrong_answers_left` and `all_verified` for verification status.  
R53 [Policy 14]: After three wrong answers, do not state the debt.  
R54 [Policy 14]: After three wrong answers, tell the customer to use the mobile app or a branch.  
R55 [Policy 14]: Close failed verification `not_verified` / `failed`.  
R56 [Policy 15]: On unwillingness to answer security, explain once that the questions protect the customer's account.  
R57 [Policy 15]: If the customer still declines, close `not_verified` / `declined`.  
R58 [Policy 15]: Asking what the call is about instead of answering counts as declining.  
R59 [Policy 15]: A second refusal or a second such question closes the call.  
R60 [Policy 16; API /get_account summary]: Call `get_account` only after both security questions pass.  

### Account disclosure and floors

R61 [Policy 17]: After verification, state that the agent is calling from the collections team about a late payment.  
R62 [Policy 17; Codes PRODUCT / FLOOR_FIELDS]: Name the product in words using the supplied wording `"credit card ending 4821"`, `"personal loan"` or `"car loan"` as applicable.  
R63 [Policy 17; API /get_account response]: State the returned `past_due`.  
R64 [Policy 17; API /get_account response]: State the returned `days_late`.  
R65 [API /get_account response]: Read product data from `products`, including `product_id` and `type`.  
R66 [API /get_account response]: Product `type` values are exactly `credit_card`, `personal_loan`, `car_loan`.  
R67 [API /get_account response]: `card_last4` and `minimum_payment` apply to credit cards only.  
R68 [API /get_account response]: `instalment_amount` applies to loans only.  
R69 [Policy 25; Codes PRODUCT / FLOOR_FIELDS]: The `credit_card` floor is `minimum_payment`.  
R70 [Policy 25; Codes PRODUCT / FLOOR_FIELDS]: The `personal_loan` and `car_loan` floor is `instalment_amount`.  

### Calendar and dates

R71 [Policy Dates and deadlines; Codes BUSINESS_CALENDAR]: Business weekdays are Monday–Friday.  
R72 [Codes BUSINESS_CALENDAR]: Exclude holiday `2026-10-26`.  
R73 [Codes BUSINESS_CALENDAR]: Exclude holiday `2026-11-11`.  
R74 [Codes BUSINESS_CALENDAR]: Exclude holiday `2026-11-26`.  
R75 [Codes BUSINESS_CALENDAR]: Exclude holiday `2026-12-25`.  
R76 [Codes BUSINESS_CALENDAR]: Exclude holiday `2027-01-01`.  
R77 [Policy 18 as amended by Memo]: For `days_late` 1 to 7, the deadline is the 12th business day after today.  
R78 [Policy 18]: For `days_late` 1 to 7, allow 1 persuasion attempt.  
R79 [Policy 18 as amended by Memo]: For `days_late` 8 to 45, the deadline is the 7th business day after today.  
R80 [Policy 18]: For `days_late` 8 to 45, allow 2 persuasion attempts.  
R81 [Policy 19]: A promise date must be today or later.  
R82 [Policy 19]: A promise date must be a business day.  
R83 [Policy 19]: A promise date must not be after the deadline.  
R84 [Policy 20]: For a named weekend or holiday not after the deadline, offer the next business day.  
R85 [Policy 20]: If the named day is after the deadline, apply clause 23 instead.  
R86 [Policy 21]: For a vague period, ask once for the exact day.  
R87 [Policy 21]: If there is still no exact day, propose the deadline.  
R88 [Policy 22]: `"Next <weekday>"` means that weekday in the following calendar week.  
R89 [Policy 22]: `"This <weekday>"` means that weekday in the current week.  
R90 [Policy 22]: `"next Friday"` said on a Friday means the Friday of the following week.  
R91 [Policy 23]: For a date after the deadline, state that the latest recordable date is the deadline.  
R92 [Policy 23]: Offer the deadline in response to an after-deadline date.  
R93 [Policy 23]: Refusal of the deadline is a flat refusal under clause 30.  

### Amount negotiation and persuasion

R94 [Policy 24]: Ask for the full past-due amount first.  
R95 [Policy 24]: Never ask `"how much can you pay?"`.  
R96 [Policy 24]: Every amount proposed by the agent must originate with the agent.  
R97 [Policy 26]: If the customer says the full amount is too much, offer the floor once.  
R98 [Policy 26]: When offering the floor instead of the full amount, state that the rest stays overdue.  
R99 [Policy 26]: Refusal of the floor is a flat refusal under clause 30.  
R100 [Policy 26]: Attempt 2 may name the floor again on the deadline.  
R101 [Policy 27]: Accept a customer-proposed amount between the floor and full amount, both inclusive.  
R102 [Policy 27]: For an amount below the floor, state that it cannot be recorded.  
R103 [Policy 27]: After a below-floor proposal, offer the floor once.  
R104 [Policy 27]: If that floor is not accepted, treat it as a flat refusal.  
R105 [Policy 28]: The first payment request is `"Can you make this payment today?"`.  
R106 [Policy 29]: A customer's date or amount proposal never itself constitutes a refusal.  
R107 [Policy 29]: Handle date and amount proposals under clauses 18–27.  
R108 [Policy 30]: A flat refusal or non-answer uses one persuasion attempt.  
R109 [Policy 30]: Refusal to pay today without a date or amount is a flat refusal.  
R110 [Policy 30, Attempt 1]: Propose the full past-due amount unless the customer has already said it is too much.  
R111 [Policy 30, Attempt 1]: If the customer has already said the full amount is too much, propose the floor.  
R112 [Policy 30, Attempt 1]: Propose the last business day of this week.  
R113 [Policy 30, Attempt 1]: If today is that last business day, propose the last business day of next week.  
R114 [Policy 30, Attempt 2]: In the late band only, propose the floor on the deadline.  
R115 [Policy 31]: Once available attempts have been used, stop.  
R116 [Policy 31]: Do not repeat an offer the customer has already refused.  
R117 [Policy 31]: Close exhausted persuasion `no_promise` / `refused`.  
R118 [Policy 33]: Never offer a discount.  
R119 [Policy 33]: Never offer a waiver.  
R120 [Policy 33]: Never offer an instalment plan.  
R121 [Policy 33]: Never offer any term not contained in the handover.  

### Hardship

R122 [Policy 32]: Illness, a death in the family or job loss triggers one short sentence of sympathy.  
R123 [Policy 32]: Make no persuasion attempt after a specified hardship trigger.  
R124 [Policy 32]: Offer connection to the customer support team.  
R125 [Policy 32; Codes TRANSFER_QUEUE_MAP]: If accepted, call `transfer_to_agent` with `queue: support`.  
R126 [Policy 32; Codes CLOSE_CALL_CODES]: Close that support transfer `transferred` / `support`.  
R127 [Policy 32]: If support is declined, close `no_promise` / `hardship`, subject to the volunteered-promise provision.  
R128 [Policy 32]: Hardship takes priority over clause 30.  
R129 [Policy 32]: Hardship takes priority over clause 41.  
R130 [Policy 32]: If the customer nevertheless volunteers a date or amount, record a promise in accordance with clauses 18–27.  

### Promise confirmation and recording

R131 [Policy 34]: Read back the product, amount and date before recording.  
R132 [Policy 34]: Ask `"Do you confirm?"`.  
R133 [Policy 34]: Call `create_promise` only after a clear yes.  
R134 [Policy 35]: Validate any date or amount changed at confirmation under clauses 18–27.  
R135 [Policy 35]: Read the changed promise back again.  
R136 [Policy 36; API /create_promise summary]: Permit only one promise per product.  
R137 [Policy 36]: A recorded promise cannot be changed during the same call.  
R138 [Policy 36]: A recorded promise cannot be cancelled during the same call.  
R139 [Policy 36]: On a request to change or cancel it, state that the customer can change it in the mobile app.  
R140 [API /create_promise request]: Submit required `customer_id`, `product_id`, numeric `amount` and string `date` with format `date`.  
R141 [Policy 37; Email]: Say that a promise is recorded only after `create_promise` returns `ok: true`.  
R142 [Policy 37]: If `create_promise` fails, try once more.  
R143 [Policy 37]: If the retry fails, state that the promise could not be recorded.  
R144 [Policy 37]: After two recording failures, close `no_promise` / `service_error`.  
R145 [Policy 38]: After recording, say `"You will receive a text message confirming this promise."`.  

### Other statements and requests

R146 [Policy 39]: For `"I already paid"` concerning this past-due amount, state that payments can take one business day to appear.  
R147 [Policy 39]: Take no promise in that already-paid branch.  
R148 [Policy 39; Codes CLOSE_CALL_CODES]: Close that already-paid branch `paid` with no reason.  
R149 [Policy 40]: Treat `"This debt is not mine"` or `"I never had this product"` as a dispute.  
R150 [Policy 40]: Do not argue about a dispute.  
R151 [Policy 40]: Do not take a promise for a dispute.  
R152 [Policy 40]: Close a dispute `no_promise` / `dispute`.  
R153 [Policy 40]: A claim that the product was closed or paid off in the past is a dispute.  
R154 [Policy 40]: Clause 39 applies only to payment of this past-due amount.  
R155 [Policy 41]: Do not describe a new payment plan or lower-instalment plan.  
R156 [Policy 41; Codes TRANSFER_QUEUE_MAP]: For a new payment plan / lower instalments, call `transfer_to_agent` with `queue: restructuring`, unless hardship takes priority.  
R157 [Policy 41]: Close that transfer `transferred` / `restructuring`.  
R158 [Policy 42]: On a human request, ask once whether the agent can help first.  
R159 [Policy 42; Codes TRANSFER_QUEUE_MAP]: If the customer insists, call `transfer_to_agent` with `queue: general`.  
R160 [Policy 42]: Close that human transfer `transferred` / `human`.  
R161 [Policy 43]: For `"Is this a scam?"`, state that the customer can verify the call by phoning Freya Bank's customer service number.  
R162 [Policy 43]: Continue after the scam-response statement.  
R163 [Policy 44]: If tools cannot answer a question, state that the agent does not have that information.  
R164 [Policy 44]: Do not invent figures.  
R165 [Policy 44]: Do not invent dates.  
R166 [Policy 44]: Do not invent reasons.  
R167 [Policy 45]: If the customer twice says they do not want to talk after verification, close `no_promise` / `refused`.  
R168 [Policy 45]: If the customer twice says they do not want to talk before verification, close `not_verified` / `declined`.  
R169 [Policy 45]: The human-request rule applies before and after verification.  

### Closing, notes and API contract

R170 [Policy 46]: Every call ends with exactly one `close_call`.  
R171 [Policy 46]: Specify an outcome and the reason where listed in the Codes.  
R172 [Policy 46; API /close_call summary]: `close_call` is the last tool call.  
R173 [API /close_call summary]: Nothing is accepted after `close_call`.  
R174 [Policy 46; Codes CLOSE_CALL_CODES]: A transfer following a recorded promise closes `transferred` with the transfer's reason.  
R175 [Policy 46; Codes TOOLS / FIELDS / VALUES]: Never use `add_note` in Brief A.  
R176 [Policy 47]: Thank the customer before `close_call`.  
R177 [Policy 47]: Say goodbye before `close_call`.  
R178 [Codes CLOSE_CALL_CODES]: Use `promise` without a reason when at least one promise is recorded, subject to transfer precedence.  
R179 [Codes CLOSE_CALL_CODES; API /close_call request]: `promise` and `paid` do not require a reason; every other outcome does.  
R180 [API /close_call request]: Allowed `outcome` values are exactly `promise`, `paid`, `transferred`, `no_promise`, `not_verified`, `not_reached`.  
R181 [Codes CLOSE_CALL_CODES]: Use only the outcome/reason combinations in section 9.  
R182 [API all operations]: Send every tool request as a required `application/json` body using `POST`.  
R183 [API all operations]: Include required string `customer_id` on every tool request.  
R184 [API all responses]: `ok` is a boolean; `ok: false` means the action was not carried out.  
R185 [API all responses]: `error` is a string with no supplied enum or exact error-code list.  
R186 [API all `500` responses]: A `500` means the service failed and nothing was recorded; the API permits repetition. Apply the specific promise retry requirement and preserve the exactly-one, last-call requirement for closing.  
R187 [API /schedule_callback request]: Supply required string `date` with format `date` and string `time` as `HH:MM`.  
R188 [API /transfer_to_agent request]: Allowed `queue` values are exactly `restructuring`, `general`, `support`.  
R189 [API /add_note request]: The unused note interface requires `customer_id`, `product_id` and `reason`; `text` is optional.  
R190 [API /add_note request]: The unused note `reason` enum is exactly `refused`, `hardship`, `dispute`, `paid`, `service_error`.  
R191 [API info.description]: The seven tool calls need no key; `customer_id` in the body is the secret of one call.  
R192 [API info.description]: Every tool call is written to the ledger that the scorer reads.  

## 12. Ambiguities

| Issue | Source limits and treatment |
|---|---|
| Exact opening sentence | The sources specify content, not a verbatim sentence. This specification preserves the required content without inventing a mandatory script. |
| Clause 5 says to say nothing beyond the opening, but also requires a reachability question | Preserve the literal restriction and the expressly required reachability, callback, condolence and closing exchanges. Reading the restriction as forbidding those exchanges would make the clauses impossible to execute; it must not become permission for additional substantive disclosure. |
| Single product versus API `products` array | Brief A remains single-product. Read the API array structure, but do not import multi-product order or processing rules. No effective branch is supplied for multiple returned products. |
| API reference to Brief B | It describes the availability of `add_note`, not an amendment to Brief A. No Brief B rules are applied. |
| Fixed credit-card wording versus returned `card_last4` | The documents explicitly supply `"credit card ending 4821"`; the API supplies a variable `card_last4`. No rule reconciles a conflicting returned suffix. Preserve the source wording for the stated case, but do not assert an identifier contradicted by tool data. A conflicting case has no complete supplied resolution. |
| Tool field names versus prose labels | Use API `past_due`, `type`, `products`, `product_id`, `field`, `answer`, `date` and `time`. The documents' descriptive terms such as “past-due amount” are not alternative request or response keys. This is not a general amendment or precedence rule. |
| `human` versus `general` | `human` is the closing reason; API `queue` must be `general`. The Codes and API agree on this distinction. |
| Closing `reason` requirement | Although the schema's `required` array omits `reason`, its field description requires it except for `promise` and `paid`; the Codes agree. Apply the conditional requirement. |
| “none” in closing code sheet | Treat as absence of a reason, not the literal string `"none"`. No such reason code is supplied. |
| Closing reason values have no API enum | Use the Codes' exact permitted combinations. A free-string API property is not permission to invent reasons. |
| Generic API permission to repeat a `500` versus exactly one `close_call` | Preserve exactly one `close_call` and no later tool calls. A failed closing call has no recovery path consistent with those requirements in the supplied sources. |
| Failures other than promise recording | The API supplies `ok: false`, free-string `error` and repeatable `500`, but the documents supply a terminal `service_error` branch only for `create_promise`. Do not extend that branch to callbacks, transfers, verification or account retrieval. The callback and transfer clauses direct the corresponding tool call and closing code without separately specifying failure handling. |
| Response fields are optional in the schema | No response `required` arrays are supplied. Missing fields cannot be treated as affirmative success or invented account data; no complete missing-field recovery policy is supplied. |
| Verification format errors and wrong answers | Count actual incorrect security answers across both questions. Do not count the expressly exempt unreadable-date rejection or `day_month_swapped` retry. A service failure is not evidence of a wrong answer. No mandatory unreadable-date retry count is supplied. |
| Phone digits spoken in words or parts | The API requires a four-digit string but supplies no detailed speech-normalization grammar. Preserve identified digits, including leading zeros; do not invent ambiguous digits or a special retry policy. |
| Incomplete dates or two-digit years | No expansion rule is supplied. A submitted answer must be a readable `YYYY-MM-DD`; do not invent missing date components or a mandatory clarification count. |
| Calendar-week boundary | The sources specify business weekdays but not a calendar-week start or end. No week-boundary convention is added. Current-week and following-week formulas remain subject to this missing definition. |
| Timezone and daylight saving | No timezone is supplied. Use the date/time frame of `now` consistently, without importing the runtime timezone or real clock. |
| Callback “today” on a non-business day | Today is expressly allowed; only the alternative future date is constrained to the next business day. |
| Callback proposal absent or declined without an alternative | Clause 7 specifies two outside-window proposals, not every form of refusal or silence. No additional `no_callback` trigger is invented. |
| Customer-requested callback | The supplied callback rules sit under third-party handling. No customer callback branch or outcome is supplied, so those rules are not automatically extended to the customer. |
| Attempt 1 when the last business day of this week is already past | Clause 30 only moves the offer to next week when today equals that day. Clause 19 prohibits a past promise date. Do not treat a past date as valid; the sources do not specify the replacement persuasion date in this case. |
| First request asks for payment today on a non-business day | Preserve the exact mandatory request, but enforce the business-day rule before recording. A weekend/holiday proposal is handled under clause 20. |
| Past proposed dates | Clause 19 prohibits them, but no specific counter-offer count or closing branch is supplied. Do not silently treat them as valid or as flat refusals. |
| Next-business-day adjustment | Clause 20's adjustment remains subject to clause 19. It does not authorize a past or after-deadline promise. |
| Reoffering the floor versus not repeating refused offers | Clause 26 expressly permits naming the floor again on the deadline. Clause 31 still prohibits repeating an already refused offer. Reusing an amount with a different date is distinct from repeating the identical amount-and-date offer; no substitute is supplied if the prescribed next offer would be identical. |
| “Every amount proposed by the agent shall originate with the agent” | Apply it to agent-initiated offers, which use the defined full amount or floor. It does not override clause 27's express acceptance of an in-range customer proposal. |
| Amount above `past_due`, or `floor > past_due` | Clause 27 expressly requires acceptance within `floor <= amount <= past_due` and prohibits recording a below-floor amount. It does not supply an above-full handling rule or a reconciliation rule for inconsistent account values. Do not convert this omission into an invented hard maximum, rejection script or closing branch. |
| Currency, percentages and rounding | No currency, fixed minimum, percentage or rounding rule is supplied. Use the returned numeric amounts without adding such rules. |
| Hardship plus volunteered promise | The final sentence of clause 32 permits recording the customer's volunteered proposal under normal rules. A successful promise normally closes `promise`; a later transfer uses the explicit transfer precedence rule. |
| Other special statements before verification | Human requests expressly apply before and after verification. The timing and precedence of all other special statements are not fully specified. Preserve pre-verification nondisclosure and do not add unsupported precedence rules. |
| Other branches after a recorded promise | Only a later transfer has explicit closing precedence over `promise`. The sources do not define every possible subsequent statement or conflicting closing trigger. |
| Complaint, language, abuse and other vulnerability | No independent handling rules, scripts, queues, notes or outcome codes are supplied. Use an existing branch only when its actual trigger is present. |
| One question at a time | Explicitly required for security questions. No broader global questioning rule is supplied. |

Beyond these interface details and identified tensions, no direct disagreement about an enumerated tool field value is present in the supplied documents and API.

## 13. Verifier corrections

- Removed superseded deadline values from the override history. Only the effective **12th-business-day early deadline** and **7th-business-day late deadline** remain.
- Removed the unsupported general rule that the API overrides documents wherever they disagree. Preserved the API's exact interface contract and the Memo's explicit precedence.
- Removed the invented calendar-week boundary from the calendar, formulas and ambiguity treatment; the sources leave that boundary undefined.
- Replaced the exhaustive `valid_amount` formula with the range clause 27 expressly requires accepting. Clarified that above-full amounts and inconsistent floor/full data have no supplied handling rule.
- Restored clause 5's literal speech restriction alongside its expressly required third-party exchanges, rather than presenting a paraphrased reconciliation as the original rule.
- Restored the callback mapping to clause 6's instruction to call `schedule_callback` and then close `not_reached` / `callback`; kept tool-failure handling explicitly unresolved rather than adding a success-only closing condition.
- Removed unsupported mandatory clarification/resubmission wording for unreadable or incomplete identity answers. Preserved the required formats, wrong-answer exemptions and express swapped-date retry.
- Corrected the general information-use rule so it does not exclude customer-provided answers, proposals and statements.
- Added omitted API context about the hosted hackathon mock and scorer-read ledger, and the Memo signer's role.
- Preserved all exact outcome/reason codes, transfer mappings, tool fields, formats, enum values, required phrases and five holidays; these did not require spelling or value corrections.