import frappe


def get_sales_targets_permission_query_conditions(user: str | None = None) -> str:
    # Open access: no row-level restriction.
    return ""


def sales_targets_has_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
    # Open access: rely only on DocType role permissions.
    return True


@frappe.whitelist()
def repair_dashboard_widget_access():
    """Repair dashboard widget visibility for Sales User / Sales Manager."""
    user_roles = set(frappe.get_roles())
    if not (frappe.session.user == "Administrator" or "System Manager" in user_roles):
        frappe.throw("Not permitted", frappe.PermissionError)

    roles = ("Sales User", "Sales Manager")
    doctypes = ("Number Card", "Dashboard Chart", "Custom HTML Block")

    # 1) Ensure Sales roles have read-only DocPerm rows on widget doctypes.
    for dt in doctypes:
        for role in roles:
            if not frappe.db.exists("DocPerm", {"parent": dt, "role": role, "permlevel": 0}):
                perm = frappe.get_doc(
                    {
                        "doctype": "DocPerm",
                        "parent": dt,
                        "parenttype": "DocType",
                        "parentfield": "permissions",
                        "role": role,
                        "permlevel": 0,
                        "read": 1,
                        "write": 0,
                        "create": 0,
                        "delete": 0,
                        "report": 0,
                        "export": 0,
                        "import": 0,
                        "print": 0,
                        "email": 0,
                        "share": 0,
                    }
                )
                perm.insert(ignore_permissions=True)

    # 2) For custom Number Cards, document_type controls row-level permission checks.
    # Use Sales Invoice as a permission anchor if empty.
    frappe.db.sql(
        """
        UPDATE `tabNumber Card`
        SET document_type = 'Sales Invoice'
        WHERE module = 'Sales Performance Dashboard'
          AND type = 'Custom'
          AND IFNULL(document_type, '') = ''
        """
    )

    # 3) For custom Dashboard Charts, assign explicit roles so Sales roles can view.
    chart_names = frappe.get_all(
        "Dashboard Chart",
        filters={"module": "Sales Performance Dashboard", "chart_type": "Custom"},
        pluck="name",
    )
    chart_roles = ("Sales User", "Sales Manager", "System Manager", "Administrator")
    for chart_name in chart_names:
        chart_doc = frappe.get_doc("Dashboard Chart", chart_name)
        existing = {row.role for row in (chart_doc.roles or [])}
        changed = False
        for role in chart_roles:
            if role not in existing:
                chart_doc.append("roles", {"role": role})
                changed = True
        if changed:
            chart_doc.save(ignore_permissions=True)

    frappe.clear_cache()
    frappe.db.commit()
    return {"ok": True}

