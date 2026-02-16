frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Personal Leads by Source"] = {
	method:
		"sales_performance_dashboard.sales_performance_dashboard.dashboard_chart_source.personal_leads_by_source.personal_leads_by_source.get_data",
	filters: [],
};
