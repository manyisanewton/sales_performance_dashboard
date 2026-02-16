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
    demo = dash.demo_pattern
    rows = frappe.db.sql(
        """
        SELECT SUM(grand_total) as total_amount,
               SUM(grand_total * (per_billed / 100)) as billed_amount
        FROM `tabSales Order`
        WHERE docstatus = 1
          AND owner = %(user)s
          AND customer NOT LIKE %(demo)s
        """,
        {"user": frappe.session.user, "demo": demo},
        as_dict=True,
    )

    total_amount = (rows[0].total_amount or 0) if rows else 0
    billed_amount = (rows[0].billed_amount or 0) if rows else 0
    amount_to_bill = max(total_amount - billed_amount, 0)

    return {
        "labels": [_("Amount to Bill"), _("Billed Amount")],
        "datasets": [{"name": _("Sales Order Analysis"), "values": [amount_to_bill, billed_amount]}],
        "colors": ["#9ad0f5", "#28a745"],
        "type": "donut",
    }
