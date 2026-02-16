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


def _month_bins(from_date, to_date):
    labels = []
    bins = []

    cursor = get_first_day(from_date)
    end = get_last_day(to_date)
    while cursor <= end:
        month_start = get_first_day(cursor)
        month_end = get_last_day(cursor)
        labels.append(month_start.strftime("%b %Y"))
        bins.append((month_start, month_end))
        cursor = add_months(cursor, 1)

    return labels, bins


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
    filters = frappe.parse_json(filters)
    today = getdate(nowdate())

    if not from_date or not to_date:
        # Default to last 12 months ending current month
        to_date = get_last_day(today)
        from_date = get_first_day(add_months(to_date, -11))
    else:
        from_date = getdate(from_date)
        to_date = getdate(to_date)

    labels, bins = _month_bins(from_date, to_date)

    dash = PersonalSalesDashboard()
    demo = dash.demo_pattern
    values = []

    for start, end in bins:
        result = frappe.db.sql(
            """
            SELECT SUM(grand_total) as total
            FROM `tabSales Order`
            WHERE docstatus = 1
              AND owner = %(user)s
              AND customer NOT LIKE %(demo)s
              AND transaction_date BETWEEN %(from_date)s AND %(to_date)s
            """,
            {"user": frappe.session.user, "demo": demo, "from_date": start, "to_date": end},
            as_dict=True,
        )

        total = (result[0].total or 0) if result else 0
        values.append(total)

    return {
        "labels": labels,
        "datasets": [{"name": _("Sales Orders"), "values": values}],
        "type": "line",
    }
