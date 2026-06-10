import frappe
from frappe.modules.utils import sync_customizations

from bartakke_erp.bartakke_erp.api.production_plan import get_total_area


def execute():
	sync_customizations(app="bartakke_erp")
	frappe.clear_cache(doctype="Production Plan")

	if not frappe.db.has_column("Production Plan", "custom_area"):
		return

	for name in frappe.get_all("Production Plan", pluck="name"):
		doc = frappe.get_doc("Production Plan", name)
		area = get_total_area(doc)
		frappe.db.set_value(
			"Production Plan",
			name,
			"custom_area",
			area,
			update_modified=False,
		)
