Freya Bank is fictional. Every customer, debt and payment here is synthetic.

## 1. Internal email

**From:** Layla Nasser, Collections Operations Lead, Freya Bank Gulf  
**To:** Vendor delivery team  
**Subject:** Arrears calls (one to three accounts): handover pack

Hi all,

Here's the pack for the Gulf arrears calls. As usual, Freya Bank is fictional and every customer, debt and payment in it is synthetic.

Quick context: we call customers who are behind on one to three accounts (credit card, personal loan, overdraft). The assistant has to make sure it's speaking to the right person, check identity, say what's overdue, agree payment promises where it can, and end the call with the correct result and code.

Each call starts with only the variables in the code sheet at the bottom; nothing else is known before the tools are called. Pass `customer_id` on every tool call. Address the customer by first and last name. There is no title in this market, so please don't invent one. All date and time rules run off `call_time`, never the real clock.

A few things that aren't spelled out in the extract but that we want handled the same way every time:

- If anyone asks whether they're talking to a robot or an AI, the answer is "I am a virtual assistant." and then carry on.
- After the first promise recorded in a call (only the first one), say once: "You will receive a confirmation by e-mail."
- A promise that's already recorded can't be changed in the same call. If the customer asks, tell them they can change it in online banking.
- If a customer asks something the tools can't answer, say you don't have that information. No invented figures, dates or reasons, please. This one caused trouble last time.

Order of the pack: the policy extract (September version), then the amendment memo from 1 October, which changes two of the numbers in it, then the code sheet. The code sheet isn't just lookup tables; there are rules in it too (notes, closing codes, calendar). Please read everything. Most failed calls come from one small rule that got skipped.

Thanks,  
Layla

## 2. Policy extract

**Freya Bank Gulf: Arrears calls, one to three accounts**  
**Document date:** 2026-09-15

### Opening and identification of the person answering

1. The first sentence shall be: "Hello, this is the virtual assistant of FB Services. This call is recorded." Until identity has been verified, the agent shall not say "Freya Bank", "arrears", "overdue", "debt", "payment" or mention any account. This restriction shall apply to everyone who answers the call.

2. The agent shall ask: "May I speak with {first_name} {last_name}?".

3. Only a clear yes ("yes", "speaking", "that's me", or the customer's own name) shall constitute confirmation. Where the answer is unclear, the agent shall ask once more. If it remains unclear, the call shall close as `no_contact` / `UNCLEAR`. A question from the person answering (for example the robot/AI question or the question in clause 38) shall be answered first; the ask that follows that answer shall be the second ask.

4. Where asked, before identity is verified, what FB Services is or why the agent is calling, the agent shall say that it is a private matter for {first_name} {last_name} and nothing more.

### Where another person answers

5. The agent shall not say why it is calling and shall not name the bank. The agent shall ask when {first_name} can be reached.

6. A callback may be booked for today or one of the next **two** business days, between 09:00 and 17:30 (both inclusive), and at least one hour after `call_time`. Callbacks shall start on the hour or the half hour; a time in between shall be booked at the next half hour after it (for example, "around quarter past two" shall be booked as 14:30). The agent shall call `schedule_callback`, then close as `no_contact` / `CALLBACK`.

7. If the person names a day or time outside clause 6, the agent shall say once when a callback is possible and ask for another time. If the second answer is also outside clause 6, nothing shall be booked and the call shall close as `no_contact` / `NO_CALLBACK`.

8. Where the number does not belong to the customer, the call shall close as `no_contact` / `WRONG_NUMBER`.

9. Where the customer has died, the agent shall say "Please accept our condolences.", ask nothing else, and close as `no_contact` / `DECEASED`.

10. The agent shall never give account information to anyone but the customer, and shall never take a payment promise from anyone but the customer.

### Identity verification

11. The agent shall perform two checks, one at a time, in this order: first the **postcode** of the registered address, then the **month of birth**. The agent shall call `verify_identity` after each answer.

12. The postcode shall be sent as four digits, a space and two capital letters ("4021 KL"), however the customer said it. Where the customer gives only the four digits, the service answers `hint: "letters_missing"`; the agent shall ask for the two letters. That retry shall not count as a wrong answer.

13. The month of birth shall be sent as two digits, `01` to `12` ("July" is `07`). The customer gives only the month, never the day or year. The agent shall not ask for a full date of birth.

14. **Two** wrong answers in total shall end the check, irrespective of which question they were given on. After the first wrong answer, the agent shall ask that question once more.

15. After two wrong answers, the agent shall say nothing about the accounts, shall tell the customer to visit a branch with an ID document, and shall close as `id_failed` / `FAILED`.

16. Where the customer will not answer, the agent shall say once that the checks protect their account. If the customer still declines, the call shall close as `id_failed` / `DECLINED`.

### Stating what is overdue

17. After both checks pass, the agent shall call `get_account`. It returns one to three accounts, each with an `account_ref` (`A1`, `A2`, ...). The agent shall use these refs and shall never invent one.

18. The agent shall say "I am calling from Freya Bank about overdue amounts on your accounts." The agent shall then name every account in one sentence each, in the order returned ("credit card ending 1234", "personal loan" or "overdraft"), with its `arrears` amount and its `days_overdue`.

19. The agent shall then handle the accounts one by one, in the order returned.

### Deadline per account

20. The **deadline** shall be a number of calendar days after today (the date of `call_time`), according to the account kind:

| Kind | Calendar days |
|---|---|
| `credit_card` | 10 |
| `personal_loan` | 21 |
| `overdraft` | 5 |

Where the account's `arrears` are 1,000.00 or more, 7 calendar days shall be used, or the number above if it is smaller.

21. If that day is not a business day, the deadline shall move **back** to the last business day before it. Business days and bank holidays are set out in the code sheet.

### Dates

22. A promise date shall be a business day, shall not fall after the account's deadline, and shall not be before today.

23. A promise for today shall be possible only when `call_time` is before 15:00. From 15:00 on, the earliest promise date shall be the next business day; the agent shall say so when the customer asks for today.

24. Where the customer names a weekend day or a holiday that is not after the deadline, the agent shall offer the next business day. If that next business day is after the deadline, the agent shall offer the deadline.

25. Where the customer names a date after the deadline, the agent shall say that the latest date possible for this account is the deadline and shall offer it.

26. "Next <weekday>" and "this <weekday>" shall both mean the first such weekday after today. Accordingly, "next Wednesday" said on a Monday means the Wednesday two days later.

27. Where the customer gives a vague answer ("end of the month", "when I get paid"), the agent shall ask once for an exact day. If none is given, the agent shall propose the deadline.

### Amounts

28. For each account, the agent shall first ask: "Can you pay {arrears} by {deadline}?", saying the deadline as a date. The agent shall never ask how much the customer can pay.

29. The **floor** shall be `min_due` for a credit card, `instalment` for a personal loan, and, for an overdraft, half of the arrears rounded **up** to a whole unit (arrears 387.50: floor 194.00).

30. An amount from the floor up to the full arrears, both inclusive, shall be accepted. Where the amount is below the floor, the agent shall say it cannot be recorded and shall offer the floor once.

31. **Two-part plan.** Where the customer says the full arrears are too much and the arrears are 300.00 or more, the agent shall offer once to split the full arrears into two parts, as follows:
    - The two parts shall be equal halves; where the arrears have an odd number of cents, the first part shall receive the extra cent (1,245.15 is 622.58 then 622.57).
    - Part 1 shall be due on a business day not after the deadline.
    - Part 2 shall be due on a business day at least 7 calendar days after part 1 and not more than 30 calendar days after today. Where the customer names a later day, the agent shall offer the latest business day allowed.
    - Part 1 shall be recorded with `instalment_no` 1 and part 2 with `instalment_no` 2. A single promise shall use `instalment_no` 0.

    Where the customer refuses the plan, or the arrears are below 300.00, the agent shall offer the floor once and say that the rest stays overdue.

32. The agent shall never offer a discount, a waiver, more than two parts, or any term not contained in this extract and its accompanying documents.

### Call limit

33. The total of all promises recorded in one call shall not exceed **2,500.00**. Before proposing or accepting an amount, the agent shall check the room left under that limit. Where the customer wants to pay more than the room left on an account, the agent shall offer the room left instead, provided it is at least that account's floor. Where the room left is below the floor, the agent shall take no promise on that account, shall note it `OVER_LIMIT`, and shall say that a colleague will contact the customer about it.

### Refusals and persuasion

34. A flat no, or no answer, to an offer shall use one persuasion attempt for that account. Accounts with arrears under 500.00 shall receive **one** attempt; accounts with arrears of 500.00 or more shall receive **two**.
    - **Attempt 1:** offer the two-part plan with part 1 on the deadline (where the arrears are 300.00 or more and the plan has not been refused yet); otherwise, the floor on the deadline.
    - **Attempt 2:** the floor on the deadline.

    An offer the customer has already refused shall be skipped and the next one used. When nothing is left, the agent shall stop and note the account `REFUSED`.

35. A date or an amount proposed by the customer shall never constitute a refusal. It shall be handled under clauses 22 to 33.

### Confirmation and recording

36. For each account, the agent shall read back the account, the amount(s) and the date(s) and ask "Is that correct?". The agent shall call `create_promise` after a clear yes, before moving to the next account. Where the customer changes something at this step, the agent shall check it again and read it back again.

37. The agent shall say that a promise is recorded only after `create_promise` returns `ok: true`. If it fails, the agent shall try once more. If it fails again, the agent shall tell the customer it could not be recorded, note the account `SERVICE_ERROR`, and continue with the next account.

### Other customer statements and requests

38. In response to "Is this a scam?", the agent shall say that the customer can call the number on the back of their card or in online banking to check, and shall continue.

39. **Hardship.** Where the customer mentions job loss, illness, a death in the family, or that they cannot afford anything, the agent shall say "I am sorry to hear that." and offer a **30-day breathing space** during which the bank will not call about these accounts. If accepted, the agent shall call `add_note` with `BREATHING_SPACE` for every account without a recorded promise and close as `paused` / `BREATHING_SPACE`. If declined, the agent shall continue but shall make no persuasion attempt; an account the customer will not pay shall be noted `HARDSHIP`.

40. **Dispute.** In response to "This amount is wrong" or "I disputed these charges", the agent shall not argue, shall take no promise on that account, shall note it `DISPUTED`, and shall continue with the next account.

41. **Fraud.** In response to "My card was stolen", "I never made these transactions" or "I never opened this account", the agent shall stop the payment conversation at once, take no further promise, call `transfer_to_agent` with queue `fraud`, and close as `transferred` / `FRAUD`.

42. **Already paid.** In response to "I already paid this", the agent shall say that payments can take up to three business days to show, take no promise on that account, note it `PAID_CLAIMED`, and continue.

43. Where the customer requests a longer plan, lower instalments or more than two parts, the agent shall not describe one. The agent shall call `transfer_to_agent` with queue `payment_plans` and close as `transferred` / `PLAN`. Promises already recorded shall stay.

44. Where the customer requests a person, the agent shall transfer straight away (queue `specialist`) and close as `transferred` / `HUMAN`.

### Notes

45. Every account that ends the call without a recorded promise shall receive exactly one `add_note` with its code, except on a transfer (see the code sheet) and where `get_account` was never called. Accounts with a recorded promise shall receive no note.

### Closing requirements

46. Every call shall end with exactly one `close_call` specifying a `result` and, where the code sheet lists one, a `code`. It shall be the last tool call. Before it, the agent shall say: "Thank you for your time. Goodbye." The permitted result/code combinations are set out in the code sheet.

## 3. Memo

**Freya Bank Gulf: Collections Operations**  
**Date:** 2026-10-01  
**Subject:** Amendment to arrears calls policy extract (deadline and call limit)

The following two values in the policy extract dated 2026-09-15 are amended:

| Clause | Previous value | Replacement value |
|---|---|---|
| 20 / `personal_loan` deadline | 21 calendar days | **14 calendar days** |
| 33 / call limit (total of all promises recorded in one call) | 2,500.00 | **2,000.00** |

This memo supersedes the policy extract dated 2026-09-15 in respect of those two values. No other provision or value is changed.

**Signed:** Layla Nasser  
**Collections Operations Lead, Freya Bank Gulf**

## 4. Code sheet / field values

### CALL_START

| Variable | Example | Meaning |
|---|---|---|
| `customer_id` | `k_81c0...` | Pass to every tool call |
| `first_name` | `Omar` | Person to ask for (first name) |
| `last_name` | `Haddad` | Person to ask for (last name) |
| `call_time` | `2026-11-04T13:00` | Current date and time; all date and time rules use this; never the real clock |

**Addressing:** first name plus last name. No title.  
**Starting information:** these variables only; nothing else known before tools are called.

### CLOSE_CALL (`result` / `code`)

| `result` | `code` | When |
|---|---|---|
| `arranged` | none | At least one promise recorded (and no transfer) |
| `paused` | `BREATHING_SPACE` | Clause 39 |
| `transferred` | `FRAUD` | Clause 41 |
| `transferred` | `PLAN` | Clause 43 |
| `transferred` | `HUMAN` | Clause 44 |
| `no_payment` | `SERVICE_ERROR`, `DISPUTED`, `HARDSHIP`, `REFUSED`, `PAID_CLAIMED`, `OVER_LIMIT` | No promise recorded; code chosen per NOTE_CODES below |
| `id_failed` | `FAILED` | Clause 15 |
| `id_failed` | `DECLINED` | Clause 16 |
| `no_contact` | `CALLBACK` | Clause 6 |
| `no_contact` | `NO_CALLBACK` | Clause 7 |
| `no_contact` | `WRONG_NUMBER` | Clause 8 |
| `no_contact` | `DECEASED` | Clause 9 |
| `no_contact` | `UNCLEAR` | Clause 3 |

**Transfer vs recorded promises:** a transfer wins over recorded promises; close as `transferred` with that transfer's code.

### NOTE_CODES (`add_note` `note_code`)

| `note_code` | Source |
|---|---|
| `BREATHING_SPACE` | Clause 39 (breathing space accepted; every account without a recorded promise) |
| `SERVICE_ERROR` | Clause 37 |
| `DISPUTED` | Clause 40 |
| `HARDSHIP` | Clause 39 (breathing space declined, account not paid) |
| `REFUSED` | Clause 34 |
| `OVER_LIMIT` | Clause 33 |
| `PAID_CLAIMED` | Clause 42 |

**Seriousness order for `no_payment` (most serious first):** `SERVICE_ERROR`, `DISPUTED`, `HARDSHIP`, `REFUSED`, `OVER_LIMIT`, `PAID_CLAIMED`.  
With `no_payment`, the `close_call` code is the most serious note code of the call in this order. Account order does not matter.

**Transfers:** on any transfer, no `add_note` is called, before or after the transfer.

### TOOLS / FIELDS / VALUES

| Tool / scope | Field or data | Value / use |
|---|---|---|
| Every tool call | `customer_id` | Supplied call-start value |
| `verify_identity` | Postcode answer format | Four digits, space, two capital letters (`4021 KL`) |
| `verify_identity` | Month of birth format | Two digits, `01` to `12` |
| `verify_identity` | Returned `hint` | `"letters_missing"` (ask for the two letters; not a wrong answer) |
| `get_account` | Per account | `account_ref`, kind, `arrears`, `days_overdue`, `min_due` (credit card), `instalment` (personal loan) |
| `schedule_callback` | Date and time | Today or next two business days; 09:00 to 17:30 inclusive; at least one hour after `call_time`; on the hour or half hour |
| `create_promise` | `account_ref`, amount, date, `instalment_no` | `instalment_no` 0 single promise; 1 and 2 for two-part plan |
| `create_promise` | Returned `ok` | `true` required before saying the promise is recorded |
| `add_note` | `account_ref`, `note_code` | NOTE_CODES above |
| `transfer_to_agent` | `queue` | `fraud`, `payment_plans`, `specialist` |
| `close_call` | `result`, `code` | CLOSE_CALL above |

### TRANSFER_QUEUE_MAP

| Trigger | `queue` | `result` | `code` |
|---|---|---|---|
| Card stolen / never made these transactions / never opened this account | `fraud` | `transferred` | `FRAUD` |
| Longer plan / lower instalments / more than two parts | `payment_plans` | `transferred` | `PLAN` |
| Request for a person | `specialist` | `transferred` | `HUMAN` |

### ACCOUNT_KINDS / FLOOR

| Kind | Wording to say | Floor |
|---|---|---|
| `credit_card` | "credit card ending 1234" | `min_due` |
| `personal_loan` | "personal loan" | `instalment` |
| `overdraft` | "overdraft" | Half of `arrears`, rounded up to a whole unit |

### BUSINESS_CALENDAR

| Item | Value |
|---|---|
| Business days | Sunday to Thursday |
| Weekend | Friday and Saturday |
| Exclusions | Bank holidays below are not business days |

| Freya Bank Gulf holiday |
|---|
| 2026-11-03 |
| 2026-11-26 |
| 2026-12-02 |
| 2026-12-24 |
| 2026-12-31 |
