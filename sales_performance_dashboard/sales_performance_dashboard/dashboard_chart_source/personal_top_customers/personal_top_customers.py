# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils.dashboard import cache_source

from sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard import (
    PersonalSalesDashboard,
)

def _get_rows():
    dash = PersonalSalesDashboard()
    demo = dash.demo_pattern
    return frappe.db.sql(
        """
        SELECT customer, SUM(grand_total) as total
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND owner = %(user)s
          AND customer NOT LIKE %(demo)s
        GROUP BY customer
        ORDER BY total DESC
        LIMIT 20
        """,
        {"user": frappe.session.user, "demo": demo},
        as_dict=True,
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
    rows = _get_rows()[:10]

    labels = [_(row.customer) for row in rows]
    values = [row.total or 0 for row in rows]

    return {
        "labels": labels,
        "datasets": [{"name": _("Amount"), "values": values}],
        "type": "bar",
    }


@frappe.whitelist()
def get_table_data_for_custom():
    rows = _get_rows()
    total = sum((row.total or 0) for row in rows)
    out = []
    for idx, row in enumerate(rows, start=1):
        out.append(
            {
                "rank": idx,
                "customer": row.customer,
                "amount": row.total or 0,
            }
        )
    return {"rows": out, "total": total}
