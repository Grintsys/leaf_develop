from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.desk.reportview import build_match_conditions
from frappe.utils import flt, getdate, nowdate
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions
from erpnext.accounts.utils import get_currency_precision


def execute(filters=None):
	filters = frappe._dict(filters or {})
	company = filters.get("company") or frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		frappe.throw(_("Seleccione una empresa."))

	if not frappe.db.exists("Company", company):
		frappe.throw(_("La empresa seleccionada no existe."))

	if not filters.get("customer"):
		frappe.throw(_("Seleccione un cliente."))

	filters.company = company
	filters.report_date = getdate(filters.get("report_date") or nowdate())
	customer = frappe.get_doc("Customer", filters.customer)
	if not frappe.has_permission("Customer", "read", doc=customer):
		frappe.throw(_("No tiene permiso para consultar este cliente."), frappe.PermissionError)

	conditions, values = get_conditions(filters)
	company_currency = frappe.get_cached_value("Company", company, "default_currency")
	columns = get_columns(company_currency)
	data = frappe.db.sql("""
		select
			posting_date, party, voucher_type, voucher_no, min(creation) as transaction_order,
			max(remarks) as remarks,
			sum(debit) as debit, sum(credit) as credit
		from `tabGL Entry`
		where {conditions}
		group by party, posting_date, voucher_type, voucher_no
		order by party, posting_date, transaction_order, voucher_type, voucher_no
	""".format(conditions=conditions), values, as_dict=True)

	customer_documents = get_customer_documents(filters)
	add_customer_document_rows(data, customer_documents)
	add_payment_application_details(data)
	add_payment_entry_details(data)
	add_invoice_outstanding(data)
	sort_statement_rows(data)

	precision = get_currency_precision() or 2
	set_running_balance(data, company_currency, precision)
	return columns, data


def get_conditions(filters):
	conditions = [
		"`tabGL Entry`.docstatus < 2",
		"`tabGL Entry`.party_type = 'Customer'",
		"ifnull(`tabGL Entry`.party, '') != ''",
		"`tabGL Entry`.company = %(company)s",
		"`tabGL Entry`.posting_date <= %(report_date)s",
		"exists (select 1 from `tabAccount` account where account.name = `tabGL Entry`.account "
		"and account.company = %(company)s and account.account_type = 'Receivable')"
	]
	values = {
		"company": filters.company,
		"report_date": filters.report_date
	}

	if filters.get("finance_book"):
		conditions.append("ifnull(`tabGL Entry`.finance_book, '') in (%(finance_book)s, '')")
		values["finance_book"] = filters.finance_book

	if filters.get("cost_center"):
		conditions.append("`tabGL Entry`.cost_center = %(cost_center)s")
		values["cost_center"] = filters.cost_center

	if filters.get("customer"):
		conditions.append("`tabGL Entry`.party = %(customer)s")
		values["customer"] = filters.customer

	add_customer_tree_filter(conditions, values, filters, "customer_group", "Customer Group")
	add_customer_tree_filter(conditions, values, filters, "territory", "Territory")

	if filters.get("payment_terms_template"):
		conditions.append("`tabGL Entry`.party in (select name from `tabCustomer` "
			"where payment_terms = %(payment_terms_template)s)")
		values["payment_terms_template"] = filters.payment_terms_template

	if filters.get("sales_partner"):
		conditions.append("`tabGL Entry`.party in (select name from `tabCustomer` "
			"where default_sales_partner = %(sales_partner)s)")
		values["sales_partner"] = filters.sales_partner

	if filters.get("sales_person"):
		left, right = get_tree_bounds("Sales Person", filters.sales_person)
		conditions.append("""exists (
			select 1 from `tabSales Team` sales_team
			where sales_team.sales_person in (
				select sales_person.name from `tabSales Person` sales_person
				where sales_person.lft >= %(sales_person_left)s
				and sales_person.rgt <= %(sales_person_right)s
			)
			and (
				(sales_team.parent = `tabGL Entry`.party and sales_team.parenttype = 'Customer')
				or (sales_team.parent = `tabGL Entry`.voucher_no
					and sales_team.parenttype = `tabGL Entry`.voucher_type)
				or (sales_team.parent = `tabGL Entry`.against_voucher
					and sales_team.parenttype = `tabGL Entry`.against_voucher_type)
			)
		)""")
		values["sales_person_left"] = left
		values["sales_person_right"] = right

	for dimension in get_accounting_dimensions():
		if filters.get(dimension):
			conditions.append("`tabGL Entry`.`{0}` = %({0})s".format(dimension))
			values[dimension] = filters.get(dimension)

	match_conditions = build_match_conditions("GL Entry")
	if match_conditions:
		conditions.append(match_conditions)

	return " and ".join(conditions), values


def get_customer_documents(filters):
	if not customer_matches_filters(filters):
		return []

	if any(filters.get(dimension) for dimension in get_accounting_dimensions()):
		return []

	document_filters = {
		"company": filters.company,
		"customer": filters.customer,
		"docstatus": 1,
		"posting_date": ["<=", filters.report_date]
	}
	if filters.get("cost_center"):
		document_filters["cost_center"] = filters.cost_center

	documents = []
	page_size = 500
	start = 0
	while True:
		page = frappe.get_all("Customer Documents", fields=["name", "customer", "posting_date",
			"creation", "document_number", "total"], filters=document_filters,
			order_by="posting_date asc, creation asc, name asc",
			limit_start=start, limit_page_length=page_size)
		if not page:
			break
		documents.extend(page)
		if len(page) < page_size:
			break
		start += page_size

	return documents


def customer_matches_filters(filters):
	customer = frappe.db.get_value("Customer", filters.customer,
		["customer_group", "territory", "payment_terms", "default_sales_partner"], as_dict=True)
	if not customer:
		return False

	if filters.get("customer_group") and not is_in_tree("Customer Group", customer.customer_group,
		filters.customer_group):
		return False

	if filters.get("territory") and not is_in_tree("Territory", customer.territory, filters.territory):
		return False

	if filters.get("payment_terms_template") and customer.payment_terms != filters.payment_terms_template:
		return False

	if filters.get("sales_partner") and customer.default_sales_partner != filters.sales_partner:
		return False

	if filters.get("sales_person"):
		left, right = get_tree_bounds("Sales Person", filters.sales_person)
		sales_people = frappe.get_all("Sales Person", filters={"lft": [">=", left], "rgt": ["<=", right]},
			fields=["name"])
		sales_person_names = [sales_person.name for sales_person in sales_people]
		if not frappe.get_all("Sales Team", filters={"parent": filters.customer, "parenttype": "Customer",
			"sales_person": ["in", sales_person_names]}, fields=["name"], limit_page_length=1):
			return False

	return True


def is_in_tree(doctype, child, parent):
	if not child:
		return False

	child_left, child_right = get_tree_bounds(doctype, child)
	parent_left, parent_right = get_tree_bounds(doctype, parent)
	return child_left >= parent_left and child_right <= parent_right


def add_customer_document_rows(rows, documents):
	existing_vouchers = set((row.get("party"), row.get("voucher_type"), row.get("voucher_no"))
		for row in rows)
	for document in documents:
		voucher = (document.get("customer"), "Customer Documents", document.get("name"))
		if voucher in existing_vouchers:
			continue

		rows.append({
			"posting_date": document.get("posting_date"),
			"transaction_order": document.get("creation") or document.get("posting_date"),
			"party": document.get("customer"),
			"voucher_type": "Customer Documents",
			"voucher_no": document.get("name"),
			"remarks": document.get("document_number"),
			"debit": document.get("total"),
			"credit": 0
		})
		existing_vouchers.add(voucher)
	return rows


def add_payment_application_details(rows, references=None):
	payment_names = list(set(row.get("voucher_no") for row in rows
		if row.get("voucher_type") == "Payment Entry"))
	if not payment_names:
		return rows

	if references is None:
		references = frappe.get_all("Payment Entry Reference",
			fields=["parent", "reference_doctype", "reference_name", "allocated_amount"],
			filters={"parent": ["in", payment_names], "parenttype": "Payment Entry"},
			order_by="parent asc, idx asc")

	applications_by_payment = {}
	for reference in references:
		applications_by_payment.setdefault(reference.get("parent"), [])
		document_type = reference.get("reference_doctype")
		if document_type == "Sales Invoice":
			document_label = _("Factura")
		else:
			document_label = _(document_type)
		applications_by_payment[reference.get("parent")].append(
			"{0} {1}: {2}".format(document_label, reference.get("reference_name"),
				flt(reference.get("allocated_amount")))
		)

	for row in rows:
		if row.get("voucher_type") == "Payment Entry":
			row["applications"] = " | ".join(applications_by_payment.get(row.get("voucher_no"), []))
	return rows


def add_payment_entry_details(rows, payments=None):
	payment_names = list(set(row.get("voucher_no") for row in rows
		if row.get("voucher_type") == "Payment Entry"))
	if not payment_names:
		return rows

	if payments is None:
		payments = frappe.get_all("Payment Entry",
			fields=["name", "status", "reason_payment", "mode_of_payment", "paid_amount",
				"total_allocated_amount", "unallocated_amount", "difference_amount",
				"reference_no", "reference_date", "user"],
			filters={"name": ["in", payment_names]})

	payments_by_name = {payment.get("name"): payment for payment in payments}
	for row in rows:
		if row.get("voucher_type") != "Payment Entry":
			continue
		payment = payments_by_name.get(row.get("voucher_no"))
		if payment:
			row.update({
				"payment_status": payment.get("status"),
				"reason_payment": payment.get("reason_payment"),
				"mode_of_payment": payment.get("mode_of_payment"),
				"paid_amount": payment.get("paid_amount"),
				"total_allocated_amount": payment.get("total_allocated_amount"),
				"unallocated_amount": payment.get("unallocated_amount"),
				"difference_amount": payment.get("difference_amount"),
				"reference_no": payment.get("reference_no"),
				"reference_date": payment.get("reference_date"),
				"created_by": payment.get("user")
			})
	return rows


def add_invoice_outstanding(rows, invoices=None):
	invoice_names = list(set(row.get("voucher_no") for row in rows
		if row.get("voucher_type") == "Sales Invoice"))
	if not invoice_names:
		return rows

	if invoices is None:
		invoices = frappe.get_all("Sales Invoice",
			fields=["name", "due_date", "outstanding_amount"],
			filters={"name": ["in", invoice_names]})

	invoices_by_name = {invoice.get("name"): invoice for invoice in invoices}
	for row in rows:
		if row.get("voucher_type") != "Sales Invoice":
			continue
		invoice = invoices_by_name.get(row.get("voucher_no"))
		if invoice:
			row["due_date"] = invoice.get("due_date")
			row["document_outstanding"] = invoice.get("outstanding_amount")
	return rows


def sort_statement_rows(rows):
	rows.sort(key=lambda row: (
		row.get("party") or "",
		getdate(row.get("posting_date")),
		row.get("transaction_order") or row.get("posting_date"),
		row.get("voucher_type") or "",
		row.get("voucher_no") or ""
	))
	for row in rows:
		row.pop("transaction_order", None)
	return rows


def add_customer_tree_filter(conditions, values, filters, filter_name, doctype):
	if not filters.get(filter_name):
		return

	left, right = get_tree_bounds(doctype, filters.get(filter_name))
	left_key = filter_name + "_left"
	right_key = filter_name + "_right"
	customer_field = frappe.scrub(filter_name)
	conditions.append("""`tabGL Entry`.party in (
		select customer.name from `tabCustomer` customer
		where customer.`{customer_field}` in (
			select tree_node.name from `tab{doctype}` tree_node
			where tree_node.lft >= %({left_key})s and tree_node.rgt <= %({right_key})s
		)
	)""".format(customer_field=customer_field, doctype=doctype,
		left_key=left_key, right_key=right_key))
	values[left_key] = left
	values[right_key] = right


def get_tree_bounds(doctype, name):
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("El filtro seleccionado no existe."))
	return frappe.db.get_value(doctype, name, ["lft", "rgt"])


def set_running_balance(rows, currency, precision):
	balance_by_customer = {}
	for row in rows:
		customer = row.get("party")
		balance = balance_by_customer.get(customer, 0)
		balance = flt(balance + flt(row.get("debit")) - flt(row.get("credit")), precision)
		balance_by_customer[customer] = balance
		row["balance"] = balance
		row["currency"] = currency
	return rows


def get_columns(currency):
	return [
		{"label": _("Cliente"), "fieldname": "party", "fieldtype": "Link", "options": "Customer", "width": 180},
		{"label": _("Fecha"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Tipo de documento"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 150},
		{"label": _("Documento"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link",
			"options": "voucher_type", "width": 180},
		{"label": _("Fecha de vencimiento"), "fieldname": "due_date", "fieldtype": "Date", "width": 120},
		{"label": _("Descripción"), "fieldname": "remarks", "fieldtype": "Text", "width": 220},
		{"label": _("Aplicado a"), "fieldname": "applications", "fieldtype": "Text", "width": 260},
		{"label": _("Estado del pago"), "fieldname": "payment_status", "fieldtype": "Data", "width": 120},
		{"label": _("Motivo del pago"), "fieldname": "reason_payment", "fieldtype": "Data", "width": 150},
		{"label": _("Método de pago"), "fieldname": "mode_of_payment", "fieldtype": "Link",
			"options": "Mode of Payment", "width": 150},
		{"label": _("Monto pagado"), "fieldname": "paid_amount", "fieldtype": "Currency",
			"options": "currency", "width": 120},
		{"label": _("Monto aplicado"), "fieldname": "total_allocated_amount", "fieldtype": "Currency",
			"options": "currency", "width": 120},
		{"label": _("Monto sin asignar"), "fieldname": "unallocated_amount", "fieldtype": "Currency",
			"options": "currency", "width": 120},
		{"label": _("Referencia"), "fieldname": "reference_no", "fieldtype": "Data", "width": 140},
		{"label": _("Fecha de referencia"), "fieldname": "reference_date", "fieldtype": "Date", "width": 120},
		{"label": _("Debe ({0})").format(currency), "fieldname": "debit", "fieldtype": "Currency",
			"options": "currency", "width": 120},
		{"label": _("Haber ({0})").format(currency), "fieldname": "credit", "fieldtype": "Currency",
			"options": "currency", "width": 120},
		{"label": _("Pendiente del documento"), "fieldname": "document_outstanding",
			"fieldtype": "Currency", "options": "currency", "width": 150},
		{"label": _("Saldo ({0})").format(currency), "fieldname": "balance", "fieldtype": "Currency",
			"options": "currency", "width": 130},
		{"label": _("Moneda"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80}
	]
