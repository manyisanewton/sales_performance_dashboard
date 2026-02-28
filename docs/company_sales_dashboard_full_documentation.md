# Company Sales Dashboard: Complete Technical Documentation

## 1. Scope of this document
This document explains the **Company Sales Dashboard** end-to-end, including:
- all global filters,
- every visual block in workspace order,
- backend data sources,
- all formulas and derivations,
- how to interpret each graph,
- drill-down/click behavior.

This documentation is based on current code in:
- `sales_performance_dashboard/workspace/company_sales_dashboard/company_sales_dashboard.json`
- `api/company_dashboard_api.py`
- all `custom_html_block/company_*` blocks used by the workspace.

## 2. Dashboard architecture
The Company dashboard is built from 3 layers:
1. **Workspace**: defines section order and block placement.
2. **Frontend custom blocks**: read filter state from localStorage and call whitelisted APIs.
3. **Backend API**: computes metrics using SQL/ORM with scope and time filters.

Main workspace file:
- `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/workspace/company_sales_dashboard/company_sales_dashboard.json`

## 3. Global filter model (critical)

### 3.1 Filter block fields
Filter block:
- `custom_html_block/company_dashboard_filters/company_dashboard_filters.json`

Fields shown:
- Company
- Department (Optional)
- View Mode (`Daily`, `Monthly`, `Quarterly`, `Yearly`)
- Reference Date
- Lead Source (Optional)
- Risk Window (`Next 7/14/30 Days`)

### 3.2 LocalStorage keys and event
Keys:
- `spd_company_dashboard_company`
- `spd_company_dashboard_department`
- `spd_company_dashboard_view_mode`
- `spd_company_dashboard_reference_date`
- `spd_company_dashboard_lead_source`
- `spd_company_dashboard_risk_window`

Filter change behavior:
- every change updates localStorage,
- dispatches custom event `spd-company-changed`,
- every company widget listens to this event and refreshes.

### 3.3 Filter options source
Backend:
- `get_company_filter_options()`

Returns:
- companies list,
- departments list,
- lead sources,
- supported view modes,
- risk windows and default risk.

Lead source resolution:
- uses `Lead Source` doctype if present,
- fallback to distinct `Lead.source` values.

### 3.4 Time range resolver used by APIs
Core helper:
- `_view_range(view_mode, reference_date)`

It returns `(from_date, to_date)` as:
- `Daily`: reference date only
- `Monthly`: first-to-last day of reference month
- `Quarterly`: full quarter of reference date
- `Yearly`: full calendar year of reference date

## 4. Scope resolution model

### 4.1 Department owner scoping
Helper:
- `_owner_users_for_department(department)`

Behavior:
- reads active employees (`status != Left`) in that department,
- extracts `user_id` list,
- many metrics then filter by document `owner IN owner_users`.

### 4.2 Invoice scoping helper
Helper:
- `_invoice_conditions(company, department, from_date, to_date)`

Default invoice filters include:
- submitted invoices (`docstatus = 1`)
- non-demo customers (`customer NOT LIKE 'SPD-DEMO-%'`)

Optional restrictions:
- company filter (`si.company = company`)
- date range (`posting_date between from/to`)
- department owner filter (`si.owner IN users`), otherwise forced `1 = 0` if no users.

### 4.3 Opportunity scoping helper
Helper:
- `_opportunity_filters(company, department, view_mode, reference_date, lead_source)`

Default opportunity filters include:
- `docstatus < 2`
- non-demo names
- `creation between start/end` (from `_view_range`)

Optional restrictions:
- company (if field exists)
- lead source (auto-detected source field)
- owner in department users (or empty scope if none).

## 5. Workspace sections and visuals (exact order)

## 5.1 Header and subtitle
Static text from workspace:
- `Company Sales Dashboard`
- `Company-wide sales performance across all departments with one global filter bar.`

No backend call.

## 5.2 Company Dashboard Filters
Frontend:
- `custom_html_block/company_dashboard_filters/company_dashboard_filters.json`
Backend:
- `get_company_filter_options()`

How to use:
- Company should always be selected.
- Department narrows the scope to owners in that department.
- Lead Source only affects opportunity-driven widgets.
- Risk Window affects at-risk calculations in revenue/waterfall views.

## 5.3 Pipeline Overview
Frontend:
- `custom_html_block/company_pipeline_overview/company_pipeline_overview.json`
Backend:
- `get_company_pipeline_overview(company, department, view_mode, reference_date, lead_source)`

Visuals in this block:
- Pipeline funnel (7-stage)
- Deal status donut (Open/Won/Lost/Other)
- period range label

### Funnel stages and math
Stages:
- Lead -> Opportunity -> Quotation -> Customer -> Sales Order -> Delivery Note -> Sales Invoice

Counts are computed in a staged way:
1. **Lead**: leads in selected period, non-demo, optional owner/lead source filters.
2. **Opportunity**: lead-origin opportunities (`opportunity_from='Lead'`) linked to scoped leads.
3. **Customer**: customers converted from scoped leads (`customer.lead_name in lead_names`).
4. **Quotation**: submitted quotations for scoped customers in period.
5. **Sales Order**: submitted sales orders for scoped customers in period.
6. **Delivery Note**: submitted delivery notes for scoped customers in period.
7. **Sales Invoice**: submitted invoices for scoped customers in period.

### Deal Status donut math
From opportunities in scope:
- buckets status via `_status_bucket`:
  - Open
  - Won
  - Lost
  - Other

How to read:
- Funnel shows throughput drop-off by lifecycle stage.
- Donut shows outcome mix quality of current opportunity pool.

## 5.4 Company Project Status & Finance
Frontend:
- `custom_html_block/company_project_status_finance/company_project_status_finance.json`
Backend:
- `get_company_project_status_finance(company, department, view_mode, reference_date)`

Visuals in this block:
- radial multi-ring for project counts,
- card grid for counts, revenue, outstanding, and aging buckets,
- clickable drilldowns.

### Math and derivation
1. **Project counts**
- base project set: `Project.docstatus < 2`
- optionally filtered by company and department owners
- computes:
  - total
  - ongoing (`Open`, `In Progress`, `Working`)
  - completed (`Completed`)

2. **Project-linked period revenue**
- submitted invoices in selected period where invoice links to scoped projects either:
  - `Sales Invoice.project in projects`, or
  - any `Sales Invoice Item.project in projects`
- `total_revenue = sum(grand_total)`

3. **Project-linked outstanding**
- submitted invoices with `outstanding_amount > 0` linked to scoped projects
- `outstanding = sum(outstanding_amount)`

4. **Aging buckets**
- overdue outstanding split by days overdue:
  - 0-30
  - 31-60
  - 61-90
  - 90+

### Click behavior
- count cards open Project list with scope filters.
- revenue/outstanding/aging cards open Sales Invoice list using exact invoice name lists returned by API.

How to read:
- use this block to connect project execution to billing and receivables pressure.

## 5.5 Company Revenue Waterfall + Target Overlay
Frontend:
- `custom_html_block/company_revenue_waterfall/company_revenue_waterfall.json`
Backend:
- `get_company_revenue_waterfall(company, department, view_mode, reference_date, lead_source, risk_window_days)`

Visuals:
- left: custom SVG waterfall with target line
- right: donut for Collected vs Outstanding (Not at Risk) vs At Risk

### Core backend math
From invoices in scope and selected period:
- `total_revenue = SUM(grand_total)`
- `total_outstanding = SUM(outstanding_amount)`
- `total_collected = max(0, total_revenue - total_outstanding)`

Target source:
- target value from `_company_scope_target(...)` based on scope and view mode.

Risk slice:
- `revenue_at_risk = SUM(outstanding_amount where due_date <= today + risk_window_days)`
- capped to total outstanding.

### Waterfall construction (frontend)
Bars:
1. Target (absolute)
2. + Revenue (incremental)
3. - Outstanding (decremental)
4. Net Position (absolute)

Net Position formula in visualization:
- `Net Position = Target + Collected`
- where `Collected = Revenue - Outstanding`

How to read:
- Dashed target line shows reference threshold.
- Compare Net Position bar against target to see net attainment after cash realization.
- Donut reveals quality of receivables (safe outstanding vs at-risk outstanding).

## 5.6 Company Gross Margin % Trend
Frontend:
- `custom_html_block/company_gross_margin_trend/company_gross_margin_trend.json`
Backend:
- `get_company_gross_margin_trend(company, department, view_mode, reference_date)`

### Math
For each trend bucket from `_trend_buckets`:
- `sales = SUM(Sales Invoice Item.base_net_amount)`
- `cogs = SUM(Sales Invoice Item.stock_qty * incoming_rate)`
- `gross_margin_pct = ((sales - cogs) / sales) * 100` if sales > 0 else 0

Bucket windows by mode:
- Daily: last 30 days
- Monthly: last 12 months
- Quarterly: last 8 quarters
- Yearly: last 5 years

Series behavior:
- single series always returned:
  - department trend if department filter set,
  - otherwise total company trend.

How to read:
- rising margin trend indicates improving profitability quality.
- sharp drops usually imply pricing pressure, COGS shift, or mix change.

## 5.7 Company Payment Delay Cost
Frontend:
- `custom_html_block/company_payment_delay_cost/company_payment_delay_cost.json`
Backend:
- `get_company_payment_delay_cost(company, department, reference_date, annual_financing_rate, top_limit)`

Visuals:
- gauge: delay cost % of overdue outstanding
- KPI text values
- aging bucket bars
- top customers by delay cost

### Math
Base set:
- submitted invoices in scope,
- outstanding > 0,
- due date < reference_date.

Per invoice:
- `days_overdue = max(reference_date - due_date, 0)`
- `rate_per_day = annual_financing_rate / 100 / 365`
- `cost = outstanding_amount * rate_per_day * days_overdue`

Aggregates:
- `overdue_outstanding = sum(outstanding_amount)`
- `estimated_delay_cost = sum(cost)`
- `daily_financing_cost = overdue_outstanding * rate_per_day`
- `cost_pct_of_overdue = estimated_delay_cost / overdue_outstanding * 100`
- `avg_overdue_days = weighted average by outstanding amount`

Buckets:
- same 0-30, 31-60, 61-90, 90+ logic.

Gauge coloring (frontend):
- green < 4%
- amber >= 4%
- red >= 8%

How to read:
- this block quantifies cost of slow collections in money terms, not only age days.

## 5.8 Revenue by Deal Source
Frontend:
- `custom_html_block/company_revenue_by_source/company_revenue_by_source.json`
Backend:
- `get_company_revenue_by_source(company, department, view_mode, reference_date, lead_source, limit)`

### Math
- reads opportunities in scope.
- includes only won statuses (`converted`, `won`, `closed won`).
- groups by source field (`source/opportunity_source/lead_source` auto-detected).
- value per source = `SUM(opportunity_amount)`.
- sorted descending, frontend requests top 10.

How to read:
- compares won revenue concentration by source channel.
- total shown under chart is sum of currently plotted sources.

## 5.9 Weighted Pipeline Coverage
Frontend:
- `custom_html_block/company_weighted_pipeline_coverage/company_weighted_pipeline_coverage.json`
Backend:
- `get_company_weighted_pipeline_coverage(company, department, view_mode, reference_date, lead_source)`

### Math
Weighted pipeline:
- from opportunities in scope,
- excludes terminal statuses (`won/converted/lost/closed won/closed lost`),
- `weighted_pipeline = SUM(opportunity_amount * probability / 100)`.

Target comparator:
- uses `_company_next_target(company, view_mode, reference_date)`
- yearly mode: current year company target
- non-yearly modes: next month company target

Output formulas:
- `coverage_pct = weighted_pipeline / next_target * 100` (if target > 0)
- `gap = weighted_pipeline - next_target`

Status thresholds:
- `No Target` if target <= 0
- `Healthy` >= 100%
- `Watch` >= 70%
- `Weak` < 70%

How to read:
- indicates whether current weighted opportunity pool can cover near-term target.

## 5.10 Deal Conversion Rate
Frontend:
- `custom_html_block/company_deal_conversion_rate/company_deal_conversion_rate.json`
Backend:
- `get_company_deal_conversion_rate(company, department, view_mode, reference_date, lead_source)`

### Math
- `total = count(opportunities in scope)`
- `won = count(status in converted/won/closed won)`
- `conversion_pct = won / total * 100`

Also returns `top_opportunities`:
- top 5 opportunities by amount in scope for context.

Gauge interpretation (frontend thresholds):
- `Healthy` >= 60%
- `Watch` >= 30%
- `Weak` < 30%

How to read:
- combine this with Weighted Pipeline Coverage:
  - high coverage + low conversion means execution risk,
  - low coverage + high conversion means pipeline generation risk.

## 5.11 Target Slippage Indicator
Frontend:
- `custom_html_block/company_target_slippage/company_target_slippage.json`
Backend:
- `get_company_target_slippage(company, department, slippage_mode, reference_date, view_mode)`

UI passes:
- `slippage_mode = selected view_mode`

### Math
1. Determine period from selected mode (`Daily/Monthly/Quarterly/Yearly`).
2. `expected_by_today` from `_company_scope_target(...)`.
3. `actual_by_today` from invoices in period up to `min(reference_date, period_end)` using:
- `SUM(grand_total - outstanding_amount)`.

Then:
- `slippage_amount = actual - expected`
- `pace_pct = actual / expected * 100`

Status:
- `No Target` if expected <= 0
- `Ahead` if pace >= 100
- `On Pace` if 95-99.99
- `Behind` if < 95

Donut composition:
- Ahead case: `Expected Pace + Ahead`
- Behind case: `Actual + Gap to Pace`

How to read:
- this is an execution pace signal against configured target for the selected mode.

## 6. Target selection logic (important)
Target helper:
- `_company_scope_target(company, department, view_mode, reference_date)`

Behavior:
- If department selected:
  - prioritizes department target rows,
  - falls back to summed individual targets in that department.
- If no department:
  - uses company-level targets.

By mode:
- Daily: individual/derived daily target.
- Monthly: monthly target fields.
- Quarterly: quarterly target fields.
- Yearly: yearly target fields.

This same logic drives both:
- Revenue Waterfall target overlay,
- Target Slippage expected pace.

## 7. Backend method mapping summary
Primary APIs used by Company dashboard:
- `get_company_filter_options`
- `get_company_pipeline_overview`
- `get_company_project_status_finance`
- `get_company_revenue_waterfall`
- `get_company_gross_margin_trend`
- `get_company_payment_delay_cost`
- `get_company_revenue_by_source`
- `get_company_weighted_pipeline_coverage`
- `get_company_deal_conversion_rate`
- `get_company_target_slippage`

Core helpers that affect results:
- `_view_range`
- `_invoice_conditions`
- `_opportunity_filters`
- `_owner_users_for_department`
- `_company_scope_target`
- `_company_next_target`
- `_trend_buckets`

## 8. How to read the dashboard as a manager
1. Set global filters first (company mandatory; department/source optional).
2. Use Pipeline Overview to judge top-of-funnel and outcome mix.
3. Check Project Status & Finance for execution-to-cash linkage.
4. Read Revenue Waterfall for target vs revenue vs outstanding vs risk.
5. Use Gross Margin Trend to validate profitability quality over time.
6. Use Payment Delay Cost for receivable financing drag.
7. Use Revenue by Source + Conversion Rate + Weighted Coverage together to validate demand quality, conversion efficiency, and forward capacity.
8. Use Target Slippage as the pace control indicator for the selected period mode.

## 9. Known implementation nuances (as coded)
1. `lead_source` filter affects opportunity-based widgets, not invoice-only widgets.
2. Revenue Waterfall uses selected period for totals but risk cutoff is based on `today + risk_window_days`.
3. Weighted Pipeline Coverage compares to next-period company target in non-yearly modes.
4. Project finance drilldowns use API-returned invoice name lists for precise navigation.
5. Pipeline funnel is stage-based and linked through lead/customer transitions, not only generic counts.

## 10. Code index
- Workspace:
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/workspace/company_sales_dashboard/company_sales_dashboard.json`
- Backend API:
  - `apps/sales_performance_dashboard/sales_performance_dashboard/api/company_dashboard_api.py`
- Custom blocks:
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/company_dashboard_filters/company_dashboard_filters.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/company_pipeline_overview/company_pipeline_overview.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/company_project_status_finance/company_project_status_finance.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/company_revenue_waterfall/company_revenue_waterfall.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/company_gross_margin_trend/company_gross_margin_trend.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/company_payment_delay_cost/company_payment_delay_cost.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/company_revenue_by_source/company_revenue_by_source.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/company_weighted_pipeline_coverage/company_weighted_pipeline_coverage.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/company_deal_conversion_rate/company_deal_conversion_rate.json`
  - `apps/sales_performance_dashboard/sales_performance_dashboard/sales_performance_dashboard/custom_html_block/company_target_slippage/company_target_slippage.json`
