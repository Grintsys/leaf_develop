import unittest
from unittest.mock import patch

import frappe
from leaf_develop.moduleview import add_report_link
from leaf_develop.account_status.report.estado_de_cuenta.estado_de_cuenta import (
	add_customer_document_rows,
	add_invoice_outstanding,
	add_payment_application_details,
	add_payment_entry_details,
	get_columns,
	get_conditions,
	sort_statement_rows,
	set_running_balance
)
from leaf_develop.query_report_overrides import build_report_response


class TestAccountStatement(unittest.TestCase):
	def test_running_balance_tracks_debits_and_customer_credits(self):
		rows = [
			{"party": "CUST-001", "debit": 100, "credit": 0},
			{"party": "CUST-001", "debit": 0, "credit": 125},
			{"party": "CUST-002", "debit": 0, "credit": 50}
		]

		set_running_balance(rows, "HNL", 2)

		self.assertEqual([row["balance"] for row in rows], [100, -25, -50])
		self.assertEqual([row["currency"] for row in rows], ["HNL", "HNL", "HNL"])

	def test_link_is_inserted_after_accounts_receivable_summary(self):
		data = [{
			"label": "Accounts Receivable",
			"items": [
				{"type": "report", "name": "Accounts Receivable"},
				{"type": "report", "name": "Accounts Receivable Summary"},
				{"type": "report", "name": "Sales Register"}
			]
		}]

		add_report_link(data)

		items = data[0]["items"]
		self.assertEqual(items[2]["name"], "Estado de Cuenta")
		self.assertEqual(items[3]["name"], "Sales Register")

	def test_link_insertion_is_idempotent(self):
		data = [{"items": [{"name": "Accounts Receivable Summary"}]}]

		add_report_link(data)
		add_report_link(data)

		self.assertEqual([item["name"] for item in data[0]["items"]],
			["Accounts Receivable Summary", "Estado de Cuenta"])

	def test_link_is_not_added_without_native_summary(self):
		data = [{"items": [{"name": "Accounts Receivable"}]}]

		add_report_link(data)

		self.assertEqual(data[0]["items"], [{"name": "Accounts Receivable"}])

	@patch(
		"leaf_develop.account_status.report.estado_de_cuenta.estado_de_cuenta.get_accounting_dimensions",
		return_value=[]
	)
	@patch("leaf_develop.account_status.report.estado_de_cuenta.estado_de_cuenta.build_match_conditions",
		return_value="`tabGL Entry`.owner = 'accounts@example.com'")
	def test_query_uses_receivable_entries_cutoff_and_permissions(self, match_conditions, dimensions):
		conditions, values = get_conditions(frappe._dict({
			"company": "Test Company",
			"report_date": "2025-01-31"
		}))

		self.assertIn("account.account_type = 'Receivable'", conditions)
		self.assertIn("posting_date <= %(report_date)s", conditions)
		self.assertIn("`tabGL Entry`.owner = 'accounts@example.com'", conditions)
		self.assertEqual(values["company"], "Test Company")
		self.assertEqual(str(values["report_date"]), "2025-01-31")

	def test_columns_include_debit_credit_and_running_balance(self):
		fieldnames = [column["fieldname"] for column in get_columns("HNL")]

		self.assertIn("debit", fieldnames)
		self.assertIn("credit", fieldnames)
		self.assertIn("balance", fieldnames)
		self.assertNotIn("range1", fieldnames)
		self.assertIn("applications", fieldnames)
		self.assertIn("paid_amount", fieldnames)
		self.assertIn("document_outstanding", fieldnames)

	def test_native_summary_response_has_details_without_total_row(self):
		rows = [
			{"voucher_type": "Sales Invoice", "voucher_no": "INV-001", "debit": 100, "credit": 0},
			{"voucher_type": "Payment Entry", "voucher_no": "PAY-001", "debit": 0, "credit": 100}
		]
		response = build_report_response(get_columns("HNL"), rows)

		self.assertEqual(len(response["result"]), 2)
		self.assertFalse(response["add_total_row"])
		self.assertEqual(response["result"][0]["voucher_no"], "INV-001")

	def test_off_ledger_customer_document_adds_one_debit(self):
		rows = []
		documents = [{
			"name": "CD-001",
			"customer": "CUST-001",
			"posting_date": "2025-01-10",
			"document_number": "FISCAL-001",
			"total": 250
		}]

		add_customer_document_rows(rows, documents)

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["voucher_type"], "Customer Documents")
		self.assertEqual(rows[0]["debit"], 250)
		self.assertEqual(rows[0]["credit"], 0)

	def test_customer_document_with_receivable_gl_is_not_duplicated(self):
		rows = [{
			"party": "CUST-001",
			"voucher_type": "Customer Documents",
			"voucher_no": "CD-001",
			"debit": 250,
			"credit": 0
		}]
		documents = [{
			"name": "CD-001",
			"customer": "CUST-001",
			"posting_date": "2025-01-10",
			"document_number": "FISCAL-001",
			"total": 250
		}]

		add_customer_document_rows(rows, documents)

		self.assertEqual(len(rows), 1)

	def test_payment_application_details_show_each_invoice_allocation(self):
		rows = [{
			"voucher_type": "Payment Entry",
			"voucher_no": "ACC-PAY-001"
		}]
		references = [
			{"parent": "ACC-PAY-001", "reference_doctype": "Sales Invoice",
				"reference_name": "INV-001", "allocated_amount": 10000},
			{"parent": "ACC-PAY-001", "reference_doctype": "Sales Invoice",
				"reference_name": "INV-002", "allocated_amount": 10000}
		]

		add_payment_application_details(rows, references)

		self.assertIn("INV-001: 10000.0", rows[0]["applications"])
		self.assertIn("INV-002: 10000.0", rows[0]["applications"])

	def test_payment_entry_details_include_payment_entry_cxc_fields(self):
		rows = [{"voucher_type": "Payment Entry", "voucher_no": "PAY-001"}]
		payments = [{
			"name": "PAY-001",
			"status": "Submitted",
			"reason_payment": "Advance",
			"mode_of_payment": "Transferencia",
			"paid_amount": 20000,
			"total_allocated_amount": 20000,
			"unallocated_amount": 0,
			"difference_amount": 0,
			"reference_no": "BANK-001",
			"reference_date": "2026-09-30",
			"user": "accounts@example.com"
		}]

		add_payment_entry_details(rows, payments)

		self.assertEqual(rows[0]["paid_amount"], 20000)
		self.assertEqual(rows[0]["total_allocated_amount"], 20000)
		self.assertEqual(rows[0]["mode_of_payment"], "Transferencia")
		self.assertEqual(rows[0]["reference_no"], "BANK-001")

	def test_invoice_details_include_outstanding_amount(self):
		rows = [{"voucher_type": "Sales Invoice", "voucher_no": "INV-001"}]
		invoices = [{"name": "INV-001", "due_date": "2026-10-15", "outstanding_amount": 250}]

		add_invoice_outstanding(rows, invoices)

		self.assertEqual(rows[0]["due_date"], "2026-10-15")
		self.assertEqual(rows[0]["document_outstanding"], 250)

	def test_same_day_invoices_precede_the_payment_in_running_balance(self):
		rows = [
			{"posting_date": "2026-09-30", "transaction_order": "2026-09-30 12:00:00",
				"voucher_type": "Payment Entry", "voucher_no": "PAY-001", "party": "CUST-001",
				"debit": 0, "credit": 20000},
			{"posting_date": "2026-09-30", "transaction_order": "2026-09-30 09:00:00",
				"voucher_type": "Sales Invoice", "voucher_no": "INV-001", "party": "CUST-001",
				"debit": 10000, "credit": 0},
			{"posting_date": "2026-09-30", "transaction_order": "2026-09-30 10:00:00",
				"voucher_type": "Sales Invoice", "voucher_no": "INV-002", "party": "CUST-001",
				"debit": 20000, "credit": 0}
		]

		sort_statement_rows(rows)
		set_running_balance(rows, "HNL", 2)

		self.assertEqual([row["voucher_no"] for row in rows], ["INV-001", "INV-002", "PAY-001"])
		self.assertEqual([row["balance"] for row in rows], [10000, 30000, 10000])
		self.assertNotIn("transaction_order", rows[0])
