# -*- coding: utf-8 -*-

import frappe
from frappe import _
from frappe.utils import add_months, get_first_day, get_last_day, getdate, nowdate
from frappe.utils.dashboard import cache_source

from sales_performance_dashboard.api.department_dashboard_api import (
    _build_sales_invoice_condition,
    _get_department_context,
)
from sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard import (
    PersonalSalesDashboard,
)


def _month_bins(reference_date):
    months = []
    for i in range(5, -1, -1):
        start = get_first_day(add_months(reference_date, -i))
        end = get_last_day(start)
        months.append((start, end))
    return months


def _compute_data(filters):
    department = filters.get("department")
    reference_date = getdate(filters.get("reference_date") or nowdate())

    if not department:
        return {
            "labels": [],
            "datasets": [
                {"name": _("Forecasted"), "values": []},
                {"name": _("Actual"), "values": []},
            ],
            "type": "line",
        }

    employee_ids, user_ids = _get_department_context(department)
    si_condition, si_dynamic = _build_sales_invoice_condition(employee_ids, user_ids)
    if si_condition == "1 = 0":
        return {
            "labels": [get_first_day(add_months(reference_date, -i)).strftime("%b %Y") for i in range(5, -1, -1)],
            "datasets": [
                {"name": _("Forecasted"), "values": [0, 0, 0, 0, 0, 0]},
                {"name": _("Actual"), "values": [0, 0, 0, 0, 0, 0]},
            ],
            "type": "line",
        }

    months = _month_bins(reference_date)
    labels = [start.strftime("%b %Y") for start, _ in months]
    forecasted = []
    actual = []

    demo = PersonalSalesDashboard().demo_pattern
    users_tuple = tuple(user_ids)

    for start, end in months:
        if users_tuple:
            forecast_row = frappe.db.sql(
                """
                SELECT COALESCE(SUM(opportunity_amount * probability / 100), 0) AS total
                FROM `tabOpportunity`
                WHERE docstatus < 2
                  AND owner IN %(users)s
                  AND IFNULL(transaction_date, DATE(creation)) BETWEEN %(from_date)s AND %(to_date)s
                  AND name NOT LIKE %(demo)s
                  AND party_name NOT LIKE %(demo)s
                """,
                {"users": users_tuple, "from_date": start, "to_date": end, "demo": demo},
                as_dict=True,
            )
        else:
            forecast_row = [{"total": 0}]

        actual_row = frappe.db.sql(
            f"""
            SELECT COALESCE(SUM(si.grand_total), 0) AS total
            FROM `tabSales Invoice` si
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

        forecasted.append(float((forecast_row[0] or {}).get("total", 0) or 0) if forecast_row else 0.0)
        actual.append(float((actual_row[0] or {}).get("total", 0) or 0) if actual_row else 0.0)

    return {
        "labels": labels,
        "datasets": [
            {"name": _("Forecasted"), "values": forecasted},
            {"name": _("Actual"), "values": actual},
        ],
        "type": "line",
    }


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
):
    filters = frappe.parse_json(filters) or {}
    return _compute_data(filters)


@frappe.whitelist()
def get_data_for_custom(department=None, reference_date=None):
    filters = {
        "department": department,
        "reference_date": reference_date or nowdate(),
    }
    return _compute_data(filters)
