# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, getdate, nowdate
from frappe.utils.dashboard import cache_source

from sales_performance_dashboard.api.personal_dashboard_api import resolve_personal_scope
from sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard import (
    PersonalSalesDashboard,
)

def _get_scope(filters=None, department=None, employee=None):
    parsed = frappe.parse_json(filters) if filters else {}
    if not isinstance(parsed, dict):
        parsed = {}
    return resolve_personal_scope(
        department=department or parsed.get("department"),
        employee=employee or parsed.get("employee"),
    )


def _coerce_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_rows(scope, from_date=None, to_date=None, start=0, page_length=None):
    today = getdate(nowdate())
    from_date = getdate(from_date) if from_date else get_first_day(today)
    to_date = getdate(to_date) if to_date else get_last_day(today)

    dash = PersonalSalesDashboard(scope["user"])
    demo = dash.demo_pattern
    params = {"user": scope["user"], "demo": demo, "from_date": from_date, "to_date": to_date}
    query = """
        SELECT sii.item_code as item_code, sii.item_name as item_name, SUM(sii.base_amount) as total
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND si.owner = %(user)s
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY sii.item_code, sii.item_name
        ORDER BY total DESC
    """
    if page_length is not None:
        params["start"] = max(0, _coerce_int(start, 0))
        params["page_length"] = max(1, _coerce_int(page_length, 5))
        query += " LIMIT %(start)s, %(page_length)s"
    return frappe.db.sql(query, params, as_dict=True)


def _get_total_item_count(scope, from_date=None, to_date=None):
    today = getdate(nowdate())
    from_date = getdate(from_date) if from_date else get_first_day(today)
    to_date = getdate(to_date) if to_date else get_last_day(today)

    dash = PersonalSalesDashboard(scope["user"])
    demo = dash.demo_pattern
    row = frappe.db.sql(
        """
        SELECT COUNT(*) AS total_count
        FROM (
            SELECT sii.item_code
            FROM `tabSales Invoice` si
            INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
            WHERE si.docstatus = 1
              AND si.owner = %(user)s
              AND si.customer NOT LIKE %(demo)s
              AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
            GROUP BY sii.item_code, sii.item_name
        ) AS grouped_items
        """,
        {"user": scope["user"], "demo": demo, "from_date": from_date, "to_date": to_date},
        as_dict=True,
    )
    return int((row[0].total_count if row else 0) or 0)


@frappe.whitelist()
@cache_source
def get_data(
    chart_name=None,
    chart=None,
    no_cache=None,
    filters=None,
    from_date=None,
    to_date=None,
    timespan=None,
    time_interval=None,
    heatmap_year=None,
    department=None,
    employee=None,
):
    scope = _get_scope(filters=filters, department=department, employee=employee)
    rows = _get_rows(scope, from_date=from_date, to_date=to_date, start=0, page_length=10)

    labels = [_(row.item_name) for row in rows]
    values = [row.total or 0 for row in rows]

    return {
        "labels": labels,
        "datasets": [{"name": _("Amount"), "values": values}],
        "type": "bar",
    }


@frappe.whitelist()
def get_table_data_for_custom(
    from_date=None,
    to_date=None,
    department=None,
    employee=None,
    start=0,
    page_length=5,
):
    scope = _get_scope(department=department, employee=employee)
    safe_start = max(0, _coerce_int(start, 0))
    safe_page_length = max(1, _coerce_int(page_length, 5))
    rows = _get_rows(
        scope,
        from_date=from_date,
        to_date=to_date,
        start=safe_start,
        page_length=safe_page_length,
    )
    out = []
    for idx, row in enumerate(rows, start=safe_start + 1):
        out.append(
            {
                "rank": idx,
                "item_code": row.item_code,
                "item_name": row.item_name,
                "amount": row.total or 0,
            }
        )
    total_count = _get_total_item_count(scope, from_date=from_date, to_date=to_date)
    return {
        "rows": out,
        "count": len(out),
        "total_count": total_count,
        "has_more": (safe_start + len(out)) < total_count,
    }
