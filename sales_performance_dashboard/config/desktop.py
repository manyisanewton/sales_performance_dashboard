from frappe import _


def get_data():
    return [
        {
            "module_name": "Sales Performance Dashboard",
            "type": "module",
            "label": _("Sales Performance Dashboard"),
            "color": "blue",
            "icon": "octicon octicon-graph",
            "onboard_present": 1,
            "items": [
                {"type": "doctype", "name": "Sales Targets"},
                {"type": "doctype", "name": "Sales Dashboard Access Settings"},
            ],
        }
    ]
