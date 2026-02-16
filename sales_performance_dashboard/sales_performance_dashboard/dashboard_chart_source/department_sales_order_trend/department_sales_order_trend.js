frappe.provide("frappe.dashboards.chart_sources");

const dsdDepartment = localStorage.getItem("spd_department_dashboard_department") || "";
const dsdViewMode = localStorage.getItem("spd_department_view_mode") || "Monthly";
const dsdReferenceDate = localStorage.getItem("spd_department_reference_date") || frappe.datetime.get_today();

frappe.dashboards.chart_sources["Department Sales Order Trend"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.department_sales_order_trend.department_sales_order_trend.get_data",
	filters: [
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
			default: dsdDepartment,
			reqd: 0,
		},
		{
			fieldname: "view_mode",
			label: __("View Mode"),
			fieldtype: "Select",
			options: "Monthly\nYearly",
			default: dsdViewMode,
			reqd: 0,
		},
		{
			fieldname: "reference_date",
			label: __("Reference Date"),
			fieldtype: "Date",
			default: dsdReferenceDate,
			reqd: 0,
		},
	],
};
