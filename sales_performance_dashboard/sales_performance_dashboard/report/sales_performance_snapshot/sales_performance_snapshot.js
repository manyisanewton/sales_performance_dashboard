// Copyright (c) 2024, Custom and contributors
// For license information, please see license.txt

frappe.query_reports["Sales Performance Snapshot"] = {
	filters: [
		{
			fieldname: "period",
			label: __("Period"),
			fieldtype: "Select",
			options: ["Daily", "Weekly", "Monthly", "Quarterly", "Yearly"],
			default: "Monthly",
			reqd: 1,
		},
		{
			fieldname: "period_date",
			label: __("Period Date"),
			fieldtype: "Date",
			default: frappe.datetime.now_date(),
			reqd: 1,
		},
		{
			fieldname: "target_level",
			label: __("Target Level"),
			fieldtype: "Select",
			options: ["Company", "Department"],
			default: "Company",
			reqd: 1,
			on_change(report) {
				const level = report.get_filter_value("target_level");
				const show_department = level === "Department";
				report.toggle_filter_display("department", show_department);
				report.set_filter_value("department", show_department ? report.get_filter_value("department") : "");
				const dept_filter = report.get_filter("department");
				dept_filter.df.reqd = show_department;
				dept_filter.refresh();
				if (!show_department) {
					report.set_filter_value("department", "");
				}
			},
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Select",
			options: [
				"",
				"Trading Division - NAL",
				"Industrial Division - NAL",
				"Commercial Division - NAL",
				"Institution Division - NAL",
				"Telesales - NAL",
				"Service Sales - NAL",
				"Mombasa Sales - NAL",
			],
		},
	],
};
