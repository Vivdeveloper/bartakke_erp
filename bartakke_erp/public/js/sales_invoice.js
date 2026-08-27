// Approvers should review Sales Invoice (Tax Invoice) from the print view
// instead of the full form — see print_workflow_actions.js for the
// Approve/Reject buttons added to that print view.
const PRINT_ONLY_ROLES = ["Document approver"];

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.is_new() || frm.__redirected_to_print) return;

		let roles = frappe.user_roles || [];
		let is_print_only_user =
			roles.some((role) => PRINT_ONLY_ROLES.includes(role)) &&
			!roles.includes("System Manager");

		if (is_print_only_user) {
			frm.__redirected_to_print = true;
			frappe.set_route("print", frm.doctype, frm.doc.name);
		}
	},
});
