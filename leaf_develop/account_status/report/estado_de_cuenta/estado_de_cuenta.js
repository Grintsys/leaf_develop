function get_account_statement_filters() {
	return [
		{
			fieldname: "company",
			label: __("Empresa"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company")
		},
		{
			fieldname: "report_date",
			label: __("Fecha de corte"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1
		},
		{
			fieldname: "finance_book",
			label: __("Libro financiero"),
			fieldtype: "Link",
			options: "Finance Book"
		},
		{
			fieldname: "cost_center",
			label: __("Centro de costo"),
			fieldtype: "Link",
			options: "Cost Center",
			get_query: function() {
				return {
					filters: {
						company: frappe.query_report.get_filter_value("company")
					}
				};
			}
		},
		{
			fieldname: "customer",
			label: __("Cliente"),
			fieldtype: "Link",
			options: "Customer",
			reqd: 1
		},
		{
			fieldname: "customer_group",
			label: __("Grupo de clientes"),
			fieldtype: "Link",
			options: "Customer Group"
		},
		{
			fieldname: "payment_terms_template",
			label: __("Plantilla de términos de pago"),
			fieldtype: "Link",
			options: "Payment Terms Template"
		},
		{
			fieldname: "territory",
			label: __("Territorio"),
			fieldtype: "Link",
			options: "Territory"
		},
		{
			fieldname: "sales_partner",
			label: __("Socio comercial"),
			fieldtype: "Link",
			options: "Sales Partner"
		},
		{
			fieldname: "sales_person",
			label: __("Vendedor"),
			fieldtype: "Link",
			options: "Sales Person"
		}
	];
}

frappe.query_reports["Estado de Cuenta"] = {
	filters: get_account_statement_filters()
};

frappe.query_reports["Accounts Receivable Summary"] = {
	filters: get_account_statement_filters()
};

(erpnext.dimension_filters || []).forEach(function(dimension) {
	["Estado de Cuenta", "Accounts Receivable Summary"].forEach(function(report_name) {
		frappe.query_reports[report_name].filters.push({
			fieldname: dimension.fieldname,
			label: __(dimension.label),
			fieldtype: "Link",
			options: dimension.document_type
		});
	});
});
