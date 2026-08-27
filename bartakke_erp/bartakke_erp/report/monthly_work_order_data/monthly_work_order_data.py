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

	if filters.get("company"):
	    where_clauses.append("company = %(company)s")
	    params["company"] = filters["company"]

	if filters.get("from_date"):
	    where_clauses.append("posting_date >= %(from_date)s")
	    params["from_date"] = filters["from_date"]

	if filters.get("to_date"):
	    where_clauses.append("posting_date <= %(to_date)s")
	    params["to_date"] = filters["to_date"]

	where_sql = " AND ".join(where_clauses)

	# --------------------------------
	# Query
	# --------------------------------

	query = f"""

	SELECT

	    posting_date,
	    custom_repeat_wo,
	    custom_standard_wo,
	    custom_special_wo,
	    custom_mkg_generating_wo

	FROM `tabProduction Plan`

	WHERE {where_sql}

	ORDER BY posting_date

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
	    "Repeat W/O": {
	        "wo_type": "Repeat W/O"
	    },
	    "Standard W/O": {
	        "wo_type": "Standard W/O"
	    },
	    "Special W/O": {
	        "wo_type": "Special W/O"
	    },
	    "Marketing Generated": {
	        "wo_type": "Marketing Generated"
	    }
	}

	for row in rows.values():
	    for m in months:
	        row[m] = 0

	# --------------------------------
	# Populate Counts
	# --------------------------------

	for d in result:

	    month = month_map.get(d.posting_date.month)

	    if d.custom_repeat_wo:
	        rows["Repeat W/O"][month] = rows["Repeat W/O"][month] + 1

	    if d.custom_standard_wo:
	        rows["Standard W/O"][month] = rows["Standard W/O"][month] + 1

	    if d.custom_special_wo:
	        rows["Special W/O"][month] = rows["Special W/O"][month] + 1

	    if d.custom_mkg_generating_wo:
	        rows["Marketing Generated"][month] = (
	            rows["Marketing Generated"][month] + 1
	        )

	# --------------------------------
	# Prepare Report Data
	# --------------------------------

	report_data = []

	monthly_total = {
	    "wo_type": "Monthly Total W/O"
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
	        "label": "WO Type",
	        "fieldname": "wo_type",
	        "fieldtype": "Data",
	        "width": 180,
	    },

	    {
	        "label": "April",
	        "fieldname": "apr",
	        "fieldtype": "Int",
	        "width": 70,
	    },

	    {
	        "label": "May",
	        "fieldname": "may",
	        "fieldtype": "Int",
	        "width": 70,
	    },

	    {
	        "label": "June",
	        "fieldname": "jun",
	        "fieldtype": "Int",
	        "width": 70,
	    },

	    {
	        "label": "July",
	        "fieldname": "jul",
	        "fieldtype": "Int",
	        "width": 70,
	    },

	    {
	        "label": "August",
	        "fieldname": "aug",
	        "fieldtype": "Int",
	        "width": 70,
	    },

	    {
	        "label": "September",
	        "fieldname": "sep",
	        "fieldtype": "Int",
	        "width": 90,
	    },

	    {
	        "label": "October",
	        "fieldname": "oct",
	        "fieldtype": "Int",
	        "width": 80,
	    },

	    {
	        "label": "November",
	        "fieldname": "nov",
	        "fieldtype": "Int",
	        "width": 90,
	    },

	    {
	        "label": "December",
	        "fieldname": "dec",
	        "fieldtype": "Int",
	        "width": 90,
	    },

	    {
	        "label": "January",
	        "fieldname": "jan",
	        "fieldtype": "Int",
	        "width": 80,
	    },

	    {
	        "label": "February",
	        "fieldname": "feb",
	        "fieldtype": "Int",
	        "width": 90,
	    },

	    {
	        "label": "March",
	        "fieldname": "mar",
	        "fieldtype": "Int",
	        "width": 80,
	    },

	    {
	        "label": "Yearly Total",
	        "fieldname": "year_total",
	        "fieldtype": "Int",
	        "width": 120,
	    }

	]

	# --------------------------------
	# Summary
	# --------------------------------

	summary = [

	    {
	        "value": len(result),
	        "label": "Total Work Orders",
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
