# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

import frappe
from frappe.utils import add_months, cint, date_diff, flt, get_first_day, get_last_day, getdate, nowdate

from sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard import (
    PersonalSalesDashboard,
)

ELEVATED_ROLES = {"Sales Manager", "System Manager", "Administrator"}
DEMO_PATTERN = "SPD-DEMO-%"


def _is_elevated_user(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    roles = set(frappe.get_roles(user))
    return bool(roles & ELEVATED_ROLES)


def _get_employee_doc(employee):
    if not employee:
        return None
    row = frappe.db.get_value(
        "Employee",
        employee,
        ["name", "user_id", "department", "status"],
        as_dict=True,
    )
    if not row or row.status == "Left":
        return None
    return row


def _get_current_user_employee(user=None):
    user = user or frappe.session.user
    row = frappe.db.get_value(
        "Employee",
        {"user_id": user},
        ["name", "user_id", "department", "status"],
        as_dict=True,
        order_by="modified desc",
    )
    if not row or row.status == "Left":
        return None
    return row


def resolve_personal_scope(department=None, employee=None, user=None):
    """
    Resolve effective scope for personal dashboard.
    Sales Manager/System Manager/Administrator can switch department/employee.
    Sales User is restricted to own employee/user.
    """
    current_user = user or frappe.session.user
    own_emp = _get_current_user_employee(current_user)

    if not _is_elevated_user(current_user):
        return {
            "user": current_user,
            "employee": own_emp.name if own_emp else None,
            "department": own_emp.department if own_emp else None,
            "is_elevated": False,
        }

    resolved_emp = _get_employee_doc(employee) if employee else None

    if resolved_emp and department and resolved_emp.department != department:
        resolved_emp = None

    resolved_department = department or (resolved_emp.department if resolved_emp else (own_emp.department if own_emp else None))

    if not resolved_emp and resolved_department:
        first_emp = frappe.db.get_value(
            "Employee",
            {"department": resolved_department, "status": ["!=", "Left"], "user_id": ["is", "set"]},
            ["name", "user_id", "department", "status"],
            as_dict=True,
            order_by="employee_name asc",
        )
        if first_emp and first_emp.get("user_id"):
            resolved_emp = first_emp

    resolved_user = resolved_emp.user_id if resolved_emp and resolved_emp.user_id else current_user

    return {
        "user": resolved_user,
        "employee": resolved_emp.name if resolved_emp else None,
        "department": resolved_department,
        "is_elevated": True,
    }


def _personal_view_range(view_mode=None, reference_date=None):
    ref = getdate(reference_date or nowdate())
    mode = (view_mode or "Monthly").strip().title()

    if mode == "Daily":
        return ref, ref
    if mode == "Quarterly":
        q = ((ref.month - 1) // 3) + 1
        start_month = (q - 1) * 3 + 1
        start = getdate(f"{ref.year}-{start_month:02d}-01")
        end = get_last_day(add_months(start, 2))
        return start, end
    if mode == "Yearly":
        return getdate(f"{ref.year}-01-01"), getdate(f"{ref.year}-12-31")
    return get_first_day(ref), get_last_day(ref)


@frappe.whitelist()
def get_personal_dashboard_filter_options(department=None):
    scope = resolve_personal_scope(department=department)
    current_user = frappe.session.user
    elevated = _is_elevated_user(current_user)
    own_emp = _get_current_user_employee(current_user)

    if elevated:
        departments = frappe.get_all(
            "Department",
            filters={"is_group": 0},
            pluck="name",
            order_by="name asc",
            limit=500,
        )
    else:
        departments = [own_emp.department] if own_emp and own_emp.department else []

    selected_department = department or (scope.get("department") or (departments[0] if departments else None))

    employees = []
    if selected_department:
        emp_rows = frappe.get_all(
            "Employee",
            filters={
                "department": selected_department,
                "status": ["!=", "Left"],
                "user_id": ["is", "set"],
            },
            fields=["name", "employee_name", "user_id"],
            order_by="employee_name asc",
            limit=500,
        )
        employees = [
            {
                "name": row.name,
                "label": f"{row.name} - {row.employee_name}" if row.employee_name else row.name,
                "user_id": row.user_id,
            }
            for row in emp_rows
        ]

    default_employee = scope.get("employee") or (employees[0]["name"] if employees else None)

    return {
        "departments": departments,
        "employees": employees,
        "default_department": selected_department,
        "default_employee": default_employee,
        "view_modes": ["Daily", "Monthly", "Quarterly", "Yearly"],
        "risk_windows": [7, 14, 30],
        "default_view_mode": "Monthly",
        "default_risk_window": 14,
        "is_elevated_user": elevated,
    }


@frappe.whitelist()
def get_personal_dashboard_data(user=None, department=None, employee=None):
    """Get all metrics for personal sales dashboard."""
    scope = resolve_personal_scope(department=department, employee=employee, user=user)
    dashboard = PersonalSalesDashboard(scope["user"])
    return dashboard.get_all_metrics()


@frappe.whitelist()
def get_personal_revenue_metric(department=None, employee=None):
    scope = resolve_personal_scope(department=department, employee=employee)
    dashboard = PersonalSalesDashboard(scope["user"])
    return {"value": dashboard.get_total_revenue(), "scope": scope}


@frappe.whitelist()
def get_my_sales_target_route(department=None, employee=None):
    """Return route info for selected scope's Sales Target."""
    scope = resolve_personal_scope(department=department, employee=employee)
    employee_name = scope.get("employee")
    if not employee_name:
        return {
            "has_target": False,
            "employee": None,
            "target_name": None,
        }

    target_name = frappe.db.get_value(
        "Sales Targets",
        {
            "target_level": "Individual",
            "employee": employee_name,
            "docstatus": ["<", 2],
        },
        "name",
        order_by="start_date desc, modified desc",
    )

    return {
        "has_target": bool(target_name),
        "employee": employee_name,
        "department": scope.get("department"),
        "target_name": target_name,
    }


@frappe.whitelist()
def get_personal_project_pipeline(department=None, employee=None):
    """Project status split for personal dashboard donut."""
    scope = resolve_personal_scope(department=department, employee=employee)
    user = scope.get("user") or frappe.session.user

    statuses = ["Open", "In Progress", "Completed", "Cancelled"]
    counts = {status: 0 for status in statuses}

    rows = frappe.db.sql(
        """
        SELECT status, COUNT(*) AS total
        FROM `tabProject`
        WHERE status IN %(statuses)s
          AND owner = %(user)s
        GROUP BY status
        """,
        {
            "statuses": tuple(statuses),
            "user": user,
        },
        as_dict=True,
    )

    for row in rows:
        key = row.get("status")
        if key in counts:
            counts[key] = cint(row.get("total"))

    labels = statuses
    values = [counts[s] for s in labels]

    return {
        "labels": labels,
        "values": values,
        "total": sum(values),
        "scope": scope,
        "colors": ["#3b82f6", "#f59e0b", "#16a34a", "#ef4444"],
    }


@frappe.whitelist()
def get_personal_project_delivery_health(department=None, employee=None, limit=5):
    """Execution view for personal projects: health, completion, and task load."""
    scope = resolve_personal_scope(department=department, employee=employee)
    user = scope.get("user") or frappe.session.user
    limit = max(1, min(cint(limit or 5), 100))
    today = getdate(nowdate())

    projects = frappe.db.sql(
        """
        SELECT
            p.name,
            COALESCE(NULLIF(p.project_name, ''), p.name) AS project_label,
            p.status,
            p.expected_start_date,
            p.expected_end_date
        FROM `tabProject` p
        WHERE p.owner = %(user)s
          AND p.status != 'Cancelled'
        ORDER BY
          p.creation DESC,
          p.modified DESC
        LIMIT %(limit)s
        """,
        {"user": user, "limit": limit},
        as_dict=True,
    )

    project_names = [row.name for row in projects]
    if not project_names:
        return {"scope": scope, "summary": {"projects": 0, "on_track": 0, "at_risk": 0, "overdue": 0}, "rows": []}

    task_stats = {
        row.project: row
        for row in frappe.db.sql(
            """
            SELECT
                t.project,
                COUNT(*) AS total_tasks,
                SUM(CASE WHEN t.status = 'Completed' THEN 1 ELSE 0 END) AS completed_tasks,
                SUM(CASE WHEN t.status NOT IN ('Completed', 'Cancelled') THEN 1 ELSE 0 END) AS open_tasks,
                SUM(
                    CASE
                        WHEN t.exp_end_date IS NOT NULL
                         AND t.exp_end_date < CURDATE()
                         AND t.status NOT IN ('Completed', 'Cancelled')
                        THEN 1 ELSE 0
                    END
                ) AS overdue_tasks,
                AVG(CASE WHEN t.progress IS NULL THEN 0 ELSE t.progress END) AS avg_progress
            FROM `tabTask` t
            WHERE t.project IN %(projects)s
            GROUP BY t.project
            """,
            {"projects": tuple(project_names)},
            as_dict=True,
        )
    }

    rows = []
    summary = {"projects": 0, "on_track": 0, "at_risk": 0, "overdue": 0}

    for project in projects:
        stats = task_stats.get(project.name) or {}
        total_tasks = cint(stats.get("total_tasks"))
        completed_tasks = cint(stats.get("completed_tasks"))
        open_tasks = cint(stats.get("open_tasks"))
        overdue_tasks = cint(stats.get("overdue_tasks"))
        avg_progress = flt(stats.get("avg_progress"))

        if total_tasks > 0:
            completion = avg_progress if avg_progress > 0 else (completed_tasks / total_tasks) * 100.0
        else:
            completion = 100.0 if project.status == "Completed" else 0.0
        completion = max(0.0, min(completion, 100.0))

        health = "On Track"
        end_date = getdate(project.expected_end_date) if project.expected_end_date else None
        if end_date and end_date < today and completion < 100.0 and project.status != "Completed":
            health = "Overdue"
        elif end_date and date_diff(end_date, today) <= 7 and completion < 80.0 and project.status != "Completed":
            health = "At Risk"

        summary["projects"] += 1
        if health == "Overdue":
            summary["overdue"] += 1
        elif health == "At Risk":
            summary["at_risk"] += 1
        else:
            summary["on_track"] += 1

        rows.append(
            {
                "project": project.name,
                "project_label": project.project_label,
                "project_status": project.status,
                "planned_end_date": project.expected_end_date,
                "completion_pct": round(completion, 1),
                "open_tasks": open_tasks,
                "overdue_tasks": overdue_tasks,
                "health": health,
            }
        )

    return {"scope": scope, "summary": summary, "rows": rows}


@frappe.whitelist()
def get_personal_project_value_billing(department=None, employee=None, limit=20):
    """Project value vs billing metrics for personal dashboard."""
    scope = resolve_personal_scope(department=department, employee=employee)
    user = scope.get("user") or frappe.session.user
    limit = max(1, min(cint(limit or 20), 100))

    projects = frappe.db.sql(
        """
        SELECT
            p.name,
            COALESCE(NULLIF(p.project_name, ''), p.name) AS project_label
        FROM `tabProject` p
        WHERE p.owner = %(user)s
        ORDER BY p.modified DESC
        LIMIT %(limit)s
        """,
        {"user": user, "limit": limit},
        as_dict=True,
    )

    project_names = [row.name for row in projects]
    if not project_names:
        return {
            "scope": scope,
            "summary": {
                "contract_value": 0.0,
                "billed_to_date": 0.0,
                "unbilled_value": 0.0,
                "percent_billed": 0.0,
            },
            "projects": [],
        }

    contract_map = {
        row.project: float(row.contract_value or 0)
        for row in frappe.db.sql(
            """
            SELECT
                so.project,
                SUM(so.grand_total) AS contract_value
            FROM `tabSales Order` so
            WHERE so.docstatus = 1
              AND so.project IN %(projects)s
            GROUP BY so.project
            """,
            {"projects": tuple(project_names)},
            as_dict=True,
        )
    }

    billed_map = {
        row.project: float(row.billed_to_date or 0)
        for row in frappe.db.sql(
            """
            SELECT
                si.project,
                SUM(si.grand_total) AS billed_to_date
            FROM `tabSales Invoice` si
            WHERE si.docstatus = 1
              AND si.project IN %(projects)s
            GROUP BY si.project
            """,
            {"projects": tuple(project_names)},
            as_dict=True,
        )
    }

    project_rows = []
    total_contract = 0.0
    total_billed = 0.0

    for row in projects:
        contract_value = float(contract_map.get(row.name, 0.0))
        billed_value = float(billed_map.get(row.name, 0.0))
        unbilled_value = max(contract_value - billed_value, 0.0)

        if contract_value > 0:
            percent_billed = min((billed_value / contract_value) * 100.0, 100.0)
        else:
            percent_billed = 100.0 if billed_value > 0 else 0.0

        total_contract += contract_value
        total_billed += billed_value

        project_rows.append(
            {
                "project": row.name,
                "project_label": row.project_label,
                "contract_value": contract_value,
                "billed_to_date": billed_value,
                "unbilled_value": unbilled_value,
                "percent_billed": round(percent_billed, 2),
            }
        )

    total_unbilled = max(total_contract - total_billed, 0.0)
    percent_billed_total = (
        min((total_billed / total_contract) * 100.0, 100.0) if total_contract > 0 else (100.0 if total_billed > 0 else 0.0)
    )

    return {
        "scope": scope,
        "summary": {
            "contract_value": total_contract,
            "billed_to_date": total_billed,
            "unbilled_value": total_unbilled,
            "percent_billed": round(percent_billed_total, 2),
        },
        "projects": project_rows,
    }


@frappe.whitelist()
def get_personal_project_status_finance(
    department=None,
    employee=None,
    view_mode="Monthly",
    reference_date=None,
):
    """Combined personal projects status + project-linked finance + aging buckets."""
    scope = resolve_personal_scope(department=department, employee=employee)
    user = scope.get("user") or frappe.session.user
    from_date, to_date = _personal_view_range(view_mode=view_mode, reference_date=reference_date)
    as_of = getdate(reference_date or nowdate())

    project_rows = frappe.db.sql(
        """
        SELECT name, status
        FROM `tabProject`
        WHERE owner = %(user)s
        """,
        {"user": user},
        as_dict=True,
    )

    project_names = [p.name for p in project_rows]
    total_projects = len(project_names)

    if not project_names:
        return {
            "scope": scope,
            "from_date": str(from_date),
            "to_date": str(to_date),
            "as_of": str(as_of),
            "counts": {"total": 0, "ongoing": 0, "completed": 0},
            "money": {"total_revenue": 0.0, "outstanding": 0.0},
            "aging": {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0},
            "invoice_names_period": [],
            "invoice_names_outstanding": [],
            "bucket_invoice_names": {"0-30": [], "31-60": [], "61-90": [], "90+": []},
        }

    ongoing_statuses = {"Open", "In Progress", "Working"}
    completed_statuses = {"Completed"}
    ongoing = sum(1 for p in project_rows if (p.status or "") in ongoing_statuses)
    completed = sum(1 for p in project_rows if (p.status or "") in completed_statuses)

    period_invoice_rows = frappe.db.sql(
        """
        SELECT
            si.name,
            si.grand_total,
            si.outstanding_amount
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND (
            si.project IN %(projects)s
            OR EXISTS (
              SELECT 1
              FROM `tabSales Invoice Item` sii
              WHERE sii.parent = si.name
                AND sii.project IN %(projects)s
            )
          )
        """,
        {
            "demo": DEMO_PATTERN,
            "from_date": from_date,
            "to_date": to_date,
            "projects": tuple(project_names),
        },
        as_dict=True,
    )

    total_revenue = round(sum(flt(r.grand_total) for r in period_invoice_rows), 2)
    invoice_names_period = [r.name for r in period_invoice_rows]

    outstanding_invoice_rows = frappe.db.sql(
        """
        SELECT
            si.name,
            si.outstanding_amount,
            si.due_date
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.customer NOT LIKE %(demo)s
          AND si.outstanding_amount > 0
          AND (
            si.project IN %(projects)s
            OR EXISTS (
              SELECT 1
              FROM `tabSales Invoice Item` sii
              WHERE sii.parent = si.name
                AND sii.project IN %(projects)s
            )
          )
        """,
        {
            "demo": DEMO_PATTERN,
            "projects": tuple(project_names),
        },
        as_dict=True,
    )

    outstanding_total = round(sum(flt(r.outstanding_amount) for r in outstanding_invoice_rows), 2)
    invoice_names_outstanding = [r.name for r in outstanding_invoice_rows]
    bucket_amounts = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    bucket_invoice_names = {"0-30": [], "31-60": [], "61-90": [], "90+": []}

    for row in outstanding_invoice_rows:
        due_date = getdate(row.due_date) if row.due_date else None
        if not due_date:
            continue
        days_overdue = max(date_diff(as_of, due_date), 0)
        if days_overdue <= 0:
            continue
        amount = flt(row.outstanding_amount)
        if days_overdue <= 30:
            key = "0-30"
        elif days_overdue <= 60:
            key = "31-60"
        elif days_overdue <= 90:
            key = "61-90"
        else:
            key = "90+"
        bucket_amounts[key] += amount
        bucket_invoice_names[key].append(row.name)

    bucket_amounts = {k: round(v, 2) for k, v in bucket_amounts.items()}

    return {
        "scope": scope,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "as_of": str(as_of),
        "counts": {"total": total_projects, "ongoing": ongoing, "completed": completed},
        "money": {"total_revenue": total_revenue, "outstanding": outstanding_total},
        "aging": bucket_amounts,
        "invoice_names_period": invoice_names_period,
        "invoice_names_outstanding": invoice_names_outstanding,
        "bucket_invoice_names": bucket_invoice_names,
    }


__all__ = [
    "get_personal_dashboard_data",
    "get_my_sales_target_route",
    "get_personal_dashboard_filter_options",
    "get_personal_project_delivery_health",
    "get_personal_project_pipeline",
    "get_personal_project_status_finance",
    "get_personal_project_value_billing",
    "get_personal_revenue_metric",
    "resolve_personal_scope",
]
