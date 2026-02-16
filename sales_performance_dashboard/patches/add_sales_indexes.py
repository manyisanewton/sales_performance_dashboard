import frappe


def execute():
    indexes = [
        ("Sales Invoice", ["posting_date"]),
        ("Sales Invoice", ["company"]),
        ("Sales Team", ["sales_person"]),
        ("Sales Person", ["department"]),
        ("Employee", ["department"]),
        ("Opportunity", ["sales_stage"]),
        ("Opportunity", ["status"]),
        ("Opportunity", ["expected_closing"]),
        ("Lead", ["creation"]),
        ("Quotation", ["transaction_date"]),
        ("Sales Order", ["transaction_date"]),
    ]

    for doctype, fields in indexes:
        try:
            frappe.db.add_index(doctype, fields)
        except Exception:
            # Ignore if index already exists or if DB doesn't support it.
            continue
