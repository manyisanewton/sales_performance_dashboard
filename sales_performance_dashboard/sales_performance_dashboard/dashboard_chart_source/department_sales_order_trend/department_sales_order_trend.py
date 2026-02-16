# -*- coding: utf-8 -*-

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import getdate, nowdate
from frappe.utils.dashboard import cache_source

from sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard import (
    PersonalSalesDashboard,
)


def _month_day_bins(ref_date: date):
    year = ref_date.year
    month = ref_date.month
    days_in_month = calendar.monthrange(year, month)[1]
    labels = []
    bins = []
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        labels.append(d.strftime("%d %b"))
        bins.append((d, d))
    return labels, bins


def _sparsify_month_labels(labels):
    total = len(labels)
    if total <= 12:
        return labels

    if total <= 16:
        step = 2
    elif total <= 24:
        step = 3
    else:
        step = 4

    return [label if (idx % step == 0 or idx == total - 1) else "" for idx, label in enumerate(labels)]


def _year_month_bins(ref_date: date):
    labels = []
    bins = []
    for month in range(1, 13):
        start = date(ref_date.year, month, 1)
        end = date(ref_date.year, month, calendar.monthrange(ref_date.year, month)[1])
        labels.append(start.strftime("%b"))
        bins.append((start, end))
    return labels, bins


def _get_department_people(department):
    employees = frappe.get_all(
        "Employee",
        filters={"department": department},
        fields=["name", "user_id"],
    )
    employee_ids = [row.name for row in employees if row.name]
    user_ids = [row.user_id for row in employees if row.user_id]
    return employee_ids, user_ids


def _build_sales_order_condition(employee_ids, user_ids):
    clauses = []
    params = {}

    if employee_ids:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM `tabSales Team` st
                INNER JOIN `tabSales Person` sp ON sp.name = st.sales_person
                WHERE st.parenttype = 'Sales Order'
                  AND st.parent = so.name
                  AND sp.employee IN %(employee_ids)s
            )
            """
        )
        params["employee_ids"] = tuple(employee_ids)

    if user_ids:
        clauses.append("so.owner IN %(user_ids)s")
        params["user_ids"] = tuple(user_ids)

    if not clauses:
        return "1 = 0", params

    return "(" + " OR ".join(clauses) + ")", params


def _compute_data(filters):
    department = filters.get("department")
    view_mode = (filters.get("view_mode") or "Monthly").strip()
    reference_date = getdate(filters.get("reference_date") or nowdate())

    if not department:
        return {
            "labels": [],
            "datasets": [
                {"name": _("Sales Amount"), "values": []},
                {"name": _("Sales Orders"), "values": []},
            ],
            "type": "line",
        }

    if view_mode == "Yearly":
        labels, bins = _year_month_bins(reference_date)
    else:
        labels, bins = _month_day_bins(reference_date)
        labels = _sparsify_month_labels(labels)

    employee_ids, user_ids = _get_department_people(department)
    person_condition, dynamic_params = _build_sales_order_condition(employee_ids, user_ids)

    dash = PersonalSalesDashboard()
    demo = dash.demo_pattern

    amounts = []
    counts = []

    for start, end in bins:
        params = {
            "from_date": start,
            "to_date": end,
            "demo": demo,
        }
        params.update(dynamic_params)

        row = frappe.db.sql(
            f"""
            SELECT
                COALESCE(SUM(so.grand_total), 0) AS amount,
                COUNT(DISTINCT so.name) AS order_count
            FROM `tabSales Order` so
            WHERE so.docstatus = 1
              AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s
              AND so.customer NOT LIKE %(demo)s
              AND {person_condition}
            """,
            params,
            as_dict=True,
        )[0]

        amounts.append(float(row.amount or 0))
        counts.append(int(row.order_count or 0))

    return {
        "labels": labels,
        "datasets": [
            {"name": _("Sales Amount"), "values": amounts},
            {"name": _("Sales Orders"), "values": counts},
        ],
        "type": "line",
    }


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
    filters = frappe.parse_json(filters) or {}
    return _compute_data(filters)


@frappe.whitelist()
def get_data_for_custom(department=None, view_mode="Monthly", reference_date=None):
    filters = {
        "department": department,
        "view_mode": view_mode or "Monthly",
        "reference_date": reference_date or nowdate(),
    }
    return _compute_data(filters)
