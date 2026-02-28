frappe.provide("frappe.dashboards.chart_sources");

const psdDepartment = localStorage.getItem("spd_personal_dashboard_department") || "";
const psdEmployee = localStorage.getItem("spd_personal_dashboard_employee") || "";

frappe.dashboards.chart_sources["Personal Sales Order Trend"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.personal_sales_order_trend.personal_sales_order_trend.get_data",
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
