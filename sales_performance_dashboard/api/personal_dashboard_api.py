# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

import frappe

from sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard import (
    PersonalSalesDashboard,
)

@frappe.whitelist()
def get_personal_dashboard_data(user=None):
    """Get all metrics for personal sales dashboard."""
    dashboard = PersonalSalesDashboard(user)
    return dashboard.get_all_metrics()


@frappe.whitelist()
def get_my_sales_target_route():
    """Return route info for current user's Sales Target."""
    user = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if not employee:
        return {
            "has_target": False,
            "employee": None,
            "target_name": None,
        }

    target_name = frappe.db.get_value(
        "Sales Targets",
        {
            "target_level": "Individual",
            "employee": employee,
            "docstatus": 0,
        },
        "name",
        order_by="start_date desc, modified desc",
    )

    return {
        "has_target": bool(target_name),
        "employee": employee,
        "target_name": target_name,
    }

__all__ = ["get_personal_dashboard_data", "get_my_sales_target_route"]
