## Internal email

**From:** Mara Ellis, Operations Manager, Freya Bank  
**To:** Vendor Delivery Team  
**Date:** 2026-09-29  
**Subject:** Brief B — multi-product collections changes

Hi team,

This is the multi-product extension to Brief A, not a replacement for the whole call flow. Freya Bank is fictional. Every customer, debt and payment here is synthetic.

Please keep every Brief A rule unless the changes below replace it. That includes the existing verbatim customer-facing wording wherever the underlying rule still applies.

The main difference is that you need to tell the customer about **every late product, one sentence each, before asking for anything**. Ask whether they can pay all of them today. If they cannot, work through the products in the order the account service returned them—don’t restart the “today” question on each one.

A customer can agree to some products and refuse others. A paid claim or dispute on one product isn’t a reason to abandon the rest. Read the promises back together and get one confirmation, then record them separately.

The older policy extract is pasted below. Please apply the later signed memo to it. The code sheet at the end is the implementation reference; Brief A remains the source for unchanged behaviour.

Thanks,  
Mara

## Policy extract

**Freya Bank — Collections Operating Policy**  
**Extract reference:** Brief B / Multi-product handling  
**Extract date:** 2026-08-12

**1. Application and account retrieval.**  
Brief B shall operate as an extension of Brief A. Every requirement of Brief A shall continue to apply except where expressly replaced by this extract, as subsequently amended. `get_account` shall return not fewer than one and not more than **two products**. Each product shall have its own `past_due`, `days_late` and floor, with the floor determined under Brief A.

**2. Disclosure of late products.**  
The agent shall state every late product, in one sentence per product, before asking for anything. The disclosure requirements of Brief A concerning the product, past-due amount and days late shall apply to each such statement.

**3. Product-specific dates.**  
The band and deadline shall be determined separately for each product using that product’s `days_late`. Products belonging to the same customer may therefore have different deadlines.

**4. Initial request and subsequent sequence.**  
In place of the single-product initial request under Brief A rule 28, the agent shall first ask whether the customer can pay all the products today. If the customer cannot do so, the agent shall proceed product by product in the order returned by `get_account`. The agent shall not ask about payment today again for each product. Each product shall begin at attempt 1 of Brief A rule 30.

**5. Persuasion accounting.**  
Persuasion attempts shall be counted separately for each product.

**6. Common date exceeding a product deadline.**  
Where the customer names one date for all products and that date falls after a product’s deadline, that product shall be recorded on its own deadline, and the adjustment shall be stated in the read-back. The other products shall retain the date named by the customer.

**7. Combined confirmation and separate recording.**  
All promises shall be read back together, including the product, amount and date for each, and the agent shall ask **"Do you confirm?"** once for the combined read-back. Following a clear yes, `create_promise` shall be called once per product, subject to the failure retry provision in clause 11. The remaining confirmation and recording requirements of Brief A shall continue to apply.

**8. Products without promises.**  
The customer may promise payment on some products and refuse others. For each product without a promise, the agent shall call `add_note`, identifying that product by `product_id` and supplying one of the following reasons: `refused`, `hardship`, `dispute`, `paid`, `service_error`. This requirement shall also apply where no product receives a promise, subject to the transfer prohibition in clause 10.

**9. Disputed products and paid claims.**  
A dispute or an “already paid” claim concerning one product shall not terminate the call. The agent shall note the relevant product and continue with the others. Brief A’s distinction between a payment of the current past-due amount and a claim that the product was previously closed or paid off shall remain applicable.

**10. Transfers.**  
A restructuring request shall continue to require transfer under Brief A rule 41, subject to Brief A’s existing precedence rules. Promises recorded before the request shall remain recorded. Promises agreed but not yet recorded shall not be recorded. The call shall close with outcome `transferred` and reason `restructuring`.

On any transfer—restructuring, support or human—no notes whatsoever shall be added, either before or after the transfer.

**11. Recording failures.**  
A failed `create_promise` call shall be retried up to a limit of **three failed calls for that product**. This limit shall replace the retry limit in Brief A rule 37. If a product reaches that failure limit, promises successfully recorded for other products shall be retained, and `add_note` shall be called for the failed product with reason `service_error`, subject to clause 10. This product-level treatment shall replace Brief A rule 37’s single-product failure closure; its other requirements shall remain applicable.

**12. Closing disposition.**  
The outcome table of Brief A shall continue to apply, with the following multi-product treatment:

12.1. Where no promise has been recorded and every product is noted `paid`, the call shall close as `paid`.

12.2. Otherwise, where no promise has been recorded, the call shall close as `no_promise`, using the reason of the first product, in `get_account` order, whose note is not `paid`.

12.3. Where several products are involved, `promise` shall take precedence whenever at least one promise has been recorded, except as provided in clause 10. Brief A’s requirement to close as `transferred`, with the applicable transfer reason, where a transfer follows a recorded promise shall remain in force.

## Memo

**Date:** 2026-10-01  
**To:** Operations; Vendor Delivery Team  
**Subject:** Override of Brief B policy extract dated 2026-08-12

The following two numeric limits are amended:

| Policy location | Old value | Replacement value |
|---|---:|---:|
| Clause 1 — maximum products returned by `get_account` | 2 products | **3 products** |
| Clause 11 — `create_promise` failure limit per product | 3 failed calls | **2 failed calls** |

The minimum product count remains one. Under the amended failure limit, a failed `create_promise` is tried once more; if it fails again, clause 11’s product-level failure treatment applies.

**This memo overrides the policy extract wherever the two conflict. These are the only two changes made by this memo. All other provisions remain unchanged.**

**Signed:** Mara Ellis  
Operations Manager, Freya Bank

## Code list / reference sheet

### Outcomes and reasons

| `outcome` | `reason` | Use |
|---|---|---|
| `promise` | none | At least one promise recorded; transfer takes precedence |
| `paid` | none | No promise recorded; every product noted `paid` |
| `no_promise` | `refused`, `hardship`, `dispute`, `service_error` | No promise recorded; use first non-`paid` product note in `get_account` order |
| `transferred` | `restructuring`, `human`, `support` | Corresponding transfer; no notes before or after |
| `not_verified` | `failed`, `declined` | Brief A, unchanged |
| `not_reached` | `callback`, `no_callback`, `wrong_number`, `deceased`, `unclear` | Brief A, unchanged |

### Tools / fields / values

| Tool / scope | Field or item | Value / meaning |
|---|---|---|
| Every tool call | `customer_id` | Call’s supplied customer identifier; Brief A unchanged |
| `get_account` | Product order | Returned order; governs product handling and first non-`paid` closing reason |
| `get_account` | `past_due` | Separate value for each product |
| `get_account` | `days_late` | Separate value for each product; determines its band and deadline |
| Credit-card floor | `minimum_payment` | Brief A floor definition, applied per product |
| Personal-loan / car-loan floor | `instalment_amount` | Brief A floor definition, applied per product |
| `add_note` | `product_id` | Product without a promise |
| `add_note` | `reason` | `refused`, `hardship`, `dispute`, `paid`, `service_error` |
| `create_promise` | Recording unit | One product per call, subject to amended retry limit |
| `create_promise` response | `ok: true` | Promise recorded; Brief A success wording remains applicable |
| `transfer_to_agent` | `queue` | `restructuring`, `support`, `general` |
| Queue-to-close mapping | `restructuring` | `transferred` / `restructuring` |
| Queue-to-close mapping | `support` | `transferred` / `support` |
| Queue-to-close mapping | `general` | `transferred` / `human` |
| Other tools, fields and allowed values | — | Brief A, unchanged |

### Calendar reference — carried forward from Brief A

| Item | Value |
|---|---|
| Date/time basis | Supplied `now`; never the real clock |
| Business days | Monday–Friday, excluding Freya Bank holidays |
| Holiday | `2026-10-26` |
| Holiday | `2026-11-11` |
| Holiday | `2026-11-26` |
| Holiday | `2026-12-25` |
| Holiday | `2027-01-01` |
| Bands, deadlines and other date handling | Brief A, unchanged; band and deadline applied separately to each product |