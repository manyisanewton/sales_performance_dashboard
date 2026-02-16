frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Personal Sales Order Trend"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.personal_sales_order_trend.personal_sales_order_trend.get_data",
	filters: [],
};
