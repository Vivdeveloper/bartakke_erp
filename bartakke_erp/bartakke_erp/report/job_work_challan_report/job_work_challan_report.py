# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	filters = filters or {}
	where_clauses = [
	    "po.docstatus = 1",
	    "COALESCE(po.custom_is_jobwork_challan, 0) = 1"
	]
	params = {}

	# ----------------------------
	# Date Filters
	# ----------------------------
	if filters.get("from_date"):
	    where_clauses.append("po.transaction_date >= %(from_date)s")
	    params["from_date"] = filters["from_date"]

	if filters.get("to_date"):
	    where_clauses.append("po.transaction_date <= %(to_date)s")
	    params["to_date"] = filters["to_date"]

	# ----------------------------
	# Other Filters
	# ----------------------------
	if filters.get("purchase_order"):
	    where_clauses.append("po.name = %(purchase_order)s")
	    params["purchase_order"] = filters["purchase_order"]

	if filters.get("supplier"):
	    where_clauses.append("po.supplier = %(supplier)s")
	    params["supplier"] = filters["supplier"]

	if filters.get("trade_type"):
	    where_clauses.append("po.custom_trade_type = %(trade_type)s")
	    params["trade_type"] = filters["trade_type"]

	if filters.get("custom_jobworker__warehouse_"):
	    where_clauses.append("po.custom_jobworker__warehouse_ = %(jobworker_warehouse)s")
	    params["jobworker_warehouse"] = filters["custom_jobworker__warehouse_"]    

	where_sql = " AND ".join(where_clauses)

	# ----------------------------
	# SQL Query
	# ----------------------------
	query = f"""
	SELECT
	    po.name AS job_work_challan,
	    po.transaction_date AS po_date,
	    po.supplier AS supplier,
	    po.schedule_date AS required_by,
	    po.custom_trade_type AS trade_type,
	    po.custom_raw_material_warehouse_ AS raw_material_warehouse,
	    po.custom_jobworker__warehouse_ AS jobworker_warehouse,

	    rm.raw_materials AS raw_materials,
	    COALESCE(rm.total_qty_sent, 0) AS total_qty_sent,

	    fg.fg_items AS fg_items,
	    COALESCE(fg.total_qty_expected, 0) AS total_qty_expected,

	    CASE WHEN po.custom_transfer_completed = 1 THEN 'Yes' ELSE 'No' END AS transfer_completed,

	    po.status AS status,
	    po.custom_challan_amount AS custom_challan_amount 

	FROM `tabPurchase Order` po

	LEFT JOIN (
	    SELECT
	        parent,
	        GROUP_CONCAT(DISTINCT item_name SEPARATOR ', ') AS raw_materials,
	        SUM(qty) AS total_qty_sent
	    FROM `tabPurchase Order Supplier Material`
	    GROUP BY parent
	) rm ON rm.parent = po.name

	LEFT JOIN (
	    SELECT
	        parent,
	        GROUP_CONCAT(DISTINCT item_name SEPARATOR ', ') AS fg_items,
	        SUM(qty) AS total_qty_expected
	    FROM `tabPurchase Order Job Work GRN`
	    GROUP BY parent
	) fg ON fg.parent = po.name

	WHERE {where_sql}

	GROUP BY
	    po.name,
	    po.transaction_date,
	    po.supplier,
	    po.schedule_date,
	    po.custom_trade_type,
	    po.custom_raw_material_warehouse_,
	    po.custom_jobworker__warehouse_,
	    rm.raw_materials,
	    rm.total_qty_sent,
	    fg.fg_items,
	    fg.total_qty_expected,
	    po.custom_transfer_completed,
	    po.status,
	    po.custom_challan_amount 

	ORDER BY
	    po.transaction_date DESC
	"""

	# ----------------------------
	# Execute Query
	# ----------------------------
	result = frappe.db.sql(query, params, as_dict=True)

	# ----------------------------
	# Columns
	# ----------------------------
	columns = [
	    {
	        "label": "Job Work Challan",
	        "fieldname": "job_work_challan",
	        "fieldtype": "Link",
	        "options": "Purchase Order",
	        "width": 150,
	    },
	    {
	        "label": "Date",
	        "fieldname": "po_date",
	        "fieldtype": "Date",
	        "width": 95,
	    },
	    {
	        "label": "Supplier",
	        "fieldname": "supplier",
	        "fieldtype": "Link",
	        "options": "Supplier",
	        "width": 160,
	    },
	    {
	        "label": "Required By",
	        "fieldname": "required_by",
	        "fieldtype": "Date",
	        "width": 95,
	    },
	    {
	        "label": "Trade Type",
	        "fieldname": "trade_type",
	        "fieldtype": "Data",
	        "width": 90,
	    },
	    {
	        "label": "Raw Material Warehouse",
	        "fieldname": "raw_material_warehouse",
	        "fieldtype": "Link",
	        "options": "Warehouse",
	        "width": 160,
	    },
	    {
	        "label": "Job Worker Warehouse",
	        "fieldname": "jobworker_warehouse",
	        "fieldtype": "Link",
	        "options": "Warehouse",
	        "width": 160,
	    },
	    {
	        "label": "Raw Materials Sent",
	        "fieldname": "raw_materials",
	        "fieldtype": "Data",
	        "width": 260,
	    },
	    {
	        "label": "Challan Amount",
	        "fieldname": "custom_challan_amount",
	        "fieldtype": "Float",
	        "width": 130,
	    },
	    {
	        "label": "Total Qty Sent",
	        "fieldname": "total_qty_sent",
	        "fieldtype": "Float",
	        "width": 100,
	    },
	    {
	        "label": "FG Items Expected",
	        "fieldname": "fg_items",
	        "fieldtype": "Data",
	        "width": 260,
	    },
	    {
	        "label": "Total Qty Expected",
	        "fieldname": "total_qty_expected",
	        "fieldtype": "Float",
	        "width": 110,
	    },
	    {
	        "label": "Transfer Completed",
	        "fieldname": "transfer_completed",
	        "fieldtype": "Data",
	        "width": 110,
	    },
	    {
	        "label": "Status",
	        "fieldname": "status",
	        "fieldtype": "Data",
	        "width": 90,
	    },
	]

	# ----------------------------
	# Report Summary
	# ----------------------------
	summary = [
	    {
	        "value": len(result),
	        "label": "Total Job Work Challans",
	        "datatype": "Int",
	    },
	    {
	        "value": sum(d.get("total_qty_sent", 0) for d in result),
	        "label": "Total Raw Material Qty Sent",
	        "datatype": "Float",
	    },
	    {
	        "value": sum(d.get("total_qty_expected", 0) for d in result),
	        "label": "Total FG Qty Expected",
	        "datatype": "Float",
	    },
	    {
	        "value": sum(1 for d in result if d.get("transfer_completed") == "No"),
	        "label": "Pending Transfer",
	        "datatype": "Int",
	    },
	    {
	        "value": sum(d.get("custom_challan_amount", 0) for d in result),
	        "label": "Total Challan Amount",
	        "datatype": "Float",
	    },
	]

	# ----------------------------
	# Return Data
	# ----------------------------
	return columns, result, None, None, summary
