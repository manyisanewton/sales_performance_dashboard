# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

import frappe
from frappe import _
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

    rows = frappe.db.sql(
        """
        SELECT COALESCE(source, 'Unknown') as source, COUNT(*) as total
        FROM `tabLead`
        WHERE owner = %(user)s
          AND name NOT LIKE %(demo)s
          AND lead_name NOT LIKE %(demo)s
        GROUP BY source
        ORDER BY total DESC
        """,
        {"user": user, "demo": dash.demo_pattern},
        as_dict=True,
    )

    labels = [_(row.source) for row in rows] or [_("Unknown")]
    values = [row.total for row in rows] or [0]

    return {
        "labels": labels,
        "datasets": [{"name": _("Leads by Source"), "values": values}],
        "type": "donut",
    }
