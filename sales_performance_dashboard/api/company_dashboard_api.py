# -*- coding: utf-8 -*-

import frappe
from frappe.utils import add_days, add_months, cint, flt, get_first_day, get_last_day, getdate, nowdate


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

    if empty_scope:
        return {
            "from_date": str(start_date),
            "to_date": str(end_date),
            "funnel": {"labels": ["Open", "Quotation", "Negotiation", "Won", "Lost"], "values": [0, 0, 0, 0, 0]},
            "deal_status": {"labels": ["Open", "Won", "Lost", "Other"], "values": [0, 0, 0, 0]},
        }

    rows = frappe.get_all(
        "Opportunity",
        filters=filters,
        fields=["status"],
        limit=20000,
    )

    funnel_labels = ["Open", "Quotation", "Negotiation", "Won", "Lost"]
    funnel_counts = {k: 0 for k in funnel_labels}
    status_labels = ["Open", "Won", "Lost", "Other"]
    status_counts = {k: 0 for k in status_labels}

    for row in rows:
        status = row.get("status")
        funnel_key = _funnel_bucket(status)
        if funnel_key in funnel_counts:
            funnel_counts[funnel_key] += 1

        status_key = _status_bucket(status)
        if status_key in status_counts:
            status_counts[status_key] += 1

    return {
        "from_date": str(start_date),
        "to_date": str(end_date),
        "funnel": {
            "labels": funnel_labels,
            "values": [funnel_counts[k] for k in funnel_labels],
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
