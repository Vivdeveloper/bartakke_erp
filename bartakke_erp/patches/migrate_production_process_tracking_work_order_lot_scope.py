import frappe

from bartakke_erp.bartakke_erp.doctype.production_process_tracking_work_order.production_process_tracking_work_order import (
	get_tracking_doc_name,
)


def execute():
	for doc in frappe.get_all(
		"Production Process Tracking Work Order",
		fields=["name", "production_plan", "production_process_tracking"],
	):
		if doc.production_process_tracking:
			expected_name = get_tracking_doc_name(
				doc.production_process_tracking, doc.production_plan
			)
			if doc.name != expected_name and not frappe.db.exists(
				"Production Process Tracking Work Order", expected_name
			):
				frappe.rename_doc(
					"Production Process Tracking Work Order",
					doc.name,
					expected_name,
					force=True,
				)
			continue

		lot_name = frappe.db.get_value(
			"Production Process Tracking Item",
			{"work_order_no": doc.production_plan},
			"parent",
			order_by="creation asc",
		)
		if not lot_name:
			continue

		new_name = get_tracking_doc_name(lot_name, doc.production_plan)
		frappe.db.set_value(
			"Production Process Tracking Work Order",
			doc.name,
			"production_process_tracking",
			lot_name,
			update_modified=False,
		)

		if doc.name == new_name:
			continue

		if frappe.db.exists("Production Process Tracking Work Order", new_name):
			continue

		frappe.rename_doc(
			"Production Process Tracking Work Order",
			doc.name,
			new_name,
			force=True,
		)
