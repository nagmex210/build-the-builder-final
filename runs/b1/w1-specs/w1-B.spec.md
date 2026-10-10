# Rule spec

## 0. Sources and precedence

### Sources

1. **`briefs/brief-a.md` — Brief A: Freya Bank, early-stage collections, one product.**
   - References use `A §<section>` for unnumbered material and `A <number>` for numbered rules.
   - Establishes the base call flow, identity checks, payment rules, calendar and closing rules.
2. **`briefs/brief-b.md` — Brief B: Freya Bank, up to three products.**
   - References use `B <number>` and `B Closing`.
   - Every rule of Brief A applies unless replaced by Brief B.
   - The effective rules below apply to customers with one to three products.
3. **Supplied tool API file — OpenAPI `3.0.3`, title `Freya Bank collections tools`, version `0.3-draft`.**
   - No filename was supplied.
   - References use `API /<tool>` and `API info`.
   - Controls tool request field names, types, formats and enum values.
   - Describes a hosted mock of the bank’s systems for the Build the Builder hackathon. Every tool call is written to the ledger the scorer reads.
   - The service does not enforce the brief’s business rules; the agent must enforce them.

No separate amendment, memo, mail, code sheet or later brief was supplied. Freya Bank is fictional; every customer, debt and payment is synthetic.

The job is early-stage collections for customers `1` to `45` days late: find the customer, verify identity, state the debt, seek payment promises where possible and close with the correct outcome.

### Overrides

The following are the **effective requirements**, with Brief B’s replacements applied:

- **Product scope and account result:** `get_account` returns one to three products, each with its own `past_due`, `days_late` and floor (B 1).
- **Disclosure:** State every late product, one sentence each, before asking for anything (B 2).
- **Band and deadline:** Calculate separately for each product; products can have different deadlines (B 3).
- **Initial payment question:** First ask whether the customer can pay all products today (B 4).
- **Product follow-up:** If not, proceed in `get_account` order. Do not ask about today again for each product. Start each product at attempt 1 of A 30, subject to applicable date/amount handling and hardship precedence (B 4; A 29, A 32).
- **Persuasion allowance:** Count attempts separately per product (B 5).
- **Shared date:** When one date is named for everything and exceeds a product’s deadline, use that product’s own deadline and say so in the read-back. Other products keep the named date, subject to the remaining date rules (B 6).
- **Confirmation:** Read all proposed promises back together and obtain one confirmation. Then call `create_promise` once per product, subject to the specified failure retry (B 7).
- **Products without promises:** On a non-transfer account-handling call, call `add_note` for every product without a promise, including when none receives a promise. Reasons are `refused`, `hardship`, `dispute`, `paid` or `service_error` (B 8).
- **Product refusal:** Stop persuasion on a product when its attempts are exhausted; use reason `refused` and apply B Closing to the overall call (B 5, B 8, B Closing).
- **Hardship without transfer or promise:** Use `hardship` for the applicable unpromised product or products and apply B Closing. Make no persuasion attempt after a hardship trigger (A 32; B 8, B Closing).
- **Recording failure:** If one product’s `create_promise` fails twice, retain successfully recorded promises and note the failed product `service_error`, unless the call transfers (B 10–11).
- **Already paid or disputed:** Take no promise for the affected product, retain its applicable reason and continue with the other products (B 9).
- **Restructuring:** Transfer to queue `restructuring`. Recorded promises stay; promises agreed but not recorded before the request are not recorded (B 10).
- **All transfers:** Add no notes at all, before or after any restructuring, support or human transfer (B 10).
- **Closing precedence:** A transfer takes precedence. Otherwise, at least one recorded promise produces `promise`. With no recorded promise, use `paid` if every product is noted `paid`; otherwise use `no_promise` and the reason of the first product, in `get_account` order, whose note is not `paid` (B Closing).

Superseded operational instructions are not retained as alternative rules. API limitations and unresolved cases are listed in section 12.

## 1. Call variables

Every call starts with only these variables. Nothing else is known before tools are called.

| Exact variable name | Source example | Use |
|---|---|---|
| `customer_id` | `c_4f2a...` | Pass to every tool call. |
| `first_name` | `Daniel` | The person to ask for. |
| `last_name` | `Reyes` | The person to ask for; also used in customer address. |
| `title` | `Mr` or `Ms` | Address the customer as title plus last name. These are examples, not an API enum. |
| `now` | `2026-10-14T11:00` | Current date and time for all date rules. Never use the real clock. |

Address the customer as `{title} {last_name}`.

Calculation notation used below:

- `today = date(now)`.
- `add_business_days(d, n)` means the `n`th business day strictly after `d`; do not count the starting date.
- These are calculation notations, not additional incoming variables or tool fields.

No timezone or explicit calendar-week starting day is supplied; see section 12.

## 2. Tools (from the tool API file)

### Common API rules

- Base URL: `https://freya-bank-mock.freyavoice.workers.dev/v1`.
- All seven operations use `POST` with a required `application/json` request body containing an object.
- No key is required. The API describes `customer_id` in the body as the secret of one call.
- Every tool call is written to the ledger the scorer reads.
- Every `200` response has an object schema with `ok` (`boolean`) and `error` (`string`) properties.
- `ok: false` means the action was not carried out. Do not represent it as successful.
- No exact `error` strings or `error` enum are supplied.
- Every tool documents `500`: “The service failed. Nothing was recorded. The call may be repeated.”
- Response properties, including product-object properties, are not marked required. Do not fabricate missing response data.
- The service can record a promise on a holiday or past the deadline without complaint. Agent-side validation remains mandatory.
- Only `create_promise` has a specified failure retry count. The exactly-once closing requirement also remains effective. Other unresolved failures are addressed in section 12.

### `verify_identity`

**When:** After confirmation that the intended customer is speaking. Ask and verify `date_of_birth` first, then `phone_last4`, one question at a time.

**Request**

| Field | Type/format | Allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | No enum | Yes |
| `field` | `string` | `date_of_birth`, `phone_last4` | Yes |
| `answer` | `string` | For `date_of_birth`: `YYYY-MM-DD`; for `phone_last4`: four digits | Yes |

**Response properties**

| Field | Type | Meaning/use |
|---|---|---|
| `ok` | `boolean` | Whether the check action was carried out. |
| `error` | `string` | Failure information, if supplied; exact values are unspecified. |
| `verified` | `boolean` | Whether this security answer passed. |
| `wrong_answers_left` | `integer` | Remaining wrong-answer allowance across both questions. |
| `all_verified` | `boolean` | Whether both questions have passed. The business prerequisite is both questions passing; the API does not mark this property required. |
| `hint` | `string`, enum `day_month_swapped` | Ask the customer to say the month as a word; that retry does not count as a wrong answer. |

**Failure handling**

- An unreadable date is rejected with `ok: false` and does not count as a wrong answer. No separate clarification script or retry cap for unreadable dates is supplied.
- `hint: "day_month_swapped"` requires asking for the month as a word. That retry does not count as a wrong answer.
- A counted wrong answer consumes the shared allowance. Three wrong answers in total end verification.
- A `500` records nothing and may be repeated. A failed service action is not itself a wrong security answer.
- Other error-specific actions are not defined.

`answer` remains a string when it contains only digits.

### `get_account`

**When:** Only after both security questions pass. The API refuses access until then.

**Request**

| Field | Type | Allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | No enum | Yes |

**Response properties**

- `ok`: `boolean`.
- `error`: `string`.
- `products`: array; Brief B requires one to three products.

Each product object has these schema properties:

| Field | Type | Allowed values/use |
|---|---|---|
| `product_id` | `string` | Identifier for promises and notes. |
| `type` | `string` | Enum: `credit_card`, `personal_loan`, `car_loan`. |
| `card_last4` | `string` | Credit cards only. |
| `past_due` | `number` | Full past-due amount. |
| `days_late` | `integer` | Lateness for disclosure, band and deadline. |
| `minimum_payment` | `number` | Credit cards only; the credit-card floor. |
| `instalment_amount` | `number` | Loans only; the loan floor. |

Preserve array order for product handling and final outcome selection.

**Failure handling:** Do not invent account information after failure. A `500` may be repeated. Other retry limits and terminal failure outcomes are unspecified.

### `create_promise`

**When:** After checking the amount and date, reading all proposed promises back together and obtaining a clear yes to "Do you confirm?". One recorded promise per product.

**Request**

| Field | Type/format | Allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | No enum | Yes |
| `product_id` | `string` | Returned product identifier | Yes |
| `amount` | `number` | Apply section 6; no API enum or numeric bounds | Yes |
| `date` | `string`, format `date` | `YYYY-MM-DD`; apply section 6 | Yes |

**Response properties**

- `ok`: `boolean`.
- `error`: `string`.
- `promise_id`: `string`.

**Failure handling**

1. If recording fails, try once more.
2. If it fails again, say the promise could not be recorded.
3. Retain successfully recorded promises for other products.
4. On a non-transfer call, note the failed product with `reason: "service_error"`.
5. Calculate the overall outcome under section 9.

Say a promise is recorded only after `ok: true`. After a recorded promise, say exactly:

"You will receive a text message confirming this promise."

### `add_note`

**When:** On a non-transfer account-handling call, for every product ending without a promise, including when no product gets a promise.

On any transfer, add no notes at all, before or after it.

**Request**

| Field | Type | Allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | No enum | Yes |
| `product_id` | `string` | Returned product identifier | Yes |
| `reason` | `string` | `refused`, `hardship`, `dispute`, `paid`, `service_error` | Yes |
| `text` | `string` | No enum or prescribed text | No |

**Response properties:** `ok` (`boolean`), `error` (`string`).

**Failure handling:** A `500` may be repeated. No specific retry cap, substitute note code or terminal failure outcome is supplied. Do not assume a failed note was recorded.

**Sequencing implication:** B 9 requires noting paid/disputed products and continuing, but B 10 forbids notes even before a later transfer. Retaining pending reasons and deferring actual note calls until a non-transfer ending is selected is a way to satisfy both. This is an implementation consequence, not a separately supplied dialogue rule; see section 12.

A product-note reason may be `paid`. For `close_call` outcome `paid`, omit `reason`.

### `schedule_callback`

**When:** A third-party answerer supplies an acceptable callback date and time under section 3.

**Request**

| Field | Type/format | Allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | No enum | Yes |
| `date` | `string`, format `date` | `YYYY-MM-DD` | Yes |
| `time` | `string`, described as `HH:MM` | Apply the callback window | Yes |

**Response properties:** `ok` (`boolean`), `error` (`string`).

**Failure handling:** A `500` may be repeated. No specific retry cap or closing code for failed scheduling is supplied. Do not claim failed scheduling booked a callback.

The request uses separate `date` and `time` fields, not a timestamp field.

### `transfer_to_agent`

**When:** Accepted hardship support, an applicable restructuring request, or an insistent request for a human.

**Request**

| Field | Type | Allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | No enum | Yes |
| `queue` | `string` | `restructuring`, `general`, `support` | Yes |

**Response properties:** `ok` (`boolean`), `error` (`string`).

**Queue-to-closing mapping**

| Trigger | `queue` | `close_call.outcome` | `close_call.reason` |
|---|---|---|---|
| New payment plan or lower instalments, subject to hardship precedence | `restructuring` | `transferred` | `restructuring` |
| Customer insists on a human after the agent asks once to help first | `general` | `transferred` | `human` |
| Customer accepts hardship support | `support` | `transferred` | `support` |

**Failure handling:** A `500` may be repeated. No specific retry cap or fallback outcome is supplied. Do not claim a failed transfer succeeded.

`human` is a closing reason, not a queue value.

### `close_call`

**When:** Exactly once at the end of every call, including after a transfer. It is the last tool call; nothing is accepted after it.

Thank the customer and say goodbye before calling it.

**Request**

| Field | Type | Allowed values | Required |
|---|---|---|---|
| `customer_id` | `string` | No enum | Yes |
| `outcome` | `string` | `promise`, `paid`, `transferred`, `no_promise`, `not_verified`, `not_reached` | Yes |
| `reason` | `string` | Applicable reason from section 9; no API enum | Conditionally required by the property description and brief |

The schema’s `required` array contains only `customer_id` and `outcome`. The description and brief require `reason` for every outcome except `promise` and `paid`.

For `promise` and `paid`, omit `reason`. The table’s “none” is not a code string.

**Response properties:** `ok` (`boolean`), `error` (`string`).

**Failure handling:** The API generically permits repeating a `500`, but the brief requires exactly one `close_call`. Retain that explicit closing requirement; recovery from a failed close is unresolved.

## 3. Opening and who answered

### Opening

The first sentence must say:

- The speaker is a digital assistant.
- The call is from Freya Bank.
- The call is recorded.

A 1 specifies content, not a fixed verbatim first sentence.

Then ask exactly:

"Am I speaking with {title} {last_name}?"

Before identity verification is complete, do not say "collections", "debt", "payment" or the product. This applies to everyone, including relatives.

### Recognising the intended customer

Only these count as confirmation:

- "yes"
- "that's me"
- "speaking"
- The customer’s own name.

These do not count:

- "Hello"
- "go ahead"
- "who is this"

After an unconfirmed first response:

1. Answer an applicable customer question first, including robot/AI and scam questions.
2. Ask for person confirmation once more.
3. That follow-up is the second ask, not a restart.
4. If still unclear after the second ask, close `not_reached` / `unclear`.

Person confirmation is not security verification.

### Third party

- Do not say why the bank is calling.
- Say nothing beyond the opening content about the purpose of the call.
- Ask when the customer can be reached.
- A relative may not answer security questions.
- Tell a relative nothing about the account, even if they offer to pay.

### Callback window

A third-party callback must satisfy:

```text
callback_date ∈ {today, add_business_days(today, 1)}
10:00 ≤ callback_time ≤ 19:00
combine(callback_date, callback_time) > now
```

- Both time endpoints are included.
- The callback must be strictly later than `now`.
- Today is expressly allowed; the source does not separately require today to be a business day.
- The alternative is the next business day, not any later business day.

For a valid proposal:

1. Call `schedule_callback` with `customer_id`, `date` and `time`.
2. Close `not_reached` / `callback`.

For a proposal outside the window:

1. Ask once for another time.
2. If that replacement is also outside the window, do not schedule.
3. Close `not_reached` / `no_callback`.

This is one replacement request, separate from technical retries.

### Other answerer branches

| Trigger | Required action | Outcome | Reason |
|---|---|---|---|
| Number does not belong to the customer | Close without account disclosure. | `not_reached` | `wrong_number` |
| Customer has died | Say "I am sorry for your loss."; ask nothing else; close. | `not_reached` | `deceased` |
| Second person-confirmation ask remains unclear | Close without security/account disclosure. | `not_reached` | `unclear` |

Thank the customer/answerer and say goodbye before `close_call`, including the deceased branch. Ask no further questions in that branch.

Customer-requested callbacks are not defined; see sections 8 and 12.

## 4. Identity verification

### Order and formats

1. Ask the date of birth.
2. Convert the answer and call:

   ```text
   verify_identity(
     customer_id,
     field = "date_of_birth",
     answer = "YYYY-MM-DD"
   )
   ```

3. After that question passes, ask the last four digits of the phone number on file.
4. Call:

   ```text
   verify_identity(
     customer_id,
     field = "phone_last4",
     answer = four-digit string
   )
   ```

5. Call `get_account` only after both questions pass. Use the returned verification information; do not assume success.

### Normalisation

- Convert dates to `YYYY-MM-DD`, whatever way the customer said them.
- Read a numbers-only date as day, month, year.
- If `hint: "day_month_swapped"` is returned, ask for the month as a word.
- `phone_last4` requires four digits in a string. Preserve those digits, including any leading zeroes.
- No detailed grammar is supplied for ambiguous years, incomplete dates, ambiguous number words or incomplete phone answers. Do not invent missing information.

### Wrong-answer allowance

```text
wrong_answer_limit = 3
wrong_answers_used = counted wrong answers across both questions
end_check when wrong_answers_used = 3
```

- The allowance is shared; it does not reset after the first question passes.
- A wrong answer may be asked again while allowance remains.
- The `day_month_swapped` retry does not count as a wrong answer.
- An unreadable date rejected with `ok: false` does not count.
- A failed service action is not itself a wrong security answer.

After three wrong answers:

- Do not state the debt.
- Tell the customer to use the mobile app or a branch.
- Close `not_verified` / `failed`.

### Declining verification

- On the first refusal, explain once that the questions protect the account.
- Asking what the call is about instead of answering counts as declining.
- A second refusal or second such question closes `not_verified` / `declined`.
- Do not disclose prohibited subject matter to answer the question.
- If the same customer says twice that they do not want to talk before verification, close `not_verified` / `declined`.
- Human-request handling applies before and after verification.

## 5. After verification: debt disclosure and products

After both security questions pass:

1. Call `get_account`.
2. Read its one to three products.
3. Say the call is from the collections team about a late payment.
4. State every late product, one sentence each, before asking for anything.
5. For each product, state:
   - Product name in words.
   - `past_due`.
   - `days_late`.

| API `type` | Spoken description |
|---|---|
| `credit_card` | "credit card ending 4821" is the source example; use the returned `card_last4`, not a hard-coded `4821`. |
| `personal_loan` | "personal loan" |
| `car_loan` | "car loan" |

First ask whether the customer can pay all products today.

If not:

- Work through products in `get_account` order.
- Do not ask about today again for each product.
- Start each product at attempt 1, subject to the rules for volunteered dates/amounts and hardship.
- Calculate each product’s band, deadline and floor separately.
- Count attempts per product.
- The customer may promise some products and refuse others.
- A dispute or already-paid claim on one product does not end the call.
- Read all proposed promises back together and obtain one confirmation.
- Call `create_promise` once per product, retrying a failed recording only once.

Do not offer discounts, waivers, instalment plans or unsupported terms. Do not invent missing account facts.

## 6. Payment promises

### Per-product amount formulas

For product `p`:

```text
full_amount(p) = p.past_due

floor(p) =
  p.minimum_payment   if p.type = "credit_card"
  p.instalment_amount if p.type ∈ {"personal_loan", "car_loan"}

explicitly_accepted_customer_proposal_range:
  floor(p) ≤ amount ≤ full_amount(p)
```

Both stated acceptance bounds are included. The sources do not specify handling of a customer proposal above `past_due`; the range above is not an API numeric constraint.

- Ask for the full past-due amount first.
- Never ask "how much can you pay?".
- The agent proposes every amount.
- Customers may nevertheless volunteer an amount.
- If full payment is too much, offer the floor once and say the rest stays overdue.
- If the floor is refused, treat that as a flat refusal.
- Attempt 2 may name the floor again on the deadline.
- Accept a customer-proposed amount from floor to full, inclusive.
- Below the floor, say it cannot be recorded and offer the floor once.
- If that floor is not accepted, treat the response as a flat refusal.

No fixed currency minimum, percentage, currency or rounding rule is supplied.

### Per-product deadline formulas

```text
band(p) =
  early if 1 ≤ p.days_late ≤ 7
  late  if 8 ≤ p.days_late ≤ 45

deadline(p) =
  add_business_days(today, 12) if band(p) = early
  add_business_days(today, 7)  if band(p) = late

persuasion_limit(p) =
  1 if band(p) = early
  2 if band(p) = late

acceptable_date(p, d) ⇔
  today ≤ d
  AND is_business_day(d)
  AND d ≤ deadline(p)
```

- Exclude today when counting business days after today.
- Today is an eligible promise date only if it is a business day.
- The deadline is included.
- Use `now`, not a due date or the real clock.
- No band or deadline is supplied outside `1` to `45` days late.

### Weekend and holiday proposals

For a weekend or holiday date `d` not after the deadline, offer:

```text
next_business_day_after(d) =
  earliest business-day date strictly after d
```

The resulting promise must still satisfy the general date bounds.

If the named day is after the deadline, use the after-deadline rule instead.

### Vague dates

For "next week", "end of the month" or "when my salary comes":

1. Ask once for the exact day.
2. If no exact day is supplied, propose the product’s deadline.

### Relative weekdays

```text
this_weekday(w) = weekday w in the current calendar week
next_weekday(w) = weekday w in the following calendar week
```

- "Next <weekday>" means that weekday in the following calendar week.
- "This <weekday>" means that weekday in the current week.
- "next Friday" said on a Friday is Friday of the following week.
- The resulting date must still satisfy the general date rules.
- The sources do not define the first day of a calendar week; this spec does not invent one.

### Individual proposal after the deadline

If `d > deadline(p)`:

1. Say the latest date that can be recorded is the deadline.
2. Offer that deadline.
3. If refused, treat the response as a flat refusal.

No extension beyond the deadline is authorised.

### One date for everything

For one named date `d` applying to everything:

```text
date_for_readback(p) =
  deadline(p) if d > deadline(p)
  d           otherwise
```

- Use an affected product’s own deadline.
- Say so in the combined read-back.
- Other products keep the named date, subject to remaining date rules.
- Obtain confirmation before recording. B 6 does not waive confirmation.

### Persuasion sequence

First ask whether all products can be paid today. If not, proceed in returned order, starting each product at attempt 1 without repeating the today question.

A flat refusal or non-answer uses a persuasion attempt. A no to paying today with no date and no amount is a flat refusal.

A volunteered date or amount is never itself a refusal; handle it under the date and amount rules.

```text
last_business_day(W) = latest business-day date in calendar week W

attempt_1_date =
  last_business_day(next_week)
    if today = last_business_day(this_week)
  last_business_day(this_week)
    otherwise

attempt_1_amount(p) =
  floor(p)       if the customer already said full_amount(p) is too much
  full_amount(p) otherwise

attempt_2_date(p) = deadline(p)
attempt_2_amount(p) = floor(p)
```

- Attempt 1 is available in both bands.
- Attempt 2 is for the `late` band only.
- Do not exceed the product’s allowance.
- When attempts are used up, stop persuasion on that product.
- Do not repeat an offer already refused.
- Use `refused` for an unpromised product whose attempts are exhausted, and apply the multi-product closing rules.
- The permission to name the floor again at attempt 2 does not supply a general permission to repeat an identical refused offer.

The sources do not provide a replacement for an attempt-1 date already in the past, or for an exactly duplicated refused offer. See section 12.

### Hardship precedence

Illness, a death in the family or job loss triggers section 8.

- Say one short sentence of sympathy.
- Make no persuasion attempt.
- Offer connection to support.
- Hardship takes precedence over persuasion and restructuring handling.
- A customer may still independently name a date or amount; apply the ordinary promise rules.

### Limits on promises and terms

```text
recorded_promises_per_product ≤ 1
recorded_promises_per_call ≤ number_of_returned_products ≤ 3
```

- A retry is not permission for a second successful promise.
- A recorded promise cannot be changed or cancelled in the same call.
- If asked, say it can be changed in the mobile app.
- Never offer a discount, waiver, instalment plan or other unsupported term.
- A new payment plan or lower-instalment request requires the applicable transfer, not agent negotiation of a plan.

### Read-back and recording

1. Check every proposed amount and date.
2. Read all proposed promises back together: product, amount and date.
3. Ask exactly "Do you confirm?".
4. Call `create_promise` only after a clear yes.
5. If an amount or date changes, check the new value and read back again.
6. Supply `customer_id`, `product_id`, numeric `amount` and date-format string `date`.
7. If recording fails, try once more.
8. After a second failure, say it could not be recorded; retain `service_error` for that product and keep successful promises.
9. Say a promise is recorded only after `ok: true`.
10. After a recorded promise, say exactly:

"You will receive a text message confirming this promise."

## 7. Calendar

### Business days

```text
is_business_day(d) ⇔
  weekday(d) ∈ {Monday, Tuesday, Wednesday, Thursday, Friday}
  AND d ∉ bank_holidays
```

Freya Bank holidays, exactly:

- `2026-10-26`
- `2026-11-11`
- `2026-11-26`
- `2026-12-25`
- `2027-01-01`

Do not add holidays.

### Clock and date conventions

- All calculations use supplied `now`, never the real clock.
- Promise dates are date-only values.
- Callback dates and times are separate fields.
- Callback time is `HH:MM`.
- Tool dates are `YYYY-MM-DD`.
- Business-day offsets exclude the starting date.
- “Today or later” and “not after the deadline” are inclusive.
- Callback times `10:00` and `19:00` are inclusive; callback datetime must be strictly later than `now`.
- “This” and “next” weekday refer to the current and following calendar weeks.
- No timezone, daylight-saving convention or calendar-week starting day is supplied.

## 8. Special situations

On non-transfer account-handling calls, product reasons are written with `add_note`. The final call-level result follows section 9.

| Situation/trigger | Say/do | Tools and exact values | Outcome and reason |
|---|---|---|---|
| Illness, a death in the family or job loss | Say one short sentence of sympathy. Make no persuasion attempt. Offer connection to customer support. This precedes persuasion and restructuring. | If accepted, `transfer_to_agent`, `queue: "support"`; no notes before or after transfer. | `transferred` / `support`. |
| Hardship support declined, no voluntary promise | Do not persuade. Use `hardship` for applicable unpromised products. The sources do not provide a detailed product-allocation dialogue for unclear hardship scope. | On non-transfer close, `add_note`, `reason: "hardship"`. | Apply section 9; the selected no-promise reason may be `hardship`. |
| Customer in hardship independently names a date or amount | Apply date, amount and confirmation rules. | `create_promise` after confirmation. | A successful promise contributes to `promise`, unless the call transfers. |
| "I already paid" referring to this past-due amount | Say payments can take one business day to appear. Take no promise for that product; continue others. | On non-transfer close, `add_note`, `reason: "paid"`. | `paid` only if no promise was recorded and every product is noted `paid`; otherwise section 9. |
| "This debt is not mine" or "I never had this product" | Do not argue. Take no promise for that product; continue others. | On non-transfer close, `add_note`, `reason: "dispute"`. | Apply section 9; selected no-promise reason may be `dispute`. |
| Product said to have been closed or paid off in the past | Treat as a dispute, not payment of the current past-due amount. | `add_note`, `reason: "dispute"`, on a non-transfer call. | Apply section 9. |
| Flat refusal or non-answer | Use the permitted product persuasion sequence, then stop. | Note an unpromised product `refused` on a non-transfer call. | Apply section 9. |
| Customer says twice they do not want to talk, before verification | End without account disclosure. | `close_call`, `outcome: "not_verified"`, `reason: "declined"`. | `not_verified` / `declined`. |
| Customer says twice they do not want to talk, after verification | Stop the conversation. Apply refusal handling to unpromised products ending for that reason; preserve already established product results and recorded promises. | Applicable non-transfer product notes, then `close_call`. | Recorded-promise and product-order precedence under section 9. |
| Request for a new payment plan or lower instalments | Do not describe a plan. Subject to hardship precedence, transfer. Recorded promises stay; do not record promises merely agreed before the request. | `transfer_to_agent`, `queue: "restructuring"`; no notes before or after transfer. | `transferred` / `restructuring`, including after a recorded promise. |
| Request for a human | Ask once whether the agent can help first. If the customer insists, transfer. Applies before and after verification. | `transfer_to_agent`, `queue: "general"`; no notes on the transferred call. | `transferred` / `human`, including after a recorded promise. |
| Robot or AI question | Say the agent is Freya Bank's digital assistant and continue. | No dedicated tool. | Continue the applicable flow. |
| "Is this a scam?" | Say the call can be verified by phoning Freya Bank's customer service number, and continue. | No dedicated tool; no actual number is supplied. | Continue the applicable flow. |
| Question not answerable from tools | Say the agent does not have that information. Do not invent figures, dates or reasons. | No additional tool supplied. | No dedicated outcome. |
| Request to change or cancel a recorded promise | Do not change or cancel it in this call. Say it can be changed in the mobile app. | No amendment/cancellation tool supplied. | Recorded promise remains relevant to closing. |
| Two recording failures for a product | Say the promise could not be recorded. Keep other recorded promises. | On non-transfer close, `add_note`, `reason: "service_error"`. | Apply section 9. |
| Customer-requested callback | No customer-specific callback rule is supplied. The documented branch is for someone else answering. | No additional parameters or dedicated code supplied. | Unspecified. |
| Complaint | No dedicated complaint policy supplied; an independently satisfied defined branch still applies. | No complaint queue, note reason or outcome supplied. | No dedicated outcome. |
| Vulnerability outside listed hardship triggers | No separate vulnerability policy supplied. | No additional queue or code supplied. | No dedicated outcome. |
| Language request or barrier | No language-handling policy supplied. | No language field, queue or code supplied. | Unspecified. |
| Abuse | No abuse-specific policy supplied. | No abuse field, note reason or outcome supplied. | Unspecified. |

Wrong number, deceased and third-party callbacks are in section 3. Verification failure/refusal is in section 4.

## 9. Closing and outcome table

### Complete effective outcome/reason table

All codes are exact strings.

| `outcome` | `reason` | When it applies |
|---|---|---|
| `promise` | Omit | At least one promise was recorded, unless the call transfers. |
| `paid` | Omit | No promise was recorded and every product is noted `paid`. |
| `transferred` | `restructuring` | Transfer with queue `restructuring`. |
| `transferred` | `human` | Insistent human request transferred with queue `general`. |
| `transferred` | `support` | Accepted hardship support transferred with queue `support`. |
| `no_promise` | `refused` | No recorded promise or transfer; first non-`paid` product note in returned order is `refused`. |
| `no_promise` | `hardship` | No recorded promise or transfer; first non-`paid` product note in returned order is `hardship`. |
| `no_promise` | `dispute` | No recorded promise or transfer; first non-`paid` product note in returned order is `dispute`. |
| `no_promise` | `service_error` | No recorded promise or transfer; first non-`paid` product note in returned order is `service_error` following two recording failures. |
| `not_verified` | `failed` | Three counted wrong security answers in total. |
| `not_verified` | `declined` | Second verification refusal or equivalent question after one protection explanation; also twice declining to talk before verification. |
| `not_reached` | `callback` | Third-party callback scheduled within the permitted window. |
| `not_reached` | `no_callback` | Initial third-party proposal and one requested replacement are outside the window; no callback scheduled. |
| `not_reached` | `wrong_number` | Answerer says the number does not belong to the customer. |
| `not_reached` | `deceased` | Answerer says the customer has died. |
| `not_reached` | `unclear` | Person confirmation remains unclear after two asks. |

A transfer overrides a recorded promise and uses its own transfer reason. No other outcome/reason pairs are supplied.

### Final selection for an account-handling call

```text
if the call transfers:
    outcome = "transferred"
    reason = transfer-specific reason
else if at least one promise was recorded:
    outcome = "promise"
    omit reason
else if every returned product is noted "paid":
    outcome = "paid"
    omit reason
else:
    p = first product in get_account order whose note reason is not "paid"
    outcome = "no_promise"
    reason = p's note reason
```

Earlier terminal branches use `not_reached` or `not_verified`. They do not require account retrieval or product notes.

### Notes

- On a non-transfer account-handling call, note every product without a recorded promise.
- This applies whether some or no products have promises.
- Supply the affected `product_id`.
- Use only `refused`, `hardship`, `dispute`, `paid` or `service_error`.
- Notes are for products without promises.
- Optional `text` has no prescribed content.
- On any transfer, add no notes before or after it.
- Pending reasons can be retained until a non-transfer ending is selected to satisfy that prohibition.
- After two recording failures, use `service_error` for the failed product and keep successful promises.
- No product notes are required for branches ending before account access.

### Final tool call

- Every call ends with exactly one `close_call`.
- It is the last tool call.
- Nothing is accepted afterward.
- A transfer does not replace `close_call`.
- Thank the customer and say goodbye before `close_call`.
- Supply `customer_id`, `outcome` and the applicable required `reason`.
- Omit `reason` for `promise` and `paid`; do not send `"none"`.

## 10. Honesty and general conduct

- Identify as a digital assistant from Freya Bank and disclose recording in the first sentence.
- On a robot/AI question, say the agent is Freya Bank's digital assistant.
- Before verification, do not say "collections", "debt", "payment" or the product.
- Never disclose account information to relatives, even if they offer to pay.
- Relatives cannot complete security questions.
- Ask security questions one at a time.
- Answer applicable questions before the second person-confirmation ask; do not reset the ask count.
- Explain the protective purpose of verification once after a refusal.
- Do not disclose debt after failed or declined verification.
- Retrieve account details only after both questions pass.
- Use returned facts and supplied `now`; do not invent figures, dates, reasons, product details or a customer service number.
- If information is unavailable from the tools, say so.
- Never ask "how much can you pay?".
- Do not treat a volunteered amount or date as itself a refusal.
- Do not argue with disputes.
- Make no persuasion attempt after a listed hardship trigger.
- Do not exceed per-product persuasion allowances or repeat refused offers.
- The floor may be named again at attempt 2 on the deadline as expressly provided; exact duplicate-offer cases remain unresolved.
- Do not offer discounts, waivers, instalment plans or unsupported terms.
- Do not describe a new plan when restructuring transfer is required.
- Do not create a promise without clear confirmation.
- Do not change or cancel a recorded promise in the same call.
- Say a promise is recorded only after `ok: true`.
- Do not represent failed tool actions as completed.
- Preserve recorded promises when another recording fails or the call transfers.
- Do not record merely agreed promises after a restructuring request.
- Do not rely on service acceptance to establish compliance with the brief.
- Ask nothing further after learning the customer has died.
- Observe the exactly-once, last-tool-call closing rule.

No broader language, abuse, complaint or vulnerability script is supplied.

## 11. Numbered rule checklist

### Scope, inputs and opening

- R1 [A preamble; B preamble]: Freya Bank is fictional; every customer, debt and payment is synthetic.
- R2 [A §1; B 1]: Handle early-stage collections for `1` to `45` days late on one to three products.
- R3 [A §1]: Find the customer, verify identity, state the debt, seek a promise where possible and close correctly.
- R4 [B introduction]: Apply every Brief A rule unless Brief B replaces it.
- R5 [A §2]: Start with `customer_id`, `first_name`, `last_name`, `title` and `now`.
- R6 [A §2]: Nothing else is known before tools are called.
- R7 [A §2]: Pass `customer_id` to every tool call.
- R8 [A §2]: Address the customer as title plus last name.
- R9 [A §2]: Use `now` for every date rule, never the real clock.
- R10 [A 1]: The first sentence identifies the speaker as a digital assistant.
- R11 [A 1]: The first sentence identifies Freya Bank as the caller.
- R12 [A 1]: The first sentence states that the call is recorded.
- R13 [A 1]: Do not say "collections", "debt", "payment" or the product before verification.
- R14 [A 1]: That restriction applies to everyone, including relatives.
- R15 [A 2]: Ask "Am I speaking with {title} {last_name}?".
- R16 [A 3]: Only "yes", "that's me", "speaking" or the customer’s own name confirms the person.
- R17 [A 3]: "Hello", "go ahead" and "who is this" do not confirm the person.
- R18 [A 3]: After an unconfirmed first response, ask once more.
- R19 [A 3]: Answer an applicable customer question before the follow-up ask.
- R20 [A 3]: The following ask is the second ask.
- R21 [A 3]: If still unclear, close `not_reached` / `unclear`.
- R22 [A 4]: On a robot/AI question, say the agent is Freya Bank's digital assistant and continue.

### Third parties and callbacks

- R23 [A 5]: Do not tell a third party why the bank is calling.
- R24 [A 5]: Disclose no further subject matter beyond the opening content.
- R25 [A 5]: Ask when the customer can be reached.
- R26 [A 6]: Callback date must be today or the next business day.
- R27 [A 6]: Callback time must be `10:00` to `19:00`, inclusive.
- R28 [A 6]: Callback datetime must be later than `now`.
- R29 [A 6]: Call `schedule_callback` with the date and time.
- R30 [A 6]: Close `not_reached` / `callback`.
- R31 [A 7]: After an out-of-window proposal, ask once for another time.
- R32 [A 7]: If the replacement is also outside the window, do not schedule.
- R33 [A 7]: Close `not_reached` / `no_callback` after that invalid replacement.
- R34 [A 8]: Wrong number closes `not_reached` / `wrong_number`.
- R35 [A 9]: If the customer has died, say "I am sorry for your loss.".
- R36 [A 9]: Ask nothing else after learning the customer has died.
- R37 [A 9]: Close `not_reached` / `deceased`.
- R38 [A 10]: A relative may not answer security questions.
- R39 [A 10]: Tell relatives nothing about the account, even if they offer to pay.

### Verification

- R40 [A 11]: Ask security questions one at a time.
- R41 [A 11]: Ask date of birth first.
- R42 [A 11]: Ask the last four phone digits on file second.
- R43 [A 11]: Call `verify_identity` with each answer.
- R44 [A 11; API]: Convert date of birth to `YYYY-MM-DD`.
- R45 [A 11]: Interpret numeric dates as day, month, year.
- R46 [API /verify_identity]: Use `date_of_birth` and `phone_last4`.
- R47 [API /verify_identity]: Send phone digits as a four-digit string.
- R48 [A 12]: A wrong answer may be asked again.
- R49 [A 12]: Three wrong answers in total end the check.
- R50 [A 12]: Count across both questions.
- R51 [API /verify_identity]: `wrong_answers_left` supplies the remaining allowance.
- R52 [A 13; API]: On `hint: "day_month_swapped"`, ask for the month as a word.
- R53 [A 13]: That retry does not count as a wrong answer.
- R54 [API /verify_identity]: An unreadable date is rejected with `ok: false`.
- R55 [API /verify_identity]: An unreadable date does not count as a wrong answer.
- R56 [A 14]: After three wrong answers, do not state the debt.
- R57 [A 14]: Tell the customer to use the mobile app or a branch.
- R58 [A 14]: Close `not_verified` / `failed`.
- R59 [A 15]: Explain once that the questions protect the account after the first refusal.
- R60 [A 15]: Asking what the call is about instead of answering counts as declining.
- R61 [A 15]: A second refusal or second such question closes `not_verified` / `declined`.
- R62 [API /verify_identity]: Use returned verification information; do not assume success or require an optional response property as an additional source rule.

### Account disclosure and multi-product handling

- R63 [A 16; API]: Call `get_account` only after both questions pass.
- R64 [B 1]: Expect one to three products.
- R65 [B 1]: Each has its own `past_due`, `days_late` and floor.
- R66 [A 17]: Say the call is from the collections team about a late payment.
- R67 [A 17; API]: Name each product in words.
- R68 [A 17; API]: Use returned `card_last4` for the credit-card description.
- R69 [A 17]: State each past-due amount.
- R70 [A 17]: State each product’s days late.
- R71 [B 2]: State every product, one sentence each, before asking for anything.
- R72 [B 3]: Calculate band and deadline per product.
- R73 [B 4]: First ask whether all products can be paid today.
- R74 [B 4]: If not, proceed in `get_account` order.
- R75 [B 4]: Do not repeat the today question per product.
- R76 [B 4; A 29, A 32]: Start each product at attempt 1, subject to applicable proposal handling and hardship.
- R77 [B 5]: Count persuasion attempts per product.

### Calendar and dates

- R78 [A §7]: Business days are Monday to Friday except listed holidays.
- R79 [A §7]: Exclude `2026-10-26`.
- R80 [A §7]: Exclude `2026-11-11`.
- R81 [A §7]: Exclude `2026-11-26`.
- R82 [A §7]: Exclude `2026-12-25`.
- R83 [A §7]: Exclude `2027-01-01`.
- R84 [A 18; B 3]: `1`–`7` days late is `early`.
- R85 [A 18; B 3]: Early deadline is the `12`th business day after today.
- R86 [A 18; B 5]: Early permits `1` persuasion attempt per product.
- R87 [A 18; B 3]: `8`–`45` days late is `late`.
- R88 [A 18; B 3]: Late deadline is the `7`th business day after today.
- R89 [A 18; B 5]: Late permits `2` persuasion attempts per product.
- R90 [A 19]: Promise dates must be today or later.
- R91 [A 19]: Promise dates must be business days.
- R92 [A 19]: Promise dates must not exceed the product deadline.
- R93 [A 20]: For a weekend/holiday date not after the deadline, offer the next business day.
- R94 [A 20]: For dates after the deadline, apply the after-deadline rule.
- R95 [A 21]: For a vague period, ask once for the exact day.
- R96 [A 21]: If still none, propose the deadline.
- R97 [A 22]: "Next <weekday>" means that weekday in the following calendar week.
- R98 [A 22]: "This <weekday>" means that weekday in the current week.
- R99 [A 22]: "next Friday" said on Friday means Friday of the following week.
- R100 [A 23]: For an individual date after the deadline, state and offer the deadline.
- R101 [A 23]: Refusal of that deadline is a flat refusal.
- R102 [B 6]: For one date covering everything, use each exceeded product deadline.
- R103 [B 6]: Disclose that adjustment in the read-back.
- R104 [B 6]: Other products keep the named date, subject to remaining date rules.

### Amounts and persuasion

- R105 [A 24]: Ask for full `past_due` first.
- R106 [A 24]: Never ask "how much can you pay?".
- R107 [A 24]: The agent proposes every amount.
- R108 [A 25]: Credit-card floor is `minimum_payment`.
- R109 [A 25]: Personal-loan floor is `instalment_amount`.
- R110 [A 25]: Car-loan floor is `instalment_amount`.
- R111 [A 26]: If full payment is too much, offer the floor once.
- R112 [A 26]: Say the rest stays overdue.
- R113 [A 26]: Floor refusal is a flat refusal.
- R114 [A 26]: Attempt 2 may name the floor again on the deadline.
- R115 [A 27]: Accept a proposed amount from floor to full, inclusive.
- R116 [A 27]: Below floor, say it cannot be recorded.
- R117 [A 27]: Offer the floor once after a below-floor proposal.
- R118 [A 27]: If not accepted, treat as flat refusal.
- R119 [A 29]: A proposed date is never itself a refusal.
- R120 [A 29]: A proposed amount is never itself a refusal.
- R121 [A 30]: Flat refusal or non-answer uses a persuasion attempt.
- R122 [A 30]: No to today with no date or amount is a flat refusal.
- R123 [A 30]: Attempt 1 proposes full payment unless already said to be too much.
- R124 [A 30]: Otherwise attempt 1 proposes the floor.
- R125 [A 30]: Attempt 1 date is the last business day of this week.
- R126 [A 30]: If today is that day, use the last business day of next week.
- R127 [A 30]: Attempt 2 is late-band only.
- R128 [A 30]: Attempt 2 proposes the floor on the deadline.
- R129 [A 31; B 5]: Stop product persuasion when attempts are exhausted.
- R130 [A 31]: Do not repeat an offer already refused.
- R131 [A 31; B 8; B Closing]: Use `refused` for that unpromised product and aggregate the call result.

### Hardship and prohibited terms

- R132 [A 32]: Illness, a death in the family or job loss triggers hardship.
- R133 [A 32]: Say one short sentence of sympathy.
- R134 [A 32]: Make no persuasion attempt.
- R135 [A 32]: Offer connection to customer support.
- R136 [A 32]: If accepted, transfer with queue `support`.
- R137 [A 32]: Close that transfer `transferred` / `support`.
- R138 [A 32; B 8; B Closing]: If declined without a promise, use applicable product reason `hardship` and aggregate.
- R139 [A 32]: Hardship precedes persuasion.
- R140 [A 32]: Hardship precedes restructuring.
- R141 [A 32]: A customer may still volunteer a date or amount for a compliant promise.
- R142 [A 33]: Never offer a discount.
- R143 [A 33]: Never offer a waiver.
- R144 [A 33]: Never offer an instalment plan.
- R145 [A 33]: Never offer unsupported terms.

### Confirmation and recording

- R146 [A 34; B 7]: Read all proposed products, amounts and dates back together.
- R147 [A 34; B 7]: Ask "Do you confirm?" for one combined confirmation.
- R148 [A 34]: Create only after a clear yes.
- R149 [B 7]: Call once per product, subject to the failure retry.
- R150 [A 35]: Check changed dates.
- R151 [A 35]: Check changed amounts.
- R152 [A 35; B 7]: Read back again after changes.
- R153 [A 36]: At most one recorded promise per product.
- R154 [A 36]: No in-call change to a recorded promise.
- R155 [A 36]: No in-call cancellation.
- R156 [A 36]: If asked, say it can be changed in the mobile app.
- R157 [A 37]: Say recorded only after `ok: true`.
- R158 [A 37]: Retry recording once after failure.
- R159 [A 37]: After the second failure, say it could not be recorded.
- R160 [B 11]: Keep other recorded promises.
- R161 [B 10–11]: Note the failed product `service_error`, except on a transfer.
- R162 [A 38]: Say "You will receive a text message confirming this promise." after a recorded promise.

### Other customer statements and transfers

- R163 [A 39]: For current past-due payment already made, say payments can take one business day to appear.
- R164 [A 39; B 9]: Take no promise for that product.
- R165 [B 9]: Note `paid` and continue others, subject to the transfer note prohibition.
- R166 [A 40]: Do not argue with "This debt is not mine" or "I never had this product".
- R167 [A 40; B 9]: Take no promise for the disputed product.
- R168 [A 40]: Claimed past closure or payoff is a dispute.
- R169 [A 40]: The already-paid branch covers payment of this past-due amount only.
- R170 [B 9]: Note `dispute` and continue others, subject to the transfer note prohibition.
- R171 [A 41]: Do not describe a new plan.
- R172 [A 41; B 10]: Subject to hardship, transfer restructuring with queue `restructuring`.
- R173 [B 10]: Recorded promises remain.
- R174 [B 10]: Do not record promises merely agreed before the restructuring request.
- R175 [A 41; B 10]: Close `transferred` / `restructuring`.
- R176 [A 42]: On a human request, ask once whether the agent can help first.
- R177 [A 42]: If the customer insists, transfer with queue `general`.
- R178 [A 42]: Close `transferred` / `human`.
- R179 [A 43]: For "Is this a scam?", say the call can be verified by phoning Freya Bank's customer service number.
- R180 [A 43]: Continue afterward.
- R181 [A 44]: If tools cannot answer, say the information is unavailable.
- R182 [A 44]: Do not invent figures.
- R183 [A 44]: Do not invent dates.
- R184 [A 44]: Do not invent reasons.
- R185 [A 45; B Closing]: After twice declining to talk after verification, stop; apply effective recorded-promise/product closing precedence.
- R186 [A 45]: Before verification, twice declining to talk closes `not_verified` / `declined`.
- R187 [A 45]: Human-request handling applies before and after verification.

### Notes and closing

- R188 [B 8]: Customers may promise some products and refuse others.
- R189 [B 8]: On a non-transfer account-handling call, note each product without a promise.
- R190 [B 8]: This includes calls with no promises.
- R191 [B 8]: Supply the product’s `product_id`.
- R192 [B 8; API]: Note reasons are `refused`, `hardship`, `dispute`, `paid`, `service_error`.
- R193 [B 10]: No notes before any transfer.
- R194 [B 10]: No notes after any transfer.
- R195 [A 46]: Exactly one `close_call` per call.
- R196 [A 46; API]: It is the last tool call.
- R197 [API /close_call]: Nothing is accepted afterward.
- R198 [A 46; API]: Supply `reason` except for outcomes `promise` and `paid`.
- R199 [A 46; B Closing]: At least one recorded promise without transfer closes `promise`.
- R200 [A 46; B 10; B Closing]: Transfer overrides promise and uses its transfer reason.
- R201 [B Closing]: With no promise, all products noted `paid` closes `paid`.
- R202 [B Closing]: Otherwise, an account-handling call with no promise or transfer closes `no_promise`.
- R203 [B Closing]: Use the first non-`paid` note reason in returned order.
- R204 [A 47]: Thank the customer before `close_call`.
- R205 [A 47]: Say goodbye before `close_call`.

### API contract

- R206 [API info]: Seven tools; no key required.
- R207 [API info]: `customer_id` is the secret of one call.
- R208 [API info]: Every call is written to the scorer’s ledger.
- R209 [API info]: The agent enforces brief rules; service acceptance is insufficient.
- R210 [API servers]: Base URL is `https://freya-bank-mock.freyavoice.workers.dev/v1`.
- R211 [API paths]: All operations are `POST` with required JSON object bodies.
- R212 [API /verify_identity]: Required strings: `customer_id`, `field`, `answer`.
- R213 [API /verify_identity]: Response properties: `ok`, `error`, `verified`, `wrong_answers_left`, `all_verified`, `hint`.
- R214 [API /verify_identity]: Only enumerated hint: `day_month_swapped`.
- R215 [API /get_account]: Required string: `customer_id`.
- R216 [API /get_account]: Response properties: `ok`, `error`, `products`.
- R217 [API /get_account]: Product types: `credit_card`, `personal_loan`, `car_loan`.
- R218 [API /get_account]: `product_id` and `card_last4` are strings; the latter is credit-card-only.
- R219 [API /get_account]: `past_due` is a number; `days_late` an integer.
- R220 [API /get_account]: `minimum_payment` is a number for credit cards only.
- R221 [API /get_account]: `instalment_amount` is a number for loans only.
- R222 [API /create_promise]: Required: string `customer_id`, string `product_id`, number `amount`, string `date` with format `date`.
- R223 [API /create_promise]: Response properties: `ok`, `error`, string `promise_id`.
- R224 [API /add_note]: Required strings: `customer_id`, `product_id`, enumerated `reason`.
- R225 [API /add_note]: `text` is an optional string.
- R226 [API /schedule_callback]: Required: string `customer_id`, date-format string `date`, string `time` described as `HH:MM`.
- R227 [API /transfer_to_agent]: Required strings: `customer_id`, `queue`.
- R228 [API /transfer_to_agent]: Queues: `restructuring`, `general`, `support`.
- R229 [API /close_call]: Schema-required strings: `customer_id`, enumerated `outcome`.
- R230 [API /close_call]: Outcomes: `promise`, `paid`, `transferred`, `no_promise`, `not_verified`, `not_reached`.
- R231 [API /close_call]: `reason` is a conditionally required string without an API enum; use the brief’s mappings.
- R232 [API `200` responses]: `ok` is boolean; `error` is string.
- R233 [API `200` responses]: `ok: false` means the action was not carried out.
- R234 [API `500` responses]: Service failed; nothing was recorded.
- R235 [API `500` responses]: Calls may be repeated, subject to the promise retry limit and exactly-once closing requirement.
- R236 [API schemas]: Response properties are not marked required; do not invent missing values.
- R237 [API schemas]: No exact error strings or error enum are supplied.

## 12. Ambiguities

| Issue | Source-supported treatment or unresolved point |
|---|---|
| Field-name or enum disagreement | None is explicit. Queue `general` maps to closing reason `human`; they are different fields, not conflicting definitions. |
| `close_call.reason` requiredness | Only `customer_id` and `outcome` appear in the schema’s `required` array. The property description and A 46 require a reason except for `promise` and `paid`. Apply that conditional requirement. |
| API does not enforce business rules | Validate against the brief even if the service would accept the request. |
| B 9 notes versus no notes before or after transfer | Retaining pending reasons and deferring actual note calls until a non-transfer ending is selected satisfies the prohibition without losing product reasons. This is derived sequencing, not an independently supplied source rule. No note-deletion tool exists. |
| One product returned under Brief B | Brief B still applies: it expressly covers one to three products. |
| Fixed opening wording | A 1 mandates content, not a verbatim script. Preserve the expressly quoted question and required phrases without inventing a fixed opening. |
| Third-party “say nothing beyond” versus callback question | A 5 itself requires asking when the customer can be reached. Do not interpret the disclosure restriction as forbidding that required question. |
| Callback today on a weekend/holiday | Today is expressly allowed. Only the alternative is specified as the next business day; no extra condition on today is supplied. |
| No callback proposal or refusal to supply a time | The supplied `no_callback` branch is two out-of-window proposals. Other no-time cases are not expressly defined. |
| Customer-requested callback | Do not invent a customer callback policy by extending the third-party branch. |
| Timezone and daylight saving | Neither is supplied. Use `now` without substituting the real clock or inventing a timezone. |
| Calendar-week starting day | Not supplied. Monday-to-Friday business days do not establish a Monday-to-Sunday calendar week. No first-day convention is imposed here. |
| Non-business-day calls | Today is not guaranteed to be a business day. Promise validation still applies. No replacement is supplied when the prescribed attempt-1 date is already past. |
| Next-business-day adjustment | The resulting promise must satisfy A 19. With a valid business-day deadline, the next business day after a non-business date not after the deadline cannot exceed that deadline. |
| Past customer-proposed date | Recording is prohibited by A 19, but no specific counter-offer count or terminal branch is supplied. |
| Shared date beyond a deadline | B 6 supplies the per-product deadline adjustment; disclose it and obtain confirmation. Remaining date rules continue to apply. |
| Refusal at shared-date read-back | Changes must be checked and reread. No special B 6 refusal branch exists; apply ordinary refusal rules where applicable without treating a new proposed amount/date as itself a refusal. |
| Attempt counting after the aggregate question | B 4 starts each product at attempt 1. A volunteered date or amount still requires handling under A 29; hardship still prohibits persuasion. |
| Floor repetition versus refused offers | A 26 permits naming the floor again at attempt 2 on the deadline; A 31 prohibits repeating a refused offer. This does not define a substitute step if the prescribed offer is exactly the same as one already refused. |
| Amount above `past_due` | The source expressly accepts the floor-to-full interval but gives no branch for a higher proposal. Do not turn that omission into an invented rejection rule or API maximum. |
| Floor above full amount, currency or rounding | No recovery, currency or rounding rule is supplied. Do not invent percentages, adjustments or amounts. |
| Spoken phone answers | The API requires four digits in a string. No detailed speech grammar or retry policy for ambiguous/incomplete phone answers is supplied. |
| Ambiguous dates and years | Numeric dates are day, month, year. No two-digit-year pivot or inference rule for missing components is supplied. |
| Unreadable dates | They return `ok: false` and do not consume a wrong answer. No distinct mandatory recovery script or retry cap is supplied. |
| Missing or contradictory verification properties | Both questions must pass. Response properties are optional in the schema; no additional requirement that a particular property must be present is supplied. Contradictory verification flags, hints or counters have no defined recovery policy. |
| “What is the call about” | A 15 applies to asking instead of answering security questions. Robot/AI and scam questions have their own response rules. No universal question taxonomy is supplied. |
| Multi-product hardship or refusal scope | Apply the supplied reasons to applicable unpromised products, preserve established results and use B Closing. Make no persuasion attempt after hardship; stop after the second refusal-to-talk. Detailed allocation for unclear scope is not supplied. |
| Unsupported special situations | No dedicated complaint, language, abuse or additional vulnerability policy exists. An independently satisfied defined trigger still applies. |
| Human request without insistence | Ask once to help first; transfer is required if the customer insists. No separate outcome is assigned merely for the first request. |
| Unrecorded agreements before non-restructuring transfers | B 10 explicitly addresses pending promises before restructuring. Other transfers have no express pending-promise recording rule. Do not invent an obligation to record them before transfer. |
| Recorded promise followed by paid/dispute claim on the same product | A recorded promise cannot be changed/cancelled in-call; notes concern products without promises. No separate reconciliation procedure is supplied. |
| Tool failures other than two recording failures | No exact error strings, general retry caps or general terminal error outcome are supplied. `service_error` is not a universal failure reason. |
| Failed `close_call` | Generic `500` repeat permission and the exactly-once closing rule leave recovery unresolved. This spec retains the explicit exactly-once requirement. |
| Failed note before aggregation | No fallback is supplied. Do not pretend a failed note exists or invent an outcome. |
| Failed transfer or scheduling | No fallback reason is supplied. Do not claim success on `ok: false`. |
| Unexpected account data | The schema does not enforce product count, lateness range, conditional fields or required response properties. Do not fabricate missing values or an out-of-range deadline. |
| One-question-at-a-time scope | The explicit restriction concerns security questions. Do not invent a universal restriction on all dialogue. |

## 13. Verifier corrections

- Replaced old-to-new override comparisons with effective Brief B requirements only, removing superseded operational wording from the spec.
- Removed the invented Monday-to-Sunday calendar-week convention; the sources do not define the week’s first day.
- Changed the amount formula from an exhaustive validity test to the expressly accepted floor-to-full range. Proposals above `past_due` remain unspecified, not subject to an invented rejection rule or API maximum.
- Clarified that both security questions must pass, but the optional `all_verified` response property is not an additional mandatory field-presence requirement.
- Removed the unsupported mandatory unreadable-date recovery instruction; retained the exact rejection and non-counting rules.
- Made volunteered-date/amount handling and hardship precedence explicit wherever per-product attempt 1 is described.
- Clarified that deferred note calls are a sequencing consequence of the transfer prohibition, not a separately supplied source rule.
- Avoided prescribing continued product dialogue or a detailed allocation policy for hardship of unclear scope.
- Added the API’s hosted-mock/hackathon and scorer-ledger context.
- Verified and retained all supplied holidays, effective numeric limits, tool fields, formats, enums, required phrases and outcome/reason mappings.