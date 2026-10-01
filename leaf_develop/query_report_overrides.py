from __future__ import unicode_literals

import json
import time

import frappe
from frappe import _
from six import string_types


SUMMARY_REPORT_NAME = "Accounts Receivable Summary"
DETAIL_REPORT_NAME = "Estado de Cuenta"


@frappe.whitelist()
def get_script(report_name):
	from frappe.desk import query_report

	if report_name != SUMMARY_REPORT_NAME:
		return query_report.get_script(report_name)

	query_report.get_report_doc(report_name)
	return query_report.get_script(DETAIL_REPORT_NAME)


@frappe.whitelist()
@frappe.read_only()
def run(report_name, filters=None, user=None, ignore_prepared_report=False, custom_columns=None):
	from frappe.desk import query_report

	if report_name != SUMMARY_REPORT_NAME:
		return query_report.run(report_name, filters, user, ignore_prepared_report, custom_columns)

	report = query_report.get_report_doc(report_name)
	if not frappe.has_permission(report.ref_doctype, "report"):
		frappe.msgprint(_("Must have report permission to access this report."), raise_exception=True)

	if not user:
		user = frappe.session.user
	if filters and isinstance(filters, string_types):
		filters = json.loads(filters)

	start_time = time.time()
	from leaf_develop.account_status.report.estado_de_cuenta.estado_de_cuenta import execute
	columns, result = execute(filters)
	columns = [query_report.get_column_as_dict(column) for column in columns]
	result = query_report.normalize_result(result, columns)
	if result:
		result = query_report.get_filtered_data(report.ref_doctype, columns, result, user)

	return build_report_response(columns, result, time.time() - start_time)


def build_report_response(columns, result, execution_time=0):
	return {
		"result": result,
		"columns": columns,
		"message": None,
		"chart": None,
		"report_summary": None,
		"skip_total_row": 1,
		"status": None,
		"execution_time": execution_time,
		"add_total_row": False
	}


@frappe.whitelist()
def export_query():
	from frappe.desk import query_report

	data = frappe._dict(frappe.local.form_dict)
	if data.get("report_name") != SUMMARY_REPORT_NAME:
		return query_report.export_query()

	report = query_report.get_report_doc(SUMMARY_REPORT_NAME)
	frappe.permissions.can_export(report.ref_doctype, raise_exception=True)
	filters = data.get("filters") or {}
	if isinstance(filters, string_types):
		filters = json.loads(filters)

	result = frappe._dict(run(SUMMARY_REPORT_NAME, filters=filters, user=data.get("user")))
	if data.get("file_format_type") != "Excel":
		return

	columns = query_report.get_columns_dict(result.columns)
	visible_idx = data.get("visible_idx") or list(range(len(result.result)))
	if isinstance(visible_idx, string_types):
		visible_idx = json.loads(visible_idx)

	include_indentation = data.get("include_indentation")
	xlsx_data, column_widths = query_report.build_xlsx_data(
		columns, result, visible_idx, include_indentation
	)
	from frappe.utils.xlsxutils import make_xlsx
	xlsx_file = make_xlsx(xlsx_data, SUMMARY_REPORT_NAME, column_widths=column_widths)
	frappe.response["filename"] = SUMMARY_REPORT_NAME + ".xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"