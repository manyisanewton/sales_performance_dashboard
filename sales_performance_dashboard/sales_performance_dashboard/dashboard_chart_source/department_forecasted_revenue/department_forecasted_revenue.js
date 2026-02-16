frappe.provide("frappe.dashboards.chart_sources");

const dsdDepartment = localStorage.getItem("spd_department_dashboard_department") || "";
const dsdReferenceDate = localStorage.getItem("spd_department_reference_date") || frappe.datetime.get_today();

frappe.dashboards.chart_sources["Department Forecasted Revenue"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.department_forecasted_revenue.department_forecasted_revenue.get_data",
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
			fieldname: "reference_date",
			label: __("Reference Date"),
			fieldtype: "Date",
			default: dsdReferenceDate,
			reqd: 0,
		},
	],
};
