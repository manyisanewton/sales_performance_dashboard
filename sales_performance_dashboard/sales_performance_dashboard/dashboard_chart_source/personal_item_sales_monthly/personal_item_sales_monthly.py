# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, getdate, nowdate
from frappe.utils.dashboard import cache_source

from sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard import (
    PersonalSalesDashboard,
)

def _get_rows(from_date=None, to_date=None):
    today = getdate(nowdate())
    from_date = getdate(from_date) if from_date else get_first_day(today)
    to_date = getdate(to_date) if to_date else get_last_day(today)

    dash = PersonalSalesDashboard()
    demo = dash.demo_pattern
    return frappe.db.sql(
        """
        SELECT sii.item_name as item_name, SUM(sii.base_amount) as total
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND si.owner = %(user)s
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY sii.item_name
        ORDER BY total DESC
        LIMIT 20
        """,
        {"user": frappe.session.user, "demo": demo, "from_date": from_date, "to_date": to_date},
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
    rows = _get_rows(from_date=from_date, to_date=to_date)[:10]

    labels = [_(row.item_name) for row in rows]
    values = [row.total or 0 for row in rows]

    return {
        "labels": labels,
        "datasets": [{"name": _("Amount"), "values": values}],
        "type": "bar",
    }


@frappe.whitelist()
def get_table_data_for_custom(from_date=None, to_date=None):
    rows = _get_rows(from_date=from_date, to_date=to_date)
    total = sum((row.total or 0) for row in rows)
    out = []
    for idx, row in enumerate(rows, start=1):
        out.append(
            {
                "rank": idx,
                "item_name": row.item_name,
                "amount": row.total or 0,
            }
        )

    return {"rows": out, "total": total}
