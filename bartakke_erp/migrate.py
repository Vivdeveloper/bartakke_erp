import json
import os
from collections import defaultdict

import frappe
from frappe.custom.doctype.property_setter.property_setter import \
    make_property_setter


def after_migrate():
	create_custom_fields()
	# create_property_setter()

def before_uninstall():
	remove_custom_fields()


def create_custom_fields():
	CUSTOM_FIELDS = {}
	print("Creating/Updating Custom Fields...")
	path = os.path.join(os.path.dirname(__file__), "custom_fields")
	for file in os.listdir(path):
		with open(os.path.join(path, file), "r") as f:
			CUSTOM_FIELDS.update(json.load(f))
	from frappe.custom.doctype.custom_field.custom_field import \
	    create_custom_fields

	create_custom_fields(CUSTOM_FIELDS)

def remove_custom_fields():
	print("Removing Custom Fields....")
	module_list = frappe.get_module_list("bartakke_erp")
	cfs = frappe.db.get_values("Custom Field", filters={"module": ["in", module_list]})
	for cf in cfs:
		frappe.delete_doc("Custom Field", cf[0])


# def create_property_setter():
# 	path = os.path.join(os.path.dirname(__file__), "property_setters")
# 	for file in os.listdir(path):
# 		with open(os.path.join(path, file), "r") as f:
# 			property_setters = json.load(f)
# 			for doctype, properties in property_setters.items():
# 				for args in properties:
# 					if not args.get("doctype"):
# 						args["doctype"] = doctype
# 					make_property_setter(**args)
