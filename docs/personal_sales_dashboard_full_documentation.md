# Personal Sales Dashboard: Complete Technical Documentation

## 1. Scope of this document
This document explains the **Personal Sales Dashboard** end-to-end, including:
- every section and widget visible on the dashboard,
- where each value comes from,
- all formulas and derivations,
- how filters are resolved,
- how to read each visual,
- how drill-down links behave.

This documentation is based on current code in:
- `workspace/personal_sales_dashboard/personal_sales_dashboard.json`
- `api/personal_dashboard_api.py`
- `sales_performance_dashboard/dashboards/personal_dashboard.py`
- all `dashboard_chart_source/personal_*` sources used by the workspace
- all personal custom blocks used in the workspace.

## 2. Dashboard architecture
The dashboard is assembled from 3 data layers:
1. **Workspace layout**: declares widget order and block/chart/card names.
2. **Frontend widget scripts**: read localStorage filters and call backend methods.
3. **Backend methods**: run SQL/ORM, compute values, and return payloads.

Main workspace definition:
- `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/workspace/personal_sales_dashboard/personal_sales_dashboard.json`

## 3. Filter and scope model (critical)

### 3.1 Personal filter block
Filter UI block:
- `custom_html_block/personal_dashboard_filters/personal_dashboard_filters.json`

LocalStorage keys used:
- `spd_personal_dashboard_department`
- `spd_personal_dashboard_employee`
- `spd_personal_view_mode`
- `spd_personal_risk_window`

Behavior:
- Filter options are fetched from `sales_performance_dashboard.api.personal_dashboard_api.get_personal_dashboard_filter_options`.
- Clicking **Apply** stores values in localStorage, fires `spd-personal-changed`, then reloads the page.
- Clicking **Reset** clears localStorage keys and reloads defaults.

### 3.2 Scope resolution logic
Central scope resolver:
- `api/personal_dashboard_api.py::resolve_personal_scope`

Rules:
- Sales Users are forced to their own user/employee/department.
- Elevated roles (`Sales Manager`, `System Manager`, `Administrator`) can switch department/employee.
- If department is chosen and employee missing, first active employee in that department is auto-selected.
- Most personal chart/custom methods use this resolved scope user.

### 3.3 Important time-range model
Two different time models exist in personal dashboard code:
1. **Classic Number Card methods** in `dashboards/personal_dashboard.py`: mostly based on server `today`, current week/current month.
2. **Custom/API methods** in `api/personal_dashboard_api.py` and chart sources: often accept view_mode/reference_date.

Implication:
- Widgets are not all driven by a single global date model.
- Some widgets always use "this month" regardless of selected view mode.

## 4. Global data hygiene rules used across queries
- Demo data exclusion patterns are used widely:
  - `%DEMO%` in `PersonalSalesDashboard`
  - `SPD-DEMO-%` in parts of `personal_dashboard_api.py`
- Most invoice/order metrics include `docstatus = 1` (submitted only).
- Ownership is mostly controlled by `owner = resolved_user` for personal scope.

## 5. Workspace sections and widgets (in exact display order)

## 5.1 Header and subtitle
- Static text from workspace JSON.
- No data source.

## 5.2 Personal Dashboard Filters
Source:
- `custom_html_block/personal_dashboard_filters/personal_dashboard_filters.json`
Backend:
- `api/personal_dashboard_api.py::get_personal_dashboard_filter_options`

What it shows:
- Department list,
- employee list for selected department,
- view mode (Daily/Monthly/Quarterly/Yearly),
- risk windows.

How to read/use:
- This block defines personal scope for most charts/custom blocks.

## 5.3 Personal Sales Order Trend (chart)
Chart source:
- `dashboard_chart_source/personal_sales_order_trend/personal_sales_order_trend.py`
- `dashboard_chart_source/personal_sales_order_trend/personal_sales_order_trend.js`

Calculation:
- Default period: last 12 months ending current month (if no from/to provided).
- For each month bin, calculates:
  - `SUM(Sales Order.grand_total)`
  - conditions: `docstatus = 1`, `owner = scoped_user`, `customer NOT LIKE demo`, `transaction_date` inside month.

Visual meaning:
- Line value at each month = submitted sales order value for that month.

## 5.4 Revenue & Targets section

### 5.4.1 Revenue Wave Card (custom block)
Source:
- `custom_html_block/revenue_wave_card/revenue_wave_card.json`
Backend:
- `api/personal_dashboard_api.py::get_personal_revenue_metric`
- wraps `PersonalSalesDashboard.get_total_revenue()`.

Formula:
- `Total Revenue = SUM(Sales Invoice.grand_total)`
- where: submitted, owner=scoped user, non-demo customer, posting_date in current month.

Visual meaning:
- Big green value = current month revenue in selected personal scope.

### 5.4.2 Number Cards in Revenue & Targets
All Number Cards use methods in:
- `sales_performance_dashboard/dashboards/personal_dashboard.py`

Cards and formulas:
1. **Total Collected**
- `SUM(Payment Entry.paid_amount)`
- `docstatus=1`, `payment_type='Receive'`, owner=user, non-demo party, posting_date in month.

2. **Total Outstanding**
- `SUM(Sales Invoice.outstanding_amount)`
- submitted, owner=user, outstanding>0, non-demo customer.

3. **Monthly Target**
- latest matching `Sales Targets` row, `target_level='Individual'`, employee=current user's employee, date within start/end.
- value: `COALESCE(monthly_target_current, monthly_target, 0)`.

4. **% Towards Target**
- `(Total Revenue / Monthly Target) * 100`.
- returns `0` if target <= 0.

5. **Total Invoices**
- count of submitted Sales Invoices this month, owner=user, non-demo customer.

6. **Opportunities Value**
- `SUM(Opportunity.opportunity_amount)` created this month, owner=user, non-demo name/party.

Read guidance:
- Compare `Total Revenue` vs `Monthly Target` and `% Towards Target` together.
- `Total Collected` and `Total Outstanding` represent cash realized vs pending exposure.

## 5.5 Customers section

### 5.5.1 Number Cards
1. **New Customers (Week)**
- count of `Customer` created this week (Mon-Sun), owner=user, non-demo name/customer_name.

2. **Customers Served (Week)**
- count of distinct `Sales Invoice.customer` this week, submitted, owner=user, non-demo.

3. **New Customers (Month)**
- count of `Customer` created this month, owner=user, non-demo.

4. **Customers Served (Month)**
- count of distinct customers invoiced this month, submitted, owner=user, non-demo.

### 5.5.2 Personal Top Customers Table (custom block)
Source:
- `custom_html_block/personal_top_customers_table/personal_top_customers_table.json`
Backend:
- `dashboard_chart_source/personal_top_customers/personal_top_customers.py::get_table_data_for_custom`

Calculation:
- grouped query on Sales Invoice:
  - per customer total billed = `SUM(grand_total)`
  - submitted only, owner=scoped user, non-demo customer,
  - ordered descending.
- paginated: default page size 5.

UI behavior:
- shows top 5 initially,
- **Show more** fetches next page,
- row click opens Customer form.

Visual meaning:
- rank and billed amount concentration by customer.

## 5.6 Deals & Pipeline section

### 5.6.1 Number Cards
1. **Total Opportunities**
- count of opportunities created this month (owner=user, non-demo).

2. **Ongoing Deals**
- opportunities in month where status not in `Converted`, `Lost`.

3. **Won Deals**
- opportunities with status `Converted` and modified in month.

4. **Lost Deals**
- opportunities with status `Lost` and modified in month.

5. **Avg. Deal Value**
- average `opportunity_amount` of opportunities created in month.

6. **Avg. Won Deal Value**
- average `opportunity_amount` of converted opportunities modified in month.

7. **Avg. Time to Close Deal**
- average `DATEDIFF(modified, creation)` on converted opportunities in month.
- displayed as text like `8 days`.

8. **Avg. Time Lead to Deal**
- joins Opportunity to Lead (`o.party_name = l.name`), converted lead-origin opportunities.
- average `DATEDIFF(o.modified, l.creation)`.
- displayed as text like `20 days`.

### 5.6.2 Personal Forecasted Revenue (chart)
Source:
- `dashboard_chart_source/personal_forecasted_revenue/personal_forecasted_revenue.py`

Calculation:
- Fixed horizon: last 6 months including current month.
- Forecasted per month:
  - `SUM(opportunity_amount * probability / 100)`
  - opportunity `docstatus < 2`, owner=scoped user,
  - date field: `IFNULL(transaction_date, DATE(creation))` in month,
  - non-demo name/party.
- Actual per month:
  - `SUM(Sales Invoice.grand_total)` submitted, owner=scoped user, non-demo customer, posting_date in month.

Visual meaning:
- `Forecasted` line = probability-weighted pipeline.
- `Actual` line = booked invoice revenue.
- Gap indicates forecast conversion performance.

### 5.6.3 Personal Sales Funnel (custom block)
Source:
- `custom_html_block/personal_sales_funnel/personal_sales_funnel.json`
Backend:
- `dashboard_chart_source/personal_sales_funnel/personal_sales_funnel.py::get_data_for_custom`

Stage flow (current):
- `Lead -> Opportunity -> Quotation -> Customer -> Sales Order -> Delivery Note -> Sales Invoice`

Stage calculations:
1. Lead count: leads owned by scoped user.
2. Opportunity count: opportunities where `opportunity_from='Lead'` and `party_name in lead_names`.
3. Quotation count: submitted quotations for lead-origin customers, owner=scoped user.
4. Customer count: customers whose `lead_name` belongs to scoped leads.
5. Sales Order count: submitted SO for those customers, owner=scoped user.
6. Delivery Note count: submitted DN for those customers, owner=scoped user.
7. Sales Invoice count: submitted SI for those customers, owner=scoped user.

Visual meaning:
- each funnel segment width corresponds to stage count,
- helps identify drop-off across lifecycle stages.

## 5.7 Orders & Billing section

### 5.7.1 Personal Sales Order Analysis Block
Source:
- `custom_html_block/personal_sales_order_analysis_block/personal_sales_order_analysis_block.json`
Backend:
- `dashboard_chart_source/personal_sales_order_analysis/personal_sales_order_analysis.py::get_data_for_custom`

Formula:
- Over submitted Sales Orders for scoped user:
  - `total_amount = SUM(grand_total)`
  - `billed_amount = SUM(grand_total * (per_billed / 100))`
  - `amount_to_bill = max(total_amount - billed_amount, 0)`

Visual meaning:
- donut split of already billed vs remaining to bill from SO base.

### 5.7.2 Personal Item Sales (Monthly) Table
Source:
- `custom_html_block/personal_item_sales_monthly_table/personal_item_sales_monthly_table.json`
Backend:
- `dashboard_chart_source/personal_item_sales_monthly/personal_item_sales_monthly.py::get_table_data_for_custom`

Calculation:
- joins Sales Invoice + Sales Invoice Item,
- groups by item_code/item_name,
- amount = `SUM(sii.base_amount)`,
- submitted invoices only,
- owner=scoped user,
- non-demo customer,
- date range default = current month (posting_date between first/last day of today).

UI behavior:
- initial top 5 rows,
- Show more pagination,
- row click opens Item form.

Visual meaning:
- top billed items by base amount within month range.

## 5.8 Projects section

### 5.8.1 Personal Project Pipeline (custom block)
Source:
- `custom_html_block/personal_project_pipeline/personal_project_pipeline.json`
Backend:
- `api/personal_dashboard_api.py::get_personal_project_status_finance`

What it uses from payload:
- counts: total/ongoing/completed projects,
- money: total_revenue, outstanding,
- aging buckets: 0-30 / 31-60 / 61-90 / 90+,
- invoice name lists for drilldown.

Core calculations in backend:
- projects: all `Project` where owner=scoped user.
- ongoing statuses: `Open`, `In Progress`, `Working`.
- completed: `Completed`.
- period revenue: sum of project-linked invoice grand totals within view range.
- outstanding: sum outstanding invoice amounts on project-linked invoices.
- aging buckets by overdue days from due_date to `as_of` date.

Project-linked invoice matching rule:
- invoice project directly matches project list, OR
- any invoice item (`Sales Invoice Item.project`) matches.

Drilldown behavior:
- clicking cards/routes opens filtered Project or Sales Invoice list via `frappe.route_options`.

Visual meaning:
- donut + list gives portfolio status mix,
- finance cards show project-backed revenue exposure and receivable aging.

### 5.8.2 Personal Project Delivery Health (custom block)
Source:
- `custom_html_block/personal_project_delivery_health/personal_project_delivery_health.json`
Backend:
- `api/personal_dashboard_api.py::get_personal_project_delivery_health`

Computation per project:
- loads latest projects (owner=scoped user, not Cancelled, limit default 5),
- aggregates tasks by project:
  - total tasks,
  - completed,
  - open (not Completed/Cancelled),
  - overdue (exp_end_date < today and not closed),
  - avg task progress.
- completion logic:
  - if tasks exist: avg_progress if >0 else completed/total*100,
  - if no tasks: 100% if project status Completed else 0%.
- health rules:
  - Overdue: planned end < today and completion <100 and project not Completed,
  - At Risk: planned end within 7 days and completion <80 and project not Completed,
  - else On Track.

UI behavior:
- row project name is clickable (opens Project form),
- Show More opens Project list for scope owner.

Visual meaning:
- operational execution health, not just financial status.

## 5.9 Leads section

### 5.9.1 Total Leads Number Card
Formula:
- count of leads created this month, owner=user, non-demo.

### 5.9.2 Personal Leads by Source Block
Source:
- `custom_html_block/personal_leads_by_source_block/personal_leads_by_source_block.json`
Backend:
- `dashboard_chart_source/personal_leads_by_source/personal_leads_by_source.py::get_data`

Calculation:
- groups Lead by source with fallback `Unknown` for empty source.
- inclusion:
  - `(owner = scoped_user OR lead_owner = scoped_user)`
  - non-demo lead name.

Visual meaning:
- donut share of lead volume by source channel.

## 5.10 Appointments section
Number Cards:
1. **Total Appointments**
- count of Appointment in month where owner=user.

2. **Open Appointments**
- count of Appointment where status in Open/Scheduled and owner=user.

3. **Closed Appointments**
- count of Appointment where status Closed, in month, owner=user.

Fallback behavior:
- if `Appointment` doctype does not exist, all three return 0.

## 5.11 Targets shortcut
Custom block:
- `custom_html_block/my_sales_targets_shortcut/my_sales_targets_shortcut.json`
Backend:
- `api/personal_dashboard_api.py::get_my_sales_target_route`

Behavior on click:
- checks scoped employee for latest Individual `Sales Targets` (`docstatus < 2`).
- if exists: opens that target form.
- if missing: opens new Sales Targets form prefilled with:
  - `target_level='Individual'`,
  - scoped department (if available),
  - scoped employee (if available).

## 6. Number Card method mapping summary
All Number Cards map to methods in:
- `sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard`

Method list used by cards:
- `get_revenue`
- `get_collected`
- `get_outstanding`
- `get_target`
- `get_target_achievement`
- `get_total_invoices`
- `get_leads`
- `get_opportunities`
- `get_opportunities_value`
- `get_won_deals`
- `get_lost_deals`
- `get_ongoing_deals`
- `get_avg_deal_value`
- `get_avg_won_deal_value`
- `get_avg_time_to_close_deal`
- `get_avg_time_lead_to_deal`
- `get_new_customers_week`
- `get_customers_served_week`
- `get_new_customers_month`
- `get_customers_served_month`
- `get_total_appointments`
- `get_open_appointments`
- `get_closed_appointments`

## 7. How to read the dashboard as a full story
1. Start at **Revenue & Targets** to check achievement and cash posture.
2. Move to **Customers** to validate whether growth and servicing trend support revenue.
3. Use **Deals & Pipeline** to diagnose conversion quality and speed.
4. Validate **Orders & Billing** to spot billing lag by order and item mix.
5. Check **Projects** for delivery health and project-linked receivable risk.
6. Use **Leads + Appointments** to confirm top-of-funnel continuity.
7. Use **Targets shortcut** to maintain target records for the selected scope.

## 8. Known implementation nuances (as coded)
1. Not every widget obeys the same date model:
- some are strictly current month/week,
- some use chart from/to range,
- project finance uses view mode + reference date logic.

2. Demo filters use two patterns in different modules:
- `%DEMO%` and `SPD-DEMO-%`.

3. Number Card methods are user-context methods from `PersonalSalesDashboard`; custom scoped widgets use `resolve_personal_scope`.

4. Lead source chart groups by `Lead.source` and maps blanks to `Unknown`.

## 9. Code index
Primary files:
- `.../workspace/personal_sales_dashboard/personal_sales_dashboard.json`
- `.../api/personal_dashboard_api.py`
- `.../dashboards/personal_dashboard.py`
- `.../custom_html_block/personal_dashboard_filters/personal_dashboard_filters.json`
- `.../custom_html_block/personal_top_customers_table/personal_top_customers_table.json`
- `.../custom_html_block/personal_item_sales_monthly_table/personal_item_sales_monthly_table.json`
- `.../custom_html_block/personal_sales_funnel/personal_sales_funnel.json`
- `.../custom_html_block/personal_sales_order_analysis_block/personal_sales_order_analysis_block.json`
- `.../custom_html_block/personal_project_pipeline/personal_project_pipeline.json`
- `.../custom_html_block/personal_project_delivery_health/personal_project_delivery_health.json`
- `.../custom_html_block/personal_leads_by_source_block/personal_leads_by_source_block.json`
- `.../custom_html_block/revenue_wave_card/revenue_wave_card.json`
- `.../custom_html_block/my_sales_targets_shortcut/my_sales_targets_shortcut.json`
- `.../dashboard_chart_source/personal_sales_order_trend/personal_sales_order_trend.py`
- `.../dashboard_chart_source/personal_top_customers/personal_top_customers.py`
- `.../dashboard_chart_source/personal_sales_order_analysis/personal_sales_order_analysis.py`
- `.../dashboard_chart_source/personal_item_sales_monthly/personal_item_sales_monthly.py`
- `.../dashboard_chart_source/personal_leads_by_source/personal_leads_by_source.py`
- `.../dashboard_chart_source/personal_forecasted_revenue/personal_forecasted_revenue.py`
- `.../dashboard_chart_source/personal_sales_funnel/personal_sales_funnel.py`

