# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

import frappe
from frappe import _

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

    # Payment Entries for those customers
    pe_count = 0
    if customer_names:
        pe_count = frappe.db.count(
            "Payment Entry",
            filters=[
                ["docstatus", "=", 1],
                ["party_type", "=", "Customer"],
                ["party", "in", customer_names],
                ["party", "not like", demo],
                ["owner", "=", user],
            ],
        )

    labels = [
        _("Lead"),
        _("Customer"),
        _("Opportunity"),
        _("Quotation"),
        _("Sales Order"),
        _("Delivery Note"),
        _("Sales Invoice"),
        _("Payment Entry"),
    ]
    values = [
        lead_count,
        customer_count,
        opp_count,
        quotation_count,
        so_count,
        dn_count,
        si_count,
        pe_count,
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
    user = frappe.session.user
    return _build_funnel_data(user)


@frappe.whitelist()
def get_data_for_custom():
    """Endpoint for Custom HTML Block (no chart wrapper)."""
    user = frappe.session.user
    return _build_funnel_data(user)
