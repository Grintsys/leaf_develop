import frappe


REPORT_NAME = "Estado de Cuenta"
SUMMARY_REPORT_NAME = "Accounts Receivable Summary"


def add_report_link(data):
	if any(item.get("name") == REPORT_NAME
		for section in data for item in section.get("items", [])):
		return data

	for section in data:
		items = section.get("items", [])
		for index, item in enumerate(items):
			if item.get("name") == SUMMARY_REPORT_NAME:
				items.insert(index + 1, {
					"type": "report",
					"name": REPORT_NAME,
					"label": REPORT_NAME,
					"doctype": "GL Entry",
					"is_query_report": 1
				})
				return data

	return data


@frappe.whitelist()
def get_accounts_module_data(module):
	from frappe.desk import moduleview

	response = moduleview.get(module)
	if frappe.scrub(module) != "accounts" or not isinstance(response, dict):
		return response

	if not frappe.db.exists("Report", REPORT_NAME):
		return response

	report = frappe.get_doc("Report", REPORT_NAME)
	if not report.is_permitted() or not frappe.has_permission(report.ref_doctype, "report"):
		return response

	response["data"] = add_report_link(response.get("data") or [])
	return response
