frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Personal Sales Funnel"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.personal_sales_funnel.personal_sales_funnel.get_data",
	filters: [],
};
