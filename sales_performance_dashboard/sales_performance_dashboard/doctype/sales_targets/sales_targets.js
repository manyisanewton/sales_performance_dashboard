frappe.ui.form.on("Sales Targets", {
    setup(frm) {
        frm.set_query("employee", () => {
            if (!frm.doc.department) {
                return {};
            }
            return {
                filters: {
                    department: frm.doc.department
                }
            };
        });
    },
    target_level(frm) {
        if (frm.doc.target_level === "Company") {
            frm.set_value("department", null);
            frm.set_value("parent_department", null);
            frm.set_value("employee", null);
        }

        if (frm.doc.target_level === "Department") {
            frm.set_value("company", null);
            frm.set_value("employee", null);
        }

        if (frm.doc.target_level === "Individual") {
            frm.set_value("company", null);
        }
        update_owner_display(frm);
    },
    department(frm) {
        if (!frm.doc.department) {
            frm.set_value("parent_department", null);
            update_owner_display(frm);
            return;
        }

        if (frm.doc.target_level === "Individual") {
            frm.set_value("employee", null);
        }

        frappe.db.get_value("Department", frm.doc.department, "parent_department").then((r) => {
            frm.set_value("parent_department", r.message ? r.message.parent_department : null);
        });

        update_owner_display(frm);
    },
    employee(frm) {
        if (frm.doc.target_level !== "Individual" || !frm.doc.employee) {
            update_owner_display(frm);
            return;
        }

        frappe.db.get_value("Employee", frm.doc.employee, "department").then((r) => {
            const department = r.message ? r.message.department : null;
            frm.set_value("department", department);
            if (!department) {
                frm.set_value("parent_department", null);
                return;
            }

            frappe.db.get_value("Department", department, "parent_department").then((res) => {
                frm.set_value("parent_department", res.message ? res.message.parent_department : null);
            });
        });
        update_owner_display(frm);
    },
    company: update_owner_display
});

function update_owner_display(frm) {
    if (frm.doc.target_level === "Company") {
        frm.set_value("owner_display", frm.doc.company || "");
    } else if (frm.doc.target_level === "Department") {
        frm.set_value("owner_display", frm.doc.department || "");
    } else if (frm.doc.target_level === "Individual") {
        frm.set_value("owner_display", frm.doc.employee || "");
    } else {
        frm.set_value("owner_display", "");
    }
}
