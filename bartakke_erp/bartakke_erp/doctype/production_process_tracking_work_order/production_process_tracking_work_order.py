# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


def get_template_stage_rows(template):
	if not template:
		return []

	return frappe.get_all(
		"Production Process Tracking Template Item",
		filters={"parent": template},
		fields=["production_stages", "sequence"],
		order_by="sequence asc, idx asc",
	)


def set_work_order_stages_from_template(doc, template=None):
	template = template or doc.production_process_tracking_template
	doc.set("production_process_tracking_work_order_stages", [])

	for row in get_template_stage_rows(template):
		if not row.production_stages:
			continue
		doc.append(
			"production_process_tracking_work_order_stages",
			{"production_stage": row.production_stages},
		)


def _assembly_totals(wo):
	total_area = 0
	total_weight = 0

	for row in wo.get("custom_assembly_item") or []:
		item_data = frappe.db.get_value(
			"Item",
			row.item_code,
			["custom_area", "weight_per_unit"],
			as_dict=True,
		) or {}

		qty = flt(row.qty)
		total_area += flt(item_data.get("custom_area")) * qty
		total_weight += flt(item_data.get("weight_per_unit")) * qty

	return total_area, total_weight


def _mr_dates(indent_no):
	if not indent_no:
		return None, None

	return frappe.db.get_value(
		"Material Request",
		indent_no,
		["transaction_date", "schedule_date"],
	) or (None, None)


def _build_tracking_item_rows(wo):
	total_area, total_weight = _assembly_totals(wo)
	indent_date, indent_received_date = _mr_dates(wo.custom_indent)
	rows = []

	for item in wo.get("po_items") or []:
		rows.append(
			{
				"item": item.item_code,
				"work_order_qty": item.planned_qty,
				"work_order_no": wo.name,
				"indent_no": wo.custom_indent,
				"indent_date": indent_date,
				"indent_received_date": indent_received_date,
				"po_number": wo.custom_customer_po_no,
				"customer_po_date": wo.custom_customer_po_date,
				"delivery_date": wo.custom_customer_delivery,
				"weight_kg": total_weight,
				"area_sq_mtr_paint": total_area,
			}
		)

	return rows, total_area, total_weight


def _build_stage_log_rows(work_order_doc):
	rows = []
	for stage in work_order_doc.get("production_process_tracking_work_order_stages") or []:
		if not stage.production_stage:
			continue
		rows.append(
			{
				"stage": stage.production_stage,
				"completed": stage.completed,
				"completed_by": stage.completed_by,
				"completed_on": stage.completed_on,
				"remarks": stage.remarks,
			}
		)
	return rows


def _derive_tracking_status(stage_rows):
	if not stage_rows:
		return None, "Open"

	incomplete = [row for row in stage_rows if not row.get("completed")]
	if not any(row.get("completed") for row in stage_rows):
		return stage_rows[0].get("stage"), "Open"
	if not incomplete:
		return stage_rows[-1].get("stage"), "Completed"
	return incomplete[0].get("stage"), "In Progress"


def get_linked_production_process_tracking(production_plan):
	return frappe.db.get_value(
		"Production Process Tracking Item",
		{"work_order_no": production_plan},
		"parent",
	)


def _upsert_ppt_item_row(ppt, item_row):
	for row in ppt.get("production_process_tracking_item") or []:
		if row.work_order_no == item_row.get("work_order_no"):
			for field, value in item_row.items():
				row.set(field, value)
			return

	ppt.append("production_process_tracking_item", item_row)


def _merge_stage_log_rows(ppt, work_order_stage_rows):
	existing = {row.stage: row for row in ppt.get("production_stage_log") or [] if row.stage}

	for wo_stage in work_order_stage_rows:
		stage_name = wo_stage.get("stage")
		if not stage_name:
			continue
		if stage_name in existing:
			row = existing[stage_name]
			row.completed = wo_stage.get("completed")
			row.completed_by = wo_stage.get("completed_by")
			row.completed_on = wo_stage.get("completed_on")
			row.remarks = wo_stage.get("remarks")
		else:
			ppt.append("production_stage_log", wo_stage)


def _recalculate_ppt_totals(ppt):
	ppt.weight_kg = sum(flt(row.weight_kg) for row in ppt.get("production_process_tracking_item") or [])
	ppt.area_sq_mtr_paint = sum(
		flt(row.area_sq_mtr_paint) for row in ppt.get("production_process_tracking_item") or []
	)


def _apply_tracking_status(ppt):
	stage_rows = [
		{"stage": row.stage, "completed": row.completed}
		for row in ppt.get("production_stage_log") or []
		if row.stage
	]
	ppt.current_stage, ppt.overall_status = _derive_tracking_status(stage_rows)


def _save_production_process_tracking(ppt, insert=False):
	ppt.flags.ignore_links = True
	if insert:
		ppt.insert(ignore_permissions=True)
	else:
		ppt.save(ignore_permissions=True)


def sync_production_process_tracking(work_order_doc):
	if not work_order_doc.production_plan:
		return None

	wo = frappe.get_doc("Production Plan", work_order_doc.production_plan)
	if wo.docstatus != 1:
		frappe.throw(_("Production Plan {0} must be submitted").format(wo.name))

	item_rows, total_area, total_weight = _build_tracking_item_rows(wo)
	if not item_rows:
		frappe.throw(_("Production Plan {0} has no items").format(wo.name))

	item_row = item_rows[0]
	stage_rows = _build_stage_log_rows(work_order_doc)
	indent_date, indent_received_date = _mr_dates(wo.custom_indent)

	header = {
		"work_order_no": wo.name,
		"customer": wo.custom_customer_name,
		"indent_no": wo.custom_indent,
		"indent_date": indent_date,
		"indent_received_date": indent_received_date,
		"po_number": wo.custom_customer_po_no,
		"customer_po_date": wo.custom_customer_po_date,
		"delivery_date": wo.custom_customer_delivery,
		"item": item_row.get("item"),
		"work_order_qty": item_row.get("work_order_qty"),
	}

	existing = get_linked_production_process_tracking(wo.name)
	if existing:
		ppt = frappe.get_doc("Production Process Tracking", existing)
		ppt.update(header)
		_upsert_ppt_item_row(ppt, item_row)
		_merge_stage_log_rows(ppt, stage_rows)
		_recalculate_ppt_totals(ppt)
		_apply_tracking_status(ppt)
		_save_production_process_tracking(ppt)
		return ppt.name

	current_stage, overall_status = _derive_tracking_status(stage_rows)
	ppt = frappe.new_doc("Production Process Tracking")
	ppt.update(header)
	ppt.current_stage = current_stage
	ppt.overall_status = overall_status
	ppt.weight_kg = total_weight
	ppt.area_sq_mtr_paint = total_area
	_upsert_ppt_item_row(ppt, item_row)
	for row in stage_rows:
		ppt.append("production_stage_log", row)
	_save_production_process_tracking(ppt, insert=True)
	return ppt.name


class ProductionProcessTrackingWorkOrder(Document):
	def before_save(self):
		if not self.production_process_tracking_template:
			return

		if self.is_new() or self.has_value_changed("production_process_tracking_template"):
			set_work_order_stages_from_template(self)

	def after_insert(self):
		if frappe.flags.get("skip_ppt_sync"):
			return

		ppt_name = sync_production_process_tracking(self)
		if ppt_name:
			frappe.msgprint(
				_("Production Process Tracking {0} created").format(
					frappe.utils.get_link_to_form("Production Process Tracking", ppt_name)
				),
				indicator="green",
			)

	def on_update(self):
		if frappe.flags.get("skip_ppt_sync"):
			return
		sync_production_process_tracking(self)


@frappe.whitelist()
def get_stages_from_template(template):
	return [
		{"production_stage": row.production_stages}
		for row in get_template_stage_rows(template)
		if row.production_stages
	]


@frappe.whitelist()
def get_linked_ppt(production_plan):
	return get_linked_production_process_tracking(production_plan)


@frappe.whitelist()
def update_work_order_stage(work_order_name, stage_name, completed):
	completed = frappe.parse_json(completed) if isinstance(completed, str) else completed
	wo_doc = frappe.get_doc("Production Process Tracking Work Order", work_order_name)

	stage_row = next(
		(
			stage
			for stage in wo_doc.get("production_process_tracking_work_order_stages") or []
			if stage.name == stage_name
		),
		None,
	)
	if not stage_row:
		frappe.throw(_("Stage row not found"))

	stage_row.completed = 1 if completed else 0
	if stage_row.completed:
		stage_row.completed_by = stage_row.completed_by or frappe.session.user
		stage_row.completed_on = stage_row.completed_on or frappe.utils.now()
	else:
		stage_row.completed_by = None
		stage_row.completed_on = None

	wo_doc.save(ignore_permissions=True)
	return {"success": True, "work_order_name": wo_doc.name}
