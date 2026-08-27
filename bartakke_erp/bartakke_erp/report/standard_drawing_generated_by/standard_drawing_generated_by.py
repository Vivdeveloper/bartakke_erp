# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	filters = filters or {}

	# --------------------------------
	# Conditions
	# --------------------------------

	where_clauses = [
	    "docstatus < 2",
	    "item_group = %(item_group)s"
	]
	params = {
	    "item_group": filters.get("item_group") or "Standard Item"
	}

	if filters.get("from_date"):
	    where_clauses.append("creation >= %(from_date)s")
	    params["from_date"] = filters["from_date"]

	if filters.get("to_date"):
	    where_clauses.append("creation <= %(to_date)s")
	    params["to_date"] = filters["to_date"]

	where_sql = " AND ".join(where_clauses)

	# --------------------------------
	# Query
	# --------------------------------

	query = f"""

	SELECT

	    creation,
	    owner

	FROM `tabDrawing`

	WHERE {where_sql}

	ORDER BY owner, creation

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
	# Owner -> Full Name Lookup
	# --------------------------------

	owners = list(set([d.owner for d in result]))

	user_names = {}

	if owners:

	    users = frappe.get_all(
	        "User",
	        filters={"name": ["in", owners]},
	        fields=["name", "full_name"]
	    )

	    for u in users:

	        user_names[u.name] = u.full_name or u.name

	# --------------------------------
	# Initial Rows
	# --------------------------------

	rows = {}

	for owner in owners:

	    full_name = user_names.get(owner, owner)

	    row = {
	        "person": full_name
	    }

	    for m in months:
	        row[m] = 0

	    rows[owner] = row

	# --------------------------------
	# Populate Data
	# --------------------------------

	for d in result:

	    month = month_map.get(d.creation.month)

	    rows[d.owner][month] = (
	        rows[d.owner][month] + 1
	    )

	# --------------------------------
	# Final Data
	# --------------------------------

	report_data = []

	monthly_total = {
	    "person": "Monthly Total Qty"
	}

	for m in months:
	    monthly_total[m] = 0

	grand_total = 0

	# Sort rows by person name for consistent display
	sorted_rows = sorted(rows.values(), key=lambda r: r["person"])

	for row in sorted_rows:

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
	        "label":"Person",
	        "fieldname":"person",
	        "fieldtype":"Data",
	        "width":150,
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
	        "label": "Total Standard Drawings",
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
