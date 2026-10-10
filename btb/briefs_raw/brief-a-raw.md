## 1. Internal email

**From:** Mara Chen, Operations Manager, Freya Bank  
**To:** Vendor delivery team  
**Subject:** Early-stage calling — one-product handover

Hi team,

Here’s the material for the early-stage collections calls. Freya Bank is fictional, and every customer, debt and payment in this project is synthetic.

We’re calling customers who are 1 to 45 days late on one product. The job is to find the customer, check identity, explain the debt, get a payment promise where possible and finish with the right outcome.

Please use the title and last name when addressing the customer. Each call starts with only the variables in the sheet at the bottom; nothing else is known until the tools are called. Pass `customer_id` on every tool call. All date calculations must use the supplied `now`, not the real clock.

A couple of things worth flagging: don’t let account information slip into the opening, including when a relative answers. A relative can’t do the security check for the customer, even if they offer to pay. And don’t tell someone a promise is recorded until the recording tool has actually succeeded.

The older policy extract is pasted below, followed by the amendment memo and the code sheet. Please read the whole pack — the small rules are usually where these calls go wrong.

Thanks,  
Mara

## 2. Policy extract

**Freya Bank — Early-stage collections, single-product calls**  
**Document date:** 2026-09-01

### Opening and identification of the person answering

1. The first sentence shall identify the caller as a digital assistant calling from Freya Bank and state that the call is recorded. Until identity has been verified, the agent shall not say "collections", "debt", "payment" or the product. This restriction applies to everyone answering the call, including relatives.

2. The agent shall ask: "Am I speaking with {title} {last_name}?".

3. Only "yes", "that's me", "speaking" or the customer's own name shall constitute confirmation. "Hello", "go ahead" and "who is this" shall not constitute confirmation. Where confirmation is unclear, the agent shall ask once more. If it remains unclear after the second ask, the call shall close as `not_reached` / `unclear`. A question from the customer shall be answered first, in accordance with clauses 4 and 43; the ask following that answer shall be the second ask.

4. Where asked whether the agent is a robot or an AI, the agent shall state that it is Freya Bank's digital assistant and continue.

### Where another person answers

5. The agent shall not disclose why it is calling and shall say nothing beyond the opening sentence required by clause 1. The agent shall ask when the customer can be reached.

6. A callback shall be for today or the next business day, at a time from 10:00 to 19:00 inclusive, and later than `now`. The agent shall call `schedule_callback` with the date and time, then close as `not_reached` / `callback`.

7. If the person offers a day or time outside that window, the agent shall ask once for another time. If that alternative is also outside the window, no callback shall be scheduled and the call shall close as `not_reached` / `no_callback`.

8. If the person states that the number does not belong to the customer, the call shall close as `not_reached` / `wrong_number`.

9. If the person states that the customer has died, the agent shall say "I am sorry for your loss.", ask nothing else, and close as `not_reached` / `deceased`.

10. A relative shall not answer the security questions and shall not receive any account information, even where that relative offers to pay.

### Identity verification

11. The agent shall ask two security questions, one at a time: first the customer's date of birth, then the last four digits of the phone number on file. The agent shall call `verify_identity` with the answer to each question. A date of birth shall be sent as `YYYY-MM-DD`, regardless of how the customer expressed it. The service rejects anything it cannot read as a date. A date expressed only in numbers shall be read as day, then month, then year.

12. A question answered incorrectly may be asked again. Three wrong answers in total shall end the check, irrespective of which question received those wrong answers.

13. Where the customer gives the day and month the other way round, `verify_identity` returns `hint: "day_month_swapped"`. The agent shall ask the customer to say the month as a word. That retry shall not count as a wrong answer.

14. After three wrong answers, the agent shall not state the debt. The agent shall tell the customer to use the mobile app or a branch and close as `not_verified` / `failed`.

15. If the customer does not wish to answer, the agent shall explain once that the questions protect their account. If the customer still declines, the call shall close as `not_verified` / `declined`. Asking what the call is about instead of answering shall count as declining. A second refusal or a second such question shall close the call.

### Disclosure of the debt

16. Once both security questions have passed, the agent shall call `get_account`.

17. The agent shall state that it is calling from the collections team about a late payment. It shall name the product in words: "credit card ending 4821", "personal loan" or "car loan". It shall state the past-due amount and the number of days late.

### Dates and deadlines

For these clauses, business days are Monday to Friday, excluding the Freya Bank holidays listed in the code sheet. All date rules use the supplied `now`, never the real clock.

18. The applicable deadline and number of persuasion attempts shall depend on `days_late`:
    - **1 to 7 days late — early band:** the deadline shall be the **10th business day after today**; **1** persuasion attempt shall be available.
    - **8 to 45 days late — late band:** the deadline shall be the **5th business day after today**; **2** persuasion attempts shall be available.

19. A promise date shall be today or later, shall be a business day, and shall not fall after the deadline.

20. If the customer names a weekend day or holiday that is not after the deadline, the agent shall offer the next business day. If the named day is after the deadline, clause 23 shall apply.

21. If the customer gives a vague period, such as "next week", "end of the month" or "when my salary comes", the agent shall ask once for the exact day. If the customer still gives no exact day, the agent shall propose the deadline.

22. "Next <weekday>" means that weekday in the following calendar week. "This <weekday>" means that weekday in the current week. Accordingly, "next Friday" said on a Friday means the Friday of the following week.

23. If the customer requests a date after the deadline, the agent shall state that the latest date it can record is the deadline and shall offer that date. Refusal of the deadline shall be treated as a flat refusal under clause 30.

### Amounts

24. The agent shall ask for the full past-due amount first. It shall never ask "how much can you pay?". Every amount proposed by the agent shall originate with the agent.

25. The floor shall be `minimum_payment` for a credit card, and `instalment_amount` for a personal loan or car loan.

26. If the customer states that the full amount is too much, the agent shall offer the floor once and state that the rest stays overdue. Refusal of the floor shall be treated as a flat refusal under clause 30. Attempt 2 may name the floor again, on the deadline.

27. If the customer proposes an amount between the floor and the full amount, both inclusive, the agent shall accept it. If the proposed amount is below the floor, the agent shall state that it cannot be recorded and shall offer the floor once. If the customer does not accept the floor, this shall be treated as a flat refusal under clause 30.

### Obtaining a payment promise

28. The first payment request shall be: "Can you make this payment today?".

29. A date or amount proposed by the customer shall never constitute a refusal. Such proposals shall be handled under clauses 18–27.

30. A flat refusal or non-answer shall use one persuasion attempt. A refusal to pay today, without a date or amount, shall constitute a flat refusal.
    - **Attempt 1:** propose the full past-due amount, or the floor if the customer has already said the full amount is too much. Propose the last business day of this week. If today is that day, propose the last business day of next week.
    - **Attempt 2, late band only:** propose the floor amount on the deadline.

31. Once the available attempts have been used, the agent shall stop. It shall not repeat an offer the customer has already refused. The call shall close as `no_promise` / `refused`.

32. If the customer mentions illness, a death in the family or job loss, the agent shall say one short sentence of sympathy and make no persuasion attempt. It shall offer to connect the customer with the customer support team. If accepted, the agent shall call `transfer_to_agent` with queue `support` and close as `transferred` / `support`. If declined, the call shall close as `no_promise` / `hardship`. This clause takes priority over clauses 30 and 41. If the customer nevertheless names a date or amount themselves, the agent shall record the promise in accordance with clauses 18–27.

33. The agent shall never offer a discount, waiver, instalment plan or any term not contained in this handover.

### Confirmation and recording

34. The agent shall read back the product, amount and date and ask "Do you confirm?". It shall call `create_promise` only after a clear yes.

35. If the customer changes the date or amount at confirmation, the agent shall check the new value against clauses 18–27 and read it back again.

36. There shall be one promise per product. A recorded promise cannot be changed or cancelled during the same call. If the customer asks to do so, the agent shall state that they can change it in the mobile app.

37. The agent shall say that the promise is recorded only after `create_promise` returns `ok: true`. If the call to that tool fails, the agent shall try once more. If it fails again, the agent shall state that it could not record the promise and close as `no_promise` / `service_error`.

38. After a promise has been recorded, the agent shall say: "You will receive a text message confirming this promise."

### Other customer statements and requests

39. In response to "I already paid", the agent shall state that payments can take one business day to appear, take no promise, and close as `paid`.

40. In response to "This debt is not mine" or "I never had this product", the agent shall not argue and shall not take a promise. It shall close as `no_promise` / `dispute`. A claim that the product was closed or paid off in the past shall constitute a dispute. Clause 39 applies only to a payment of this past-due amount.

41. Where the customer requests a new payment plan or lower instalments, the agent shall not describe a plan. It shall call `transfer_to_agent` with queue `restructuring` and close as `transferred` / `restructuring`.

42. Where the customer requests a human, the agent shall ask once whether it can help first. If the customer insists, it shall call `transfer_to_agent` with queue `general` and close as `transferred` / `human`.

43. In response to "Is this a scam?", the agent shall state that the customer can verify the call by phoning Freya Bank's customer service number, and continue.

44. Where a question cannot be answered from the tools, the agent shall state that it does not have that information. It shall not invent figures, dates or reasons.

45. If the customer says twice that they do not want to talk, the call shall close as `no_promise` / `refused`. If identity has not yet been verified, the same customer shall instead be closed as `not_verified` / `declined`. Clause 42 applies both before and after verification.

### Closing requirements

46. Every call shall end with exactly one `close_call`, specifying an outcome and, where listed in the code sheet, a reason. It shall be the last tool call. The permitted outcome/reason combinations and their applications are set out in the code sheet. If a transfer follows a recorded promise, the call shall close as `transferred` with the reason for that transfer. Brief A shall never use `add_note`.

47. The agent shall thank the customer and say goodbye before calling `close_call`.

## 3. Memo

**Freya Bank — Operations**  
**Date:** 2026-10-09  
**Subject:** Amendment to early-stage collections deadlines

The following two values in clause 18 of the policy extract dated 2026-09-01 are amended:

| Clause / band | Previous value | Replacement value |
|---|---|---|
| 18 / early, `days_late` 1 to 7 | 10th business day after today | **12th business day after today** |
| 18 / late, `days_late` 8 to 45 | 5th business day after today | **7th business day after today** |

This memo overrides the policy extract in respect of those two deadline values. No other provision or value is changed.

**Signed:** Mara Chen  
**Operations Manager, Freya Bank**

## 4. Code sheet / field values

### CALL_START

| Variable | Example / values | Meaning |
|---|---|---|
| `customer_id` | `c_4f2a...` | Pass to every tool call |
| `first_name` | `Daniel` | Person to ask for — first name |
| `last_name` | `Reyes` | Person to ask for — last name |
| `title` | `Mr` or `Ms` | Address customer as title plus last name |
| `now` | `2026-10-14T11:00` | Current date/time; source for every date rule; never use real clock |

**Starting information:** these variables only; nothing else known before tools are called.

### CLOSE_CALL_CODES

| Outcome | Reason | Application |
|---|---|---|
| `promise` | none | At least one promise recorded |
| `paid` | none | Clause 39 |
| `transferred` | `restructuring` | Clause 41 |
| `transferred` | `human` | Clause 42 |
| `transferred` | `support` | Clause 32 |
| `no_promise` | `refused` | Clauses 31 and 45 |
| `no_promise` | `hardship` | Clause 32 |
| `no_promise` | `dispute` | Clause 40 |
| `no_promise` | `service_error` | Clause 37 |
| `not_verified` | `failed` | Clause 14 |
| `not_verified` | `declined` | Clauses 15 and 45 |
| `not_reached` | `callback` | Clause 6 |
| `not_reached` | `no_callback` | Clause 7 |
| `not_reached` | `wrong_number` | Clause 8 |
| `not_reached` | `deceased` | Clause 9 |
| `not_reached` | `unclear` | Clause 3 |

**Recorded promise followed by transfer:** `transferred` + that transfer's reason.

### TOOLS / FIELDS / VALUES

| Tool / scope | Field or data | Value / use |
|---|---|---|
| Every tool call | `customer_id` | Supplied call-start value |
| `verify_identity` | Answer to current security question | Date of birth first; last four digits of phone number on file second |
| `verify_identity` | Date-of-birth answer format | `YYYY-MM-DD` |
| `verify_identity` | Returned `hint` | `"day_month_swapped"` |
| `get_account` | Account information | Product; past-due amount; `days_late`; applicable floor field below |
| `schedule_callback` | Date and time | Today or next business day; 10:00–19:00 inclusive; later than `now` |
| `create_promise` | Returned `ok` | `true` required before saying promise is recorded |
| `transfer_to_agent` | `queue` | `support`, `restructuring`, `general` |
| `close_call` | Outcome and applicable reason | `CLOSE_CALL_CODES` above |
| `add_note` | Usage | Never used in Brief A |

### TRANSFER_QUEUE_MAP

| Trigger | `queue` | Outcome | Reason |
|---|---|---|---|
| Hardship support offer accepted | `support` | `transferred` | `support` |
| New payment plan / lower instalments | `restructuring` | `transferred` | `restructuring` |
| Human request maintained after one offer to help | `general` | `transferred` | `human` |

### PRODUCT / FLOOR_FIELDS

| Product wording to say | Floor field |
|---|---|
| "credit card ending 4821" | `minimum_payment` |
| "personal loan" | `instalment_amount` |
| "car loan" | `instalment_amount` |

### BUSINESS_CALENDAR

| Item | Value |
|---|---|
| Business weekdays | Monday–Friday |
| Exclusions | Freya Bank holidays below |

| Freya Bank holiday |
|---|
| 2026-10-26 |
| 2026-11-11 |
| 2026-11-26 |
| 2026-12-25 |
| 2027-01-01 |