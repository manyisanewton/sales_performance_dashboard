import frappe
from frappe.model.document import Document


class SalesDashboardAccessSettings(Document):
    def validate(self):
        # Keep role visibility aligned with this settings UI.
        from sales_performance_dashboard.api.access_settings import apply_workspace_roles_from_settings

        apply_workspace_roles_from_settings(self)


@frappe.whitelist()
def apply_now():
    """Apply current settings to workspace role rows immediately."""
    from sales_performance_dashboard.api.access_settings import apply_workspace_roles_from_settings

    doc = frappe.get_single("Sales Dashboard Access Settings")
    apply_workspace_roles_from_settings(doc)
    frappe.db.commit()
    frappe.clear_cache()
    return {"ok": True}
