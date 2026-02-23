import frappe
from frappe.query_builder import DocType

from frappe.model.document import Document

class ProductionProcessTracking(Document):
    def before_insert(doc, method=None):
        last = frappe.db.sql("""
            SELECT MAX(CAST(lot_no AS UNSIGNED))
            FROM `tabProduction Process Tracking`
        """)[0][0] or 1000

        doc.lot_no = last + 1

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_assembly_items(doctype, txt, searchfield, start, page_len, filters):

    wo = filters.get("work_order_no")
    if not wo:
        return []

    ProductionPlanItem = frappe.qb.DocType("Production Plan Item")
    PPT = frappe.qb.DocType("Production Process Tracking")
    used_items = (
        frappe.qb.from_(PPT)
        .select(PPT.item)
        .where(PPT.work_order_no == wo)
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