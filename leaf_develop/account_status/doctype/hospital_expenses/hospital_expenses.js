// Copyright (c) 2021, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Hospital Expenses', {
	// refresh: function(frm) {

	// }
	onload: function(frm) {
		cur_frm.fields_dict['patient_statement'].get_query = function(doc, cdt, cdn) {
			return {
				filters:{'state': "Open", 'acc_sta': ["=","Open"]}
			}
		},

		cur_frm.fields_dict['service'].get_query = function(doc, cdt, cdn) {
			return {
				filters:{'default_company': doc.company}
			}
		}
	}
});
