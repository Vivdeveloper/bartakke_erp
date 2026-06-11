import frappe

from bartakke_erp.bartakke_erp.api.production_plan import apply_work_order_metrics_to_ppt


def execute():
	for name in frappe.get_all("Production Process Tracking", pluck="name"):
		doc = frappe.get_doc("Production Process Tracking", name)
		apply_work_order_metrics_to_ppt(doc)
		frappe.db.set_value(
			"Production Process Tracking",
			name,
			{
				"weight_kg": doc.weight_kg,
				"area_sq_mtr_paint": doc.area_sq_mtr_paint,
			},
			update_modified=False,
		)
		for row in doc.get("production_process_tracking_item") or []:
			frappe.db.set_value(
				"Production Process Tracking Item",
				row.name,
				{
					"weight_kg": row.weight_kg,
					"area_sq_mtr_paint": row.area_sq_mtr_paint,
				},
				update_modified=False,
			)
