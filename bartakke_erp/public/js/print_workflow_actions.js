// Adds workflow action buttons (Approve/Reject/etc.) to the standalone
// print page, for roles that are meant to review documents there instead
// of the full form (see sales_invoice.js redirect). For those same roles,
// the print-settings sidebar (Print Format/Language/Letter Head/etc.) is
// hidden so they can't change how the document is rendered — just review
// and act on it.
(function () {
	if (!frappe.ui.form.PrintView) return;

	const PRINT_ONLY_ROLES = ["Document approver"];
	const original_show = frappe.ui.form.PrintView.prototype.show;

	frappe.ui.form.PrintView.prototype.show = function (frm) {
		let result = original_show.call(this, frm);
		let after_show = () => {
			setup_workflow_action_buttons(this, frm);
			hide_sidebar_for_print_only_roles(this);
		};

		if (result && result.then) {
			result.then(after_show);
		} else {
			after_show();
		}

		return result;
	};

	function hide_sidebar_for_print_only_roles(print_view) {
		let roles = frappe.user_roles || [];
		let is_print_only_user =
			roles.some((role) => PRINT_ONLY_ROLES.includes(role)) && !roles.includes("System Manager");

		if (is_print_only_user && print_view.sidebar) {
			print_view.sidebar.hide();
		}
	}

	function setup_workflow_action_buttons(print_view, frm) {
		(print_view._workflow_buttons || []).forEach(($btn) => $btn.remove());
		print_view._workflow_buttons = [];

		if (!frm || !frm.doc || frm.doc.__islocal) return;

		frappe.workflow.get_transitions(frm.doc).then((transitions) => {
			(transitions || []).forEach((transition) => {
				if (!frappe.user_roles.includes(transition.allowed)) return;

				let $btn = print_view.page.add_button(
					__(transition.action),
					() => {
						frappe.confirm(
							__("Are you sure you want to {0} this document?", [__(transition.action)]),
							() => apply_workflow_action(print_view, frm, transition)
						);
					},
					{ icon: "right-arrow" }
				);
				print_view._workflow_buttons.push($btn);
			});
		});
	}

	function apply_workflow_action(print_view, frm, transition) {
		frappe.dom.freeze();
		frappe
			.xcall("frappe.model.workflow.apply_workflow", {
				doc: frm.doc,
				action: transition.action,
			})
			.then((doc) => {
				frappe.model.sync(doc);
				let state_field = frappe.workflow.get_state_fieldname(frm.doctype);
				frappe.show_alert({
					message: __("Document {0}", [doc[state_field]]),
					indicator: "green",
				});
				frm.doc = doc;
				print_view.show(frm);
			})
			.finally(() => frappe.dom.unfreeze());
	}
})();
