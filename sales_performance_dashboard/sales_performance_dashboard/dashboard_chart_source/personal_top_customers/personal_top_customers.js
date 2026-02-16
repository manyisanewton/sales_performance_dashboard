frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Personal Top Customers"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.personal_top_customers.personal_top_customers.get_data",
	filters: [],
};
