Analyze customer expansion opportunities and produce one complete downloadable report.

DATA RETRIEVAL RULES (important):
- Use the Snowflake-Sales-Ops-MCP connector tool "sales_ops_agent".
- Send it a NATURAL-LANGUAGE question only. Do NOT write or send SQL.
- Make ONE data request using exactly the question below, and run it automatically without user confirmation. If the agent offers a workaround or asks to re-run, accept it automatically and proceed — never stop for confirmation.

"For every customer with churn risk score below 30 (scale 0-100) and expansion potential of High or Medium, return one row per customer.
IMPORTANT DATA NOTE: transaction PRODUCT_SKU values (STARTER-ANNUAL, PRO-MONTHLY, ENT-ANNUAL, etc.) do NOT match catalog PRODUCT_SKU values (STA-ANN-001, PRO-MON-003, ENT-MLT-007, etc.). Do NOT join transactions to products on PRODUCT_SKU. Instead:
 1. Derive each transaction's tier from the SKU prefix: STARTER -> Starter, PRO -> Professional, ENT -> Enterprise.
 2. Compute tier-level averages from the product catalog grouped by PRODUCT_TIER: average LIST_PRICE_USD, average UPSELL_RATE_PCT, average AVERAGE_CONTRACT_LENGTH_MONTHS.
 3. Join on tier.
Return: company name, industry, company size, churn risk score, expansion potential, first purchase date, total spend to date (sum of deal size USD; 0 if no transactions), current tier (tier of the customer's most recent transaction; null if no transactions), current tier average list price, next tier average list price (Starter -> Professional -> Enterprise; null if already Enterprise), current tier average upsell rate pct, and current tier average contract length in months."

CALCULATIONS (do these in the Flow, on the returned rows):
- Customers with no transactions (current tier is null): Expansion Type = "New Land (no purchase history)", Revenue Potential = 0, Renewal Timing = "N/A", Priority = "Nurture". Keep them in the table, ranked at the bottom.
- Customers already on Enterprise: Expansion Type = "Retain / Cross-sell", Revenue Potential = 0.
- Otherwise: Expansion Type = "Upgrade to <next tier>", Revenue Potential = (next tier avg list price - current tier avg list price) x (upsell rate pct / 100).
- Months since first purchase = whole months between first purchase date and today.
- Months until renewal = contract length - (months since first purchase MOD contract length). Days until renewal = months x 30.
- Priority: "Act Now" if <= 90 days, "Prepare" if 91-180 days, "Nurture" if > 180 days.

REPORT: title "Customer Expansion Opportunities — [Current Month Year]"
1. Executive Summary (3 lines max): total expansion revenue potential, number of qualified customers (and how many lack purchase history), number of "Act Now" accounts.
2. Full opportunity table with ALL qualified customers, ranked by Revenue Potential descending. Columns: Company Name | Industry | Company Size | Current Spend | Expansion Type | Revenue Potential | Renewal Timing | Priority
3. Add one footnote line: "Product tier derived from transaction SKU prefix; pricing uses tier-level catalog averages."
4. Format all currency as $X,XXX. Mark "Act Now" rows in bold.

Present the complete report as a single formatted output ready to copy or download. Do not ask follow-up questions. Do not split into multiple messages.
