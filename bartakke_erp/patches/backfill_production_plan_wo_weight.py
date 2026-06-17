import frappe

from bartakke_erp.bartakke_erp.api.production_plan import get_total_weight


def execute():
	for name in frappe.get_all(
		"Production Plan",
		filters={"docstatus": ["!=", 2]},
		pluck="name",
	):
		doc = frappe.get_doc("Production Plan", name)
		frappe.db.set_value(
			"Production Plan",
			name,
			"custom_wo_weight_",
			get_total_weight(doc),
			update_modified=False,
		)
