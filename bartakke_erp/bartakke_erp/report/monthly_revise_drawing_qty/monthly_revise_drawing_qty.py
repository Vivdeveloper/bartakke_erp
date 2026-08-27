# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):


	filters = filters or {}

	# --------------------------------
	# Conditions
	# --------------------------------

	where_clauses = ["dr.docstatus < 2"]
	params = {}

	if filters.get("from_date"):
	    where_clauses.append("dr.creation >= %(from_date)s")
	    params["from_date"] = filters["from_date"]

	if filters.get("to_date"):
	    where_clauses.append("dr.creation <= %(to_date)s")
	    params["to_date"] = filters["to_date"]

	if filters.get("revision"):
	    where_clauses.append("dr.revision = %(revision)s")
	    params["revision"] = filters["revision"]

	where_sql = " AND ".join(where_clauses)

	# --------------------------------
	# Query
	# --------------------------------

	query = f"""

	SELECT

	    dr.creation

	FROM `tabDrawing Revision` dr

	WHERE {where_sql}

	ORDER BY dr.creation

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
	# Row
	# --------------------------------

	row = {
	    "description": "Monthly Revised Drawing Qty"
	}

	for m in months:
	    row[m] = 0

	# --------------------------------
	# Count Revisions
	# --------------------------------

	for d in result:

	    month = month_map.get(d.creation.month)

	    row[month] = row[month] + 1

	# --------------------------------
	# Yearly Total
	# --------------------------------

	year_total = 0

	for m in months:
	    year_total = year_total + row[m]

	row["year_total"] = year_total

	report_data = [row]

	# --------------------------------
	# Columns
	# --------------------------------

	columns = [

	    {
	        "label":"Description",
	        "fieldname":"description",
	        "fieldtype":"Data",
	        "width":220,
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
	        "label":"Yearly Rev Drg Total",
	        "fieldname":"year_total",
	        "fieldtype":"Int",
	        "width":130,
	    }

	]

	# --------------------------------
	# Summary
	# --------------------------------

	summary = [

	    {
	        "value": year_total,
	        "label": "Total Revised Drawings",
	        "datatype": "Int"
	    }

	]

	# --------------------------------
	# Return
	# --------------------------------

	return columns, report_data, None, None, summary
