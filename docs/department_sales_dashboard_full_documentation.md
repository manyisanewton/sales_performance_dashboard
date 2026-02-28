# Department Sales Dashboard: Complete Technical Documentation

## 1. Scope of this document
This document explains the **Department Sales Dashboard** end-to-end, including:
- every section and widget visible on the dashboard,
- where each value comes from,
- all formulas and derivations,
- how filters are resolved,
- how to read each graph and KPI,
- how click-through and Show More actions behave.

This documentation is based on current code in:
- `workspace/department_sales_dashboard/department_sales_dashboard.json`
- `api/department_dashboard_api.py`
- `dashboard_chart_source/department_sales_order_trend/department_sales_order_trend.py`
- `dashboard_chart_source/department_forecasted_revenue/department_forecasted_revenue.py`
- `dashboard_chart_source/department_sales_funnel/department_sales_funnel.py`
- all `custom_html_block/department_*` blocks used by the workspace.

## 2. Dashboard architecture
The dashboard is assembled from 3 layers:
1. **Workspace layout** defines order and block names.
2. **Frontend custom blocks** read localStorage filters and call backend methods.
3. **Backend API/chart source methods** run SQL/ORM and return computed payloads.

Main workspace definition:
- `apps/sales_performance_dashboard/sales_performance_dashboard/workspace/department_sales_dashboard/department_sales_dashboard.json`

## 3. Filter and scope model (critical)

### 3.1 Department filter block
Filter UI block:
- `custom_html_block/department_dashboard_filters/department_dashboard_filters.json`

Fields:
- Department
- View Mode (`Monthly`, `Yearly`)
- Reference Date
- Risk Window (`Next 7 Days`, `Next 14 Days`)

LocalStorage keys used across department widgets:
- `spd_department_dashboard_department`
- `spd_department_view_mode`
- `spd_department_reference_date`
- `spd_department_risk_window`
- `spd_department_slippage_mode` (used only by Target Slippage widget mode selector)

Behavior:
- Department list is loaded from `get_department_options()`.
- Selected values are written to localStorage.
- Filter changes dispatch `window` event `spd-department-changed`.
- All department widgets listen to this event and refresh from server.

### 3.2 Department ownership scope resolution
Core resolver:
- `api/department_dashboard_api.py::_get_department_context`

Logic:
- Reads active `Employee` rows for selected `department` with `status != 'Left'`.
- Builds:
  - `employee_ids` (for Sales Team/Sales Person linkage)
  - `user_ids` (for owner-based linkage)

This dual scope is then reused by most finance/order/invoice metrics.

### 3.3 Sales Invoice attribution logic
Core helper:
- `api/department_dashboard_api.py::_build_sales_invoice_condition`

A Sales Invoice belongs to the department scope if either condition is true:
1. It has a Sales Team row linked to a Sales Person whose `employee` is in department employees.
2. Its `owner` is in department users.

If neither employees nor users exist, condition becomes `1 = 0` (forced no data).

### 3.4 Time-range model
The dashboard uses two time models:
1. **Filter-driven period widgets** use `view_mode + reference_date`.
2. **Current-month/current-week KPI widgets** use month/week boundaries around `reference_date` and fixed logic in `get_department_kpis`.

Important implication:
- Not every widget changes the same way with `view_mode`; some are always monthly by design.

## 4. Global data hygiene rules
Across backend queries, common safeguards are applied:
- Demo data exclusion by pattern from `PersonalSalesDashboard().demo_pattern`.
- Submitted-only transactions for most accounting documents (`docstatus = 1`).
- Department user/employee scope enforcement via helper conditions.
- Null-safe sums/averages with `COALESCE`/`IFNULL` and safe divide guards.

## 5. Workspace sections and widgets (exact display order)

## 5.1 Header and subtitle
Static workspace text:
- `Department Sales Dashboard`
- `Department-level sales trend across all people in the selected department.`

No backend call.

## 5.2 Department Dashboard Filters
Frontend:
- `custom_html_block/department_dashboard_filters/department_dashboard_filters.json`
Backend:
- `get_department_options()`

How managers should use it:
- Pick a department first (required for meaningful results).
- Choose `Monthly` or `Yearly` view.
- Set a reference date anchoring period calculations.
- Set risk window to 7 or 14 days to control “revenue at risk” exposure horizon.

## 5.3 Revenue & Targets (Department KPI Revenue Customers)
Frontend:
- `custom_html_block/department_kpi_revenue_customers/department_kpi_revenue_customers.json`
Backend:
- `get_department_kpis(department, risk_window_days, reference_date)`

Displayed KPIs:
- Total Revenue
- Total Collected
- Total Outstanding
- Revenue At Risk
- Monthly Target
- % Towards Target
- Total Invoices
- Opportunities Value
- Collection Efficiency (Month)
- Collection Efficiency (Rolling 3M)
- Cash Conversion Flag

### Math and derivation
Reference window setup:
- `today = reference_date`
- `month_start = first day of month(today)`
- `month_end = last day of month(today)`
- `rolling_3m_start = first day of month(today - 2 months)`
- `week_start/week_end = Monday-Sunday week containing today`

1. **Total Revenue**
- `SUM(Sales Invoice.grand_total)`
- filters: submitted, non-demo customer, `posting_date between month_start and month_end`, department invoice scope.

2. **Total Collected**
- `SUM(Payment Entry Reference.allocated_amount)`
- joined to submitted Payment Entry + submitted Sales Invoice,
- payment entry posting date in current month,
- same department invoice scope.

3. **Total Outstanding**
- `SUM(Sales Invoice.outstanding_amount)`
- submitted, outstanding > 0, non-demo, department scope.

4. **Revenue At Risk**
- `SUM(Sales Invoice.outstanding_amount)` where due date is either:
  - overdue (`due_date < today`) or
  - due soon (`today <= due_date <= today + risk_window_days`).

5. **Monthly Target**
- Uses `_get_department_monthly_target(department, today)`:
  - first tries department-level Sales Targets (`target_level='Department'`),
  - falls back to sum of individual targets in department if no department-level target.

6. **% Towards Target**
- `target_pct = (revenue / monthly_target) * 100`, else 0 if target is 0.

7. **Total Invoices**
- `COUNT(DISTINCT Sales Invoice.name)` in current month, submitted, non-demo, scoped.

8. **Opportunities Value**
- `SUM(Opportunity.opportunity_amount)`
- owners in department users,
- creation in current month,
- non-demo names/party.

9. **Collection Efficiency (Month)**
- `collection_efficiency_month = (collected / revenue) * 100`, guarded for zero denominator.

10. **Collection Efficiency (Rolling 3M)**
- `rolling_3m_invoiced = SUM(invoice grand_total from rolling_3m_start to month_end)`
- `rolling_3m_collected = SUM(allocated_amount over same period)`
- `collection_efficiency_3m = rolling_3m_collected / rolling_3m_invoiced * 100`.

11. **Cash Conversion Flag**
- `Weak` if month < 70 or rolling-3m < 75.
- `Watch` if month < 85 or rolling-3m < 90.
- Else `Healthy`.

### Click-through behavior
Cards are clickable and route to source records:
- Revenue/Invoices -> Sales Invoice list.
- Collected -> Payment Entry list.
- Outstanding/Efficiency/Flag -> Sales Invoice outstanding list.
- Revenue at risk -> Sales Invoice list with due date cutoff by risk window.
- Target cards -> Sales Targets list filtered to selected department.
- Opportunities value -> Opportunity list for department users.

## 5.4 Target Slippage Indicator
Frontend:
- `custom_html_block/department_target_slippage/department_target_slippage.json`
Backend:
- `get_department_target_slippage(department, slippage_mode, reference_date)`

Modes:
- Daily
- Monthly

### Math and derivation
Daily mode:
- `period_target = daily department target`
- `expected_by_today = period_target`
- `actual_by_today = collected amount for that day`

Monthly mode:
- `period_target = monthly department target`
- `expected_by_today = period_target`
- `actual_by_today = collected amount from month_start to month_end`

Common formulas:
- `slippage_amount = actual_by_today - expected_by_today`
- `pace_pct = (actual_by_today / expected_by_today) * 100` (or 0 if expected is 0)
- status:
  - `No Target` if expected <= 0
  - `Ahead` if `pace_pct >= 100`
  - `On Pace` if `95 <= pace_pct < 100`
  - `Behind` if `< 95`

Donut chart composition:
- If ahead: `Expected Pace + Ahead surplus`.
- If behind: `Actual + Gap to Pace`.

How to read:
- Pace is the primary signal.
- Slippage value sign indicates over/under pace.
- Donut legend breaks value contribution, not just percentages.

## 5.5 Customers KPIs
Frontend:
- `custom_html_block/department_kpi_customers/department_kpi_customers.json`
Backend:
- `get_department_kpis(...)`

Displayed metrics:
- New Customers (Week)
- Customers Served (Week)
- New Customers (Month)
- Customers Served (Month)

Math:
- New customers use `Customer.creation` in period, owner in department users.
- Customers served use count of distinct invoiced customers in period from submitted Sales Invoices in department scope.

Click-through behavior:
- Cards route to Sales Invoice list filtered by department users.

## 5.6 Department Sales Order Trend
Frontend:
- `custom_html_block/department_sales_order_trend_block/department_sales_order_trend_block.json`
Backend:
- `dashboard_chart_source/department_sales_order_trend/department_sales_order_trend.py::get_data_for_custom`

### Data logic
Period bins:
- Monthly view: day bins across selected month.
- Yearly view: month bins Jan-Dec of selected year.

Per bin values:
- Sales Amount = `SUM(Sales Order.grand_total)`.
- Sales Orders = `COUNT(DISTINCT Sales Order.name)`.
- filters: submitted sales orders, non-demo customers, department scope via Sales Team or owner.

### Graph nuance (important)
The frontend simulates dual axis by scaling order counts:
- right axis is fixed 0-100,
- order count values are multiplied by `amount_max / 100` before charting,
- tooltip converts back to real count.

How to read:
- Pink line reflects monetary trend.
- Blue line reflects order volume trend using rescaled overlay.
- For exact order counts, use tooltip values, not raw vertical position.

## 5.7 Deals & Pipeline KPIs
Frontend:
- `custom_html_block/department_kpi_deals_pipeline/department_kpi_deals_pipeline.json`
Backend:
- `get_department_kpis(...)`

Displayed metrics:
- Total Opportunities
- Ongoing Deals
- Won Deals
- Lost Deals
- Avg. Deal Value
- Avg. Won Deal Value
- Avg. Time to Close Deal
- Avg. Time Lead to Deal

Math:
- opportunity scope = owners in department users, filtered to current month windows.
- Ongoing = status not in `Converted`, `Lost`.
- Won = status `Converted` modified in current month.
- Lost = status `Lost` modified in current month.
- Avg close days = average `DATEDIFF(modified, creation)` over converted opportunities.
- Avg lead-to-deal days = average `DATEDIFF(opportunity.modified, lead.creation)` for converted opportunities from lead source.

Click-through behavior:
- Cards route to Opportunity list with status filters matching the metric.

## 5.8 Weighted Pipeline Coverage
Frontend:
- `custom_html_block/department_weighted_pipeline_coverage/department_weighted_pipeline_coverage.json`
Backend:
- `get_department_weighted_pipeline_coverage(department, view_mode, reference_date)`

### Math
1. **Weighted Pipeline**
- `SUM(opportunity_amount * probability / 100)`
- owners in department users,
- excludes statuses `Converted`, `Lost`,
- created up to reference date.

2. **Target comparator**
- Yearly view uses current year target.
- Monthly view uses current month target.

3. **Coverage**
- `coverage_pct = weighted_pipeline / next_target * 100`.
- `gap = weighted_pipeline - next_target`.

Status thresholds:
- `No Target` if target <= 0
- `Healthy` if coverage >= 100
- `Watch` if coverage >= 70
- `Weak` otherwise

UI nuance:
- Gauge displays up to 150% scale.
- Additional `Strong` visual tone appears client-side when pct >= 130.

How to read:
- Coverage near or above 100% means weighted open pipeline can cover current target.
- Gap positive means projected surplus; negative means shortfall.

## 5.9 Department Forecasted Revenue
Frontend:
- `custom_html_block/department_forecasted_revenue_block/department_forecasted_revenue_block.json`
Backend:
- `dashboard_chart_source/department_forecasted_revenue/department_forecasted_revenue.py::get_data_for_custom`

### Math
Fixed horizon = last 6 months including selected month.

Per month:
- Forecasted = `SUM(opportunity_amount * probability / 100)`
  - opportunities owned by department users,
  - `docstatus < 2`,
  - date filter: `IFNULL(transaction_date, DATE(creation))`.
- Actual = `SUM(Sales Invoice.grand_total)`
  - submitted invoices,
  - non-demo,
  - department invoice scope.

How to read:
- Forecasted bars show probability-weighted expected revenue.
- Actual bars show booked invoice revenue.
- Persistent positive forecast gap indicates conversion risk.

## 5.10 Gross Margin % Trend
Frontend:
- `custom_html_block/department_gross_margin_trend/department_gross_margin_trend.json`
Backend:
- `get_department_gross_margin_trend(department, reference_date, months=12)`

### Math
For each month in 12-month range:
- `sales = SUM(Sales Invoice Item.base_net_amount)`
- `cogs = SUM(Sales Invoice Item.stock_qty * incoming_rate)`
- `gross_margin_pct = ((sales - cogs) / sales) * 100` if sales > 0 else 0

How to read:
- Positive higher values mean stronger margin.
- Drops can indicate discount pressure, COGS increase, or mix shift.

## 5.11 Discount Leakage
Frontend:
- `custom_html_block/department_discount_leakage/department_discount_leakage.json`
Backend:
- `get_department_discount_leakage_dashboard(department, view_mode, reference_date, limit, table_limit)`

Displayed parts:
- KPI cards
- leakage trend line
- top reps bar chart
- top customers bar chart (top 5 rendered in UI)
- leakage by item group bar chart
- highest leakage invoices table (5 initial rows + Show more)

### Math core
Per invoice:
- `list_value = SUM(base_price_list_rate * qty)`
- `billed_value = SUM(base_net_amount)`
- `leakage = max(0, list_value - billed_value)`
- `leakage_pct = leakage / list_value * 100` (if list_value > 0)

Aggregate KPIs:
- `leakage_amount = SUM(leakage)`
- `leakage_pct = leakage_amount / total_list * 100`
- `net_realization_pct = total_billed / total_list * 100`
- `avg_discount_pct = average of per-invoice leakage_pct`

Rep attribution:
- Uses Sales Team allocated percentages on each invoice.
- If allocation totals 0, rep share is split equally.
- If no Sales Team rows, falls back to invoice owner fullname.

Trend:
- grouped by posting month within selected period,
- outputs both leakage amount and leakage % per month.

### UI behavior
- `TOP_CUSTOMERS_LIMIT = 5` in frontend for top-customer chart.
- Highest leakage invoices table:
  - receives up to 100 rows from API,
  - shows first 5,
  - Show more increments by 5,
  - invoice row click opens Sales Invoice form.

How to read:
- Start with KPI cards for scale and severity.
- Use top reps/customers/item groups to localize source of leakage.
- Use invoice table for immediate corrective action.

## 5.12 Payment Delay Cost
Frontend:
- `custom_html_block/department_payment_delay_cost/department_payment_delay_cost.json`
Backend:
- `get_department_payment_delay_cost(department, reference_date, annual_financing_rate, top_limit)`

### Math
Base set:
- submitted invoices, outstanding > 0, overdue (`due_date < reference_date`), non-demo, department scope.

For each overdue invoice:
- `days_overdue = max(reference_date - due_date, 0)`
- `rate_per_day = annual_financing_rate / 100 / 365`
- `cost = outstanding_amount * rate_per_day * days_overdue`

Aggregates:
- `overdue_outstanding = SUM(outstanding_amount)`
- `estimated_delay_cost = SUM(cost)`
- `daily_financing_cost = overdue_outstanding * rate_per_day`
- `cost_pct_of_overdue = estimated_delay_cost / overdue_outstanding * 100`
- `avg_overdue_days = weighted average by outstanding amount`

Buckets:
- 0-30, 31-60, 61-90, 90+ days overdue.

Top customers:
- ranked by estimated delay cost, limited by `top_limit` (frontend uses 6).

How to read:
- Gauge shows financing drag as a percentage of overdue portfolio.
- Bucket mix indicates whether debt is becoming structurally old.
- Top-customer list helps prioritise collections focus.

## 5.13 Department Sales Funnel
Frontend:
- `custom_html_block/department_sales_funnel/department_sales_funnel.json`
Backend:
- `dashboard_chart_source/department_sales_funnel/department_sales_funnel.py::get_data_for_custom`

Stage flow (current):
- `Lead -> Opportunity -> Quotation -> Customer -> Sales Order -> Delivery Note -> Sales Invoice`

Stage calculations:
1. Lead count: leads owned by department users.
2. Opportunity count: opportunities owned by department users.
3. Quotation count: submitted quotations owned by department users.
4. Customer count: customers owned by department users.
5. Sales Order count: submitted sales orders owned by department users.
6. Delivery Note count: submitted delivery notes owned by department users.
7. Sales Invoice count: submitted invoices owned by department users.

How to read:
- Compare each step with the previous one to detect drop-offs.
- This is a **count funnel** (volume), not a value funnel.

## 5.14 Department Top Customers Table
Frontend:
- `custom_html_block/department_top_customers_table/department_top_customers_table.json`
Backend:
- `get_department_top_customers_table(department, limit)`

Behavior and math:
- Aggregates submitted Sales Invoices by customer across department scope.
- `amount = SUM(invoice grand_total)` per customer.
- `served_by` sourced from Sales Team employee names; fallback to owner fullname if no team.
- UI requests `limit: 5`.
- Customer rows are clickable and open Customer form.
- No total footer row is rendered in UI.

How to read:
- Shows revenue concentration and who serves each key account.

## 5.15 Department Project Pipeline
Frontend:
- `custom_html_block/department_project_pipeline/department_project_pipeline.json`
Backend:
- `get_department_project_status_finance(department, view_mode, reference_date)`

Returned blocks:
- project status counts,
- period revenue linked to projects,
- outstanding linked to projects,
- aging buckets for overdue project-linked receivables,
- invoice name lists for drilldowns.

### Math
Project scope:
- projects where `Project.owner` is in department users.

Counts:
- `total`, `ongoing` (Open/In Progress/Working), `completed`.

Revenue:
- submitted invoices in selected period where invoice/project link exists either:
  - directly on `Sales Invoice.project`, or
  - on any `Sales Invoice Item.project`.

Outstanding and aging:
- submitted invoices with outstanding > 0 and linked project condition above.
- overdue days split into 0-30, 31-60, 61-90, 90+.

Click-through behavior:
- Status list and total open filtered Project list.
- Revenue/outstanding/aging cards open Sales Invoice list with exact invoice name filters.

## 5.16 Project Delivery Health
Frontend:
- `custom_html_block/department_project_delivery_health/department_project_delivery_health.json`
Backend:
- `get_department_project_delivery_health(department, limit=5)`

Displayed:
- summary pills (On Track, At Risk, Overdue, Projects),
- top 5 project rows,
- Show More button.

### Math and rules
Project selection:
- non-cancelled projects owned by department users, newest first, limited to 5 rows.

Task-derived metrics per project:
- total tasks,
- completed tasks,
- open tasks,
- overdue open tasks,
- average task progress.

Completion %:
- if tasks exist:
  - use average progress when available,
  - else `completed_tasks / total_tasks * 100`.
- if no tasks:
  - 100% if project status is Completed, else 0%.

Health classification:
- `Overdue` if planned end date passed and completion < 100 and status not Completed.
- `At Risk` if planned end date within 7 days and completion < 80 and status not Completed.
- else `On Track`.

Show More behavior:
- routes to Project list filtered by owners in selected department.

## 5.17 Targets shortcut
Frontend:
- `custom_html_block/department_sales_targets_shortcut/department_sales_targets_shortcut.json`
Backend:
- `get_department_sales_target_route(department)`

Behavior:
- On click, reads selected department from localStorage.
- If a department-level Sales Target exists:
  - opens that `Sales Targets` document form.
- If none exists:
  - opens a new Sales Targets form prefilled with:
    - `target_level = Department`
    - selected `department`.

This ensures shortcut is filter-aware and manager-friendly.

## 6. Backend method map summary
Main API methods used by this dashboard:
- `get_department_options`
- `get_department_kpis`
- `get_department_target_slippage`
- `get_department_weighted_pipeline_coverage`
- `get_department_gross_margin_trend`
- `get_department_discount_leakage_dashboard`
- `get_department_payment_delay_cost`
- `get_department_top_customers_table`
- `get_department_project_status_finance`
- `get_department_project_delivery_health`
- `get_department_owner_users`
- `get_department_sales_target_route`

Chart source methods used:
- `department_sales_order_trend.get_data_for_custom`
- `department_forecasted_revenue.get_data_for_custom`
- `department_sales_funnel.get_data_for_custom`

## 7. How managers should read the dashboard (recommended flow)
1. Start with **Filters**: verify department, period mode, date, risk window.
2. Check **Revenue & Targets**: target attainment, collection efficiency, risk exposure.
3. Use **Target Slippage + Pipeline Coverage**: pace against target and forward-looking capacity.
4. Inspect **Sales Order Trend + Forecasted Revenue + Gross Margin**: trend direction, conversion realism, profitability quality.
5. Drill into **Discount Leakage + Payment Delay Cost**: margin and cash leakage controls.
6. Validate process throughput via **Sales Funnel** and account concentration in **Top Customers**.
7. Close with **Project Pipeline + Delivery Health** for execution risk affecting billings.

## 8. Known implementation nuances (as coded)
1. KPI methods are anchored to month/week windows around `reference_date`; they are not fully view-mode switched.
2. Sales Order Trend uses client-side scaled dual-axis simulation; tooltip is authoritative for order count.
3. Discount Leakage API returns `waterfall` data, but this specific block does not currently render a waterfall chart.
4. Funnel is owner-based counts per doctype stage; it is not constrained to only records transformed from prior stage.
5. Department scope combines Sales Team-based invoice attribution and owner-based attribution for invoice metrics.

## 9. Code index
- Workspace:
  - `apps/sales_performance_dashboard/sales_performance_dashboard/workspace/department_sales_dashboard/department_sales_dashboard.json`
- Backend API:
  - `apps/sales_performance_dashboard/sales_performance_dashboard/api/department_dashboard_api.py`
- Chart sources:
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/dashboard_chart_source/department_sales_order_trend/department_sales_order_trend.py`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/dashboard_chart_source/department_forecasted_revenue/department_forecasted_revenue.py`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/dashboard_chart_source/department_sales_funnel/department_sales_funnel.py`
- Custom blocks:
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_dashboard_filters/department_dashboard_filters.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_kpi_revenue_customers/department_kpi_revenue_customers.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_target_slippage/department_target_slippage.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_kpi_customers/department_kpi_customers.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_sales_order_trend_block/department_sales_order_trend_block.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_kpi_deals_pipeline/department_kpi_deals_pipeline.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_weighted_pipeline_coverage/department_weighted_pipeline_coverage.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_forecasted_revenue_block/department_forecasted_revenue_block.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_gross_margin_trend/department_gross_margin_trend.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_discount_leakage/department_discount_leakage.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_payment_delay_cost/department_payment_delay_cost.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_sales_funnel/department_sales_funnel.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_top_customers_table/department_top_customers_table.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_project_pipeline/department_project_pipeline.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_project_delivery_health/department_project_delivery_health.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/department_sales_targets_shortcut/department_sales_targets_shortcut.json`
