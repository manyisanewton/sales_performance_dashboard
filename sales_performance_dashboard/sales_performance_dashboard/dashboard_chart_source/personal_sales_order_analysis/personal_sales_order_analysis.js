frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Personal Sales Order Analysis"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.personal_sales_order_analysis.personal_sales_order_analysis.get_data",
	filters: [],
};
