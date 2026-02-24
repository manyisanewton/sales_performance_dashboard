frappe.ui.form.on("Sales Dashboard Access Settings", {
	refresh(frm) {
		const help = frm.get_field("help_html");
		if (help && help.$wrapper) {
			help.$wrapper.html(`
				<div class="text-muted" style="margin-bottom:12px;">
					Use these toggles to control who can see each dashboard. Save or click <b>Apply Access Now</b> to update workspace visibility.
				</div>
			`);
		}

		frm.add_custom_button("Apply Access Now", () => {
			frappe.call({
				method:
					"sales_performance_dashboard.sales_performance_dashboard.doctype.sales_dashboard_access_settings.sales_dashboard_access_settings.apply_now",
				freeze: true,
				freeze_message: __("Applying dashboard access..."),
				callback: () => {
					frappe.show_alert({
						message: __("Access settings applied"),
						indicator: "green",
					});
				},
			});
		});
	},
});
