frappe.provide("frappe.dashboards.chart_sources");

const psdDepartment = localStorage.getItem("spd_personal_dashboard_department") || "";
const psdEmployee = localStorage.getItem("spd_personal_dashboard_employee") || "";

frappe.dashboards.chart_sources["Personal Leads by Source"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.personal_leads_by_source.personal_leads_by_source.get_data",
	filters: [
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Data",
			default: psdDepartment,
			hidden: 1,
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Data",
			default: psdEmployee,
			hidden: 1,
		},
	],
};
