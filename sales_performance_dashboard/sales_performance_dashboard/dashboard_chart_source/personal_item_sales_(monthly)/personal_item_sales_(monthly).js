frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Personal Item Sales (Monthly)"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.personal_item_sales_monthly.personal_item_sales_monthly.get_data",
	filters: [],
};
