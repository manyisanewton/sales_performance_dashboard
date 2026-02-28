# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import timedelta

import frappe
from frappe.utils import add_months, cint, date_diff, flt, get_first_day, get_last_day, getdate, nowdate

from sales_performance_dashboard.api.access_settings import get_annual_financing_rate
from sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard import (
    PersonalSalesDashboard,
)


def _tracked_departments():
    # Sales departments currently tracked in this project.
    return [
        "Trading Division - NAL",
        "Industrial Division - NAL",
        "Commercial Division - NAL",
        "Institution Division - NAL",
        "Telesales - NAL",
        "Service Sales - NAL",
        "Mombasa Sales - NAL",
        "IT - NAD",
    ]


def _get_department_context(department):
    employees = frappe.get_all(
        "Employee",
        filters={"department": department, "status": ["!=", "Left"]},
        fields=["name", "user_id"],
    )
    employee_ids = [row.name for row in employees if row.name]
    user_ids = [row.user_id for row in employees if row.user_id]
    return employee_ids, user_ids


def _build_sales_invoice_condition(employee_ids, user_ids):
    clauses = []
    params = {}

    if employee_ids:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM `tabSales Team` st
                INNER JOIN `tabSales Person` sp ON sp.name = st.sales_person
                WHERE st.parenttype = 'Sales Invoice'
                  AND st.parent = si.name
                  AND sp.employee IN %(employee_ids)s
            )
            """
        )
        params["employee_ids"] = tuple(employee_ids)

    if user_ids:
        clauses.append("si.owner IN %(user_ids)s")
        params["user_ids"] = tuple(user_ids)

    if not clauses:
        return "1 = 0", params

    return "(" + " OR ".join(clauses) + ")", params


def _sum_value(query, params):
    row = frappe.db.sql(query, params, as_dict=True)
    return flt(row[0].value) if row else 0.0


def _sum_department_collected(
    si_condition,
    si_dynamic,
    demo_pattern,
    from_date,
    to_date,
):
    return _sum_value(
        f"""
        SELECT COALESCE(SUM(per.allocated_amount), 0) AS value
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
        INNER JOIN `tabSales Invoice` si ON si.name = per.reference_name
        WHERE per.reference_doctype = 'Sales Invoice'
          AND pe.docstatus = 1
          AND si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND {si_condition}
        """,
        {
            "demo": demo_pattern,
            "from_date": from_date,
            "to_date": to_date,
            **si_dynamic,
        },
    )


def _month_bins(reference_date, months=12):
    bins = []
    for i in range(months - 1, -1, -1):
        start = get_first_day(add_months(reference_date, -i))
        end = get_last_day(start)
        bins.append((start, end, start.strftime("%b %Y")))
    return bins


def _sum_department_revenue(
    si_condition,
    si_dynamic,
    demo_pattern,
    from_date,
    to_date,
):
    return _sum_value(
        f"""
        SELECT COALESCE(SUM(si.grand_total), 0) AS value
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND {si_condition}
        """,
        {
            "demo": demo_pattern,
            "from_date": from_date,
            "to_date": to_date,
            **si_dynamic,
        },
    )


def _get_department_monthly_target(department, as_of_date):
    department_target = _sum_value(
        """
        SELECT COALESCE(SUM(COALESCE(monthly_target_current, monthly_target, 0)), 0) AS value
        FROM `tabSales Targets`
        WHERE target_level = 'Department'
          AND department = %(department)s
          AND start_date <= %(as_of_date)s
          AND end_date >= %(as_of_date)s
          AND docstatus < 2
        """,
        {"department": department, "as_of_date": as_of_date},
    )
    if department_target > 0:
        return department_target

    return _sum_value(
        """
        SELECT COALESCE(SUM(COALESCE(monthly_target_current, monthly_target, 0)), 0) AS value
        FROM `tabSales Targets`
        WHERE target_level = 'Individual'
          AND department = %(department)s
          AND start_date <= %(as_of_date)s
          AND end_date >= %(as_of_date)s
          AND docstatus < 2
        """,
        {"department": department, "as_of_date": as_of_date},
    )


def _get_department_daily_target(department, as_of_date):
    return _sum_value(
        """
        SELECT COALESCE(SUM(COALESCE(daily_target_current, daily_target, 0)), 0) AS value
        FROM `tabSales Targets`
        WHERE target_level = 'Individual'
          AND department = %(department)s
          AND start_date <= %(as_of_date)s
          AND end_date >= %(as_of_date)s
          AND docstatus < 2
        """,
        {"department": department, "as_of_date": as_of_date},
    )


def _get_department_yearly_target(department, as_of_date):
    department_target = _sum_value(
        """
        SELECT COALESCE(SUM(COALESCE(yearly_target_current, yearly_target, 0)), 0) AS value
        FROM `tabSales Targets`
        WHERE target_level = 'Department'
          AND department = %(department)s
          AND start_date <= %(as_of_date)s
          AND end_date >= %(as_of_date)s
          AND docstatus < 2
        """,
        {"department": department, "as_of_date": as_of_date},
    )
    if department_target > 0:
        return department_target

    return _sum_value(
        """
        SELECT COALESCE(SUM(COALESCE(yearly_target_current, yearly_target, 0)), 0) AS value
        FROM `tabSales Targets`
        WHERE target_level = 'Individual'
          AND department = %(department)s
          AND start_date <= %(as_of_date)s
          AND end_date >= %(as_of_date)s
          AND docstatus < 2
        """,
        {"department": department, "as_of_date": as_of_date},
    )


@frappe.whitelist()
def get_department_sales_target_route(department=None):
    if not department:
        return {
            "has_target": False,
            "department": None,
            "target_name": None,
        }

    target_name = frappe.db.get_value(
        "Sales Targets",
        {
            "target_level": "Department",
            "department": department,
            "docstatus": ["<", 2],
        },
        "name",
        order_by="start_date desc, modified desc",
    )

    return {
        "has_target": bool(target_name),
        "department": department,
        "target_name": target_name,
    }


@frappe.whitelist()
def get_department_weighted_pipeline_coverage(department=None, view_mode="Monthly", reference_date=None):
    if not department:
        return {
            "coverage_pct": 0,
            "weighted_pipeline": 0,
            "next_target": 0,
            "gap": 0,
            "status": "No Target",
            "next_target_label": "Current Target",
        }

    ref = getdate(reference_date or nowdate())
    mode = (view_mode or "Monthly").strip().title()
    demo_pattern = PersonalSalesDashboard().demo_pattern

    employee_ids, user_ids = _get_department_context(department)
    users_tuple = tuple(user_ids) if user_ids else ()

    if users_tuple:
        row = frappe.db.sql(
            """
            SELECT COALESCE(SUM(IFNULL(opportunity_amount, 0) * IFNULL(probability, 0) / 100), 0) AS value
            FROM `tabOpportunity`
            WHERE owner IN %(user_ids)s
              AND status NOT IN ('Converted', 'Lost')
              AND name NOT LIKE %(demo)s
              AND party_name NOT LIKE %(demo)s
              AND creation <= %(reference_date)s
            """,
            {
                "user_ids": users_tuple,
                "demo": demo_pattern,
                "reference_date": ref,
            },
            as_dict=True,
        )
        weighted_pipeline = flt(row[0].value) if row else 0
    else:
        weighted_pipeline = 0

    if mode == "Yearly":
        current_year_date = getdate(f"{ref.year}-01-01")
        next_target = _get_department_yearly_target(department, current_year_date)
        next_target_label = f"Current Year Target ({ref.year})"
    else:
        current_month_date = get_first_day(ref)
        next_target = _get_department_monthly_target(department, current_month_date)
        next_target_label = f"Current Month Target ({current_month_date.strftime('%b %Y')})"

    coverage_pct = round((weighted_pipeline / next_target) * 100, 2) if next_target > 0 else 0
    gap = round(weighted_pipeline - next_target, 2)

    if next_target <= 0:
        status = "No Target"
    elif coverage_pct >= 100:
        status = "Healthy"
    elif coverage_pct >= 70:
        status = "Watch"
    else:
        status = "Weak"

    return {
        "coverage_pct": coverage_pct,
        "weighted_pipeline": round(weighted_pipeline, 2),
        "next_target": round(next_target, 2),
        "gap": gap,
        "status": status,
        "next_target_label": next_target_label,
    }


@frappe.whitelist()
def get_department_target_slippage(
    department=None,
    slippage_mode="Monthly",
    reference_date=None,
    view_mode=None,
):
    if not department:
        return {
            "status": "No Department",
            "expected_label": "Expected",
            "actual_label": "Actual",
            "expected_by_today": 0,
            "actual_by_today": 0,
            "slippage_amount": 0,
            "pace_pct": 0,
            "period_target": 0,
            "chart": {
                "labels": ["Actual", "Gap to Pace"],
                "values": [0, 0],
                "colors": ["#3b82f6", "#f43f5e"],
            },
        }

    ref = getdate(reference_date or nowdate())
    mode = (slippage_mode or view_mode or "Monthly").strip().title()

    if mode == "Daily":
        period_start = ref
        period_end = ref
        period_target = _get_department_daily_target(department, ref)
        expected_by_today = round(period_target, 2)
        expected_label = "Daily Target"
        actual_label = "Collected Today"
        effective_ref = ref
    else:
        period_start = get_first_day(ref)
        period_end = get_last_day(ref)
        period_target = _get_department_monthly_target(department, ref)
        expected_by_today = round(period_target, 2)
        expected_label = "Monthly Target"
        actual_label = "Collected (Month)"
        # Monthly slippage compares full-month collection against monthly target.
        effective_ref = period_end

    employee_ids, user_ids = _get_department_context(department)
    si_condition, si_dynamic = _build_sales_invoice_condition(employee_ids, user_ids)
    demo_pattern = PersonalSalesDashboard().demo_pattern
    actual_by_today = _sum_department_collected(
        si_condition=si_condition,
        si_dynamic=si_dynamic,
        demo_pattern=demo_pattern,
        from_date=period_start,
        to_date=effective_ref,
    )

    slippage_amount = round(actual_by_today - expected_by_today, 2)
    pace_pct = round((actual_by_today / expected_by_today) * 100, 2) if expected_by_today > 0 else 0

    if expected_by_today <= 0:
        status = "No Target"
    elif pace_pct >= 100:
        status = "Ahead"
    elif pace_pct >= 95:
        status = "On Pace"
    else:
        status = "Behind"

    if slippage_amount >= 0:
        chart_labels = ["Expected Pace", "Ahead"]
        chart_values = [round(expected_by_today, 2), round(slippage_amount, 2)]
        chart_colors = ["#93c5fd", "#16a34a"]
    else:
        chart_labels = ["Actual", "Gap to Pace"]
        chart_values = [round(actual_by_today, 2), round(abs(slippage_amount), 2)]
        chart_colors = ["#3b82f6", "#f43f5e"]

    return {
        "status": status,
        "mode": mode,
        "expected_label": expected_label,
        "actual_label": actual_label,
        "expected_by_today": round(expected_by_today, 2),
        "actual_by_today": round(actual_by_today, 2),
        "slippage_amount": slippage_amount,
        "pace_pct": pace_pct,
        "period_target": round(period_target, 2),
        "chart": {
            "labels": chart_labels,
            "values": chart_values,
            "colors": chart_colors,
        },
    }


@frappe.whitelist()
def get_department_options():
    tracked = set(_tracked_departments())
    all_departments = frappe.get_all(
        "Department",
        filters={"is_group": 0},
        pluck="name",
        order_by="name asc",
        limit=200,
    )
    if not all_departments:
        return []

    tracked_existing = [d for d in all_departments if d in tracked]
    others = [d for d in all_departments if d not in tracked]
    return tracked_existing + others


@frappe.whitelist()
def get_department_gross_margin_trend(department=None, reference_date=None, months=12):
    months = cint(months) if months else 12
    months = max(6, min(months, 24))
    ref_date = getdate(reference_date or nowdate())

    if not department:
        return {"labels": [], "datasets": [{"name": "Gross Margin %", "values": []}]}

    employee_ids, user_ids = _get_department_context(department)
    si_condition, si_dynamic = _build_sales_invoice_condition(employee_ids, user_ids)
    if si_condition == "1 = 0":
        labels = [label for _, _, label in _month_bins(ref_date, months)]
        return {"labels": labels, "datasets": [{"name": "Gross Margin %", "values": [0] * len(labels)}]}

    demo = PersonalSalesDashboard().demo_pattern
    labels = []
    values = []

    for start, end, label in _month_bins(ref_date, months):
        row = frappe.db.sql(
            f"""
            SELECT
                COALESCE(SUM(sii.base_net_amount), 0) AS sales,
                COALESCE(SUM(IFNULL(sii.stock_qty, 0) * IFNULL(sii.incoming_rate, 0)), 0) AS cogs
            FROM `tabSales Invoice` si
            INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
            WHERE si.docstatus = 1
              AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
              AND si.customer NOT LIKE %(demo)s
              AND {si_condition}
            """,
            {
                "from_date": start,
                "to_date": end,
                "demo": demo,
                **si_dynamic,
            },
            as_dict=True,
        )

        sales = flt((row[0] or {}).get("sales", 0)) if row else 0
        cogs = flt((row[0] or {}).get("cogs", 0)) if row else 0
        gross_margin_pct = round(((sales - cogs) / sales) * 100, 2) if sales > 0 else 0

        labels.append(label)
        values.append(gross_margin_pct)

    return {
        "labels": labels,
        "datasets": [{"name": "Gross Margin %", "values": values}],
    }


def _get_period_range(view_mode, reference_date):
    ref = getdate(reference_date or nowdate())
    mode = (view_mode or "Monthly").strip()
    if mode == "Yearly":
        start = getdate(f"{ref.year}-01-01")
        end = getdate(f"{ref.year}-12-31")
    else:
        start = get_first_day(ref)
        end = get_last_day(ref)
    return start, end


def _get_department_invoice_leakage_rows(department, from_date, to_date):
    demo_pattern = PersonalSalesDashboard().demo_pattern
    employee_ids, user_ids = _get_department_context(department)
    si_condition, si_dynamic = _build_sales_invoice_condition(employee_ids, user_ids)
    if si_condition == "1 = 0":
        return []

    rows = frappe.db.sql(
        f"""
        SELECT
            si.name AS invoice,
            si.posting_date,
            si.customer,
            si.owner,
            COALESCE(SUM(IFNULL(sii.base_price_list_rate, 0) * IFNULL(sii.qty, 0)), 0) AS list_value,
            COALESCE(SUM(IFNULL(sii.base_net_amount, 0)), 0) AS billed_value
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND {si_condition}
        GROUP BY si.name, si.posting_date, si.customer, si.owner
        ORDER BY si.posting_date ASC
        """,
        {
            "demo": demo_pattern,
            "from_date": from_date,
            "to_date": to_date,
            **si_dynamic,
        },
        as_dict=True,
    )

    out = []
    for row in rows:
        list_value = flt(row.list_value)
        billed_value = flt(row.billed_value)
        leakage = max(0.0, list_value - billed_value)
        leakage_pct = round((leakage / list_value) * 100, 2) if list_value > 0 else 0
        out.append(
            {
                "invoice": row.invoice,
                "posting_date": row.posting_date,
                "customer": row.customer,
                "owner": row.owner,
                "list_value": list_value,
                "billed_value": billed_value,
                "leakage": leakage,
                "leakage_pct": leakage_pct,
            }
        )
    return out


def _get_invoice_rep_shares(invoice_names):
    if not invoice_names:
        return {}

    team_rows = frappe.db.sql(
        """
        SELECT
            st.parent AS invoice,
            COALESCE(NULLIF(e.employee_name, ''), NULLIF(e.name, ''), st.sales_person) AS rep_name,
            IFNULL(st.allocated_percentage, 0) AS allocated_percentage
        FROM `tabSales Team` st
        LEFT JOIN `tabSales Person` sp ON sp.name = st.sales_person
        LEFT JOIN `tabEmployee` e ON e.name = sp.employee
        WHERE st.parenttype = 'Sales Invoice'
          AND st.parent IN %(invoice_names)s
        """,
        {"invoice_names": tuple(invoice_names)},
        as_dict=True,
    )

    by_invoice = defaultdict(list)
    for row in team_rows:
        by_invoice[row.invoice].append(
            {
                "rep_name": row.rep_name or "Unknown",
                "allocated_percentage": flt(row.allocated_percentage),
            }
        )

    rep_shares = {}
    for invoice, reps in by_invoice.items():
        total_alloc = sum(max(flt(r["allocated_percentage"]), 0) for r in reps)
        if total_alloc > 0:
            rep_shares[invoice] = [
                (r["rep_name"], max(flt(r["allocated_percentage"]), 0) / total_alloc) for r in reps
            ]
        else:
            split = 1 / len(reps) if reps else 1
            rep_shares[invoice] = [(r["rep_name"], split) for r in reps]
    return rep_shares


def _get_department_item_group_leakage(department, from_date, to_date, limit=8):
    limit = max(3, min(cint(limit) if limit else 8, 20))
    demo_pattern = PersonalSalesDashboard().demo_pattern
    employee_ids, user_ids = _get_department_context(department)
    si_condition, si_dynamic = _build_sales_invoice_condition(employee_ids, user_ids)
    if si_condition == "1 = 0":
        return []

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(NULLIF(sii.item_group, ''), 'Uncategorized') AS item_group,
            COALESCE(SUM(IFNULL(sii.base_price_list_rate, 0) * IFNULL(sii.qty, 0)), 0) AS list_value,
            COALESCE(SUM(IFNULL(sii.base_net_amount, 0)), 0) AS billed_value
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND {si_condition}
        GROUP BY COALESCE(NULLIF(sii.item_group, ''), 'Uncategorized')
        ORDER BY (
            COALESCE(SUM(IFNULL(sii.base_price_list_rate, 0) * IFNULL(sii.qty, 0)), 0)
            - COALESCE(SUM(IFNULL(sii.base_net_amount, 0)), 0)
        ) DESC
        LIMIT {limit}
        """,
        {
            "demo": demo_pattern,
            "from_date": from_date,
            "to_date": to_date,
            **si_dynamic,
        },
        as_dict=True,
    )

    out = []
    for row in rows:
        list_value = flt(row.list_value)
        billed_value = flt(row.billed_value)
        leakage = max(0.0, list_value - billed_value)
        out.append(
            {
                "name": row.item_group or "Uncategorized",
                "leakage": round(leakage, 2),
                "leakage_pct": round((leakage / list_value) * 100, 2) if list_value > 0 else 0,
                "list_value": round(list_value, 2),
                "billed_value": round(billed_value, 2),
            }
        )
    return out


@frappe.whitelist()
def get_department_discount_leakage_dashboard(
    department=None,
    view_mode="Monthly",
    reference_date=None,
    limit=10,
    table_limit=30,
):
    limit = max(3, min(cint(limit) if limit else 10, 25))
    table_limit = max(10, min(cint(table_limit) if table_limit else 30, 100))
    if not department:
        return {
            "kpis": {
                "leakage_amount": 0,
                "leakage_pct": 0,
                "net_realization_pct": 0,
                "avg_discount_pct": 0,
            },
            "top_reps": [],
            "top_customers": [],
            "item_groups": [],
            "trend": {"labels": [], "amount": [], "pct": []},
            "waterfall": {"labels": ["List Price", "Discount Leakage", "Actual Billed"], "values": [0, 0, 0]},
            "table": [],
            "total_leakage": 0,
        }

    from_date, to_date = _get_period_range(view_mode, reference_date)
    rows = _get_department_invoice_leakage_rows(department, from_date, to_date)
    if not rows:
        return {
            "kpis": {
                "leakage_amount": 0,
                "leakage_pct": 0,
                "net_realization_pct": 0,
                "avg_discount_pct": 0,
            },
            "top_reps": [],
            "top_customers": [],
            "item_groups": [],
            "trend": {"labels": [], "amount": [], "pct": []},
            "waterfall": {"labels": ["List Price", "Discount Leakage", "Actual Billed"], "values": [0, 0, 0]},
            "table": [],
            "total_leakage": 0,
        }

    invoice_names = [r["invoice"] for r in rows]
    rep_shares = _get_invoice_rep_shares(invoice_names)

    total_list = sum(r["list_value"] for r in rows)
    total_billed = sum(r["billed_value"] for r in rows)
    total_leakage = sum(r["leakage"] for r in rows)
    leakage_pct = round((total_leakage / total_list) * 100, 2) if total_list > 0 else 0
    net_realization_pct = round((total_billed / total_list) * 100, 2) if total_list > 0 else 0
    avg_discount_pct = round(
        (sum(r["leakage_pct"] for r in rows) / len(rows)) if rows else 0,
        2,
    )

    reps = defaultdict(lambda: {"list": 0.0, "billed": 0.0, "leakage": 0.0})
    customers = defaultdict(lambda: {"list": 0.0, "billed": 0.0, "leakage": 0.0})
    month_agg = defaultdict(lambda: {"list": 0.0, "leakage": 0.0})

    owner_names = {}

    for r in rows:
        cust = r["customer"] or "Unknown"
        customers[cust]["list"] += r["list_value"]
        customers[cust]["billed"] += r["billed_value"]
        customers[cust]["leakage"] += r["leakage"]

        month_key = getdate(r["posting_date"]).strftime("%b %Y")
        month_agg[month_key]["list"] += r["list_value"]
        month_agg[month_key]["leakage"] += r["leakage"]

        shares = rep_shares.get(r["invoice"], [])
        if not shares:
            owner = r["owner"] or "Unknown"
            if owner not in owner_names:
                owner_names[owner] = frappe.utils.get_fullname(owner) or owner
            shares = [(owner_names[owner], 1.0)]

        for rep_name, share in shares:
            reps[rep_name]["list"] += r["list_value"] * share
            reps[rep_name]["billed"] += r["billed_value"] * share
            reps[rep_name]["leakage"] += r["leakage"] * share

    def _to_ranked(data_map):
        out = []
        for key, agg in data_map.items():
            l = flt(agg["list"])
            leakage = flt(agg["leakage"])
            out.append(
                {
                    "name": key,
                    "leakage": leakage,
                    "leakage_pct": round((leakage / l) * 100, 2) if l > 0 else 0,
                    "list_value": l,
                    "billed_value": flt(agg["billed"]),
                }
            )
        out.sort(key=lambda d: d["leakage"], reverse=True)
        return out

    top_reps = _to_ranked(reps)[:limit]
    top_customers = _to_ranked(customers)[:limit]
    item_groups = _get_department_item_group_leakage(
        department=department,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )

    # Stable month order for trend (existing months only in selected period).
    month_labels = sorted(month_agg.keys(), key=lambda m: getdate("01 " + m))
    trend_amount = [round(flt(month_agg[m]["leakage"]), 2) for m in month_labels]
    trend_pct = [
        round((flt(month_agg[m]["leakage"]) / flt(month_agg[m]["list"])) * 100, 2)
        if flt(month_agg[m]["list"]) > 0
        else 0
        for m in month_labels
    ]

    rows_sorted = sorted(rows, key=lambda d: d["leakage"], reverse=True)[:table_limit]
    table = []
    for idx, r in enumerate(rows_sorted, start=1):
        shares = rep_shares.get(r["invoice"], [])
        if not shares:
            owner = r["owner"] or "Unknown"
            rep_names = frappe.utils.get_fullname(owner) or owner
        else:
            rep_names = ", ".join([name for name, _ in shares])

        table.append(
            {
                "idx": idx,
                "date": str(r["posting_date"]),
                "invoice": r["invoice"],
                "customer": r["customer"] or "Unknown",
                "rep": rep_names,
                "list_value": round(r["list_value"], 2),
                "billed_value": round(r["billed_value"], 2),
                "leakage": round(r["leakage"], 2),
                "leakage_pct": round(r["leakage_pct"], 2),
            }
        )

    return {
        "kpis": {
            "leakage_amount": round(total_leakage, 2),
            "leakage_pct": leakage_pct,
            "net_realization_pct": net_realization_pct,
            "avg_discount_pct": avg_discount_pct,
        },
        "top_reps": top_reps,
        "top_customers": top_customers,
        "item_groups": item_groups,
        "trend": {"labels": month_labels, "amount": trend_amount, "pct": trend_pct},
        "waterfall": {
            "labels": ["List Price", "Discount Leakage", "Actual Billed"],
            "values": [round(total_list, 2), round(-total_leakage, 2), round(total_billed, 2)],
        },
        "table": table,
        "total_leakage": round(total_leakage, 2),
    }


@frappe.whitelist()
def get_department_kpis(department=None, risk_window_days=14, reference_date=None):
    risk_window_days = cint(risk_window_days) if risk_window_days else 14
    if risk_window_days not in (7, 14):
        risk_window_days = 14
    if not department:
        return {
            "department": None,
            "revenue": 0,
            "collected": 0,
            "outstanding": 0,
            "monthly_target": 0,
            "revenue_at_risk": 0,
            "target_pct": 0,
            "total_invoices": 0,
            "opportunities_value": 0,
            "total_opportunities": 0,
            "ongoing_deals": 0,
            "won_deals": 0,
            "lost_deals": 0,
            "avg_deal_value": 0,
            "avg_won_deal_value": 0,
            "avg_time_to_close_deal": 0,
            "avg_time_lead_to_deal": 0,
            "new_customers_week": 0,
            "customers_served_week": 0,
            "new_customers_month": 0,
            "customers_served_month": 0,
            "collection_efficiency_month": 0,
            "collection_efficiency_3m": 0,
            "cash_conversion_flag": "Weak",
        }

    today = getdate(reference_date or nowdate())
    month_start = get_first_day(today)
    month_end = get_last_day(today)
    rolling_3m_start = get_first_day(add_months(today, -2))
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    demo_pattern = PersonalSalesDashboard().demo_pattern

    employee_ids, user_ids = _get_department_context(department)
    si_condition, si_dynamic = _build_sales_invoice_condition(employee_ids, user_ids)

    base_params = {"demo": demo_pattern}
    base_params.update(si_dynamic)

    revenue = _sum_value(
        f"""
        SELECT COALESCE(SUM(si.grand_total), 0) AS value
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND {si_condition}
        """,
        {**base_params, "from_date": month_start, "to_date": month_end},
    )

    outstanding = _sum_value(
        f"""
        SELECT COALESCE(SUM(si.outstanding_amount), 0) AS value
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.outstanding_amount > 0
          AND si.customer NOT LIKE %(demo)s
          AND {si_condition}
        """,
        base_params,
    )

    revenue_at_risk = _sum_value(
        f"""
        SELECT COALESCE(SUM(si.outstanding_amount), 0) AS value
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.outstanding_amount > 0
          AND si.customer NOT LIKE %(demo)s
          AND (
                si.due_date < %(today)s
                OR si.due_date BETWEEN %(today)s AND DATE_ADD(%(today)s, INTERVAL %(risk_window_days)s DAY)
          )
          AND {si_condition}
        """,
        {
            **base_params,
            "today": today,
            "risk_window_days": risk_window_days,
        },
    )

    collected = _sum_department_collected(
        si_condition=si_condition,
        si_dynamic=si_dynamic,
        demo_pattern=demo_pattern,
        from_date=month_start,
        to_date=month_end,
    )

    rolling_3m_invoiced = _sum_value(
        f"""
        SELECT COALESCE(SUM(si.grand_total), 0) AS value
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND {si_condition}
        """,
        {**base_params, "from_date": rolling_3m_start, "to_date": month_end},
    )
    rolling_3m_collected = _sum_department_collected(
        si_condition=si_condition,
        si_dynamic=si_dynamic,
        demo_pattern=demo_pattern,
        from_date=rolling_3m_start,
        to_date=month_end,
    )
    collection_efficiency_month = round((collected / revenue) * 100, 2) if revenue > 0 else 0
    collection_efficiency_3m = (
        round((rolling_3m_collected / rolling_3m_invoiced) * 100, 2) if rolling_3m_invoiced > 0 else 0
    )
    if collection_efficiency_month < 70 or collection_efficiency_3m < 75:
        cash_conversion_flag = "Weak"
    elif collection_efficiency_month < 85 or collection_efficiency_3m < 90:
        cash_conversion_flag = "Watch"
    else:
        cash_conversion_flag = "Healthy"

    invoice_rows = frappe.db.sql(
        f"""
        SELECT COUNT(DISTINCT si.name) AS value
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND {si_condition}
        """,
        {**base_params, "from_date": month_start, "to_date": month_end},
        as_dict=True,
    )
    total_invoices = int(invoice_rows[0].value) if invoice_rows else 0

    served_week_rows = frappe.db.sql(
        f"""
        SELECT COUNT(DISTINCT si.customer) AS value
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND {si_condition}
        """,
        {**base_params, "from_date": week_start, "to_date": week_end},
        as_dict=True,
    )
    customers_served_week = int(served_week_rows[0].value) if served_week_rows else 0

    served_month_rows = frappe.db.sql(
        f"""
        SELECT COUNT(DISTINCT si.customer) AS value
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND {si_condition}
        """,
        {**base_params, "from_date": month_start, "to_date": month_end},
        as_dict=True,
    )
    customers_served_month = int(served_month_rows[0].value) if served_month_rows else 0

    monthly_target = _get_department_monthly_target(department, today)

    target_pct = round((revenue / monthly_target) * 100, 3) if monthly_target > 0 else 0

    if user_ids:
        users_tuple = tuple(user_ids)
        opp_rows = frappe.db.sql(
            """
            SELECT COALESCE(SUM(opportunity_amount), 0) AS value
            FROM `tabOpportunity`
            WHERE owner IN %(user_ids)s
              AND name NOT LIKE %(demo)s
              AND party_name NOT LIKE %(demo)s
              AND creation BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                "user_ids": users_tuple,
                "demo": demo_pattern,
                "from_date": month_start,
                "to_date": month_end,
            },
            as_dict=True,
        )
        opportunities_value = flt(opp_rows[0].value) if opp_rows else 0

        total_opportunities = frappe.db.count(
            "Opportunity",
            {
                "owner": ["in", users_tuple],
                "name": ["not like", demo_pattern],
                "party_name": ["not like", demo_pattern],
                "creation": ["between", [month_start, month_end]],
            },
        )
        ongoing_deals = frappe.db.count(
            "Opportunity",
            {
                "owner": ["in", users_tuple],
                "status": ["not in", ["Converted", "Lost"]],
                "name": ["not like", demo_pattern],
                "party_name": ["not like", demo_pattern],
                "creation": ["between", [month_start, month_end]],
            },
        )
        won_deals = frappe.db.count(
            "Opportunity",
            {
                "owner": ["in", users_tuple],
                "status": "Converted",
                "name": ["not like", demo_pattern],
                "party_name": ["not like", demo_pattern],
                "modified": ["between", [month_start, month_end]],
            },
        )
        lost_deals = frappe.db.count(
            "Opportunity",
            {
                "owner": ["in", users_tuple],
                "status": "Lost",
                "name": ["not like", demo_pattern],
                "party_name": ["not like", demo_pattern],
                "modified": ["between", [month_start, month_end]],
            },
        )

        avg_deal_rows = frappe.db.sql(
            """
            SELECT COALESCE(AVG(opportunity_amount), 0) AS value
            FROM `tabOpportunity`
            WHERE owner IN %(user_ids)s
              AND name NOT LIKE %(demo)s
              AND party_name NOT LIKE %(demo)s
              AND creation BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                "user_ids": users_tuple,
                "demo": demo_pattern,
                "from_date": month_start,
                "to_date": month_end,
            },
            as_dict=True,
        )
        avg_deal_value = flt(avg_deal_rows[0].value) if avg_deal_rows else 0

        avg_won_rows = frappe.db.sql(
            """
            SELECT COALESCE(AVG(opportunity_amount), 0) AS value
            FROM `tabOpportunity`
            WHERE owner IN %(user_ids)s
              AND status = 'Converted'
              AND name NOT LIKE %(demo)s
              AND party_name NOT LIKE %(demo)s
              AND modified BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                "user_ids": users_tuple,
                "demo": demo_pattern,
                "from_date": month_start,
                "to_date": month_end,
            },
            as_dict=True,
        )
        avg_won_deal_value = flt(avg_won_rows[0].value) if avg_won_rows else 0

        close_days_rows = frappe.db.sql(
            """
            SELECT DATEDIFF(modified, creation) AS days
            FROM `tabOpportunity`
            WHERE owner IN %(user_ids)s
              AND status = 'Converted'
              AND name NOT LIKE %(demo)s
              AND party_name NOT LIKE %(demo)s
              AND modified BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                "user_ids": users_tuple,
                "demo": demo_pattern,
                "from_date": month_start,
                "to_date": month_end,
            },
            as_dict=True,
        )
        if close_days_rows:
            avg_time_to_close_deal = round(
                sum((row.days or 0) for row in close_days_rows) / max(len(close_days_rows), 1)
            )
        else:
            avg_time_to_close_deal = 0

        lead_days_rows = frappe.db.sql(
            """
            SELECT DATEDIFF(o.modified, l.creation) AS days
            FROM `tabOpportunity` o
            INNER JOIN `tabLead` l ON l.name = o.party_name
            WHERE o.owner IN %(user_ids)s
              AND o.opportunity_from = 'Lead'
              AND o.status = 'Converted'
              AND o.name NOT LIKE %(demo)s
              AND o.party_name NOT LIKE %(demo)s
              AND l.name NOT LIKE %(demo)s
              AND o.modified BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                "user_ids": users_tuple,
                "demo": demo_pattern,
                "from_date": month_start,
                "to_date": month_end,
            },
            as_dict=True,
        )
        if lead_days_rows:
            avg_time_lead_to_deal = round(
                sum((row.days or 0) for row in lead_days_rows) / max(len(lead_days_rows), 1)
            )
        else:
            avg_time_lead_to_deal = 0

        new_cust_week = frappe.db.count(
            "Customer",
            {
                "owner": ["in", users_tuple],
                "name": ["not like", demo_pattern],
                "customer_name": ["not like", demo_pattern],
                "creation": ["between", [week_start, week_end]],
            },
        )
        new_cust_month = frappe.db.count(
            "Customer",
            {
                "owner": ["in", users_tuple],
                "name": ["not like", demo_pattern],
                "customer_name": ["not like", demo_pattern],
                "creation": ["between", [month_start, month_end]],
            },
        )
    else:
        opportunities_value = 0
        total_opportunities = 0
        ongoing_deals = 0
        won_deals = 0
        lost_deals = 0
        avg_deal_value = 0
        avg_won_deal_value = 0
        avg_time_to_close_deal = 0
        avg_time_lead_to_deal = 0
        new_cust_week = 0
        new_cust_month = 0

    return {
        "department": department,
        "revenue": revenue,
        "collected": collected,
        "outstanding": outstanding,
        "monthly_target": monthly_target,
        "revenue_at_risk": revenue_at_risk,
        "target_pct": target_pct,
        "total_invoices": total_invoices,
        "opportunities_value": opportunities_value,
        "total_opportunities": int(total_opportunities),
        "ongoing_deals": int(ongoing_deals),
        "won_deals": int(won_deals),
        "lost_deals": int(lost_deals),
        "avg_deal_value": avg_deal_value,
        "avg_won_deal_value": avg_won_deal_value,
        "avg_time_to_close_deal": int(avg_time_to_close_deal),
        "avg_time_lead_to_deal": int(avg_time_lead_to_deal),
        "new_customers_week": int(new_cust_week),
        "customers_served_week": customers_served_week,
        "new_customers_month": int(new_cust_month),
        "customers_served_month": customers_served_month,
        "collection_efficiency_month": collection_efficiency_month,
        "collection_efficiency_3m": collection_efficiency_3m,
        "cash_conversion_flag": cash_conversion_flag,
    }


@frappe.whitelist()
def get_department_payment_delay_cost(
    department=None,
    reference_date=None,
    annual_financing_rate=None,
    top_limit=6,
):
    top_limit = max(3, min(cint(top_limit) if top_limit else 6, 12))
    configured_rate = get_annual_financing_rate()
    annual_financing_rate = flt(
        annual_financing_rate if annual_financing_rate not in (None, "") else configured_rate
    )
    if annual_financing_rate < 0:
        annual_financing_rate = 0
    as_of = getdate(reference_date or nowdate())

    if not department:
        return {
            "as_of": str(as_of),
            "annual_financing_rate": annual_financing_rate,
            "overdue_outstanding": 0,
            "estimated_delay_cost": 0,
            "cost_pct_of_overdue": 0,
            "daily_financing_cost": 0,
            "buckets": [],
            "top_customers": [],
        }

    demo_pattern = PersonalSalesDashboard().demo_pattern
    employee_ids, user_ids = _get_department_context(department)
    si_condition, si_dynamic = _build_sales_invoice_condition(employee_ids, user_ids)
    if si_condition == "1 = 0":
        return {
            "as_of": str(as_of),
            "annual_financing_rate": annual_financing_rate,
            "overdue_outstanding": 0,
            "estimated_delay_cost": 0,
            "cost_pct_of_overdue": 0,
            "daily_financing_cost": 0,
            "buckets": [],
            "top_customers": [],
        }

    rows = frappe.db.sql(
        f"""
        SELECT
            si.name AS invoice,
            si.customer,
            si.outstanding_amount,
            si.due_date,
            DATEDIFF(%(as_of)s, si.due_date) AS days_overdue
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.outstanding_amount > 0
          AND si.due_date < %(as_of)s
          AND {si_condition}
        """,
        {"as_of": as_of, "demo": demo_pattern, **si_dynamic},
        as_dict=True,
    )

    if not rows:
        return {
            "as_of": str(as_of),
            "annual_financing_rate": annual_financing_rate,
            "overdue_outstanding": 0,
            "estimated_delay_cost": 0,
            "cost_pct_of_overdue": 0,
            "daily_financing_cost": 0,
            "buckets": [
                {"label": "0-30", "amount": 0, "cost": 0, "count": 0},
                {"label": "31-60", "amount": 0, "cost": 0, "count": 0},
                {"label": "61-90", "amount": 0, "cost": 0, "count": 0},
                {"label": "90+", "amount": 0, "cost": 0, "count": 0},
            ],
            "top_customers": [],
        }

    rate_per_day = annual_financing_rate / 100 / 365
    buckets = {
        "0-30": {"label": "0-30", "amount": 0.0, "cost": 0.0, "count": 0},
        "31-60": {"label": "31-60", "amount": 0.0, "cost": 0.0, "count": 0},
        "61-90": {"label": "61-90", "amount": 0.0, "cost": 0.0, "count": 0},
        "90+": {"label": "90+", "amount": 0.0, "cost": 0.0, "count": 0},
    }
    customer_cost = defaultdict(lambda: {"amount": 0.0, "cost": 0.0, "count": 0})

    overdue_outstanding = 0.0
    estimated_delay_cost = 0.0
    weighted_days = 0.0

    for row in rows:
        amount = flt(row.outstanding_amount)
        days = max(cint(row.days_overdue), 0)
        cost = amount * rate_per_day * days
        overdue_outstanding += amount
        estimated_delay_cost += cost
        weighted_days += (amount * days)

        if days <= 30:
            key = "0-30"
        elif days <= 60:
            key = "31-60"
        elif days <= 90:
            key = "61-90"
        else:
            key = "90+"

        buckets[key]["amount"] += amount
        buckets[key]["cost"] += cost
        buckets[key]["count"] += 1

        customer = row.customer or "Unknown"
        customer_cost[customer]["amount"] += amount
        customer_cost[customer]["cost"] += cost
        customer_cost[customer]["count"] += 1

    avg_overdue_days = (weighted_days / overdue_outstanding) if overdue_outstanding > 0 else 0
    daily_financing_cost = overdue_outstanding * rate_per_day
    cost_pct_of_overdue = (estimated_delay_cost / overdue_outstanding * 100) if overdue_outstanding > 0 else 0

    bucket_rows = [buckets["0-30"], buckets["31-60"], buckets["61-90"], buckets["90+"]]
    for b in bucket_rows:
        b["amount"] = round(b["amount"], 2)
        b["cost"] = round(b["cost"], 2)

    top_customers = []
    for customer, agg in customer_cost.items():
        top_customers.append(
            {
                "customer": customer,
                "amount": round(agg["amount"], 2),
                "cost": round(agg["cost"], 2),
                "count": int(agg["count"]),
                "cost_pct": round((agg["cost"] / estimated_delay_cost * 100), 2) if estimated_delay_cost > 0 else 0,
            }
        )
    top_customers.sort(key=lambda d: d["cost"], reverse=True)
    top_customers = top_customers[:top_limit]

    return {
        "as_of": str(as_of),
        "annual_financing_rate": round(annual_financing_rate, 2),
        "overdue_outstanding": round(overdue_outstanding, 2),
        "estimated_delay_cost": round(estimated_delay_cost, 2),
        "cost_pct_of_overdue": round(cost_pct_of_overdue, 2),
        "daily_financing_cost": round(daily_financing_cost, 2),
        "avg_overdue_days": round(avg_overdue_days, 1),
        "buckets": bucket_rows,
        "top_customers": top_customers,
    }


@frappe.whitelist()
def get_department_top_customers_table(department=None, limit=20):
    limit = cint(limit) if limit else 20
    limit = max(1, min(limit, 100))
    if not department:
        return {"rows": [], "total": 0}

    demo_pattern = PersonalSalesDashboard().demo_pattern
    employee_ids, user_ids = _get_department_context(department)
    si_condition, si_dynamic = _build_sales_invoice_condition(employee_ids, user_ids)
    if si_condition == "1 = 0":
        return {"rows": [], "total": 0}

    rows = frappe.db.sql(
        f"""
        SELECT si.name, si.customer, si.grand_total, si.owner
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND {si_condition}
        """,
        {"demo": demo_pattern, **si_dynamic},
        as_dict=True,
    )
    if not rows:
        return {"rows": [], "total": 0}

    invoice_names = [r.name for r in rows]
    team_rows = frappe.db.sql(
        """
        SELECT
            st.parent AS invoice_name,
            e.name AS employee_id,
            COALESCE(NULLIF(e.employee_name, ''), e.name) AS employee_name
        FROM `tabSales Team` st
        INNER JOIN `tabSales Person` sp ON sp.name = st.sales_person
        LEFT JOIN `tabEmployee` e ON e.name = sp.employee
        WHERE st.parenttype = 'Sales Invoice'
          AND st.parent IN %(invoice_names)s
        """,
        {"invoice_names": tuple(invoice_names)},
        as_dict=True,
    )
    by_invoice = {}
    for t in team_rows:
        by_invoice.setdefault(t.invoice_name, set()).add(t.employee_name or t.employee_id or "")

    owner_fullname = {}
    for r in rows:
        if r.owner and r.owner not in owner_fullname:
            owner_fullname[r.owner] = frappe.utils.get_fullname(r.owner) or r.owner

    aggregate = {}
    for r in rows:
        key = r.customer or "Unknown"
        if key not in aggregate:
            aggregate[key] = {"customer": key, "amount": 0.0, "served_by": set()}
        aggregate[key]["amount"] += flt(r.grand_total)

        team_names = by_invoice.get(r.name, set())
        if team_names:
            aggregate[key]["served_by"].update([n for n in team_names if n])
        elif r.owner:
            aggregate[key]["served_by"].add(owner_fullname.get(r.owner, r.owner))

    ordered = sorted(aggregate.values(), key=lambda d: d["amount"], reverse=True)[:limit]
    total = sum(item["amount"] for item in ordered)

    output_rows = []
    for idx, item in enumerate(ordered, start=1):
        served = ", ".join(sorted(item["served_by"])) if item["served_by"] else "-"
        output_rows.append(
            {
                "rank": idx,
                "customer": item["customer"],
                "served_by": served,
                "amount": item["amount"],
            }
        )

    return {"rows": output_rows, "total": total}


@frappe.whitelist()
def get_department_owner_users(department=None):
    if not department:
        return []
    _, user_ids = _get_department_context(department)
    return user_ids or []


@frappe.whitelist()
def get_department_project_pipeline(department=None):
    """Project status split for selected department owners."""
    statuses = ["Open", "In Progress", "Completed", "Cancelled"]
    counts = {status: 0 for status in statuses}

    if not department:
        return {
            "labels": statuses,
            "values": [0, 0, 0, 0],
            "total": 0,
            "colors": ["#3b82f6", "#f59e0b", "#16a34a", "#ef4444"],
            "scope": {"department": None},
            "owners": [],
        }

    _, user_ids = _get_department_context(department)
    users = tuple([u for u in user_ids if u])
    if users:
        rows = frappe.db.sql(
            """
            SELECT status, COUNT(*) AS total
            FROM `tabProject`
            WHERE status IN %(statuses)s
              AND owner IN %(users)s
            GROUP BY status
            """,
            {"statuses": tuple(statuses), "users": users},
            as_dict=True,
        )
        for row in rows:
            key = row.get("status")
            if key in counts:
                counts[key] = cint(row.get("total"))

    labels = statuses
    values = [counts[s] for s in labels]
    return {
        "labels": labels,
        "values": values,
        "total": sum(values),
        "colors": ["#3b82f6", "#f59e0b", "#16a34a", "#ef4444"],
        "scope": {"department": department},
        "owners": list(users) if users else [],
    }


@frappe.whitelist()
def get_department_project_status_finance(
    department=None,
    view_mode="Monthly",
    reference_date=None,
):
    """Department projects status + finance + aging buckets for compact dashboard cards."""
    from_date, to_date = _get_period_range(view_mode, reference_date)
    as_of = getdate(reference_date or nowdate())
    demo_pattern = PersonalSalesDashboard().demo_pattern

    if not department:
        return {
            "scope": {"department": None},
            "from_date": str(from_date),
            "to_date": str(to_date),
            "as_of": str(as_of),
            "counts": {"total": 0, "ongoing": 0, "completed": 0},
            "money": {"total_revenue": 0.0, "outstanding": 0.0},
            "aging": {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0},
            "invoice_names_period": [],
            "invoice_names_outstanding": [],
            "bucket_invoice_names": {"0-30": [], "31-60": [], "61-90": [], "90+": []},
            "owners": [],
        }

    _, user_ids = _get_department_context(department)
    users = tuple([u for u in user_ids if u])
    if not users:
        return {
            "scope": {"department": department},
            "from_date": str(from_date),
            "to_date": str(to_date),
            "as_of": str(as_of),
            "counts": {"total": 0, "ongoing": 0, "completed": 0},
            "money": {"total_revenue": 0.0, "outstanding": 0.0},
            "aging": {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0},
            "invoice_names_period": [],
            "invoice_names_outstanding": [],
            "bucket_invoice_names": {"0-30": [], "31-60": [], "61-90": [], "90+": []},
            "owners": [],
        }

    project_rows = frappe.db.sql(
        """
        SELECT name, status
        FROM `tabProject`
        WHERE owner IN %(users)s
        """,
        {"users": users},
        as_dict=True,
    )
    project_names = [p.name for p in project_rows]

    total_projects = len(project_names)
    ongoing_statuses = {"Open", "In Progress", "Working"}
    completed_statuses = {"Completed"}
    ongoing = sum(1 for p in project_rows if (p.status or "") in ongoing_statuses)
    completed = sum(1 for p in project_rows if (p.status or "") in completed_statuses)

    if not project_names:
        return {
            "scope": {"department": department},
            "from_date": str(from_date),
            "to_date": str(to_date),
            "as_of": str(as_of),
            "counts": {"total": total_projects, "ongoing": ongoing, "completed": completed},
            "money": {"total_revenue": 0.0, "outstanding": 0.0},
            "aging": {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0},
            "invoice_names_period": [],
            "invoice_names_outstanding": [],
            "bucket_invoice_names": {"0-30": [], "31-60": [], "61-90": [], "90+": []},
            "owners": list(users),
        }

    period_invoice_rows = frappe.db.sql(
        """
        SELECT
            si.name,
            si.grand_total
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND (
            si.project IN %(projects)s
            OR EXISTS (
              SELECT 1
              FROM `tabSales Invoice Item` sii
              WHERE sii.parent = si.name
                AND sii.project IN %(projects)s
            )
          )
        """,
        {
            "demo": demo_pattern,
            "from_date": from_date,
            "to_date": to_date,
            "projects": tuple(project_names),
        },
        as_dict=True,
    )
    total_revenue = round(sum(flt(r.grand_total) for r in period_invoice_rows), 2)
    invoice_names_period = [r.name for r in period_invoice_rows]

    outstanding_rows = frappe.db.sql(
        """
        SELECT
            si.name,
            si.outstanding_amount,
            si.due_date
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.outstanding_amount > 0
          AND (
            si.project IN %(projects)s
            OR EXISTS (
              SELECT 1
              FROM `tabSales Invoice Item` sii
              WHERE sii.parent = si.name
                AND sii.project IN %(projects)s
            )
          )
        """,
        {
            "demo": demo_pattern,
            "projects": tuple(project_names),
        },
        as_dict=True,
    )

    outstanding_total = round(sum(flt(r.outstanding_amount) for r in outstanding_rows), 2)
    invoice_names_outstanding = [r.name for r in outstanding_rows]
    bucket_amounts = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    bucket_invoice_names = {"0-30": [], "31-60": [], "61-90": [], "90+": []}

    for row in outstanding_rows:
        due_date = getdate(row.due_date) if row.due_date else None
        if not due_date:
            continue
        days_overdue = max(date_diff(as_of, due_date), 0)
        if days_overdue <= 0:
            continue
        amount = flt(row.outstanding_amount)
        if days_overdue <= 30:
            key = "0-30"
        elif days_overdue <= 60:
            key = "31-60"
        elif days_overdue <= 90:
            key = "61-90"
        else:
            key = "90+"
        bucket_amounts[key] += amount
        bucket_invoice_names[key].append(row.name)

    bucket_amounts = {k: round(v, 2) for k, v in bucket_amounts.items()}

    return {
        "scope": {"department": department},
        "from_date": str(from_date),
        "to_date": str(to_date),
        "as_of": str(as_of),
        "counts": {"total": total_projects, "ongoing": ongoing, "completed": completed},
        "money": {"total_revenue": total_revenue, "outstanding": outstanding_total},
        "aging": bucket_amounts,
        "invoice_names_period": invoice_names_period,
        "invoice_names_outstanding": invoice_names_outstanding,
        "bucket_invoice_names": bucket_invoice_names,
        "owners": list(users),
    }


def _owner_initials(display_name):
    text = (display_name or "").strip()
    if not text:
        return "--"

    if "@" in text:
        text = text.split("@", 1)[0].replace(".", " ").replace("_", " ")

    parts = [p for p in text.replace("-", " ").split() if p]
    if not parts:
        return (display_name or "--")[:2].upper()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[1][0]}".upper()


@frappe.whitelist()
def get_department_project_delivery_health(department=None, limit=5):
    """Execution view for department projects with owner initials in each row."""
    limit = max(1, min(cint(limit or 5), 100))
    today = getdate(nowdate())

    if not department:
        return {"summary": {"projects": 0, "on_track": 0, "at_risk": 0, "overdue": 0}, "rows": []}

    _, user_ids = _get_department_context(department)
    users = tuple([u for u in user_ids if u])
    if not users:
        return {"summary": {"projects": 0, "on_track": 0, "at_risk": 0, "overdue": 0}, "rows": []}

    projects = frappe.db.sql(
        """
        SELECT
            p.name,
            COALESCE(NULLIF(p.project_name, ''), p.name) AS project_label,
            p.status,
            p.expected_end_date,
            p.owner,
            COALESCE(NULLIF(u.full_name, ''), p.owner) AS owner_name
        FROM `tabProject` p
        LEFT JOIN `tabUser` u ON u.name = p.owner
        WHERE p.owner IN %(users)s
          AND p.status != 'Cancelled'
        ORDER BY p.creation DESC, p.modified DESC
        LIMIT %(limit)s
        """,
        {"users": users, "limit": limit},
        as_dict=True,
    )

    project_names = [row.name for row in projects]
    if not project_names:
        return {"summary": {"projects": 0, "on_track": 0, "at_risk": 0, "overdue": 0}, "rows": []}

    task_stats = {
        row.project: row
        for row in frappe.db.sql(
            """
            SELECT
                t.project,
                COUNT(*) AS total_tasks,
                SUM(CASE WHEN t.status = 'Completed' THEN 1 ELSE 0 END) AS completed_tasks,
                SUM(CASE WHEN t.status NOT IN ('Completed', 'Cancelled') THEN 1 ELSE 0 END) AS open_tasks,
                SUM(
                    CASE
                        WHEN t.exp_end_date IS NOT NULL
                         AND t.exp_end_date < CURDATE()
                         AND t.status NOT IN ('Completed', 'Cancelled')
                        THEN 1 ELSE 0
                    END
                ) AS overdue_tasks,
                AVG(CASE WHEN t.progress IS NULL THEN 0 ELSE t.progress END) AS avg_progress
            FROM `tabTask` t
            WHERE t.project IN %(projects)s
            GROUP BY t.project
            """,
            {"projects": tuple(project_names)},
            as_dict=True,
        )
    }

    rows = []
    summary = {"projects": 0, "on_track": 0, "at_risk": 0, "overdue": 0}

    for project in projects:
        stats = task_stats.get(project.name) or {}
        total_tasks = cint(stats.get("total_tasks"))
        completed_tasks = cint(stats.get("completed_tasks"))
        open_tasks = cint(stats.get("open_tasks"))
        overdue_tasks = cint(stats.get("overdue_tasks"))
        avg_progress = flt(stats.get("avg_progress"))

        if total_tasks > 0:
            completion = avg_progress if avg_progress > 0 else (completed_tasks / total_tasks) * 100.0
        else:
            completion = 100.0 if project.status == "Completed" else 0.0
        completion = max(0.0, min(completion, 100.0))

        health = "On Track"
        end_date = getdate(project.expected_end_date) if project.expected_end_date else None
        if end_date and end_date < today and completion < 100.0 and project.status != "Completed":
            health = "Overdue"
        elif end_date and date_diff(end_date, today) <= 7 and completion < 80.0 and project.status != "Completed":
            health = "At Risk"

        summary["projects"] += 1
        if health == "Overdue":
            summary["overdue"] += 1
        elif health == "At Risk":
            summary["at_risk"] += 1
        else:
            summary["on_track"] += 1

        owner_name = project.owner_name or project.owner or ""
        rows.append(
            {
                "project": project.name,
                "project_label": project.project_label,
                "planned_end_date": project.expected_end_date,
                "completion_pct": round(completion, 1),
                "open_tasks": open_tasks,
                "overdue_tasks": overdue_tasks,
                "health": health,
                "owner_name": owner_name,
                "owner_initials": _owner_initials(owner_name),
            }
        )

    return {"summary": summary, "rows": rows}
