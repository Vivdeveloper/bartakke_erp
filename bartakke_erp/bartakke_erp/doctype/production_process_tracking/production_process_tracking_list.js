frappe.provide("bartakke_erp.production_process_tracking");

const PPT_ITEM = "Production Process Tracking Item";

function get_work_order_no_from_row(doc) {
	return doc.work_order_no || doc[`${PPT_ITEM}:work_order_no`] || null;
}

function get_stage_action_selection(listview) {
	const selected = listview.get_checked_items();
	if (!selected.length) {
		return null;
	}

	const lots = [...new Set(selected.map((doc) => doc.name))];
	let work_orders = null;

	if (listview.view === "Report") {
		work_orders = [
			...new Set(
				selected.map((doc) => get_work_order_no_from_row(doc)).filter(Boolean)
			),
		];
		if (!work_orders.length) {
			work_orders = null;
		}
	}

	return { lots, work_orders };
}

function complete_stage_for_selected(listview, stage) {
	const selection = get_stage_action_selection(listview);
	if (!selection) {
		frappe.msgprint(__("Please select at least one Lot Generation record"));
		return;
	}

	frappe.dom.freeze(__("Updating stage..."));
	frappe.call({
		method:
			"bartakke_erp.bartakke_erp.doctype.production_process_tracking.production_process_tracking.complete_stage_for_lots",
		args: {
			docs: selection.lots,
			stage,
			work_orders: selection.work_orders,
		},
		callback(r) {
			const result = r.message || {};
			let message = result.message || __("Done");

			if (result.skipped) {
				message += __(", {0} already completed", [result.skipped]);
			}
			if (result.missing_tracking?.length) {
				message +=
					"<br>" +
					__("Work Order Tracking not found for: {0}", [
						result.missing_tracking.join(", "),
					]);
			}

			frappe.show_alert({ message, indicator: "green" });
			listview.refresh();
		},
		error(err) {
			frappe.msgprint({
				title: __("Update Stage"),
				message: err.message || __("Failed to update stage"),
				indicator: "red",
			});
		},
		always() {
			frappe.dom.unfreeze();
		},
	});
}

function show_generate_work_order_tracking_dialog(listview) {
	const selected = listview.get_checked_items();

	if (!selected.length) {
		frappe.msgprint(__("Please select at least one Lot Generation record"));
		return;
	}

	const d = new frappe.ui.Dialog({
		title: __("Generate Work Order Tracking"),
		fields: [
			{
				fieldname: "template",
				fieldtype: "Link",
				label: __("Production Process Tracking Template"),
				options: "Production Process Tracking Template",
				reqd: 1,
			},
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			frappe.dom.freeze(__("Creating Work Order Tracking..."));

			const calls = selected.map(
				(doc) =>
					new Promise((resolve, reject) => {
						frappe.call({
							method:
								"bartakke_erp.bartakke_erp.doctype.production_process_tracking.production_process_tracking.create_production_process_tracking_work_orders",
							args: {
								source_name: doc.name,
								template: values.template,
							},
							callback(r) {
								resolve({
									lot: doc.name,
									result: r.message || {},
								});
							},
							error(err) {
								reject(err);
							},
						});
					})
			);

			Promise.all(calls)
				.then((results) => {
					d.hide();

					const created = [];
					const existing = [];

					results.forEach(({ lot, result }) => {
						(result.created || []).forEach((wo) => created.push(`${lot}: ${wo}`));
						(result.existing || []).forEach((wo) =>
							existing.push(`${lot}: ${wo}`)
						);
					});

					let message = "";
					if (created.length) {
						message += __("Created: {0}", [created.join(", ")]);
					}
					if (existing.length) {
						message +=
							(message ? "<br>" : "") +
							__("Already exists: {0}", [existing.join(", ")]);
					}
					if (!message) {
						message = __("No work orders were created.");
					}

					frappe.msgprint({
						title: __("Work Order Tracking"),
						message,
						indicator: "green",
					});
					listview.refresh();
				})
				.catch((err) => {
					frappe.msgprint({
						title: __("Work Order Tracking"),
						message: err.message || __("Failed to create work order tracking"),
						indicator: "red",
					});
				})
				.finally(() => frappe.dom.unfreeze());
		},
	});
	d.show();
}

function get_issue_to_shop_action_item(listview) {
	return listview.page.actions
		.find("a.grey-link span")
		.filter((_, el) => $(el).text().trim() === __("Issue to Shop").trim())
		.closest("li");
}

function toggle_issue_to_shop_action(listview) {
	const $item = get_issue_to_shop_action_item(listview);
	if (!$item.length) {
		return;
	}

	const selection = get_stage_action_selection(listview);
	if (!selection) {
		$item.hide();
		return;
	}

	frappe
		.xcall(
			"bartakke_erp.bartakke_erp.doctype.production_process_tracking.production_process_tracking.lots_have_work_order_tracking",
			{
				docs: selection.lots,
				work_orders: selection.work_orders,
			}
		)
		.then((result) => {
			$item.toggle(result?.ready);
		});
}

function setup_issue_to_shop_action_visibility(listview) {
	get_issue_to_shop_action_item(listview).hide();

	listview.page.actions_btn_group.on("show.bs.dropdown", () => {
		toggle_issue_to_shop_action(listview);
	});

	listview.$result?.on("change", ".list-row-checkbox", () => {
		get_issue_to_shop_action_item(listview).hide();
	});
}

function setup_report_view_fields(listview) {
	if (listview.view !== "Report") {
		return;
	}

	const swap_parent_field = (fieldname) => {
		const parent_idx = listview.fields.findIndex(
			(f) => f[0] === fieldname && f[1] === listview.doctype
		);
		const child_idx = listview.fields.findIndex(
			(f) => f[0] === fieldname && f[1] === PPT_ITEM
		);

		if (parent_idx >= 0) {
			listview.fields[parent_idx] = [fieldname, PPT_ITEM];
		} else if (child_idx < 0) {
			listview._add_field(fieldname, PPT_ITEM);
		}
	};

	const ensure_child_field = (fieldname) => {
		if (!listview.fields.find((f) => f[0] === fieldname && f[1] === PPT_ITEM)) {
			listview._add_field(fieldname, PPT_ITEM);
		}
	};

	const original_set_fields = listview.set_fields.bind(listview);
	listview.set_fields = function () {
		original_set_fields();
		swap_parent_field("current_stage");
		swap_parent_field("overall_status");
		ensure_child_field("work_order_no");
		ensure_child_field("item");
	};
}

frappe.listview_settings["Production Process Tracking"] = {
	add_fields: [
		["work_order_no", PPT_ITEM],
		["item", PPT_ITEM],
		["current_stage", PPT_ITEM],
		["overall_status", PPT_ITEM],
	],
	onload(listview) {
		setup_report_view_fields(listview);
		if (listview.view === "Report") {
			listview.set_fields();
			listview.setup_columns();
		}

		const get_actions_menu_items = listview.get_actions_menu_items.bind(listview);

		listview.get_actions_menu_items = function () {
			return [
				{
					label: __("Issue to Shop"),
					action: () => complete_stage_for_selected(listview, "Issue to Shop"),
					standard: true,
				},
				{
					label: __("Generate Work Order Tracking"),
					action: () => show_generate_work_order_tracking_dialog(listview),
					standard: true,
				},
				...get_actions_menu_items(),
			];
		};

		listview.page.clear_actions_menu();
		listview.set_actions_menu_items();
		setup_issue_to_shop_action_visibility(listview);
	},
};
