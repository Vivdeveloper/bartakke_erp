import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Sum
from frappe.model.document import Document

from bartakke_erp.bartakke_erp.doctype.production_process_tracking_work_order.production_process_tracking_work_order import (
	set_work_order_stages_from_template,
)

class ProductionProcessTracking(Document):
    def before_insert(doc, method=None):
        last = frappe.db.sql("""
            SELECT MAX(CAST(lot_no AS UNSIGNED))
            FROM `tabProduction Process Tracking`
        """)[0][0] or 1000

        doc.lot_no = last + 1
        wo = [wo.work_order_no for wo in doc.production_process_tracking_item]
        for i in wo:
            wo_doc = frappe.get_doc("Production Plan", i)
            if wo_doc.docstatus != 1:
                frappe.throw(_("Work Order linked must be submitted"))
            else:
                wo_doc.custom_lot_generated = 1
                wo_doc.save()

    # def validate_qty(doc, method=None):
    #     qty = frappe.db.get_all("Production Plan Item", {'parent': doc.work_order_no}, 'planned_qty')


        

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_assembly_items(doctype, txt, searchfield, start, page_len, filters):
    wo = filters.get("work_order_no")
    if not wo:
        return []

    ProductionPlanItem = frappe.qb.DocType("Production Plan Item")
    PPT = frappe.qb.DocType("Production Process Tracking")
    PPI = DocType("Production Plan Item")

    used_items = (
        frappe.qb.from_(PPT)
        .join(PPI)
        .on(
            (PPT.work_order_no == PPI.parent) &
            (PPT.item == PPI.item_code)
        )
        .select(PPT.item)
        .where(PPT.work_order_no == wo)
        .groupby(PPT.item, PPI.planned_qty)
        .having(Sum(PPT.qty) >= PPI.planned_qty)
    ).run(pluck=True)

   
    query = (
        frappe.qb.from_(ProductionPlanItem)
        .select(ProductionPlanItem.item_code)
        .where(ProductionPlanItem.parent == wo)
    )

    # Ignore already-used items
    if used_items:
        query = query.where(ProductionPlanItem.item_code.notin(used_items))

    # Search text filter
    if txt:
        query = query.where(ProductionPlanItem.item_code.like(f"%{txt}%"))

    query = (
        query.orderby(ProductionPlanItem.item_code)
        .limit(page_len)
        .offset(start)
    )

    return query.run(as_dict=False)

def _work_orders_from_ppt(ppt):
	work_orders = list(
		{
			row.work_order_no
			for row in ppt.get("production_process_tracking_item") or []
			if row.work_order_no
		}
	)
	if not work_orders and ppt.get("work_order_no"):
		work_orders = [ppt.work_order_no]
	return work_orders


def _stage_log_by_stage(ppt):
	return {
		row.stage: row
		for row in ppt.get("production_stage_log") or []
		if row.stage
	}


def _apply_ppt_stage_log_to_work_order(wo_doc, ppt):
	stage_log = _stage_log_by_stage(ppt)
	for stage in wo_doc.get("production_process_tracking_work_order_stages") or []:
		log = stage_log.get(stage.production_stage)
		if not log:
			continue
		stage.completed = log.completed
		stage.completed_by = log.completed_by
		stage.completed_on = log.completed_on
		stage.remarks = log.remarks


@frappe.whitelist()
def create_production_process_tracking_work_orders(source_name, template):
	ppt = frappe.get_doc("Production Process Tracking", source_name)
	work_orders = _work_orders_from_ppt(ppt)

	if not work_orders:
		frappe.throw(_("No Work Order found in Production Process Tracking Item"))

	if not template:
		frappe.throw(_("Production Process Tracking Template is required"))

	created = []
	existing = []

	for wo_name in work_orders:
		if frappe.db.exists("Production Process Tracking Work Order", wo_name):
			existing.append(wo_name)
			continue

		wo_doc = frappe.new_doc("Production Process Tracking Work Order")
		wo_doc.production_plan = wo_name
		wo_doc.production_process_tracking_template = template
		set_work_order_stages_from_template(wo_doc)
		_apply_ppt_stage_log_to_work_order(wo_doc, ppt)

		frappe.flags.skip_ppt_sync = True
		try:
			wo_doc.insert(ignore_permissions=True)
		finally:
			frappe.flags.skip_ppt_sync = False

		created.append(wo_doc.name)

	return {"created": created, "existing": existing}


@frappe.whitelist()
def get_work_order_tracking_map(source_name):
	ppt = frappe.get_doc("Production Process Tracking", source_name)
	result = {}
	for wo_name in _work_orders_from_ppt(ppt):
		result[wo_name] = frappe.db.exists("Production Process Tracking Work Order", wo_name)
	return result


@frappe.whitelist()
def get_work_order_tracking_dashboard(source_name):
	ppt = frappe.get_doc("Production Process Tracking", source_name)
	rows = []
	stage_columns = []
	seen_stages = set()

	for item in ppt.get("production_process_tracking_item") or []:
		wo_name = item.work_order_no
		tracking_name = None
		stage_map = {}
		stage_order = []

		if wo_name and frappe.db.exists("Production Process Tracking Work Order", wo_name):
			wo_doc = frappe.get_doc("Production Process Tracking Work Order", wo_name)
			tracking_name = wo_doc.name
			for stage in wo_doc.get("production_process_tracking_work_order_stages") or []:
				if not stage.production_stage:
					continue
				stage_order.append(stage.production_stage)
				stage_map[stage.production_stage] = {
					"name": stage.name,
					"completed": stage.completed,
					"completed_by": stage.completed_by,
					"completed_on": stage.completed_on,
				}
				if stage.production_stage not in seen_stages:
					stage_columns.append(stage.production_stage)
					seen_stages.add(stage.production_stage)

		rows.append(
			{
				"work_order_no": wo_name,
				"item": item.item,
				"work_order_qty": item.work_order_qty,
				"tracking_name": tracking_name,
				"stage_map": stage_map,
				"stage_order": stage_order,
			}
		)

	if not stage_columns:
		for row in rows:
			for stage_name in row.get("stage_order") or []:
				if stage_name not in seen_stages:
					stage_columns.append(stage_name)
					seen_stages.add(stage_name)

	return {"stage_columns": stage_columns, "rows": rows}


@frappe.whitelist()
def get_planned_qty(work_order_no):
    planned_qty = frappe.db.get_value(
        "Production Plan Item",
        {"parent": work_order_no},
        "planned_qty"
    )

    qty_utilized = sum(frappe.db.get_all("Production Process Tracking", {"work_order_no": work_order_no}, 'qty', pluck = 'qty'))

    return planned_qty - qty_utilized