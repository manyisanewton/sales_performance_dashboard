import frappe

DEFAULTS = {
    "psd_sales_user": 1,
    "psd_sales_manager": 1,
    "psd_system_manager": 1,
    "psd_administrator": 1,
    "dsd_sales_user": 1,
    "dsd_sales_manager": 1,
    "dsd_system_manager": 1,
    "dsd_administrator": 1,
    "csd_sales_user": 0,
    "csd_sales_manager": 1,
    "csd_system_manager": 1,
    "csd_administrator": 1,
    "sales_user_targets_mode": "Scoped",
    "sales_manager_targets_mode": "All",
}

ROLE_FIELDS = {
    "Personal Sales Dashboard": {
        "Sales User": "psd_sales_user",
        "Sales Manager": "psd_sales_manager",
        "System Manager": "psd_system_manager",
        "Administrator": "psd_administrator",
    },
    "Department Sales Dashboard": {
        "Sales User": "dsd_sales_user",
        "Sales Manager": "dsd_sales_manager",
        "System Manager": "dsd_system_manager",
        "Administrator": "dsd_administrator",
    },
    "Company Sales Dashboard": {
        "Sales User": "csd_sales_user",
        "Sales Manager": "csd_sales_manager",
        "System Manager": "csd_system_manager",
        "Administrator": "csd_administrator",
    },
}

ALLOWED_DASHBOARD_ROLES = ("Sales User", "Sales Manager", "System Manager", "Administrator")


def get_access_settings():
    settings = dict(DEFAULTS)
    if not frappe.db.exists("DocType", "Sales Dashboard Access Settings"):
        return settings

    doc = frappe.get_single("Sales Dashboard Access Settings")
    for key in DEFAULTS:
        value = doc.get(key)
        if value is not None and value != "":
            settings[key] = value
    return settings


def get_workspace_roles_map(settings: dict | None = None) -> dict[str, list[str]]:
    settings = settings or get_access_settings()

    role_map: dict[str, list[str]] = {}
    for workspace, role_field_map in ROLE_FIELDS.items():
        roles = [role for role, field in role_field_map.items() if int(settings.get(field) or 0) == 1]
        role_map[workspace] = roles
    return role_map


def apply_workspace_roles_from_settings(settings_doc=None):
    # Restricted visibility mode: only approved sales roles can access dashboards.
    for workspace_name in ROLE_FIELDS:
        if not frappe.db.exists("Workspace", workspace_name):
            continue

        ws = frappe.get_doc("Workspace", workspace_name)
        ws.public = 1
        ws.for_user = ""
        ws.is_hidden = 0
        ws.set("roles", [])
        for role in ALLOWED_DASHBOARD_ROLES:
            ws.append("roles", {"role": role})
        ws.save(ignore_permissions=True)

    frappe.clear_cache()


def get_targets_mode_for_user(user: str) -> str:
    if frappe.has_role(user=user, role="Administrator") or frappe.has_role(user=user, role="System Manager"):
        return "All"

    settings = get_access_settings()
    modes = []

    if frappe.has_role(user=user, role="Sales Manager"):
        modes.append(settings.get("sales_manager_targets_mode", "All"))
    if frappe.has_role(user=user, role="Sales User"):
        modes.append(settings.get("sales_user_targets_mode", "Scoped"))

    if "All" in modes:
        return "All"
    if "Scoped" in modes:
        return "Scoped"
    return "None"


@frappe.whitelist()
def reset_access_defaults():
    """Reset access settings to safe defaults and apply to workspaces."""
    if not frappe.has_permission("Sales Dashboard Access Settings", ptype="write"):
        frappe.throw("Not permitted", frappe.PermissionError)

    doc = frappe.get_single("Sales Dashboard Access Settings")
    for key, value in DEFAULTS.items():
        doc.set(key, value)
    doc.save(ignore_permissions=True)
    apply_workspace_roles_from_settings(doc)
    frappe.db.commit()
    return {"ok": True}
