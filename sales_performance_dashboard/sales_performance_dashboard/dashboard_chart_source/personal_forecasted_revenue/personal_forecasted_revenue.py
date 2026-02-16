# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_months, get_first_day, get_last_day, getdate, nowdate
from frappe.utils.dashboard import cache_source

from sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard import (
    PersonalSalesDashboard,
)


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
    dash = PersonalSalesDashboard()
    user = dash.user
    demo = dash.demo_pattern

    today = getdate(nowdate())
    months = []
    for i in range(5, -1, -1):
        start = get_first_day(add_months(today, -i))
        end = get_last_day(start)
        months.append((start, end))

    labels = [start.strftime("%b %Y") for start, _ in months]
    forecasted = []
    actual = []

    for start, end in months:
        forecast_row = frappe.db.sql(
            """
            SELECT COALESCE(SUM(opportunity_amount * probability / 100), 0) as total
            FROM `tabOpportunity`
            WHERE docstatus < 2
              AND owner = %(user)s
              AND IFNULL(transaction_date, DATE(creation)) BETWEEN %(from_date)s AND %(to_date)s
              AND name NOT LIKE %(demo)s
              AND party_name NOT LIKE %(demo)s
            """,
            {"user": user, "from_date": start, "to_date": end, "demo": demo},
            as_dict=True,
        )
        actual_row = frappe.db.sql(
            """
            SELECT COALESCE(SUM(grand_total), 0) as total
            FROM `tabSales Invoice`
            WHERE docstatus = 1
              AND owner = %(user)s
              AND posting_date BETWEEN %(from_date)s AND %(to_date)s
              AND customer NOT LIKE %(demo)s
            """,
            {"user": user, "from_date": start, "to_date": end, "demo": demo},
            as_dict=True,
        )

        forecasted.append(float(forecast_row[0].total) if forecast_row else 0.0)
        actual.append(float(actual_row[0].total) if actual_row else 0.0)

    return {
        "labels": labels,
        "datasets": [
            {"name": _("Forecasted"), "values": forecasted},
            {"name": _("Actual"), "values": actual},
        ],
        "type": "line",
    }
