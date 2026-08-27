# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):


	filters = filters or {}

	# --------------------------------
	# Conditions
	# --------------------------------

	where_clauses = ["docstatus < 2"]
	params = {}

	if filters.get("from_date"):
	    where_clauses.append("creation >= %(from_date)s")
	    params["from_date"] = filters["from_date"]

	if filters.get("to_date"):
	    where_clauses.append("creation <= %(to_date)s")
	    params["to_date"] = filters["to_date"]

	if filters.get("item_group"):
	    where_clauses.append("item_group = %(item_group)s")
	    params["item_group"] = filters["item_group"]

	where_sql = " AND ".join(where_clauses)

	# --------------------------------
	# Query
	# --------------------------------

	query = f"""

	SELECT

	    creation,
	    item_group

	FROM `tabDrawing`

	WHERE {where_sql}

	ORDER BY creation

	"""

	result = frappe.db.sql(query, params, as_dict=True)

	# --------------------------------
	# Month Mapping
	# --------------------------------

	month_map = {
	    4: "apr",
	    5: "may",
	    6: "jun",
	    7: "jul",
	    8: "aug",
	    9: "sep",
	    10: "oct",
	    11: "nov",
	    12: "dec",
	    1: "jan",
	    2: "feb",
	    3: "mar",
	}

	months = [
	    "apr",
	    "may",
	    "jun",
	    "jul",
	    "aug",
	    "sep",
	    "oct",
	    "nov",
	    "dec",
	    "jan",
	    "feb",
	    "mar",
	]

	# --------------------------------
	# Initial Rows
	# --------------------------------

	rows = {

	    "Standard Drawing": {
	        "drawing_type": "Standard Drawing"
	    },

	    "Special Drawing": {
	        "drawing_type": "Special Drawing"
	    },

	    "Cutout Drawing": {
	        "drawing_type": "Cutout Drawing"
	    }

	}

	for row in rows.values():

	    for m in months:

	        row[m] = 0

	# --------------------------------
	# Populate Data
	# --------------------------------

	for d in result:

	    month = month_map.get(d.creation.month)

	    if d.item_group == "Standard Item":

	        rows["Standard Drawing"][month] = (
	            rows["Standard Drawing"][month] + 1
	        )

	    elif d.item_group == "Specialised Item":

	        rows["Special Drawing"][month] = (
	            rows["Special Drawing"][month] + 1
	        )

	    elif d.item_group == "Cutout Item":

	        rows["Cutout Drawing"][month] = (
	            rows["Cutout Drawing"][month] + 1
	        )

	# --------------------------------
	# Final Data
	# --------------------------------

	report_data = []

	monthly_total = {
	    "drawing_type": "Monthly Total Qty"
	}

	for m in months:
	    monthly_total[m] = 0

	grand_total = 0

	for row in rows.values():

	    total = 0

	    for m in months:

	        total = total + row[m]

	        monthly_total[m] = monthly_total[m] + row[m]

	    row["year_total"] = total

	    grand_total = grand_total + total

	    report_data.append(row)

	monthly_total["year_total"] = grand_total

	report_data.append(monthly_total)

	# --------------------------------
	# Columns
	# --------------------------------

	columns = [

	    {
	        "label":"Drawing Type",
	        "fieldname":"drawing_type",
	        "fieldtype":"Data",
	        "width":180,
	    },

	    {
	        "label":"April",
	        "fieldname":"apr",
	        "fieldtype":"Int",
	        "width":70,
	    },

	    {
	        "label":"May",
	        "fieldname":"may",
	        "fieldtype":"Int",
	        "width":70,
	    },

	    {
	        "label":"June",
	        "fieldname":"jun",
	        "fieldtype":"Int",
	        "width":70,
	    },

	    {
	        "label":"July",
	        "fieldname":"jul",
	        "fieldtype":"Int",
	        "width":70,
	    },

	    {
	        "label":"August",
	        "fieldname":"aug",
	        "fieldtype":"Int",
	        "width":70,
	    },

	    {
	        "label":"September",
	        "fieldname":"sep",
	        "fieldtype":"Int",
	        "width":80,
	    },

	    {
	        "label":"October",
	        "fieldname":"oct",
	        "fieldtype":"Int",
	        "width":70,
	    },

	    {
	        "label":"November",
	        "fieldname":"nov",
	        "fieldtype":"Int",
	        "width":80,
	    },

	    {
	        "label":"December",
	        "fieldname":"dec",
	        "fieldtype":"Int",
	        "width":80,
	    },

	    {
	        "label":"January",
	        "fieldname":"jan",
	        "fieldtype":"Int",
	        "width":70,
	    },

	    {
	        "label":"February",
	        "fieldname":"feb",
	        "fieldtype":"Int",
	        "width":80,
	    },

	    {
	        "label":"March",
	        "fieldname":"mar",
	        "fieldtype":"Int",
	        "width":70,
	    },

	    {
	        "label":"Yearly Total",
	        "fieldname":"year_total",
	        "fieldtype":"Int",
	        "width":120,
	    }

	]

	# --------------------------------
	# Summary
	# --------------------------------

	summary = [

	    {
	        "value": len(result),
	        "label": "Total Drawings",
	        "datatype": "Int"
	    },

	    {
	        "value": grand_total,
	        "label": "Yearly Total",
	        "datatype": "Int"
	    }

	]

	# --------------------------------
	# Return
	# --------------------------------

	return columns, report_data, None, None, summary
