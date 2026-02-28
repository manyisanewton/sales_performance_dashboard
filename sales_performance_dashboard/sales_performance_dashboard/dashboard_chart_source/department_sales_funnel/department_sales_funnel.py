# -*- coding: utf-8 -*-

import frappe
from frappe import _

from sales_performance_dashboard.api.department_dashboard_api import _get_department_context
from sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard import (
    PersonalSalesDashboard,
)


def _build_funnel_data(department):
    demo = PersonalSalesDashboard().demo_pattern

    if not department:
        return {
            "labels": [_("Lead"), _("Opportunity"), _("Quotation"), _("Customer"), _("Sales Order"), _("Delivery Note"), _("Sales Invoice")],
            "datasets": [{"name": _("Funnel"), "values": [0, 0, 0, 0, 0, 0, 0]}],
            "type": "bar",
        }

    employee_ids, user_ids = _get_department_context(department)
    if not user_ids:
        return {
            "labels": [_("Lead"), _("Opportunity"), _("Quotation"), _("Customer"), _("Sales Order"), _("Delivery Note"), _("Sales Invoice")],
            "datasets": [{"name": _("Funnel"), "values": [0, 0, 0, 0, 0, 0, 0]}],
            "type": "bar",
        }

    users_tuple = tuple(user_ids)

    lead_names = frappe.get_all(
        "Lead",
        filters=[
            ["owner", "in", users_tuple],
            ["name", "not like", demo],
            ["lead_name", "not like", demo],
        ],
        pluck="name",
    )
    lead_count = len(lead_names)

    opp_names = frappe.get_all(
        "Opportunity",
        filters=[
            ["owner", "in", users_tuple],
            ["name", "not like", demo],
            ["party_name", "not like", demo],
        ],
        pluck="name",
    )
    opportunity_count = len(opp_names)

    customer_names = frappe.get_all(
        "Customer",
        filters=[
            ["owner", "in", users_tuple],
            ["name", "not like", demo],
            ["customer_name", "not like", demo],
        ],
        pluck="name",
    )
    customer_count = len(customer_names)

    quotation_count = frappe.db.count(
        "Quotation",
        filters=[
            ["docstatus", "=", 1],
            ["owner", "in", users_tuple],
            ["party_name", "not like", demo],
        ],
    )

    sales_order_count = frappe.db.count(
        "Sales Order",
        filters=[
            ["docstatus", "=", 1],
            ["owner", "in", users_tuple],
            ["customer", "not like", demo],
        ],
    )

    delivery_note_count = frappe.db.count(
        "Delivery Note",
        filters=[
            ["docstatus", "=", 1],
            ["owner", "in", users_tuple],
            ["customer", "not like", demo],
        ],
    )

    sales_invoice_count = frappe.db.count(
        "Sales Invoice",
        filters=[
            ["docstatus", "=", 1],
            ["owner", "in", users_tuple],
            ["customer", "not like", demo],
        ],
    )

    labels = [
        _("Lead"),
        _("Opportunity"),
        _("Quotation"),
        _("Customer"),
        _("Sales Order"),
        _("Delivery Note"),
        _("Sales Invoice"),
    ]
    values = [
        lead_count,
        opportunity_count,
        quotation_count,
        customer_count,
        sales_order_count,
        delivery_note_count,
        sales_invoice_count,
    ]

    return {
        "labels": labels,
        "datasets": [{"name": _("Funnel"), "values": values}],
        "type": "bar",
    }


@frappe.whitelist()
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
    department = filters.get("department")
    return _build_funnel_data(department)


@frappe.whitelist()
def get_data_for_custom(department=None):
    return _build_funnel_data(department)
