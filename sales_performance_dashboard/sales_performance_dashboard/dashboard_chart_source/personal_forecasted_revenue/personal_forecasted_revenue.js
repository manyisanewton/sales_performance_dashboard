frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Personal Forecasted Revenue"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.personal_forecasted_revenue.personal_forecasted_revenue.get_data",
	filters: [],
};
