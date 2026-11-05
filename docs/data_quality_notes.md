# Data quality and source review

Review date: 2026-11-02  
Reviewer: Pammela Vicenti Ribeiro

## Sources inspected

- Technical challenge PDF: 3 pages.
- Store policy PDF: 8 pages, version 2.1, June 2025.
- Categories: 9 rows.
- Customers: 50 rows.
- Orders: 20 rows.
- Order items: 22 rows.
- Products: 65 rows.
- Promotions: 25 rows.

Primary and foreign-key references used by the prototype have no orphan rows.

## Confirmed anomalies and decisions

### Store contacts

- Policy cover: `(67) 3341-4444`, `contato@emporiodamusica.com.br`.
- Policy page 2: Telephone/WhatsApp `(67) 3341-4444`, with an accented domain in the displayed e-mail.
- Policy page 6: WhatsApp `(67) 3321-4500`.

Decision: retrieval returns the conflict. The assistant must not select one remote contact as definitive.

### Credit-card minimum installments

- Page 3 summary table: up to 12 installments, minimum BRL 100.00.
- Page 3 detailed rules: up to 3 installments with a BRL 50.00 floor; 4-6 with an BRL 80.00 floor; 7-12 with a BRL 100.00 floor.

Decision: calculations on which both sections agree are returned as allowed or not allowed. Values between the detailed threshold and BRL 100.00 are returned as `needs_manager_confirmation`.

### Catalog status and stock

- Product 96 is active with zero stock: unavailable because it is out of stock.
- Product 130 is `coming_soon` with two units: unavailable because it is not active.
- Product 136 is `discontinued` with 13 units: unavailable because it is discontinued.
- Product 113 is discontinued with zero stock.

Decision: sale availability requires both `status == active` and positive stock.

### Orders and historical prices

- Order 3 total is BRL 3,450.00; the current list-price sum of its items is BRL 3,498.00.
- Order 20 total is BRL 1,400.00; the current list-price sum is BRL 1,488.00.

These differences may reflect historical pricing or discounts and are not treated as data corruption. Stored order totals remain authoritative for order-status answers.

### Delivery and return eligibility

Delivered orders include an estimated delivery date but not an actual receipt timestamp. No purchase-channel field states whether the sale was online. Therefore, the seven-day withdrawal period cannot be evaluated from the order table alone.

Decision: ask for purchase channel, actual receipt date, product condition, packaging, and relevant exclusions before explaining possible eligibility.

### Personal data

The customer CSV contains name, phone, e-mail, and city. It is synthetic challenge data but is treated as personal information. The order tool reads it only to verify an exact e-mail and does not return the customer row.

## Policy extraction completeness review

The runtime policy extraction was checked again against all eight PDF pages. The review added material facts that were missing or incomplete: the CNPJ and company identity, mission and founding year, accepted debit-card brands, tracking-code format and example, named large-item freight cases, promotion calendar, five-minute service response target, standard service flow, and the instruction to consult management when a policy is uncertain. Customer-facing retrieval tests now cover these additions.

The extraction remains a reviewed operational representation rather than an automatic PDF parser. The original PDF stays in the repository as the authoritative source, and source contradictions are preserved instead of normalized away.
