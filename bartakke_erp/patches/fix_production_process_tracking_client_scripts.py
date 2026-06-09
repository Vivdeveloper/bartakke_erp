import frappe


LIST_SCRIPT_NAME = "Report Button- Production Process Tracking"
FORM_SCRIPT_NAME = "Production Process Tracking"


def execute():
	_fix_list_client_script()
	_disable_broken_form_client_script()


def _fix_list_client_script():
	if not frappe.db.exists("Client Script", LIST_SCRIPT_NAME):
		return

	frappe.db.set_value(
		"Client Script",
		LIST_SCRIPT_NAME,
		"script",
		"""const _ppt_list_settings = frappe.listview_settings["Production Process Tracking"] || {};
const _ppt_prev_onload = _ppt_list_settings.onload;

frappe.listview_settings["Production Process Tracking"] = {
	..._ppt_list_settings,
	onload(listview) {
		if (_ppt_prev_onload) {
			_ppt_prev_onload(listview);
		}

		listview.page.add_inner_button(__("View in Planning Sheet"), function () {
			const filters = {
				from_date: frappe.datetime.add_months(frappe.datetime.get_today(), -36),
				to_date: frappe.datetime.get_today(),
			};

			const query_string = Object.keys(filters)
				.map(function (key) {
					return encodeURIComponent(key) + "=" + encodeURIComponent(filters[key]);
				})
				.join("&");

			const url = "/app/query-report/WorkOrder%20Planning%20Sheet?" + query_string;
			window.open(url, "_blank");
		});
	},
};""",
	)


def _disable_broken_form_client_script():
	"""Uses removed field `stage_logs`; stages come from Production Stages master."""
	if not frappe.db.exists("Client Script", FORM_SCRIPT_NAME):
		return

	frappe.db.set_value("Client Script", FORM_SCRIPT_NAME, "enabled", 0)
