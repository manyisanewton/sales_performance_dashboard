# -*- coding: utf-8 -*-

import frappe
from frappe.utils import add_days, add_months, cint, flt, get_first_day, get_last_day, getdate, nowdate
from collections import defaultdict
from sales_performance_dashboard.api.access_settings import get_annual_financing_rate


DEMO_PATTERN = "SPD-DEMO-%"


def _view_range(view_mode, reference_date):
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


def _source_field():
    meta = frappe.get_meta("Opportunity")
    for candidate in ("source", "opportunity_source", "lead_source"):
        if meta.has_field(candidate):
            return candidate
    return None


def _owner_users_for_department(department):
    if not department:
        return []
    rows = frappe.get_all(
        "Employee",
        filters={"department": department, "status": ["!=", "Left"]},
        fields=["user_id"],
        limit=5000,
    )
    return [r.user_id for r in rows if r.user_id]


def _invoice_conditions(company=None, department=None, from_date=None, to_date=None):
    where = [
        "si.docstatus = 1",
        "si.customer NOT LIKE %(demo)s",
    ]
    params = {"demo": DEMO_PATTERN}

    if from_date and to_date:
        where.append("si.posting_date BETWEEN %(from_date)s AND %(to_date)s")
        params["from_date"] = from_date
        params["to_date"] = to_date

    if company:
        where.append("si.company = %(company)s")
        params["company"] = company

    if department:
        owner_users = _owner_users_for_department(department)
        if not owner_users:
            where.append("1 = 0")
        else:
            where.append("si.owner IN %(owner_users)s")
            params["owner_users"] = tuple(owner_users)

    return " AND ".join(where), params


def _opportunity_filters(company=None, department=None, view_mode="Monthly", reference_date=None, lead_source=None):
    start_date, end_date = _view_range(view_mode, reference_date)
    source_field = _source_field()
    opp_meta = frappe.get_meta("Opportunity")

    filters = {
        "docstatus": ["<", 2],
        "name": ["not like", DEMO_PATTERN],
        "creation": ["between", [start_date, end_date]],
    }

    if company and opp_meta.has_field("company"):
        filters["company"] = company

    if lead_source and source_field:
        filters[source_field] = lead_source

    owner_users = _owner_users_for_department(department)
    if department:
        if not owner_users:
            return filters, start_date, end_date, True
        filters["owner"] = ["in", owner_users]

    return filters, start_date, end_date, False


def _status_bucket(status):
    value = (status or "").strip().lower()
    if value in {"converted", "won", "closed won"}:
        return "Won"
    if value in {"lost", "closed lost"}:
        return "Lost"
    if value in {"open", "replied", "quotation", "quoted", "proposal", "proposal/price quote", "negotiation", "negotiation/review"}:
        return "Open"
    return "Other"


def _funnel_bucket(status):
    value = (status or "").strip().lower()
    if value in {"open", "replied"}:
        return "Open"
    if value in {"quotation", "quoted", "proposal", "proposal/price quote"}:
        return "Quotation"
    if value in {"negotiation", "negotiation/review"}:
        return "Negotiation"
    if value in {"converted", "won", "closed won"}:
        return "Won"
    if value in {"lost", "closed lost"}:
        return "Lost"
    return "Open"


@frappe.whitelist()
def get_company_filter_options():
    companies = frappe.get_all("Company", pluck="name", order_by="name asc")

    departments = frappe.get_all(
        "Department",
        filters={"is_group": 0},
        pluck="name",
        order_by="name asc",
        limit=500,
    )

    lead_sources = []
    if frappe.db.exists("DocType", "Lead Source"):
        lead_sources = frappe.get_all("Lead Source", pluck="name", order_by="name asc")
    else:
        # Fallback for instances without Lead Source doctype records.
        sources = frappe.db.sql(
            """
            SELECT DISTINCT NULLIF(source, '') AS source
            FROM `tabLead`
            WHERE source IS NOT NULL AND source != ''
            ORDER BY source
            """,
            as_dict=True,
        )
        lead_sources = [r.source for r in sources if r.source]

    return {
        "companies": companies or [],
        "departments": departments or [],
        "lead_sources": lead_sources or [],
        "view_modes": ["Daily", "Monthly", "Quarterly", "Yearly"],
        "risk_windows": [7, 14, 30],
        "default_risk_window": 14,
    }


@frappe.whitelist()
def get_company_dashboard_preview(company=None, department=None, reference_date=None):
    """Minimal placeholder payload for first phase wiring checks."""
    return {
        "company": company,
        "department": department,
        "reference_date": reference_date,
        "ok": 1,
        "rows": cint(0),
    }


@frappe.whitelist()
def get_company_pipeline_overview(
    company=None,
    department=None,
    view_mode="Monthly",
    reference_date=None,
    lead_source=None,
):
    filters, start_date, end_date, empty_scope = _opportunity_filters(
        company=company,
        department=department,
        view_mode=view_mode,
        reference_date=reference_date,
        lead_source=lead_source,
    )

    funnel_labels = ["Lead", "Opportunity", "Quotation", "Customer", "Sales Order", "Delivery Note", "Sales Invoice"]
    zero_funnel = {"labels": funnel_labels, "values": [0] * len(funnel_labels)}
    status_labels = ["Open", "Won", "Lost", "Other"]

    if empty_scope:
        return {
            "from_date": str(start_date),
            "to_date": str(end_date),
            "funnel": zero_funnel,
            "deal_status": {"labels": status_labels, "values": [0, 0, 0, 0]},
        }

    owner_users = _owner_users_for_department(department)
    if department and not owner_users:
        return {
            "from_date": str(start_date),
            "to_date": str(end_date),
            "funnel": zero_funnel,
            "deal_status": {"labels": status_labels, "values": [0, 0, 0, 0]},
        }

    users_tuple = tuple(owner_users) if owner_users else ()
    source_field = _source_field()

    def _field_exists(doctype, fieldname):
        return frappe.get_meta(doctype).has_field(fieldname)

    # Lead stage
    lead_filters = [
        ["name", "not like", DEMO_PATTERN],
        ["lead_name", "not like", DEMO_PATTERN],
        ["creation", "between", [start_date, end_date]],
    ]
    if users_tuple:
        lead_filters.append(["owner", "in", users_tuple])
    if lead_source and _field_exists("Lead", "source"):
        lead_filters.append(["source", "=", lead_source])

    lead_names = frappe.get_all("Lead", filters=lead_filters, pluck="name", limit=50000)
    lead_count = len(lead_names)

    # Opportunity stage (from leads in current scope)
    opportunity_count = 0
    if lead_names:
        opp_filters = [
            ["name", "not like", DEMO_PATTERN],
            ["party_name", "not like", DEMO_PATTERN],
            ["creation", "between", [start_date, end_date]],
            ["opportunity_from", "=", "Lead"],
            ["party_name", "in", tuple(lead_names)],
        ]
        if users_tuple:
            opp_filters.append(["owner", "in", users_tuple])
        if company and _field_exists("Opportunity", "company"):
            opp_filters.append(["company", "=", company])
        if lead_source and source_field and _field_exists("Opportunity", source_field):
            opp_filters.append([source_field, "=", lead_source])

        opportunity_count = frappe.db.count("Opportunity", filters=opp_filters)

    # Customer stage (converted from scoped leads)
    customer_names = []
    if lead_names:
        customer_filters = [
            ["name", "not like", DEMO_PATTERN],
            ["customer_name", "not like", DEMO_PATTERN],
            ["creation", "between", [start_date, end_date]],
            ["lead_name", "in", tuple(lead_names)],
        ]
        if users_tuple:
            customer_filters.append(["owner", "in", users_tuple])
        customer_names = frappe.get_all("Customer", filters=customer_filters, pluck="name", limit=50000)
    customer_count = len(customer_names)

    # Quotation / Sales Order / Delivery Note / Sales Invoice stages
    quotation_count = 0
    sales_order_count = 0
    delivery_note_count = 0
    sales_invoice_count = 0
    if customer_names:
        customer_tuple = tuple(customer_names)

        quotation_filters = [
            ["docstatus", "=", 1],
            ["party_name", "in", customer_tuple],
            ["party_name", "not like", DEMO_PATTERN],
            ["transaction_date", "between", [start_date, end_date]],
        ]
        if users_tuple:
            quotation_filters.append(["owner", "in", users_tuple])
        if company and _field_exists("Quotation", "company"):
            quotation_filters.append(["company", "=", company])
        quotation_count = frappe.db.count("Quotation", filters=quotation_filters)

        so_filters = [
            ["docstatus", "=", 1],
            ["customer", "in", customer_tuple],
            ["customer", "not like", DEMO_PATTERN],
            ["transaction_date", "between", [start_date, end_date]],
        ]
        if users_tuple:
            so_filters.append(["owner", "in", users_tuple])
        if company and _field_exists("Sales Order", "company"):
            so_filters.append(["company", "=", company])
        sales_order_count = frappe.db.count("Sales Order", filters=so_filters)

        dn_filters = [
            ["docstatus", "=", 1],
            ["customer", "in", customer_tuple],
            ["customer", "not like", DEMO_PATTERN],
            ["posting_date", "between", [start_date, end_date]],
        ]
        if users_tuple:
            dn_filters.append(["owner", "in", users_tuple])
        if company and _field_exists("Delivery Note", "company"):
            dn_filters.append(["company", "=", company])
        delivery_note_count = frappe.db.count("Delivery Note", filters=dn_filters)

        si_filters = [
            ["docstatus", "=", 1],
            ["customer", "in", customer_tuple],
            ["customer", "not like", DEMO_PATTERN],
            ["posting_date", "between", [start_date, end_date]],
        ]
        if users_tuple:
            si_filters.append(["owner", "in", users_tuple])
        if company and _field_exists("Sales Invoice", "company"):
            si_filters.append(["company", "=", company])
        sales_invoice_count = frappe.db.count("Sales Invoice", filters=si_filters)

    rows = frappe.get_all(
        "Opportunity",
        filters=filters,
        fields=["status"],
        limit=20000,
    )

    status_counts = {k: 0 for k in status_labels}

    for row in rows:
        status = row.get("status")
        status_key = _status_bucket(status)
        if status_key in status_counts:
            status_counts[status_key] += 1

    return {
        "from_date": str(start_date),
        "to_date": str(end_date),
        "funnel": {
            "labels": funnel_labels,
            "values": [
                lead_count,
                opportunity_count,
                quotation_count,
                customer_count,
                sales_order_count,
                delivery_note_count,
                sales_invoice_count,
            ],
        },
        "deal_status": {
            "labels": status_labels,
            "values": [status_counts[k] for k in status_labels],
        },
    }


def _company_next_target(company, view_mode, reference_date):
    ref = getdate(reference_date or nowdate())
    mode = (view_mode or "Monthly").strip().title()

    if mode == "Yearly":
        target_date = getdate(f"{ref.year}-01-01")
        value = frappe.db.sql(
            """
            SELECT COALESCE(SUM(COALESCE(yearly_target_current, yearly_target, 0)), 0) AS value
            FROM `tabSales Targets`
            WHERE docstatus < 2
              AND target_level = 'Company'
              AND company = %(company)s
              AND start_date <= %(d)s
              AND end_date >= %(d)s
            """,
            {"company": company, "d": target_date},
            as_dict=True,
        )
        return flt(value[0].value) if value else 0.0, f"Current Year Target ({target_date.year})"

    next_month = get_first_day(add_months(ref, 1))
    value = frappe.db.sql(
        """
        SELECT COALESCE(SUM(COALESCE(monthly_target_current, monthly_target, 0)), 0) AS value
        FROM `tabSales Targets`
        WHERE docstatus < 2
          AND target_level = 'Company'
          AND company = %(company)s
          AND start_date <= %(d)s
          AND end_date >= %(d)s
        """,
        {"company": company, "d": next_month},
        as_dict=True,
    )
    return flt(value[0].value) if value else 0.0, f"Next Month Target ({next_month.strftime('%b %Y')})"


def _sum_targets(level, field_current, field_base, as_of_date, company=None, department=None):
    filters = [
        "docstatus < 2",
        "target_level = %(level)s",
        "start_date <= %(d)s",
        "end_date >= %(d)s",
    ]
    params = {"level": level, "d": as_of_date}

    if company:
        filters.append("company = %(company)s")
        params["company"] = company
    if department:
        filters.append("department = %(department)s")
        params["department"] = department

    row = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(COALESCE({field_current}, {field_base}, 0)), 0) AS value
        FROM `tabSales Targets`
        WHERE {' AND '.join(filters)}
        """,
        params,
        as_dict=True,
    )
    return flt(row[0].value) if row else 0.0


def _company_scope_target(company=None, department=None, view_mode="Monthly", reference_date=None):
    ref = getdate(reference_date or nowdate())
    mode = (view_mode or "Monthly").strip().title()

    if department:
        if mode == "Yearly":
            dept_target = _sum_targets("Department", "yearly_target_current", "yearly_target", ref, department=department)
            if dept_target > 0:
                return dept_target, f"Department Year Target ({ref.year})"
            return _sum_targets("Individual", "yearly_target_current", "yearly_target", ref, department=department), f"Department Year Target ({ref.year})"

        if mode == "Quarterly":
            dept_target = _sum_targets("Department", "quarterly_target_current", "quarterly_target", ref, department=department)
            if dept_target > 0:
                return dept_target, f"Department Quarter Target ({ref.year})"
            return _sum_targets("Individual", "quarterly_target_current", "quarterly_target", ref, department=department), f"Department Quarter Target ({ref.year})"

        if mode == "Daily":
            return _sum_targets("Individual", "daily_target_current", "daily_target", ref, department=department), f"Department Daily Target ({ref.strftime('%d %b %Y')})"

        # Monthly default
        dept_target = _sum_targets("Department", "monthly_target_current", "monthly_target", ref, department=department)
        if dept_target > 0:
            return dept_target, f"Department Month Target ({ref.strftime('%b %Y')})"
        return _sum_targets("Individual", "monthly_target_current", "monthly_target", ref, department=department), f"Department Month Target ({ref.strftime('%b %Y')})"

    # Company-wide target
    if mode == "Yearly":
        return _sum_targets("Company", "yearly_target_current", "yearly_target", ref, company=company), f"Company Year Target ({ref.year})"

    if mode == "Quarterly":
        return _sum_targets("Company", "quarterly_target_current", "quarterly_target", ref, company=company), f"Company Quarter Target ({ref.year})"

    if mode == "Daily":
        monthly_target = _sum_targets("Company", "monthly_target_current", "monthly_target", ref, company=company)
        days_in_month = max(1, get_last_day(ref).day)
        return monthly_target / days_in_month, f"Company Daily Target (Pro-rated, {ref.strftime('%b %Y')})"

    # Monthly default
    return _sum_targets("Company", "monthly_target_current", "monthly_target", ref, company=company), f"Company Month Target ({ref.strftime('%b %Y')})"


@frappe.whitelist()
def get_company_revenue_by_source(
    company=None,
    department=None,
    view_mode="Monthly",
    reference_date=None,
    lead_source=None,
    limit=8,
):
    filters, start_date, end_date, empty_scope = _opportunity_filters(
        company=company,
        department=department,
        view_mode=view_mode,
        reference_date=reference_date,
        lead_source=lead_source,
    )

    source_field = _source_field() or "source"
    if empty_scope:
        return {"from_date": str(start_date), "to_date": str(end_date), "labels": [], "values": []}

    rows = frappe.get_all(
        "Opportunity",
        filters=filters,
        fields=[source_field, "status", "opportunity_amount"],
        limit=20000,
    )

    by_source = {}
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status not in {"converted", "won", "closed won"}:
            continue
        source = (row.get(source_field) or "Unknown").strip() or "Unknown"
        by_source[source] = by_source.get(source, 0.0) + flt(row.get("opportunity_amount") or 0)

    sorted_rows = sorted(by_source.items(), key=lambda x: x[1], reverse=True)[: cint(limit or 8)]
    labels = [r[0] for r in sorted_rows]
    values = [flt(r[1], 2) for r in sorted_rows]

    return {
        "from_date": str(start_date),
        "to_date": str(end_date),
        "labels": labels,
        "values": values,
        "total": flt(sum(values), 2),
    }


@frappe.whitelist()
def get_company_weighted_pipeline_coverage(
    company=None,
    department=None,
    view_mode="Monthly",
    reference_date=None,
    lead_source=None,
):
    filters, _, _, empty_scope = _opportunity_filters(
        company=company,
        department=department,
        view_mode=view_mode,
        reference_date=reference_date,
        lead_source=lead_source,
    )

    if empty_scope:
        return {
            "coverage_pct": 0,
            "weighted_pipeline": 0,
            "next_target": 0,
            "gap": 0,
            "status": "No Target",
            "next_target_label": "Next Target",
        }

    rows = frappe.get_all(
        "Opportunity",
        filters=filters,
        fields=["status", "opportunity_amount", "probability"],
        limit=20000,
    )

    weighted_pipeline = 0.0
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status in {"converted", "won", "closed won", "lost", "closed lost"}:
            continue
        weighted_pipeline += flt(row.get("opportunity_amount") or 0) * (flt(row.get("probability") or 0) / 100.0)

    next_target, target_label = _company_next_target(company, view_mode, reference_date)
    coverage_pct = round((weighted_pipeline / next_target) * 100, 2) if next_target > 0 else 0
    gap = round(weighted_pipeline - next_target, 2)

    if next_target <= 0:
        status = "No Target"
    elif coverage_pct >= 100:
        status = "Healthy"
    elif coverage_pct >= 70:
        status = "Watch"
    else:
        status = "Weak"

    return {
        "coverage_pct": coverage_pct,
        "weighted_pipeline": round(weighted_pipeline, 2),
        "next_target": round(next_target, 2),
        "gap": gap,
        "status": status,
        "next_target_label": target_label,
    }


@frappe.whitelist()
def get_company_deal_conversion_rate(
    company=None,
    department=None,
    view_mode="Monthly",
    reference_date=None,
    lead_source=None,
):
    filters, _, _, empty_scope = _opportunity_filters(
        company=company,
        department=department,
        view_mode=view_mode,
        reference_date=reference_date,
        lead_source=lead_source,
    )

    if empty_scope:
        return {"conversion_pct": 0}

    rows = frappe.get_all(
        "Opportunity",
        filters=filters,
        fields=["name", "title", "party_name", "opportunity_from", "status", "opportunity_amount"],
        limit=20000,
    )
    total = len(rows)
    won = 0
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        if status in {"converted", "won", "closed won"}:
            won += 1

    conversion_pct = round((won / total) * 100, 2) if total else 0
    top_candidates = [
        r for r in rows if flt(r.get("opportunity_amount") or 0) > 0
    ]
    top_candidates.sort(key=lambda d: flt(d.get("opportunity_amount") or 0), reverse=True)

    top_opportunities = []
    for row in top_candidates[:5]:
        display_name = (
            (row.get("party_name") or "").strip()
            or (row.get("title") or "").strip()
            or (row.get("name") or "").strip()
            or "Opportunity"
        )
        top_opportunities.append(
            {
                "name": display_name,
                "amount": round(flt(row.get("opportunity_amount") or 0), 2),
            }
        )

    return {
        "conversion_pct": conversion_pct,
        "won": won,
        "total": total,
        "top_opportunities": top_opportunities,
    }


@frappe.whitelist()
def get_company_revenue_waterfall(
    company=None,
    department=None,
    view_mode="Monthly",
    reference_date=None,
    lead_source=None,
    risk_window_days=14,
):
    del lead_source  # Not applicable on Sales Invoice calculations for this metric.

    from_date, to_date = _view_range(view_mode, reference_date)
    where_sql, params = _invoice_conditions(
        company=company,
        department=department,
        from_date=from_date,
        to_date=to_date,
    )

    row = frappe.db.sql(
        f"""
        SELECT
            COALESCE(SUM(si.grand_total), 0) AS total_revenue,
            COALESCE(SUM(si.outstanding_amount), 0) AS total_outstanding
        FROM `tabSales Invoice` si
        WHERE {where_sql}
        """,
        params,
        as_dict=True,
    )
    totals = row[0] if row else {}
    total_revenue = flt(totals.get("total_revenue"))
    total_outstanding = flt(totals.get("total_outstanding"))
    total_collected = max(0, total_revenue - total_outstanding)

    target_value, target_label = _company_scope_target(
        company=company,
        department=department,
        view_mode=view_mode,
        reference_date=reference_date,
    )

    risk_days = cint(risk_window_days or 14)
    if risk_days <= 0:
        risk_days = 14
    cutoff_date = add_days(nowdate(), risk_days)

    risk_row = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(si.outstanding_amount), 0) AS value
        FROM `tabSales Invoice` si
        WHERE {where_sql}
          AND si.outstanding_amount > 0
          AND si.due_date IS NOT NULL
          AND si.due_date <= %(risk_cutoff)s
        """,
        {**params, "risk_cutoff": cutoff_date},
        as_dict=True,
    )
    revenue_at_risk = flt(risk_row[0].value) if risk_row else 0
    revenue_at_risk = min(revenue_at_risk, total_outstanding)

    return {
        "from_date": str(from_date),
        "to_date": str(to_date),
        "monthly_target": round(target_value, 2),
        "target_value": round(target_value, 2),
        "target_label": target_label,
        "total_revenue": round(total_revenue, 2),
        "total_collected": round(total_collected, 2),
        "total_outstanding": round(total_outstanding, 2),
        "revenue_at_risk": round(revenue_at_risk, 2),
        "risk_window_days": risk_days,
    }


def _trend_buckets(view_mode="Monthly", reference_date=None):
    ref = getdate(reference_date or nowdate())
    mode = (view_mode or "Monthly").strip().title()
    buckets = []

    if mode == "Daily":
        # Last 30 days ending at reference date.
        for i in range(29, -1, -1):
            d = add_days(ref, -i)
            buckets.append((d, d, d.strftime("%d %b")))
        return buckets

    if mode == "Quarterly":
        # Last 8 quarters ending at reference quarter.
        current_q_start_month = (((ref.month - 1) // 3) * 3) + 1
        current_q_start = getdate(f"{ref.year}-{current_q_start_month:02d}-01")
        for i in range(7, -1, -1):
            q_start = add_months(current_q_start, -(i * 3))
            q_end = get_last_day(add_months(q_start, 2))
            q = ((q_start.month - 1) // 3) + 1
            buckets.append((q_start, q_end, f"Q{q} {q_start.year}"))
        return buckets

    if mode == "Yearly":
        # Last 5 years ending at reference year.
        for i in range(4, -1, -1):
            y = ref.year - i
            buckets.append((getdate(f"{y}-01-01"), getdate(f"{y}-12-31"), str(y)))
        return buckets

    # Monthly default: last 12 months ending at reference month.
    current_month_start = get_first_day(ref)
    for i in range(11, -1, -1):
        month_start = add_months(current_month_start, -i)
        month_end = get_last_day(month_start)
        buckets.append((month_start, month_end, month_start.strftime("%b %Y")))
    return buckets


def _departments_for_gross_margin():
    rows = frappe.db.sql(
        """
        SELECT DISTINCT e.department
        FROM `tabEmployee` e
        INNER JOIN `tabDepartment` d ON d.name = e.department
        WHERE IFNULL(e.department, '') != ''
          AND IFNULL(e.status, '') != 'Left'
          AND IFNULL(d.is_group, 0) = 0
        ORDER BY e.department
        """,
        as_dict=True,
    )
    return [r.department for r in rows if r.get("department")]


def _company_gross_margin_for_period(company, department, from_date, to_date):
    where_sql, params = _invoice_conditions(
        company=company,
        department=department,
        from_date=from_date,
        to_date=to_date,
    )
    row = frappe.db.sql(
        f"""
        SELECT
            COALESCE(SUM(sii.base_net_amount), 0) AS sales,
            COALESCE(SUM(IFNULL(sii.stock_qty, 0) * IFNULL(sii.incoming_rate, 0)), 0) AS cogs
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE {where_sql}
        """,
        params,
        as_dict=True,
    )
    sales = flt((row[0] or {}).get("sales", 0)) if row else 0
    cogs = flt((row[0] or {}).get("cogs", 0)) if row else 0
    if sales <= 0:
        return 0.0
    return round(((sales - cogs) / sales) * 100, 2)


@frappe.whitelist()
def get_company_gross_margin_trend(
    company=None,
    department=None,
    view_mode="Monthly",
    reference_date=None,
):
    buckets = _trend_buckets(view_mode=view_mode, reference_date=reference_date)
    labels = [b[2] for b in buckets]

    # Always return a single series:
    # - if department is selected, that department trend
    # - otherwise, overall company trend
    series_name = department or "Total"
    values = []
    for start_date, end_date, _ in buckets:
        values.append(
            _company_gross_margin_for_period(
                company=company,
                department=department or None,
                from_date=start_date,
                to_date=end_date,
            )
        )

    return {"labels": labels, "datasets": [{"name": series_name, "values": values}]}


@frappe.whitelist()
def get_company_payment_delay_cost(
    company=None,
    department=None,
    reference_date=None,
    view_mode=None,
    annual_financing_rate=None,
    top_limit=6,
):
    del view_mode  # Not required for overdue aging as-of snapshot.
    top_limit = max(3, min(cint(top_limit) if top_limit else 6, 12))
    configured_rate = get_annual_financing_rate()
    annual_financing_rate = flt(
        annual_financing_rate if annual_financing_rate not in (None, "") else configured_rate
    )
    if annual_financing_rate < 0:
        annual_financing_rate = 0
    as_of = getdate(reference_date or nowdate())

    where_sql, params = _invoice_conditions(
        company=company,
        department=department,
        from_date=None,
        to_date=None,
    )

    rows = frappe.db.sql(
        f"""
        SELECT
            si.name AS invoice,
            si.customer,
            si.outstanding_amount,
            si.due_date,
            DATEDIFF(%(as_of)s, si.due_date) AS days_overdue
        FROM `tabSales Invoice` si
        WHERE {where_sql}
          AND si.outstanding_amount > 0
          AND si.due_date IS NOT NULL
          AND si.due_date < %(as_of)s
        """,
        {**params, "as_of": as_of},
        as_dict=True,
    )

    if not rows:
        return {
            "as_of": str(as_of),
            "annual_financing_rate": round(annual_financing_rate, 2),
            "overdue_outstanding": 0,
            "estimated_delay_cost": 0,
            "cost_pct_of_overdue": 0,
            "daily_financing_cost": 0,
            "avg_overdue_days": 0,
            "buckets": [
                {"label": "0-30", "amount": 0, "cost": 0, "count": 0},
                {"label": "31-60", "amount": 0, "cost": 0, "count": 0},
                {"label": "61-90", "amount": 0, "cost": 0, "count": 0},
                {"label": "90+", "amount": 0, "cost": 0, "count": 0},
            ],
            "top_customers": [],
        }

    rate_per_day = annual_financing_rate / 100 / 365
    buckets = {
        "0-30": {"label": "0-30", "amount": 0.0, "cost": 0.0, "count": 0},
        "31-60": {"label": "31-60", "amount": 0.0, "cost": 0.0, "count": 0},
        "61-90": {"label": "61-90", "amount": 0.0, "cost": 0.0, "count": 0},
        "90+": {"label": "90+", "amount": 0.0, "cost": 0.0, "count": 0},
    }
    customer_cost = defaultdict(lambda: {"amount": 0.0, "cost": 0.0, "count": 0})

    overdue_outstanding = 0.0
    estimated_delay_cost = 0.0
    weighted_days = 0.0

    for row in rows:
        amount = flt(row.outstanding_amount)
        days = max(cint(row.days_overdue), 0)
        cost = amount * rate_per_day * days
        overdue_outstanding += amount
        estimated_delay_cost += cost
        weighted_days += (amount * days)

        if days <= 30:
            key = "0-30"
        elif days <= 60:
            key = "31-60"
        elif days <= 90:
            key = "61-90"
        else:
            key = "90+"

        buckets[key]["amount"] += amount
        buckets[key]["cost"] += cost
        buckets[key]["count"] += 1

        customer = row.customer or "Unknown"
        customer_cost[customer]["amount"] += amount
        customer_cost[customer]["cost"] += cost
        customer_cost[customer]["count"] += 1

    avg_overdue_days = (weighted_days / overdue_outstanding) if overdue_outstanding > 0 else 0
    daily_financing_cost = overdue_outstanding * rate_per_day
    cost_pct_of_overdue = (estimated_delay_cost / overdue_outstanding * 100) if overdue_outstanding > 0 else 0

    bucket_rows = [buckets["0-30"], buckets["31-60"], buckets["61-90"], buckets["90+"]]
    for b in bucket_rows:
        b["amount"] = round(b["amount"], 2)
        b["cost"] = round(b["cost"], 2)

    top_customers = []
    for customer, agg in customer_cost.items():
        top_customers.append(
            {
                "customer": customer,
                "amount": round(agg["amount"], 2),
                "cost": round(agg["cost"], 2),
                "count": int(agg["count"]),
                "cost_pct": round((agg["cost"] / estimated_delay_cost * 100), 2) if estimated_delay_cost > 0 else 0,
            }
        )
    top_customers.sort(key=lambda d: d["cost"], reverse=True)
    top_customers = top_customers[:top_limit]

    return {
        "as_of": str(as_of),
        "annual_financing_rate": round(annual_financing_rate, 2),
        "overdue_outstanding": round(overdue_outstanding, 2),
        "estimated_delay_cost": round(estimated_delay_cost, 2),
        "cost_pct_of_overdue": round(cost_pct_of_overdue, 2),
        "daily_financing_cost": round(daily_financing_cost, 2),
        "avg_overdue_days": round(avg_overdue_days, 1),
        "buckets": bucket_rows,
        "top_customers": top_customers,
    }


@frappe.whitelist()
def get_company_target_slippage(
    company=None,
    department=None,
    slippage_mode="Monthly",
    reference_date=None,
    view_mode=None,
):
    ref = getdate(reference_date or nowdate())
    mode = (slippage_mode or view_mode or "Monthly").strip().title()
    period_start, period_end = _view_range(mode, ref)
    effective_ref = min(ref, period_end)

    target_value, target_label = _company_scope_target(
        company=company,
        department=department,
        view_mode=mode,
        reference_date=ref,
    )

    expected_label = target_label
    actual_label_map = {
        "Daily": "Collected Today",
        "Monthly": "Collected (Month)",
        "Quarterly": "Collected (Quarter)",
        "Yearly": "Collected (Year)",
    }
    actual_label = actual_label_map.get(mode, "Collected (Period)")

    where_sql, params = _invoice_conditions(
        company=company,
        department=department,
        from_date=period_start,
        to_date=effective_ref,
    )
    row = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(si.grand_total - si.outstanding_amount), 0) AS collected
        FROM `tabSales Invoice` si
        WHERE {where_sql}
        """,
        params,
        as_dict=True,
    )
    actual_by_today = flt((row[0] or {}).get("collected", 0)) if row else 0
    expected_by_today = round(flt(target_value), 2)

    slippage_amount = round(actual_by_today - expected_by_today, 2)
    pace_pct = round((actual_by_today / expected_by_today) * 100, 2) if expected_by_today > 0 else 0

    if expected_by_today <= 0:
        status = "No Target"
    elif pace_pct >= 100:
        status = "Ahead"
    elif pace_pct >= 95:
        status = "On Pace"
    else:
        status = "Behind"

    if slippage_amount >= 0:
        chart_labels = ["Expected Pace", "Ahead"]
        chart_values = [round(expected_by_today, 2), round(slippage_amount, 2)]
        chart_colors = ["#93c5fd", "#16a34a"]
    else:
        chart_labels = ["Actual", "Gap to Pace"]
        chart_values = [round(actual_by_today, 2), round(abs(slippage_amount), 2)]
        chart_colors = ["#3b82f6", "#f43f5e"]

    return {
        "status": status,
        "mode": mode,
        "expected_label": expected_label,
        "actual_label": actual_label,
        "expected_by_today": round(expected_by_today, 2),
        "actual_by_today": round(actual_by_today, 2),
        "slippage_amount": slippage_amount,
        "pace_pct": pace_pct,
        "period_target": round(expected_by_today, 2),
        "chart": {
            "labels": chart_labels,
            "values": chart_values,
            "colors": chart_colors,
        },
    }


@frappe.whitelist()
def get_company_project_status_finance(
    company=None,
    department=None,
    view_mode="Monthly",
    reference_date=None,
):
    """Company project status + project-linked finance summary for dashboard."""
    from_date, to_date = _view_range(view_mode, reference_date)
    as_of = getdate(reference_date or nowdate())

    project_meta = frappe.get_meta("Project")
    has_company = project_meta.has_field("company")

    project_where = ["p.docstatus < 2"]
    project_params = {}

    if has_company and company:
        project_where.append("p.company = %(company)s")
        project_params["company"] = company

    if department:
        owner_users = _owner_users_for_department(department)
        if not owner_users:
            return {
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
        project_where.append("p.owner IN %(owner_users)s")
        project_params["owner_users"] = tuple(owner_users)

    projects = frappe.db.sql(
        f"""
        SELECT p.name, p.status
        FROM `tabProject` p
        WHERE {' AND '.join(project_where)}
        """,
        project_params,
        as_dict=True,
    )
    project_names = [p.name for p in projects]

    total_projects = len(project_names)
    ongoing_statuses = {"Open", "In Progress", "Working"}
    completed_statuses = {"Completed"}
    ongoing = sum(1 for p in projects if (p.status or "") in ongoing_statuses)
    completed = sum(1 for p in projects if (p.status or "") in completed_statuses)

    if not project_names:
        return {
            "from_date": str(from_date),
            "to_date": str(to_date),
            "as_of": str(as_of),
            "counts": {"total": total_projects, "ongoing": ongoing, "completed": completed},
            "money": {"total_revenue": 0.0, "outstanding": 0.0},
            "aging": {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0},
            "invoice_names_period": [],
            "invoice_names_outstanding": [],
            "bucket_invoice_names": {"0-30": [], "31-60": [], "61-90": [], "90+": []},
        }

    period_invoice_where = [
        "si.docstatus = 1",
        "si.customer NOT LIKE %(demo)s",
        "si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
        "(si.project IN %(projects)s OR EXISTS (SELECT 1 FROM `tabSales Invoice Item` sii WHERE sii.parent = si.name AND sii.project IN %(projects)s))",
    ]
    period_invoice_params = {
        "demo": DEMO_PATTERN,
        "from_date": from_date,
        "to_date": to_date,
        "projects": tuple(project_names),
    }
    if company:
        period_invoice_where.append("si.company = %(company)s")
        period_invoice_params["company"] = company
    if department:
        owner_users = _owner_users_for_department(department)
        period_invoice_where.append("si.owner IN %(owner_users)s")
        period_invoice_params["owner_users"] = tuple(owner_users)

    period_invoice_rows = frappe.db.sql(
        f"""
        SELECT si.name, si.grand_total
        FROM `tabSales Invoice` si
        WHERE {' AND '.join(period_invoice_where)}
        """,
        period_invoice_params,
        as_dict=True,
    )
    total_revenue = round(sum(flt(r.grand_total) for r in period_invoice_rows), 2)
    invoice_names_period = [r.name for r in period_invoice_rows]

    outstanding_where = [
        "si.docstatus = 1",
        "si.customer NOT LIKE %(demo)s",
        "si.outstanding_amount > 0",
        "(si.project IN %(projects)s OR EXISTS (SELECT 1 FROM `tabSales Invoice Item` sii WHERE sii.parent = si.name AND sii.project IN %(projects)s))",
    ]
    outstanding_params = {"demo": DEMO_PATTERN, "projects": tuple(project_names)}
    if company:
        outstanding_where.append("si.company = %(company)s")
        outstanding_params["company"] = company
    if department:
        owner_users = _owner_users_for_department(department)
        outstanding_where.append("si.owner IN %(owner_users)s")
        outstanding_params["owner_users"] = tuple(owner_users)

    outstanding_rows = frappe.db.sql(
        f"""
        SELECT si.name, si.outstanding_amount, si.due_date
        FROM `tabSales Invoice` si
        WHERE {' AND '.join(outstanding_where)}
        """,
        outstanding_params,
        as_dict=True,
    )
    outstanding_total = round(sum(flt(r.outstanding_amount) for r in outstanding_rows), 2)
    invoice_names_outstanding = [r.name for r in outstanding_rows]

    bucket_amounts = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    bucket_invoice_names = {"0-30": [], "31-60": [], "61-90": [], "90+": []}

    for row in outstanding_rows:
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
