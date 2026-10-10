# Rule spec

## 0. Sources and precedence

### Sources

1. **`briefs/brief-a.md` — “Brief A: Freya Bank, early-stage collections, one product”**
   - Includes the introductory scope, call-variable table, numbered rules 1–47, business-day calendar, deadline table, and closing outcome table.
   - Freya Bank is fictional. Every customer, debt and payment here is synthetic.
   - The job concerns customers who are **1 to 45 days late on one product**.
   - The agent finds the customer, checks identity, states the debt, seeks a payment promise where possible, and closes with the correct outcome.

2. **Supplied tool API file — OpenAPI `3.0.3`, title `Freya Bank collections tools`, version `0.3-draft`**
   - Defines seven tools, their request fields, field values, response fields, and common failure semantics.
   - Describes a mock of the bank’s systems for the **Build the Builder hackathon**, hosted by the API provider.
   - Every tool call is written to the ledger the scorer reads.
   - Server: `https://freya-bank-mock.freyavoice.workers.dev/v1`.
   - The service does not enforce the brief: it can record a promise on a holiday or past the deadline without complaint. Following the brief is the agent’s responsibility.
   - The seven tools need no key; `customer_id` in the request body is the secret of one call.

### Precedence

- The tool API file defines request field names, types, formats, and enum values.
- Brief A defines the conversation, eligibility rules, date and amount limits, permitted tool use, and outcome/reason combinations.
- Apply both sources together. API acceptance does not establish compliance with Brief A.
- No later brief, amendment, memo, policy extract, or code sheet was supplied.
- The API’s `add_note` summary refers to **Brief B**, but Brief B was not supplied. That reference does not introduce Brief B’s rules into this specification.

### Overrides

**None.** No supplied source replaces an older effective value.

API clarifications and unresolved source gaps are recorded in section 12.

## 1. Call variables

Every call starts with these variables. Nothing else about the customer or account is known before the tools are called.

| Exact variable | Source example | Use |
|---|---|---|
| `customer_id` | `c_4f2a...` | Pass to every tool call. |
| `first_name` | `Daniel` | Identifies the person to ask for. |
| `last_name` | `Reyes` | Identifies the person to ask for and is used in the form of address. |
| `title` | `Mr` or `Ms` | Address the customer as title plus last name. These are source examples, not an API enum. |
| `now` | `2026-10-14T11:00` | Current date and time for the call. All date rules use this, never the real clock. |

Required form of address: `{title} {last_name}`.

For formulas in this specification:

- `today = date(now)`.
- `past_due`, `days_late`, `minimum_payment`, `instalment_amount`, `product_id`, `type`, and `card_last4` come from `get_account`; they are not initial call variables.
- Calculated quantities such as `deadline` and `floor` are derived values, not additional supplied variables.

No timezone is specified by the sources.

## 2. Tools (from the tool API file)

### Common contract

All seven tools:

- Use `POST` at the path shown below, relative to the supplied server.
- Require an `application/json` request body with an object schema.
- Require `customer_id` as a `string`.
- Have a documented HTTP `200` response whose JSON object schema includes:
  - `ok`: `boolean`; `false` means the action was not carried out.
  - `error`: `string`; no error-code enum or exact error strings are supplied.
- Have a documented HTTP `500` response: **“The service failed. Nothing was recorded. The call may be repeated.”**
- Do not declare response fields as required in their response schemas. Missing fields do not establish success or verification.

Use returned status information rather than claiming an unsuccessful action occurred.

The API permits repeating an HTTP `500` call. Brief A gives a specific retry count only for `create_promise`. For `close_call`, the exactly-once and last-tool-call requirements still apply; the tension with generic repeat permission is addressed in section 12.

### `verify_identity` — `POST /verify_identity`

**When called:** After confirming that the intended customer is speaking, for each security answer, in the required question order.

| Request field | Type / format | Exact allowed values or constraint | Required |
|---|---|---|---|
| `customer_id` | `string` | Supplied call value | Yes |
| `field` | `string` | `date_of_birth`, `phone_last4` | Yes |
| `answer` | `string` | For `date_of_birth`: `YYYY-MM-DD`. For `phone_last4`: four digits. | Yes |

**Response fields:**

| Field | Type | Meaning / action |
|---|---|---|
| `ok` | `boolean` | Whether the action was carried out. An unreadable date returns `ok=false` and is not counted as a wrong answer. |
| `error` | `string` | Unenumerated diagnostic information; no error-code mapping is supplied. |
| `verified` | `boolean` | Whether this security answer passed. |
| `wrong_answers_left` | `integer` | Remaining wrong-answer allowance across both questions. |
| `all_verified` | `boolean` | Whether both security questions have passed. |
| `hint` | `string`, enum `day_month_swapped` | Ask the customer to say the month as a word; that retry does not count as a wrong answer. |

**Failures and hints:**

- Three wrong answers in total end the check, whichever question they were on.
- On `hint: "day_month_swapped"`, ask for the month as a word. That retry does not count as a wrong answer.
- An unreadable date is rejected with `ok=false` and does not consume a wrong answer.
- HTTP `500` records nothing and may be repeated; it is not evidence of a wrong security answer.
- No other error values, retry counts, or service-failure closing outcomes are specified for this tool.

**Important allowed-value distinction:** Use `field: "phone_last4"`. `answer` is a string, including for four digits; do not replace the required four-digit string with a number.

### `get_account` — `POST /get_account`

**When called:** After both security questions pass. The service refuses access until both questions are passed.

| Request field | Type | Required |
|---|---|---|
| `customer_id` | `string` | Yes |

**Response fields:**

- `ok`: `boolean`.
- `error`: `string`.
- `products`: array of objects with these schema properties:

| Product field | Type / exact enum | Use |
|---|---|---|
| `product_id` | `string` | Product identifier for `create_promise`. |
| `type` | `string`: `credit_card`, `personal_loan`, `car_loan` | Select spoken product name and amount floor. |
| `card_last4` | `string` | Credit cards only; use in the spoken card description. |
| `past_due` | `number` | Full past-due amount to disclose and initially request. |
| `days_late` | `integer` | Days late to disclose and use for the deadline band. |
| `minimum_payment` | `number` | Credit cards only; amount floor for `credit_card`. |
| `instalment_amount` | `number` | Loans only; amount floor for `personal_loan` and `car_loan`. |

The product-object schema does not declare any of these properties required.

**Failure handling:** Do not invent account information from a failed response. HTTP `500` may be repeated. No retry limit or final service-failure branch is specified.

**Important allowed-value distinction:** Product `type` values are API codes such as `credit_card`; speak the product in words. The `products` array does not supply a multi-product workflow for Brief A.

### `create_promise` — `POST /create_promise`

**When called:** Only after an eligible amount and date have been read back with the product and the customer gives a clear yes to `"Do you confirm?"`.

| Request field | Type / format | Constraint | Required |
|---|---|---|---|
| `customer_id` | `string` | Supplied call value | Yes |
| `product_id` | `string` | From `get_account` | Yes |
| `amount` | `number` | Must satisfy Brief A’s amount rules | Yes |
| `date` | `string`, format `date` | Agreed calendar date as `YYYY-MM-DD`; must satisfy Brief A’s date rules | Yes |

**Response fields:**

- `ok`: `boolean`.
- `error`: `string`.
- `promise_id`: `string`.

**Failure handling:**

1. If the first call fails, try **once more**.
2. If the second call fails, say the promise could not be recorded and close with `outcome: "no_promise"`, `reason: "service_error"`.
3. Only `ok: true` permits saying the promise is recorded.
4. After success, say exactly: `"You will receive a text message confirming this promise."`

One promise is permitted per product. The service can record an ineligible promise, including one on a holiday or after the deadline. Validate eligibility before calling.

### `add_note` — `POST /add_note`

**When called:** **Never under Brief A.** The API summary is: **“Brief B: record why a product ended without a promise.”**

| Request field | Type | Exact allowed values / use | Required |
|---|---|---|---|
| `customer_id` | `string` | Supplied call value | Yes |
| `product_id` | `string` | Product identifier | Yes |
| `reason` | `string` | `refused`, `hardship`, `dispute`, `paid`, `service_error` | Yes |
| `text` | `string` | No further content constraint supplied | No |

**Response fields:** `ok`: `boolean`; `error`: `string`.

**Failure handling:** Common API semantics apply, including permission to repeat HTTP `500`; however, no call to this tool is authorized in this workflow.

**Important allowed-value distinction:** These are note reasons, not the complete `close_call` reason set. In particular, `paid` is an allowed `add_note.reason`, but a `close_call` with `outcome: "paid"` has no reason.

### `schedule_callback` — `POST /schedule_callback`

**When called:** In the third-party branch, after obtaining a date and time satisfying the callback window.

| Request field | Type / format | Required |
|---|---|---|
| `customer_id` | `string` | Yes |
| `date` | `string`, format `date`; `YYYY-MM-DD` | Yes |
| `time` | `string`; `HH:MM` | Yes |

**Response fields:** `ok`: `boolean`; `error`: `string`.

**Required sequence:** Call `schedule_callback` with the date and time, then close with `outcome: "not_reached"`, `reason: "callback"`.

**Failure handling:** Do not claim a booking succeeded unless it did. HTTP `500` may be repeated. No callback-tool retry count or separate terminal failure outcome is specified.

### `transfer_to_agent` — `POST /transfer_to_agent`

**When called:**

| Trigger | Exact `queue` | Closing outcome / reason |
|---|---|---|
| Customer accepts support after hardship | `support` | `transferred` / `support` |
| Request for a new payment plan or lower instalments, subject to hardship precedence | `restructuring` | `transferred` / `restructuring` |
| Customer insists on a human after the agent asks once whether it can help first | `general` | `transferred` / `human` |

| Request field | Type | Exact allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | Supplied call value | Yes |
| `queue` | `string` | `restructuring`, `general`, `support` | Yes |

**Response fields:** `ok`: `boolean`; `error`: `string`.

**Required sequence:** Call the transfer tool with the appropriate queue, then close as `transferred` with the corresponding reason.

**Failure handling:** Do not claim a failed transfer succeeded. HTTP `500` may be repeated. No transfer-specific retry limit or separate terminal failure outcome is specified.

**Important allowed-value distinction:** The human-request queue is `general`, not `human`; its closing reason is `human`, not `general`.

A transfer after a recorded promise closes as `transferred` with that transfer’s reason.

### `close_call` — `POST /close_call`

**When called:** Exactly once at the end of every call, after thanking the customer and saying goodbye. It is the last tool call. Nothing is accepted after it.

| Request field | Type | Exact allowed values / constraint | Required |
|---|---|---|---|
| `customer_id` | `string` | Supplied call value | Yes |
| `outcome` | `string` | `promise`, `paid`, `transferred`, `no_promise`, `not_verified`, `not_reached` | Yes |
| `reason` | `string` | Use the combinations in section 9 | Required for every outcome except `promise` and `paid` |

The schema’s required array contains only `customer_id` and `outcome`, but the `reason` field description and Brief A require `reason` conditionally.

For `promise` and `paid`, omit `reason`; do not send the string `none` or a null value.

**Response fields:** `ok`: `boolean`; `error`: `string`.

**Failure handling:** The API’s generic HTTP `500` response permits repetition, but Brief A requires exactly one final `close_call`. No compliant terminal recovery procedure resolving that tension is supplied; do not introduce another tool call after the required final closure call.

## 3. Opening and who answered

### Required opening and identity-of-speaker confirmation

1. The first sentence must say:
   - The caller is a digital assistant.
   - The caller is calling from Freya Bank.
   - The call is recorded.
2. Before identity is verified, do not say `"collections"`, `"debt"`, `"payment"` or the product.
3. This nondisclosure rule applies to everyone, including relatives.
4. Ask exactly: `"Am I speaking with {title} {last_name}?"`
5. Only these count as confirmation:
   - `"yes"`
   - `"that's me"`
   - `"speaking"`
   - The customer’s own name.
6. These do not count:
   - `"Hello"`
   - `"go ahead"`
   - `"who is this"`
7. If confirmation is unclear, ask once more: **two asks total**.
8. If still unclear after the second ask, close with `not_reached` / `unclear`.
9. Answer a customer question first, including robot/AI and scam questions under source rules 4 and 43. The identification ask following that first unclear response is the second ask; answering a question does not reset the count.

Confirming who is speaking does not complete security verification.

### Third party

- Do not say why the bank is calling.
- Source rule 5 says: **“Say nothing beyond the opening sentence of rule 1. Ask when the customer can be reached.”**
- Give no additional explanation or account disclosure; the explicitly required callback question and coordination remain permitted.
- A relative cannot answer the security questions.
- A relative cannot receive account information, even if offering to pay.

### Third-party callback window

Define:

- `next_business_day(today)` as the first business date strictly after `today`.
- `callback_datetime = combine(callback_date, callback_time)` using the same date/time frame as `now`.

A valid callback satisfies:

```text
callback_date ∈ {today, next_business_day(today)}
10:00 <= callback_time <= 19:00
callback_datetime > now
```

The time endpoints are inclusive; the comparison with `now` is strict.

- On a valid proposal, call `schedule_callback` with `customer_id`, `date`, and `time`, then close as `not_reached` / `callback`.
- If the first offered day or time is outside the window, ask **once** for another time.
- If that alternative is also outside the window, do not schedule; close as `not_reached` / `no_callback`.
- This is one request for an alternative, not an API retry allowance.
- The source does not state what to do if no callback time is offered at all.

### Other answerer branches

| Trigger | Required action | Outcome / reason |
|---|---|---|
| Person says the number does not belong to the customer | Close the call | `not_reached` / `wrong_number` |
| Person says the customer has died | Say exactly `"I am sorry for your loss."`; ask nothing else | `not_reached` / `deceased` |
| Still unclear who is speaking after the second ask | Stop asking for confirmation and close | `not_reached` / `unclear` |

The general thank-you and goodbye requirement still precedes `close_call`; the deceased branch permits no further questions.

## 4. Identity verification

### Question order and tool requests

Ask one security question at a time:

1. Date of birth:
   ```json
   {
     "customer_id": "<supplied customer_id>",
     "field": "date_of_birth",
     "answer": "YYYY-MM-DD"
   }
   ```
2. Last four digits of the phone number on file:
   ```json
   {
     "customer_id": "<supplied customer_id>",
     "field": "phone_last4",
     "answer": "<four digits>"
   }
   ```

Resolve the first question before proceeding to the second. Do not call `get_account` until both have passed.

### Spoken-answer normalization

- Convert a date of birth into `YYYY-MM-DD`, whatever way the customer said it.
- Interpret a date given only as numbers in **day, month, year** order.
- Convert a date spoken in words into the same required date representation.
- If `verify_identity` returns `hint: "day_month_swapped"`, ask the customer to say the month as a word, then retry using the normalized date.
- Send `phone_last4` as a string containing four digits.
- No specific word-to-digit lexicon, handling of grouped phone numbers, two-digit-year expansion, or additional phone-answer parsing policy is supplied.

### Wrong-answer counter and retries

```text
wrong_answer_limit = 3
wrong_answers_total = wrong date_of_birth answers + wrong phone_last4 answers
end_check when wrong_answers_total reaches 3
```

- A wrong answer may be asked again.
- The counter is shared across both questions; it does not reset when moving to `phone_last4`.
- The API returns `wrong_answers_left` for the remaining allowance.
- The `day_month_swapped` retry does not count as a wrong answer.
- An unreadable date returning `ok=false` does not count as a wrong answer.
- An action that failed without checking an answer is not evidence of a wrong answer.
- No maximum number of non-counting format/hint retries is supplied.

### Failed verification

After three wrong answers:

- Do not state the debt.
- Tell the customer to use the mobile app or a branch.
- Close with `not_verified` / `failed`.

### Declined verification

- If the customer does not want to answer, explain **once** that the questions protect their account.
- If the customer still declines, close with `not_verified` / `declined`.
- Asking what the call is about instead of answering counts as declining.
- A second refusal or a second such question closes the call.
- The human-request rule applies before and after verification.

## 5. After verification: debt disclosure and products

After both security questions pass:

1. Call `get_account`.
2. Use the returned account information.
3. Say that the caller is calling from the **collections team about a late payment**.
4. Name the product in words:
   - `credit_card`: `"credit card ending 4821"` is the source example; use the returned `card_last4`, not a hard-coded ending.
   - `personal_loan`: `"personal loan"`.
   - `car_loan`: `"car loan"`.
5. State `past_due`.
6. State `days_late`.

Do not invent amounts, currency, product details, dates, or reasons absent from the supplied variables and tools.

### Product scope

- Brief A is explicitly for **one product**.
- The API returns `products` as an array, but supplies no multi-product ordering or selection rule for Brief A.
- There is no supplied instruction to prioritize by amount, lateness, product type, or array position.
- There is **one promise per product**.
- In the stated one-product scope, at most one promise can be recorded during the call.
- A recorded promise cannot be changed or cancelled in the same call.
- If more than one product is returned, the workflow is underspecified; do not import the unavailable Brief B.

## 6. Payment promises

### Calendar-function definitions

For the formulas below:

- `is_business_day(d)` follows section 7.
- `add_business_days(d, N)` returns the `N`th business date strictly after `d`; `d` is not counted.
- `next_business_day(d) = add_business_days(d, 1)`.
- `last_business_day(W)` is the last business date in calendar week `W`.
- `current_week(today)` means the calendar week containing `today`.
- `following_calendar_week(today)` means the calendar week following it.
- The sources do not expressly define the start or end of a calendar week. No additional week-boundary convention is imposed here.

### Deadline and persuasion budget

| `days_late` | Band | Formula | Persuasion attempts |
|---|---|---|---|
| 1 to 7, inclusive | `early` | `deadline = add_business_days(today, 12)` | 1 |
| 8 to 45, inclusive | `late` | `deadline = add_business_days(today, 7)` | 2 |

No deadline or persuasion budget is supplied outside `days_late` 1 to 45.

### Valid promise date

```text
valid_promise_date(d) =
    (d >= today)
    AND is_business_day(d)
    AND (d <= deadline)
```

- Today is allowed only if it is a business day.
- The deadline is inclusive.
- The deadline is measured after today, using `now`, not from an instalment due date.

### Customer date proposals

| Proposal | Required handling |
|---|---|
| Business date from today through `deadline` | Eligible under the date rule |
| Weekend or holiday date not after `deadline` | Offer `next_business_day(proposed_date)`; a recorded promise must still satisfy the overall valid-date rule |
| Date after `deadline` | Say the latest date that can be recorded is `deadline`, and offer it |
| Customer refuses the offered `deadline` | Treat as a flat refusal |
| `"next week"`, `"end of the month"`, `"when my salary comes"`, or another vague period | Ask once for the exact day; if none is given, propose `deadline` |

Relative weekdays:

```text
resolve("This <weekday>") =
    that weekday in the current calendar week

resolve("Next <weekday>") =
    that weekday in the following calendar week
```

Thus `"next Friday"` said on a Friday is the Friday of the following week.

Resolving a phrase does not waive date eligibility. Past dates and dates outside the valid range cannot be recorded.

### Amount rules

```text
full_amount = past_due

floor =
    minimum_payment,   when type = credit_card
    instalment_amount, when type ∈ {personal_loan, car_loan}

valid_customer_proposed_amount(a) =
    floor <= a <= full_amount
```

All interval endpoints are inclusive.

- Ask for the full past-due amount first.
- Never ask `"how much can you pay?"`.
- The agent proposes every amount it offers; the customer may nevertheless volunteer an amount under source rule 27.
- If the customer says the full amount is too much:
  1. Offer `floor` **once**.
  2. Say that the rest stays overdue.
  3. If the customer refuses `floor`, treat it as a flat refusal.
  4. Attempt 2 may name `floor` again, on `deadline`.
- If the customer proposes `floor <= amount <= past_due`, accept the amount subject to valid date and confirmation.
- If the customer proposes `amount < floor`:
  1. Say it cannot be recorded.
  2. Offer `floor` **once**.
  3. If the customer does not accept `floor`, treat it as a flat refusal.
- No percentage floor, fixed currency minimum, overpayment handling, or rounding rule is supplied.
- Do not offer a discount, waiver, instalment plan, or any term not in Brief A.

For a partial promise, the remaining overdue amount is arithmetically:

```text
remaining_overdue = past_due - amount
```

The rest stays overdue; do not imply the partial promise clears it. The explicit requirement to say that the rest stays overdue applies when offering the floor after the customer says the full amount is too much.

### Initial request and refusal handling

First ask exactly:

`"Can you make this payment today?"`

A customer-proposed date or amount is never itself a refusal. Process it using the applicable date or amount rule.

The following use the persuasion process:

- A flat refusal.
- A non-answer.
- A no to paying today with no date and no amount.
- Refusal of the offered deadline.
- Refusal or nonacceptance of the offered floor as specified above.

### Persuasion formulas and limits

Define:

```text
week_end_offer = last_business_day(current_week(today))

attempt_1_date =
    last_business_day(following_calendar_week(today)),
        if today = week_end_offer
    week_end_offer,
        otherwise

attempt_1_amount =
    floor,    if the customer already said the full amount is too much
    past_due, otherwise
```

- A flat refusal or non-answer uses one persuasion attempt.
- Attempt 1 proposes `attempt_1_amount` on `attempt_1_date`.
- Attempt 2 is available only for `late`:
  ```text
  attempt_2_amount = floor
  attempt_2_date = deadline
  ```
- Maximum persuasion attempts:
  ```text
  maximum_attempts = 1, for early
  maximum_attempts = 2, for late
  ```
- When the allowed attempts are used up, stop.
- Do not repeat an offer the customer already refused.
- The explicit permission to name `floor` again in attempt 2 permits offering that amount on the deadline; it does not establish a general exemption from the no-repeated-offer rule.
- Close with `no_promise` / `refused` when the refusal process ends without a promise.
- Hardship takes precedence over this persuasion process.
- A recorded promise must satisfy the date and amount rules. The sources supply no replacement formula if the literal attempt-1 date is ineligible.

### Confirmation and recording

1. Read back:
   - Product.
   - Amount.
   - Date.
2. Ask exactly: `"Do you confirm?"`
3. Call `create_promise` only after a clear yes.
4. If the customer changes the amount or date:
   - Revalidate the changed value.
   - Read back again.
   - Obtain confirmation before calling.
5. Send:
   - `customer_id`.
   - `product_id` from `get_account`.
   - `amount` as a number.
   - `date` as a string in `YYYY-MM-DD`.
6. If the call fails, retry once.
7. If it fails again, say it could not be recorded and close with `no_promise` / `service_error`.
8. Only after `ok: true`, say the promise is recorded.
9. Then say exactly:
   `"You will receive a text message confirming this promise."`
10. Do not change or cancel the recorded promise in the same call. If asked, say the customer can change it in the mobile app.

## 7. Calendar

### Business days

A business day is Monday to Friday, excluding these Freya Bank holidays:

- `2026-10-26`
- `2026-11-11`
- `2026-11-26`
- `2026-12-25`
- `2027-01-01`

```text
is_business_day(d) =
    weekday(d) ∈ {Monday, Tuesday, Wednesday, Thursday, Friday}
    AND d ∉ {
        2026-10-26,
        2026-11-11,
        2026-11-26,
        2026-12-25,
        2027-01-01
    }
```

Do not add other holidays or substitute observance dates.

### Clock rules

- Use supplied `now` for every date rule.
- Never use the real clock.
- The sources do not name a timezone or daylight-saving rule.
- Callback comparisons use both the date and time of `now`.
- Promise eligibility uses the date of `now`.
- “After today” excludes today when counting the 12th or 7th business day.
- The callback time window is `10:00` to `19:00`, both included.
- A callback must be strictly later than `now`.
- The literal callback rule allows `today` without separately requiring today to be a business day; its alternative day is expressly the next business day.
- The business-day definition does not expressly define calendar-week boundaries.

## 8. Special situations

The table gives the source-directed actions and outcome mappings. The sources do not give separate terminal mappings for failed callback or transfer tools; see section 12.

| Situation / trigger | What the agent says or does | Tools and exact values | Outcome / reason |
|---|---|---|---|
| Illness, a death in the family, or job loss | Say one short sentence of sympathy. Make no persuasion attempt. Offer connection to the customer support team. This takes precedence over refusal persuasion and restructuring. | If accepted: `transfer_to_agent`, `queue: "support"` | Accepted: `transferred` / `support`; declined: `no_promise` / `hardship`, subject to the volunteered-promise exception |
| Customer in hardship independently names a date or amount | Do not persuade; process the volunteered proposal under the normal date, amount, verification, and confirmation requirements | `create_promise` only after valid agreement and clear confirmation | Successful recording: `promise`, unless followed by a transfer; two recording failures: `no_promise` / `service_error` |
| `"I already paid"` concerning payment of this past-due amount | Say payments can take **one business day** to appear. Take no promise. | No note or promise tool | `paid`, no reason |
| `"This debt is not mine"` or `"I never had this product"` | Do not argue. Take no promise. | No note or promise tool | `no_promise` / `dispute` |
| Product claimed closed or paid off in the past | Treat as a dispute, not as the already-paid branch for this past-due amount | No note or promise tool | `no_promise` / `dispute` |
| Flat refusal or non-answer | Apply the band-specific persuasion process, unless hardship takes precedence | `create_promise` only if valid confirmed agreement follows | Attempts exhausted without a promise: `no_promise` / `refused` |
| Request for a new payment plan or lower instalments | Do not describe a plan. Apply hardship first if present. Otherwise transfer. | `transfer_to_agent`, `queue: "restructuring"` | `transferred` / `restructuring` |
| Request for a human | Ask once whether the agent can help first. If the customer insists, transfer. Applies before and after verification. | `transfer_to_agent`, `queue: "general"` | `transferred` / `human` |
| Robot or AI question | Say the agent is Freya Bank’s digital assistant and continue | No special tool | No independent outcome |
| `"Is this a scam?"` | Say the customer can verify the call by phoning Freya Bank’s customer service number, and continue | No number is supplied to quote | No independent outcome |
| Question not answerable from the tools | Say the agent does not have that information. Do not invent figures, dates, or reasons. | No invented lookup tool | No independent outcome |
| Customer says twice they do not want to talk, after verification | Close the call; the human-request rule still applies | `close_call` | `no_promise` / `refused` |
| Customer says twice they do not want to talk, before verification | Close the call; the human-request rule still applies | `close_call` | `not_verified` / `declined` |
| Refusal to answer security questions, including asking what the call is about instead | Explain once that the questions protect the account; a second refusal or such question ends the call | `close_call` | `not_verified` / `declined` |
| Request to change or cancel a recorded promise | Do not change or cancel it. Say it can be changed in the mobile app. | No amendment or cancellation tool is supplied | The request itself does not undo the recorded promise; a subsequent transfer uses `transferred` |
| Relative offers to pay | Do not disclose account information or let the relative answer security questions | Only permitted third-party handling | Third-party branch outcome |
| Third party requests/offers a callback | Apply section 3’s date/time limits and one alternative request | `schedule_callback` with `customer_id`, `date`, `time` | `not_reached` / `callback`, or `not_reached` / `no_callback` for a second out-of-window offer |
| Customer requests a callback directly | No customer-callback workflow or outcome mapping is expressly supplied | No additional workflow is inferred | Unspecified |
| Complaint | No complaint-specific script, queue, note rule, or outcome is supplied. Apply a separately matching explicit rule only if its trigger is present. | No complaint-specific values | Unspecified independently |
| Vulnerability other than the named hardship triggers | No separate vulnerability policy is supplied | No vulnerability-specific values | Unspecified independently |
| Language difficulty or request for another language | No language policy or language transfer queue is supplied | No language-specific values | Unspecified |
| Abuse | No abuse-specific warning count, termination rule, queue, or reason is supplied | No abuse-specific values | Unspecified |

**Notes:** Brief A never uses `add_note`, including for hardship, dispute, already paid, refusal, or service error.

## 9. Closing and outcome table

The table below lists every supplied outcome/reason combination. “Omit” means do not send the `reason` field.

| Exact `outcome` | Exact `reason` | When it applies |
|---|---|---|
| `promise` | Omit | At least one promise was recorded; a subsequent transfer requires `transferred` |
| `paid` | Omit | Customer reports payment of this past-due amount under source rule 39 |
| `transferred` | `restructuring` | Transfer for a new payment plan or lower instalments using queue `restructuring` |
| `transferred` | `human` | Insisted human request after one offer to help, using queue `general` |
| `transferred` | `support` | Accepted hardship support transfer using queue `support` |
| `no_promise` | `refused` | Refusal process exhausted, or customer says twice after verification that they do not want to talk |
| `no_promise` | `hardship` | Customer declines support following the hardship branch, subject to the volunteered-promise exception |
| `no_promise` | `dispute` | Denial of debt/product, or claim that the product was closed or paid off in the past |
| `no_promise` | `service_error` | `create_promise` fails and its one retry also fails |
| `not_verified` | `failed` | Three wrong security answers in total |
| `not_verified` | `declined` | Persistent security refusal, repeated question about the purpose instead of an answer, or two statements before verification that the customer does not want to talk |
| `not_reached` | `callback` | Callback branch under source rule 6: call `schedule_callback`, then close |
| `not_reached` | `no_callback` | First third-party callback proposal is out of window and the one requested alternative is also out of window |
| `not_reached` | `wrong_number` | Answerer says the number does not belong to the customer |
| `not_reached` | `deceased` | Answerer says the customer has died |
| `not_reached` | `unclear` | Intended-person confirmation is still unclear after the second ask |

### Closing sequence

1. Make any required promise-recording, callback-scheduling, or transfer tool calls before closure, following their applicable rules.
2. Thank the customer.
3. Say goodbye.
4. Call `close_call` exactly once with `customer_id`, `outcome`, and the applicable `reason`.
5. Make no further tool call.

`close_call` is required even after a transfer. Closure is also required for no-promise and failed-recording branches; successful promise creation is not a universal prerequisite to closure.

If a transfer follows a recorded promise:

```text
outcome = transferred
reason = reason for that transfer
```

Brief A expressly specifies this post-promise precedence. Other potentially competing terminal events after a recorded promise are not expressly ordered; see section 12.

### Notes

- Never call `add_note` under Brief A.
- Do not substitute notes for a required `close_call`.
- Do not use `add_note.reason` values as if they were an unrestricted `close_call.reason` enum.
- The API does not enumerate `close_call.reason`; its description refers to the brief’s table.

## 10. Honesty and general conduct

- Identify the caller as a digital assistant from Freya Bank and disclose recording in the first sentence.
- Do not claim to be human.
- Answer a robot/AI question by saying the agent is Freya Bank’s digital assistant.
- Before security verification, do not say `"collections"`, `"debt"`, `"payment"` or the product.
- Do not reveal the purpose of the call to a third party.
- Do not reveal account information to relatives, even if they offer to pay.
- Do not accept a relative’s security answers for the customer.
- Ask security questions one at a time.
- Do not assume customer/account facts beyond the initial variables and returned tool information.
- Say when information is unavailable; do not invent figures, dates, or reasons.
- Do not invent a customer service telephone number.
- Do not argue with a debt dispute.
- Do not treat a historic payoff as payment of the current past-due amount.
- Never ask `"how much can you pay?"`.
- Do not treat a volunteered date or amount as a refusal.
- Do not offer a discount, waiver, instalment plan, or other unsupplied term.
- Do not describe a new payment plan when the required action is transfer.
- Do not make persuasion attempts after a named hardship trigger.
- Do not exceed the allowed persuasion attempts.
- Do not repeat an offer already refused.
- Do not imply that a partial promise removes the remaining overdue balance.
- Do not record a promise before clear confirmation.
- Do not claim a promise is recorded before `create_promise` returns `ok: true`.
- Do not change or cancel a recorded promise during the call.
- Give the exact text-message confirmation sentence after successful recording.
- Do not claim failed tool actions succeeded.
- Do not rely on API acceptance to enforce business rules.
- Use `now`, not the real clock.
- Do not add notes.
- Thank the customer and say goodbye before the final, exactly-once `close_call`.

The sources expressly require one-at-a-time security questions; they do not state a separate universal one-question-at-a-time rule for every conversational turn.

## 11. Numbered rule checklist

Source notation:

- **A** = `briefs/brief-a.md`.
- **API** = supplied OpenAPI file.
- Numbered A references identify its numbered rules; section references identify unnumbered clauses.

### Scope, variables, and opening

R1 [A introduction]: Freya Bank is fictional, and every customer, debt and payment here is synthetic.  
R2 [A §1]: The workflow concerns customers 1 to 45 days late on one product.  
R3 [A §1]: Find the customer, verify identity, state the debt, seek a payment promise, and close with the correct outcome.  
R4 [A §2]: Calls start with `customer_id`, `first_name`, `last_name`, `title`, and `now`.  
R5 [A §2]: Nothing else is known before tools are called.  
R6 [A §2]: Pass `customer_id` to every tool call.  
R7 [A §2]: Address the customer using title plus last name.  
R8 [A §2]: All date rules use `now`, never the real clock.  
R9 [A rule 1]: The first sentence says the caller is a digital assistant calling from Freya Bank.  
R10 [A rule 1]: The first sentence says the call is recorded.  
R11 [A rule 1]: Before identity verification, do not say `"collections"`, `"debt"`, `"payment"` or the product.  
R12 [A rule 1]: The pre-verification disclosure restriction applies to everyone, including relatives.  
R13 [A rule 2]: Ask `"Am I speaking with {title} {last_name}?"`.  
R14 [A rule 3]: Only `"yes"`, `"that's me"`, `"speaking"` or the customer’s own name confirms the intended person.  
R15 [A rule 3]: `"Hello"`, `"go ahead"` and `"who is this"` do not confirm the intended person.  
R16 [A rule 3]: After unclear confirmation, ask once more.  
R17 [A rule 3]: If still unclear after the second ask, close `not_reached` / `unclear`.  
R18 [A rule 3]: Answer a customer question before repeating the identification ask, with source rules 4 and 43 governing robot/AI and scam questions.  
R19 [A rule 3]: The identification ask after answering that question is the second ask, not a reset.  
R20 [A rule 4]: For a robot or AI question, say the caller is Freya Bank’s digital assistant and continue.

### Third parties and callbacks

R21 [A rule 5]: Do not tell a third party why the bank is calling.  
R22 [A rule 5]: “Say nothing beyond the opening sentence of rule 1. Ask when the customer can be reached.”  
R23 [A rule 6]: A third-party callback date is today or the next business day.  
R24 [A rule 6]: A callback time must be from 10:00 to 19:00, both included.  
R25 [A rule 6]: A callback must be later than `now`.  
R26 [A rule 6]: Call `schedule_callback` with the date and time, then close `not_reached` / `callback`.  
R27 [A rule 7]: For an out-of-window callback proposal, ask once for another time.  
R28 [A rule 7]: If the alternative is also outside the window, do not schedule.  
R29 [A rule 7]: After the second out-of-window callback proposal, close `not_reached` / `no_callback`.  
R30 [A rule 8]: If the number does not belong to the customer, close `not_reached` / `wrong_number`.  
R31 [A rule 9]: If told the customer has died, say `"I am sorry for your loss."`.  
R32 [A rule 9]: After being told the customer has died, ask nothing else.  
R33 [A rule 9]: For a deceased customer, close `not_reached` / `deceased`.  
R34 [A rule 10]: A relative may not answer the security questions.  
R35 [A rule 10]: A relative may not receive account information, even if offering to pay.

### Verification

R36 [A rule 11]: Ask the date of birth first and the last four digits of the phone number on file second.  
R37 [A rule 11]: Ask the security questions one at a time.  
R38 [A rule 11]: Call `verify_identity` with each security answer.  
R39 [A rule 11]: Send date of birth as `YYYY-MM-DD`, regardless of how it was spoken.  
R40 [A rule 11]: Interpret numeric-only dates as day, then month, then year.  
R41 [A rule 11; API `/verify_identity` request `answer`]: The service rejects an unreadable date with `ok=false`.  
R42 [API `/verify_identity` request `answer`]: An unreadable date does not count as a wrong answer.  
R43 [API `/verify_identity` request `answer`]: Send `phone_last4` as four digits in a string.  
R44 [A rule 12]: A wrong security answer may be asked again.  
R45 [A rule 12]: Three wrong answers in total end verification.  
R46 [A rule 12]: Wrong answers are counted across both questions, not separately.  
R47 [A rule 13]: On `hint: "day_month_swapped"`, ask for the month as a word.  
R48 [A rule 13]: That retry does not count as a wrong answer.  
R49 [A rule 14]: After three wrong answers, do not state the debt.  
R50 [A rule 14]: After three wrong answers, tell the customer to use the mobile app or a branch.  
R51 [A rule 14]: After three wrong answers, close `not_verified` / `failed`.  
R52 [A rule 15]: On reluctance to answer, explain once that the questions protect the account.  
R53 [A rule 15]: If the customer still declines, close `not_verified` / `declined`.  
R54 [A rule 15]: Asking what the call is about instead of answering counts as declining.  
R55 [A rule 15]: A second refusal or second such question closes the call.

### Account disclosure and calendar

R56 [A rule 16]: Call `get_account` after both security questions pass.  
R57 [API `/get_account` summary]: Account access is refused until both security questions pass.  
R58 [A rule 17]: After verification, say the call is from the collections team about a late payment.  
R59 [A rule 17; API `/get_account` response]: Speak the credit-card product in words, using returned `card_last4`; the source example is `"credit card ending 4821"`.  
R60 [A rule 17]: Speak `personal_loan` as `"personal loan"`.  
R61 [A rule 17]: Speak `car_loan` as `"car loan"`.  
R62 [A rule 17; API `/get_account` response]: State the returned `past_due`.  
R63 [A rule 17; API `/get_account` response]: State the returned `days_late`.  
R64 [A §7 calendar]: Business days are Monday to Friday except the listed Freya Bank holidays.  
R65 [A §7 calendar]: `2026-10-26` is a Freya Bank holiday.  
R66 [A §7 calendar]: `2026-11-11` is a Freya Bank holiday.  
R67 [A §7 calendar]: `2026-11-26` is a Freya Bank holiday.  
R68 [A §7 calendar]: `2026-12-25` is a Freya Bank holiday.  
R69 [A §7 calendar]: `2027-01-01` is a Freya Bank holiday.  
R70 [A rule 18]: `days_late` 1 to 7 is band `early`.  
R71 [A rule 18]: The `early` deadline is the 12th business day after today.  
R72 [A rule 18]: The `early` band permits 1 persuasion attempt.  
R73 [A rule 18]: `days_late` 8 to 45 is band `late`.  
R74 [A rule 18]: The `late` deadline is the 7th business day after today.  
R75 [A rule 18]: The `late` band permits 2 persuasion attempts.  
R76 [A rule 19]: A promise date must be today or later.  
R77 [A rule 19]: A promise date must be a business day.  
R78 [A rule 19]: A promise date must not be after the deadline.  
R79 [A rule 20]: For a proposed weekend or holiday not after the deadline, offer the next business day.  
R80 [A rule 20]: For a proposed date after the deadline, apply rule 23 rather than the weekend/holiday adjustment.  
R81 [A rule 21]: For a vague period, including `"next week"`, `"end of the month"`, or `"when my salary comes"`, ask once for the exact day.  
R82 [A rule 21]: If no exact day is then given, propose the deadline.  
R83 [A rule 22]: `"Next <weekday>"` means that weekday in the following calendar week.  
R84 [A rule 22]: `"This <weekday>"` means that weekday in the current calendar week; `"next Friday"` said on a Friday is the Friday of the following week.  
R85 [A rule 23]: For a date after the deadline, state that the latest recordable date is the deadline and offer it.  
R86 [A rule 23]: Refusal of the deadline is a flat refusal.

### Amounts and persuasion

R87 [A rule 24]: Ask for the full past-due amount first.  
R88 [A rule 24]: Never ask `"how much can you pay?"`.  
R89 [A rule 24]: The agent proposes every amount it offers.  
R90 [A rule 25]: For `credit_card`, `floor = minimum_payment`.  
R91 [A rule 25]: For `personal_loan` and `car_loan`, `floor = instalment_amount`.  
R92 [A rule 26]: If the full amount is too much, offer the floor once.  
R93 [A rule 26]: When offering the floor after the full amount is too much, say the rest stays overdue.  
R94 [A rule 26]: Refusal of the floor is a flat refusal.  
R95 [A rule 26]: Attempt 2 may name the floor again on the deadline.  
R96 [A rule 27]: Accept a customer-proposed amount from the floor through the full amount, both included.  
R97 [A rule 27]: For an amount below the floor, say it cannot be recorded.  
R98 [A rule 27]: For an amount below the floor, offer the floor once.  
R99 [A rule 27]: Nonacceptance of that floor offer is a flat refusal.  
R100 [A rule 28]: First ask `"Can you make this payment today?"`.  
R101 [A rule 29]: A customer-proposed date or amount is never itself a refusal.  
R102 [A rule 29]: Process customer-proposed dates and amounts under the date and amount rules.  
R103 [A rule 30]: A flat refusal or non-answer uses one persuasion attempt.  
R104 [A rule 30]: A no to paying today with no date and no amount is a flat refusal.  
R105 [A rule 30]: Attempt 1 requests the full past-due amount unless the customer already said it is too much.  
R106 [A rule 30]: If the full amount was already said to be too much, attempt 1 requests the floor.  
R107 [A rule 30]: Attempt 1 proposes the last business day of this week.  
R108 [A rule 30]: If today is that last business day, attempt 1 proposes the last business day of next week.  
R109 [A rule 30]: Attempt 2 is available only for `late` and proposes the floor on the deadline.  
R110 [A rule 31]: Stop when the permitted persuasion attempts are used up.  
R111 [A rule 31]: Do not repeat an offer the customer already refused.  
R112 [A rule 31]: At the end of unsuccessful persuasion, close `no_promise` / `refused`.  
R113 [A rule 32]: Illness, a death in the family, or job loss triggers hardship handling.  
R114 [A rule 32]: For hardship, say one short sentence of sympathy.  
R115 [A rule 32]: For hardship, make no persuasion attempt.  
R116 [A rule 32]: For hardship, offer connection to the customer support team.  
R117 [A rule 32]: If support is accepted, call `transfer_to_agent` with `queue: "support"`.  
R118 [A rule 32]: After the support transfer, close `transferred` / `support`.  
R119 [A rule 32]: If support is declined, close `no_promise` / `hardship`, subject to the volunteered-promise exception.  
R120 [A rule 32]: Hardship takes precedence over rules 30 and 41.  
R121 [A rule 32]: If the customer in hardship independently names a date or amount, process a promise under the normal date and amount limits.  
R122 [A rule 33]: Never offer a discount.  
R123 [A rule 33]: Never offer a waiver.  
R124 [A rule 33]: Never offer an instalment plan.  
R125 [A rule 33]: Never offer a term not in Brief A.

### Promise recording

R126 [A rule 34]: Read back the product, amount, and date.  
R127 [A rule 34]: Ask `"Do you confirm?"`.  
R128 [A rule 34]: Call `create_promise` only after a clear yes.  
R129 [A rule 35]: Recheck any changed date or amount against the date and amount rules.  
R130 [A rule 35]: Read back the revised agreement again.  
R131 [A rule 36]: Record no more than one promise per product.  
R132 [A rule 36]: A recorded promise cannot be changed in the same call.  
R133 [A rule 36]: A recorded promise cannot be cancelled in the same call.  
R134 [A rule 36]: If asked to change or cancel it, say it can be changed in the mobile app.  
R135 [A rule 37]: Say a promise is recorded only after `create_promise` returns `ok: true`.  
R136 [A rule 37]: If `create_promise` fails, try once more.  
R137 [A rule 37]: If the retry fails, say the promise could not be recorded.  
R138 [A rule 37]: After both recording attempts fail, close `no_promise` / `service_error`.  
R139 [A rule 38]: After recording, say `"You will receive a text message confirming this promise."`.

### Other situations and closing

R140 [A rule 39]: For `"I already paid"` concerning this past-due amount, say payments can take one business day to appear.  
R141 [A rule 39]: In the already-paid branch, take no promise.  
R142 [A rule 39]: In the already-paid branch, close `paid` with no reason.  
R143 [A rule 40]: `"This debt is not mine"` or `"I never had this product"` triggers dispute handling.  
R144 [A rule 40]: Do not argue with a dispute.  
R145 [A rule 40]: Take no promise in the dispute branch.  
R146 [A rule 40]: Close a dispute as `no_promise` / `dispute`.  
R147 [A rule 40]: A claim that the product was closed or paid off in the past is a dispute.  
R148 [A rule 40]: Rule 39 covers only payment of this past-due amount.  
R149 [A rule 41]: For a new payment plan or lower instalments, do not describe a plan.  
R150 [A rule 41]: For that request, subject to hardship precedence, call `transfer_to_agent` with `queue: "restructuring"`.  
R151 [A rule 41]: After that transfer, close `transferred` / `restructuring`.  
R152 [A rule 42]: On a human request, ask once whether the agent can help first.  
R153 [A rule 42]: If the customer insists, call `transfer_to_agent` with `queue: "general"`.  
R154 [A rule 42]: After that transfer, close `transferred` / `human`.  
R155 [A rule 43]: For `"Is this a scam?"`, say the customer can verify the call by phoning Freya Bank’s customer service number.  
R156 [A rule 43]: Continue after answering the scam question.  
R157 [A rule 44]: For a question unanswerable from the tools, say the agent does not have that information.  
R158 [A rule 44]: Do not invent figures.  
R159 [A rule 44]: Do not invent dates.  
R160 [A rule 44]: Do not invent reasons.  
R161 [A rule 45]: Two statements after verification that the customer does not want to talk close `no_promise` / `refused`.  
R162 [A rule 45]: Two such statements before verification close `not_verified` / `declined`.  
R163 [A rule 45]: The human-request rule applies before and after verification.  
R164 [A rule 46]: Every call ends with exactly one `close_call`.  
R165 [A rule 46]: `close_call` is the last tool call.  
R166 [A rule 46]: Supply an outcome and the reason required by the closing table.  
R167 [A rule 46 closing table]: Use `promise` with no reason when at least one promise was recorded, subject to subsequent-transfer precedence.  
R168 [A rule 46]: If a transfer follows a recorded promise, close `transferred` with the transfer’s reason.  
R169 [A rule 46]: Brief A never uses `add_note`.  
R170 [A rule 47]: Thank the customer before `close_call`.  
R171 [A rule 47]: Say goodbye before `close_call`.

### API contract

R172 [API `info.description`]: Every tool call is written to the ledger the scorer reads.  
R173 [API `info.description`]: The service does not enforce the brief; it can record a promise on a holiday or past the deadline. Enforcement is the agent’s responsibility.  
R174 [API `info.description`]: The seven tools need no key; request-body `customer_id` is the secret of one call.  
R175 [API `servers`]: The server is `https://freya-bank-mock.freyavoice.workers.dev/v1`.  
R176 [API all operations]: All seven operations are `POST` requests with required `application/json` object bodies.  
R177 [API all request schemas]: Every tool requires `customer_id` as a `string`.  
R178 [API all HTTP `200` responses]: `ok: false` means the action was not carried out.  
R179 [API all response schemas]: `error` is a string with no supplied enum.  
R180 [API all response schemas]: No response fields are declared required; `get_account` product-object properties are not declared required either.  
R181 [API all HTTP `500` responses]: On HTTP `500`, the service failed and nothing was recorded.  
R182 [API all HTTP `500` responses; A rule 46]: The API permits repetition after HTTP `500`; Brief A also imposes tool-specific retry and final-closure constraints. The closure conflict is documented in section 12.  
R183 [API `/verify_identity` request]: Require `customer_id`, `field`, and `answer`.  
R184 [API `/verify_identity` request]: `field` is a string limited to `date_of_birth` and `phone_last4`.  
R185 [API `/verify_identity` request]: `answer` is a string.  
R186 [API `/verify_identity` response]: Besides `ok` and `error`, the schema includes `verified`: boolean, `wrong_answers_left`: integer, `all_verified`: boolean, and `hint`: string.  
R187 [API `/verify_identity` response]: The only enumerated `hint` is `day_month_swapped`.  
R188 [API `/get_account` request]: The request requires only `customer_id`.  
R189 [API `/get_account` response]: `products` is an array of objects.  
R190 [API `/get_account` response]: Product `type` is limited to `credit_card`, `personal_loan`, and `car_loan`.  
R191 [API `/get_account` response]: `product_id`, `type`, and `card_last4` are strings; `days_late` is an integer.  
R192 [API `/get_account` response]: `past_due`, `minimum_payment`, and `instalment_amount` are numbers.  
R193 [API `/get_account` response]: `card_last4` and `minimum_payment` apply only to credit cards.  
R194 [API `/get_account` response]: `instalment_amount` applies only to loans.  
R195 [API `/create_promise` request]: Require `customer_id`, `product_id`, `amount`, and `date`.  
R196 [API `/create_promise` request]: `product_id` is a string, `amount` is a number, and `date` is a string with format `date`.  
R197 [API `/create_promise` response]: Besides `ok` and `error`, the schema includes `promise_id` as a string.  
R198 [API `/add_note` summary; A rule 46]: The API describes Brief B’s recording of why a product ended without a promise, but Brief A does not call `add_note`.  
R199 [API `/add_note` request]: Its API request requires string fields `customer_id`, `product_id`, and `reason`; string `text` is optional.  
R200 [API `/add_note` request]: Its `reason` enum is `refused`, `hardship`, `dispute`, `paid`, `service_error`.  
R201 [API `/schedule_callback` request]: Require `customer_id`, `date`, and `time`.  
R202 [API `/schedule_callback` request]: `date` is a string with format `date`; `time` is a string in `HH:MM`.  
R203 [API `/transfer_to_agent` request]: Require `customer_id` and string `queue`.  
R204 [API `/transfer_to_agent` request]: The queue enum is `restructuring`, `general`, `support`.  
R205 [API `/close_call` request]: Require `customer_id` and string `outcome`.  
R206 [API `/close_call` request]: The outcome enum is `promise`, `paid`, `transferred`, `no_promise`, `not_verified`, `not_reached`.  
R207 [API `/close_call` request `reason`]: String `reason` is required for every outcome except `promise` and `paid`.  
R208 [API `/close_call` request `reason`; A rule 46 closing table]: Although `reason` has no schema enum, use the brief’s exact permitted outcome/reason combinations.  
R209 [API `/close_call` summary]: Nothing is accepted after `close_call`.

## 12. Ambiguities

| Issue | Source limitation or interpretation |
|---|---|
| No amendment documents | No overrides are invented. Brief A and the supplied API are the only effective sources. |
| API mentions Brief B | Brief B was not supplied. Its mention does not override Brief A’s prohibition on `add_note` or create a multi-product workflow. |
| Field-name or enum disagreements | No direct Brief A/API field-name or enum disagreement is present. Queue `general` maps to closing reason `human`; these are different fields, not interchangeable codes. |
| `close_call.reason` is absent from the schema’s required array | The same API’s field description requires it for every outcome except `promise` and `paid`, agreeing with Brief A. Apply that conditional requirement. |
| `close_call.reason` has no enum | It is a string at schema level; actual use follows Brief A’s outcome/reason table. API permissiveness is not permission to invent reasons. |
| “none” for reason | Implement the closing table’s “none” by omitting the field, not sending the string `none` or a null value unsupported by its string schema. |
| One-product brief versus `products` array | The array is the API response structure; it does not supersede the one-product scope. No selection or ordering rule is supplied for multiple returned products. |
| General tool-failure recovery | Except for `create_promise`, no retry count or separate terminal service-failure outcome is supplied. HTTP `500` permits repetition. Do not invent a `no_promise` / `service_error` mapping for other tools. |
| Callback and transfer failures | Brief A directs calling the relevant tool and then closing with the corresponding callback or transfer outcome. It does not separately explain an `ok:false` or exhausted-failure branch for those tools. Preserve the supplied sequence and mappings without inventing a successful action or an alternative failure code. |
| HTTP `500` retry permission versus exactly-once `close_call` | The generic API response permits repetition, while Brief A requires exactly one final `close_call` and the API says nothing is accepted afterward. This specification preserves the specific final-closure constraint; no recovery resolving all requirements is supplied. |
| Missing response fields | Response schemas do not declare required fields. Missing values do not prove success, verification, or a recorded booking. No recovery workflow is supplied for malformed or incomplete responses. |
| Third-party “say nothing beyond the opening” versus “ask when” | Preserve both source instructions: no additional explanation or disclosure, while allowing the expressly required callback question and coordination. A prohibition on every later utterance would contradict the same rule. |
| First-sentence wording | Its content is mandatory, but no exact full sentence is supplied. No additional mandatory verbatim script is introduced. |
| Timezone | No named timezone, offset, or daylight-saving conversion is supplied. Use `now`; do not introduce another clock. |
| Calendar-week boundary | The sources say “current” and “following” calendar week but do not expressly define their boundaries. Monday-to-Friday business days alone do not establish a mandatory Monday-to-Sunday calendar-week convention. No boundary convention is added. |
| Callback on a non-business `today` | The callback rule says today **or** the next business day. Today is not separately required to be a business day. |
| No third-party callback proposal | The sources define one alternative request for an invalid proposal, but no branch for no proposed time at all. Do not invent a retry count or closing reason. |
| Customer-requested callback | The documented callback rules are in the third-party section. They do not expressly provide a workflow or outcome for a reached customer requesting a callback. |
| Non-counting verification retries | Unreadable dates and the `day_month_swapped` retry do not consume the wrong-answer allowance. No independent maximum retry count is supplied. |
| Spoken phone digits | The tool requires a four-digit string. No grouped-number interpretation, word-to-digit lexicon, or additional phone-answer parsing policy is supplied. |
| Ambiguous spoken dates | Numeric-only dates use day, month, year. No two-digit-year expansion or other ambiguity-resolution policy is supplied beyond the month-as-a-word hint. |
| Initial “today” question on a non-business day | The exact first question remains required by rule 28, but rule 19 prohibits recording a non-business promise date. A weekend/holiday proposal follows rule 20; no exception is created. |
| Attempt-1 date may be past | The literal “last business day of this week” instruction can identify a date before today when today falls after that business day. Rule 19 still prohibits recording a past date. No replacement persuasion date is supplied. |
| Weekend/holiday adjustment versus other date limits | Offer the next business day as directed, but a recorded promise must still satisfy the today-or-later and deadline limits. No specific further script is supplied for an ineligible result. |
| Customer proposes a past date | Rule 19 excludes it, but no specific counter-offer count or terminal branch is supplied. |
| Customer proposes more than `past_due` | The explicit acceptance interval ends at `past_due`. No overpayment acceptance or counter-offer policy is supplied. |
| `floor > past_due`, missing product fields, or unsupported `days_late` | No workflow is supplied for these cases. Do not invent a cap, substitute amount, or deadline band. |
| Repeat-floor permission versus no repeated offer | Rule 26 expressly permits naming the floor again on the deadline in attempt 2. Rule 31 also prohibits repeating a refused offer. Preserve both; the sources do not supply a general definition of offer equivalence or another exception. |
| Persuasion attempt counting | Flat refusals and non-answers use the listed persuasion attempts. Stop when the allowed attempts are used up. No extra final persuasion offer is authorized. |
| Hardship plus restructuring | Rule 32 expressly takes precedence over rule 41. Apply hardship handling and offer support rather than automatically transferring to restructuring. |
| Hardship plus volunteered proposal | The explicit exception allows a customer-initiated promise despite the no-persuasion rule. It does not waive verification, amount/date limits, or confirmation. |
| Refusal to answer versus asking the call’s purpose | A purpose question instead of a security answer counts as declining. Explain protection once without prohibited disclosure. A second refusal or such question ends verification. |
| Multiple competing terminal events after a promise | The closing table specifies `promise` when at least one promise was recorded, and expressly gives a subsequent transfer precedence. Other rules separately direct `paid`, `dispute`, or `refused` outcomes for their triggers, without expressly ordering those later events against an existing promise. No additional precedence hierarchy is supplied. Do not cancel or alter the recorded promise. |
| Transfer and goodbye ordering | The transfer tool precedes final `close_call`; thanks and goodbye also precede `close_call`. No additional transfer-completion script is supplied. |
| Complaints, other vulnerability, language, and abuse | No independent workflows, codes, scripts, or limits are supplied. Apply another explicit rule only when its trigger matches. |
| One question at a time | Expressly mandatory for the two security questions. No separate universal conversation rule is supplied. |
| Currency, rounding, percentages, and payment mechanics | None is supplied. Do not add a currency, decimal rule, percentage threshold, payment method, or payment-taking capability. |
| Customer service number | The scam response refers to the number but does not supply it. Do not invent one. |

These gaps remain source limitations. No unsupported branch, code, retry count, holiday, amount limit, or banking term is added to resolve them.

## 13. Verifier corrections

- Removed the unsupported mandatory Monday-to-Sunday calendar-week convention everywhere. The sources define business days, not calendar-week boundaries.
- Removed the added phone-answer parsing rule for digits spoken “in parts.” Retained the API’s exact four-digit string requirement and documented the missing parsing policy.
- Removed the unsupported assertion that the specified next-week attempt-1 offer can exceed the deadline. Retained the actual date-eligibility requirements and the unresolved past-date case.
- Removed the imposed general definition of a repeated offer as an identical amount/date pair. Preserved both the no-repeated-offer rule and the explicit permission to name the floor again on the deadline in attempt 2.
- Restored the source’s callback and transfer sequence without adding an unstated success-only outcome condition. Kept failed-tool handling explicitly unresolved rather than inventing a failure mapping.
- Clarified that successful promise recording is not a universal prerequisite for closure; failed-recording and other terminal branches still require exactly one `close_call`.
- Restored the exact third-party disclosure wording alongside its expressly permitted callback question.
- Added omitted API context: the Build the Builder hackathon mock, provider hosting, ledger use by the scorer, and the purpose stated in the `add_note` summary.
- Explicitly documented that product-object response properties are not declared required, and distinguished API response-schema properties from additional mandatory response-reading procedures.
- Clarified where the source expressly requires saying that the remainder stays overdue, without adding a universal partial-payment script.
- Retained all supplied limits, holidays, quoted customer phrases, required scripts, API field names, formats, enum values, and outcome/reason mappings. No amendments or replacement values were supplied.