import frappe


def update_sales_targets():
    targets = frappe.get_all("Sales Targets", pluck="name")
    if not targets:
        return

    for name in targets:
        doc = frappe.get_doc("Sales Targets", name)
        doc.set_achieved_total()
        doc.set_carryover_targets()
        doc.update_progress_fields()
        frappe.db.set_value(
            "Sales Targets",
            name,
            {
                "achieved_total": doc.achieved_total,
                "daily_target_current": doc.daily_target_current,
                "monthly_target_current": doc.monthly_target_current,
                "quarterly_target_current": doc.quarterly_target_current,
                "yearly_target_current": doc.yearly_target_current,
                "yearly_progress": doc.yearly_progress,
                "quarterly_progress": doc.quarterly_progress,
                "monthly_progress": doc.monthly_progress,
                "weekly_progress": doc.weekly_progress,
                "daily_progress": doc.daily_progress,
            },
            update_modified=False,
        )
