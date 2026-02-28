# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

import frappe
from frappe import _
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
    dash = PersonalSalesDashboard(scope["user"])
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
        {"user": scope["user"], "demo": demo},
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


@frappe.whitelist()
def get_data_for_custom(department=None, employee=None):
    scope = _get_scope(department=department, employee=employee)
    dash = PersonalSalesDashboard(scope["user"])
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
        {"user": scope["user"], "demo": demo},
        as_dict=True,
    )

    total_amount = (rows[0].total_amount or 0) if rows else 0
    billed_amount = (rows[0].billed_amount or 0) if rows else 0
    amount_to_bill = max(total_amount - billed_amount, 0)

    return {
        "labels": [_("Amount to Bill"), _("Billed Amount")],
        "values": [amount_to_bill, billed_amount],
        "colors": ["#9ad0f5", "#28a745"],
    }
