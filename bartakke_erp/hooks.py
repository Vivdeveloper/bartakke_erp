app_name = "bartakke_erp"
app_title = "Bartakke ERP"
app_publisher = "Viv Choudhary"
app_description = "Bartakke ERP"
app_email = "choudharyvivek195@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "bartakke_erp",
# 		"logo": "/assets/bartakke_erp/logo.png",
# 		"title": "Bartakke ERP",
# 		"route": "/bartakke_erp",
# 		"has_permission": "bartakke_erp.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/bartakke_erp/css/bartakke_erp.css"
# app_include_js = "/assets/bartakke_erp/js/bartakke_erp.js"

# include js, css files in header of web template
# web_include_css = "/assets/bartakke_erp/css/bartakke_erp.css"
# web_include_js = "/assets/bartakke_erp/js/bartakke_erp.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "bartakke_erp/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
page_js = {
	"print": "public/js/print_workflow_actions.js",
}

# include js in doctype views
doctype_js = {
	"Material Request": [
		"public/js/material_request.js",
		"public/js/mr_update_items.js",
		"public/js/mr_production_plan.js",
	],
	"Production Plan": "public/js/production_plan.js",
    "Sales Order": "public/js/sales_order.js",
    "Item": "public/js/item.js",
    "Sales Order": "public/js/so.js",
    "Sales Invoice": "public/js/sales_invoice.js"
}
doctype_list_js = {"Production Plan": "public/js/production_plan_list.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Fixtures
# --------
# Site-level customizations (Customize Form, Client/Server Scripts, Print Formats,
# Workflows, Reports) that were done directly on the site rather than in code.
# BT Barcode doctype customizations are excluded here — they live in bt_erp_barcode.
# GST India / Income Tax India / Audit Trail customizations are excluded — those are
# owned and managed by india_compliance/hrms/frappe respectively, not this app.
# Exacuer CRM / MSME Compliance customizations are excluded — those live in their own apps.
_excluded_modules = [
	"GST India",
	"Income Tax India",
	"Audit Trail",
	"Exacuer CRM",
	"MSME Compliance",
	"BT ERP Barcode",
]
_bt_barcode_doctypes = ["BT Barcode", "BT Barcode Item"]
# These doctypes already have a dedicated bartakke_erp/custom/<doctype>.json bundle
# (Custom Field + Property Setter, synced on every migrate) — do not duplicate them
# here as well via the blanket fixtures export.
_doctypes_with_custom_bundle = [
	"Item",
	"BOM",
	"BOM Item",
	"Material Request",
	"Material Request Item",
	"Material Request Plan Item",
	"Production Plan",
	"Production Plan Item",
	"Production Plan Sub Assembly Item",
	"Item Barcode",
	"Item Default",
	"Supplier",  # owned by msme_compliance/custom/supplier.json
]

fixtures = [
	{
		"doctype": "Custom Field",
		"filters": [
			["dt", "not in", _bt_barcode_doctypes + _doctypes_with_custom_bundle],
			["module", "not in", _excluded_modules],
		],
	},
	{
		"doctype": "Property Setter",
		"filters": [
			["doc_type", "not in", _bt_barcode_doctypes + _doctypes_with_custom_bundle],
			["module", "not in", _excluded_modules],
		],
	},
	{
		"doctype": "Client Script",
		"filters": [
			["dt", "not in", _bt_barcode_doctypes],
			["module", "not in", ["Exacuer CRM"]],
			["enabled", "=", 1],
		],
	},
	{
		"doctype": "Server Script",
		"filters": [
			["disabled", "=", 0],
		],
	},
	{
		"doctype": "Print Format",
		"filters": [
			["doc_type", "not in", _bt_barcode_doctypes],
			["standard", "=", "No"],
			["disabled", "=", 0],
		],
	},
	{
		"doctype": "Workflow",
		"filters": [
			["is_active", "=", 1],
		],
	},
	{
		"doctype": "Report",
		"filters": [
			["is_standard", "=", "No"],
			["disabled", "=", 0],
		],
	},
	{
		"doctype": "Workspace",
		"filters": [
			["module", "in", ["", None]],
		],
	},
	{
		"doctype": "Document Naming Rule",
	},
	{
		"doctype": "Role",
		"filters": [
			[
				"name",
				"in",
				[
					"Planning",
					"Api User",
					"Document approver",
					"Production planning approver",
					"Document verifier",
				],
			],
		],
	},
	{
		"doctype": "Number Card",
		"filters": [
			["module", "in", ["", None]],
		],
	},
	{
		"doctype": "Workflow State",
	},
	{
		"doctype": "Workflow Action Master",
	},
]

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "bartakke_erp/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "bartakke_erp.utils.jinja_methods",
# 	"filters": "bartakke_erp.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "bartakke_erp.install.before_install"
# after_install = "bartakke_erp.install.after_install"

# Uninstallation
# ------------
#after_migrate = "bartakke_erp.migrate.after_migrate"
# before_uninstall = "bartakke_erp.uninstall.before_uninstall"
# after_uninstall = "bartakke_erp.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "bartakke_erp.utils.before_app_install"
# after_app_install = "bartakke_erp.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "bartakke_erp.utils.before_app_uninstall"
# after_app_uninstall = "bartakke_erp.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bartakke_erp.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"Purchase Order": "bartakke_erp.bartakke_erp.overrides.purchase_order.OverridePurchaseOrder",
#     "Subcontracting Order": "bartakke_erp.bartakke_erp.overrides.subcontracting_order.OverrideSubcontractingOrder",
#     "Subcontracting Receipt": "bartakke_erp.bartakke_erp.overrides.subcontracting_receipt.OverrideSubcontractingReceipt",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Production Plan": {
		"autoname": "bartakke_erp.bartakke_erp.api.production_plan.autoname",
		"validate": [
			"bartakke_erp.bartakke_erp.api.production_plan.validate_production_plan_mr_links",
			"bartakke_erp.bartakke_erp.api.production_plan.validate_production_plan_qty",
			"bartakke_erp.bartakke_erp.api.production_plan.validate",
		],
		"on_submit": "bartakke_erp.bartakke_erp.api.production_plan.validate_production_plan_qty"

	},
	"Item": {
		"on_update": "bartakke_erp.bartakke_erp.api.item.sync_store_item_from_item",
		"on_trash": "bartakke_erp.bartakke_erp.api.item.on_trash",
        "validate": "bartakke_erp.bartakke_erp.api.item.validate",
        "autoname": "bartakke_erp.bartakke_erp.api.item.autoname",
        "before_save": "bartakke_erp.bartakke_erp.api.item.before_save",
        "after_insert": "bartakke_erp.bartakke_erp.api.item.after_insert"
	},
	"Customer": {
		"validate": "bartakke_erp.bartakke_erp.api.party.validate_unique_gstin",
	},
	"Supplier": {
		"validate": "bartakke_erp.bartakke_erp.api.party.validate_unique_gstin",
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"bartakke_erp.tasks.all"
# 	],
# 	"daily": [
# 		"bartakke_erp.tasks.daily"
# 	],
# 	"hourly": [
# 		"bartakke_erp.tasks.hourly"
# 	],
# 	"weekly": [
# 		"bartakke_erp.tasks.weekly"
# 	],
# 	"monthly": [
# 		"bartakke_erp.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "bartakke_erp.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "bartakke_erp.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "bartakke_erp.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["bartakke_erp.utils.before_request"]
# after_request = ["bartakke_erp.utils.after_request"]

# Job Events
# ----------
# before_job = ["bartakke_erp.utils.before_job"]
# after_job = ["bartakke_erp.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"bartakke_erp.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
