import frappe

from bartakke_erp.bartakke_erp.doctype.production_process_tracking_work_order.production_process_tracking_work_order import (
	_build_stage_log_rows,
	_derive_tracking_status,
	get_tracking_doc_for_lot,
)


def execute():
	for ppt_name in frappe.get_all("Production Process Tracking", pluck="name"):
		items = frappe.get_all(
			"Production Process Tracking Item",
			filters={"parent": ppt_name},
			fields=["name", "work_order_no", "current_stage", "overall_status"],
		)
		item_statuses = []

		for item in items:
			wo_name = item.work_order_no
			tracking_name = get_tracking_doc_for_lot(ppt_name, wo_name) if wo_name else None
			if not tracking_name:
				current_stage, overall_status = None, "Open"
			else:
				wo_doc = frappe.get_doc("Production Process Tracking Work Order", tracking_name)
				current_stage, overall_status = _derive_tracking_status(
					_build_stage_log_rows(wo_doc)
				)
				frappe.db.set_value(
					"Production Process Tracking Work Order",
					tracking_name,
					{
						"current_stage": current_stage,
						"overall_status": overall_status,
					},
					update_modified=False,
				)

			frappe.db.set_value(
				"Production Process Tracking Item",
				item.name,
				{
					"current_stage": current_stage,
					"overall_status": overall_status,
				},
				update_modified=False,
			)
			item_statuses.append(
				{"current_stage": current_stage, "overall_status": overall_status}
			)

		parent_stage = None
		parent_status = "Open"
		stages = [row["current_stage"] for row in item_statuses if row["current_stage"]]
		statuses = [row["overall_status"] or "Open" for row in item_statuses]

		if stages:
			parent_stage = stages[0] if len(set(stages)) == 1 else None
		if statuses and all(status == "Completed" for status in statuses):
			parent_status = "Completed"
		elif any(status in ("In Progress", "Completed") for status in statuses):
			parent_status = "In Progress"

		frappe.db.set_value(
			"Production Process Tracking",
			ppt_name,
			{
				"current_stage": parent_stage,
				"overall_status": parent_status,
			},
			update_modified=False,
		)
