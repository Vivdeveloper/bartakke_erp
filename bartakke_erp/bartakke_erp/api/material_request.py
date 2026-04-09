import frappe
from frappe import _
import json


@frappe.whitelist()
def create_production_plan(material_request):
	"""
	Create a Production Plan from a Material Request
	"""
	mr = frappe.get_doc("Material Request", material_request)

	if mr.material_request_type != "Manufacture":
		frappe.throw(_("Material Request must be of type Manufacture"))

	# if mr.docstatus != 1:
		# frappe.throw(_("Material Request must be submitted"))

	# Check if all items are already fully planned
	pending_items = get_pending_items_for_production_plan(material_request)

	if not pending_items:
		frappe.throw(_("All items from this Material Request have already been fully planned in Production Plans"))

	# Create Production Plan
	pp = frappe.new_doc("Production Plan")
	pp.company = mr.company
	pp.get_items_from = "Material Request"

	# Add material request reference
	pp.append("material_requests", {
		"material_request": mr.name,
		"material_request_date": mr.transaction_date
	})

	# Add only pending items to production plan
	for item_data in pending_items:
		pp.append("po_items", {
			"item_code": item_data["item_code"],
			"bom_no": item_data["bom_no"],
			"planned_qty": item_data["pending_qty"],
			"stock_uom": item_data["stock_uom"],
			"warehouse": item_data["warehouse"],
			"description": item_data["description"],
			"material_request": mr.name,
			"material_request_item": item_data["material_request_item"],
			"planned_start_date": frappe.utils.now()
		})

		bom = frappe.get_doc("BOM", item_data["bom_no"])
		if bom.exploded_items:
			for exploded in bom.exploded_items:
				if frappe.db.get_value("Item", exploded.item_code, 'custom_parent_item_group') == "Assembly Item":
					pp.append("custom_assembly_item", {
						"item_code": exploded.item_code,
						"item_name": exploded.item_name,
						"item_description": exploded.description,
						"uom": exploded.stock_uom,
						"qty": exploded.stock_qty
					}) 

	pp.insert()

	frappe.msgprint(_("Production Plan {0} created successfully").format(pp.name))

	return pp.name


@frappe.whitelist()
def get_pending_items_for_production_plan(material_request):
	"""
	Get items from Material Request that still have pending quantity to be planned
	"""
	mr = frappe.get_doc("Material Request", material_request)

	# Get all planned quantities for this material request from existing production plans
	planned_qtys = {}

	production_plan_items = frappe.db.sql("""
		SELECT
			ppi.material_request_item,
			SUM(ppi.planned_qty) as total_planned_qty
		FROM `tabProduction Plan Item` ppi
		INNER JOIN `tabProduction Plan` pp ON pp.name = ppi.parent
		WHERE ppi.material_request = %s
			AND pp.docstatus != 2
		GROUP BY ppi.material_request_item
	""", (material_request,), as_dict=1)

	for row in production_plan_items:
		planned_qtys[row.material_request_item] = row.total_planned_qty or 0

	# Calculate pending items
	pending_items = []

	for item in mr.items:
		if item.item_code:
			already_planned = planned_qtys.get(item.name, 0)
			pending_qty = item.qty - already_planned

			if pending_qty > 0:
				pending_items.append({
					"item_code": item.item_code,
					"bom_no": item.bom_no,
					"pending_qty": pending_qty,
					"requested_qty": item.qty,
					"already_planned": already_planned,
					"stock_uom": item.stock_uom,
					"warehouse": item.warehouse,
					"description": item.description,
					"material_request_item": item.name
				})

	return pending_items


@frappe.whitelist()
def update_material_request_qty(material_request, items):
	"""
	Update Material Request item quantities after submission
	"""
	if isinstance(items, str):
		items = json.loads(items)

	mr = frappe.get_doc("Material Request", material_request)

	if mr.material_request_type != "Manufacture":
		frappe.throw(_("Material Request must be of type Manufacture"))

	# if mr.docstatus != 1:
	# 	frappe.throw(_("Material Request must be submitted to update quantities"))

	# Get already planned quantities for all items
	planned_qtys = {}
	production_plan_items = frappe.db.sql("""
		SELECT
			ppi.material_request_item,
			SUM(ppi.planned_qty) as total_planned_qty,
			ppi.item_code
		FROM `tabProduction Plan Item` ppi
		INNER JOIN `tabProduction Plan` pp ON pp.name = ppi.parent
		WHERE ppi.material_request = %s
			AND pp.docstatus != 2
		GROUP BY ppi.material_request_item
	""", (material_request,), as_dict=1)

	for row in production_plan_items:
		planned_qtys[row.material_request_item] = {
			"qty": row.total_planned_qty or 0,
			"item_code": row.item_code
		}

	# Update quantities
	for item_update in items:
		item_name = item_update.get("name")
		new_qty = item_update.get("qty")

		if not item_name or new_qty is None:
			continue

		# Check if new qty is lower than already planned qty
		if item_name in planned_qtys:
			already_planned = planned_qtys[item_name]["qty"]
			item_code = planned_qtys[item_name]["item_code"]

			if new_qty < already_planned:
				frappe.throw(
					_("Cannot update quantity for item {0}. New quantity {1} is lower than already planned quantity {2} in Production Plans").format(
						item_code, new_qty, already_planned
					)
				)

		# Update only the qty field
		frappe.db.sql("""
			UPDATE `tabMaterial Request Item`
			SET qty = %s
			WHERE name = %s
		""", (new_qty, item_name))

	# Commit the database changes
	frappe.db.commit()

	frappe.msgprint(_("Material Request quantities updated successfully"))

	return True