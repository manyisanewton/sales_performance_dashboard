frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Department Sales Funnel"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.department_sales_funnel.department_sales_funnel.get_data",
	filters: [],
};
