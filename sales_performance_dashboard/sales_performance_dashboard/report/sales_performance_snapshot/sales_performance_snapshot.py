import datetime

import frappe
from frappe.utils import add_days, add_months, flt, get_first_day, get_last_day, getdate

DEPARTMENTS = [
    "Trading Division - NAL",
    "Industrial Division - NAL",
    "Commercial Division - NAL",
    "Institution Division - NAL",
    "Telesales - NAL",
    "Service Sales - NAL",
    "Mombasa Sales - NAL",
    "IT - NAD",
]


def execute(filters=None):
    filters = filters or {}
    period = filters.get("period") or "Monthly"
    period_date = getdate(filters.get("period_date") or datetime.date.today())
    period_start, period_end = get_period_range(period, period_date)

    columns = [
        {"label": "Sales Target", "fieldname": "sales_target", "fieldtype": "Link", "options": "Sales Targets", "width": 160},
        {"label": "Target Level", "fieldname": "target_level", "fieldtype": "Data", "width": 120},
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 140},
        {"label": "Department", "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 140},
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 140},
        {"label": "Period", "fieldname": "period", "fieldtype": "Data", "width": 90},
        {"label": "Period Start", "fieldname": "period_start", "fieldtype": "Date", "width": 110},
        {"label": "Period End", "fieldname": "period_end", "fieldtype": "Date", "width": 110},
        {"label": "Target Value", "fieldname": "target_value", "fieldtype": "Currency", "width": 120},
        {"label": "Achieved", "fieldname": "achieved", "fieldtype": "Currency", "width": 120},
        {"label": "Progress (%)", "fieldname": "progress", "fieldtype": "Percent", "width": 110},
    ]

    data = get_snapshot_rows(filters, period, period_start, period_end)

    return columns, data


def get_snapshot_rows(filters, period, period_start, period_end):
    target_level = filters.get("target_level") or "Company"
    if target_level == "Company":
        return get_company_rows(period, period_start, period_end)
    if target_level == "Department":
        return get_department_rows(filters, period, period_start, period_end)
    return []


def get_company_rows(period, period_start, period_end):
    rows = []
    totals = {"target_value": 0, "achieved": 0}
    for department in DEPARTMENTS:
        targets = frappe.get_all(
            "Sales Targets",
            filters={"target_level": "Department", "department": department},
            fields=["name"],
        )
        target_value, achieved = (0, 0)
        if targets:
            target_value, achieved = sum_targets_for_period(targets, period, period_start, period_end)
        totals["target_value"] += target_value
        totals["achieved"] += achieved
        rows.append(
            {
                "sales_target": "",
                "target_level": "Department",
                "company": "",
                "department": department,
                "employee": "",
                "period": period,
                "period_start": period_start,
                "period_end": period_end,
                "target_value": target_value,
                "achieved": achieved,
                "progress": calculate_progress(achieved, target_value),
            }
        )
    if rows:
        rows.append(build_total_row(period, period_start, period_end, totals))
    return rows


def get_department_rows(filters, period, period_start, period_end):
    department = filters.get("department")
    if not department:
        return []
    targets = frappe.get_all(
        "Sales Targets",
        filters={"target_level": "Individual", "department": department},
        fields=["name"],
    )
    rows = []
    totals = {"target_value": 0, "achieved": 0}
    for row in targets:
        doc = frappe.get_doc("Sales Targets", row.name)
        target_value = get_target_value(doc, period) or 0
        start, end = clamp_period(doc, period_start, period_end)
        achieved = doc.get_achieved_between(start, end) if start and end else 0
        totals["target_value"] += target_value
        totals["achieved"] += achieved
        rows.append(
            {
                "sales_target": doc.name,
                "target_level": doc.target_level,
                "company": doc.company,
                "department": doc.department,
                "employee": doc.employee,
                "period": period,
                "period_start": start,
                "period_end": end,
                "target_value": target_value,
                "achieved": achieved,
                "progress": calculate_progress(achieved, target_value),
            }
        )
    if rows:
        rows.append(build_total_row(period, period_start, period_end, totals))
    return rows


def sum_targets_for_period(targets, period, period_start, period_end):
    total_target = 0
    total_achieved = 0
    for row in targets:
        doc = frappe.get_doc("Sales Targets", row.name)
        target_value = get_target_value(doc, period) or 0
        start, end = clamp_period(doc, period_start, period_end)
        achieved = doc.get_achieved_between(start, end) if start and end else 0
        total_target += target_value
        total_achieved += achieved
    return total_target, total_achieved


def build_total_row(period, period_start, period_end, totals):
    achieved = totals["achieved"]
    target_value = totals["target_value"]
    return {
        "sales_target": "",
        "target_level": "Total",
        "company": "",
        "department": "Total",
        "employee": "",
        "period": period,
        "period_start": period_start,
        "period_end": period_end,
        "target_value": target_value,
        "achieved": achieved,
        "progress": calculate_progress(achieved, target_value),
    }


def get_period_range(period, period_date):
    if period == "Daily":
        return period_date, period_date
    if period == "Weekly":
        start = period_date - datetime.timedelta(days=period_date.weekday())
        return start, start + datetime.timedelta(days=6)
    if period == "Monthly":
        return get_first_day(period_date), get_last_day(period_date)
    if period == "Quarterly":
        quarter_month = ((period_date.month - 1) // 3) * 3 + 1
        start = datetime.date(period_date.year, quarter_month, 1)
        end = add_months(start, 3)
        return start, add_days(end, -1)
    if period == "Yearly":
        start = datetime.date(period_date.year, 1, 1)
        return start, datetime.date(period_date.year, 12, 31)

    return period_date, period_date


def clamp_period(doc, period_start, period_end):
    if not doc.start_date or not doc.end_date:
        return period_start, period_end

    start = max(getdate(doc.start_date), getdate(period_start))
    end = min(getdate(doc.end_date), getdate(period_end))
    if end < start:
        return None, None
    return start, end


def get_target_value(doc, period):
    if period == "Daily":
        return doc.daily_target if doc.target_level == "Individual" else None
    if period == "Weekly":
        return doc.weekly_target if doc.target_level == "Individual" else None
    if period == "Monthly":
        return doc.monthly_target
    if period == "Quarterly":
        return doc.quarterly_target
    if period == "Yearly":
        return doc.yearly_target
    return None


def calculate_progress(achieved, target):
    target_value = flt(target)
    if target_value <= 0:
        return 0
    return min((flt(achieved) / target_value) * 100, 100)
