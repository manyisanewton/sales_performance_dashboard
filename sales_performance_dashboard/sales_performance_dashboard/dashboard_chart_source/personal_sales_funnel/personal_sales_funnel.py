# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

import frappe
from frappe import _

from sales_performance_dashboard.api.personal_dashboard_api import resolve_personal_scope
from sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard import (
    PersonalSalesDashboard,
)


def _build_funnel_data(user):
    demo = "%DEMO%"
    # Leads owned by user
    lead_names = frappe.get_all(
        "Lead",
        filters={"owner": user, "name": ["not like", demo], "lead_name": ["not like", demo]},
        pluck="name",
    )

    lead_count = len(lead_names)

    # Opportunities created from leads
    opp_count = 0
    if lead_names:
        opp_count = frappe.db.count(
            "Opportunity",
            {
                "opportunity_from": "Lead",
                "party_name": ["in", lead_names],
                "name": ["not like", demo],
            },
        )

    # Customers that originated from those leads
    customer_names = []
    if lead_names:
        customer_names = frappe.get_all(
            "Customer",
            filters={
                "lead_name": ["in", lead_names],
                "name": ["not like", demo],
                "customer_name": ["not like", demo],
            },
            pluck="name",
        )
    customer_count = len(customer_names)

    # Quotations for those customers (lead-origin), owner-only
    quotation_count = 0
    if customer_names:
        quotation_count = frappe.db.count(
            "Quotation",
            filters=[
                ["docstatus", "=", 1],
                ["party_name", "in", customer_names],
                ["party_name", "not like", demo],
                ["owner", "=", user],
            ],
        )

    # Sales Orders from those customers, owner-only
    so_count = 0
    if customer_names:
        so_count = frappe.db.count(
            "Sales Order",
            filters=[
                ["docstatus", "=", 1],
                ["customer", "in", customer_names],
                ["customer", "not like", demo],
                ["owner", "=", user],
            ],
        )

    # Delivery Notes for those customers, owner-only
    dn_count = 0
    if customer_names:
        dn_count = frappe.db.count(
            "Delivery Note",
            filters=[
                ["docstatus", "=", 1],
                ["customer", "in", customer_names],
                ["customer", "not like", demo],
                ["owner", "=", user],
            ],
        )

    # Sales Invoices from those customers, owner-only
    si_count = 0
    if customer_names:
        si_count = frappe.db.count(
            "Sales Invoice",
            filters=[
                ["docstatus", "=", 1],
                ["customer", "in", customer_names],
                ["customer", "not like", demo],
                ["owner", "=", user],
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
        opp_count,
        quotation_count,
        customer_count,
        so_count,
        dn_count,
        si_count,
    ]

    return {
        "labels": labels,
        "datasets": [{"name": _("Funnel"), "values": values}],
        "type": "bar",
    }


def _get_scope(filters=None, department=None, employee=None):
    parsed = frappe.parse_json(filters) if filters else {}
    if not isinstance(parsed, dict):
        parsed = {}
    return resolve_personal_scope(
        department=department or parsed.get("department"),
        employee=employee or parsed.get("employee"),
    )


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
    department=None,
    employee=None,
):
    scope = _get_scope(filters=filters, department=department, employee=employee)
    return _build_funnel_data(scope["user"])


@frappe.whitelist()
def get_data_for_custom(department=None, employee=None):
    """Endpoint for Custom HTML Block (no chart wrapper)."""
    scope = _get_scope(department=department, employee=employee)
    return _build_funnel_data(scope["user"])
