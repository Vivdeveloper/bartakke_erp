import frappe

from bartakke_erp.bartakke_erp.api.production_plan import apply_work_order_metrics_to_ppt


def execute():
	"""Recompute parent weight/area with split-WO group deduplication."""
	for name in frappe.get_all("Production Process Tracking", pluck="name"):
		doc = frappe.get_doc("Production Process Tracking", name)
		metrics = apply_work_order_metrics_to_ppt(doc)
		frappe.db.set_value(
			"Production Process Tracking",
			name,
			{
				"weight_kg": metrics["weight_kg"],
				"area_sq_mtr_paint": metrics["area_sq_mtr_paint"],
			},
			update_modified=False,
		)
