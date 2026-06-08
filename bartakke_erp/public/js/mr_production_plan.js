// Copyright (c) 2026, Viv Choudhary and contributors
// Split Material Request quantities into multiple Production Plans.

function open_mr_split_production_plan_dialog(frm) {
	frappe.call({
		method: "bartakke_erp.bartakke_erp.api.mr_production_plan.get_mr_split_production_plan_rows",
		args: { material_request: frm.doc.name },
		freeze: true,
		freeze_message: __("Loading items..."),
		callback(r) {
			if (r.exc) {
				return;
			}
			const rows = r.message || [];
			if (!rows.length) {
				frappe.msgprint({
					title: __("Production Plan"),
					message: __("All items are already fully planned."),
					indicator: "green",
				});
				return;
			}
			const blocked = rows.some((row) => !row.resolved_bom);
			if (blocked) {
				frappe.msgprint({
					title: __("Production Plan"),
					message: __("Every pending line needs an active BOM before creating Production Plans."),
					indicator: "orange",
				});
				return;
			}
			show_mr_split_production_plan_dialog(frm, rows);
		},
	});
}

function show_mr_split_production_plan_dialog(frm, rows) {
	const table_data = rows.map((row) => ({ ...row }));

	let d;
	const refresh_split_row = (grid_row) => {
		if (!grid_row?.doc) return;
		const doc = grid_row.doc;
		const pending = flt(doc.pending_qty);
		const sum = parse_split_string(doc.split_quantities).reduce((a, b) => a + b, 0);
		const remaining = pending - sum;
		doc.balance_qty = remaining > 0 ? remaining : 0;
		grid_row.refresh_field("balance_qty");
		if (d) refresh_split_preview(d);
	};

	d = new frappe.ui.Dialog({
		title: __("Create Production Plan(s)"),
		size: "extra-large",
		static: true,
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "help",
				options: `<p class="text-muted small">${__(
					"Enter split quantities per item (comma-separated). Example: pending 5 → <code>2,1,1,1</code> creates 4 Production Plans. Leave split empty to skip an item."
				)}</p>`,
			},
			{
				fieldtype: "HTML",
				fieldname: "preview",
				options: `<p id="mr-pp-split-preview" class="text-muted">${__("Enter splits to preview plan count.")}</p>`,
			},
			{
				fieldtype: "Table",
				fieldname: "items",
				label: __("Items"),
				cannot_add_rows: true,
				cannot_delete_rows: true,
				data: table_data,
				fields: [
					{
						fieldtype: "Link",
						fieldname: "item_code",
						label: __("Item"),
						options: "Item",
						in_list_view: 1,
						read_only: 1,
						columns: 2,
					},
					{
						fieldtype: "Data",
						fieldname: "custom_full_drawing_number_",
						label: __("Drawing No"),
						in_list_view: 1,
						read_only: 1,
						columns: 2,
					},
					{
						fieldtype: "Float",
						fieldname: "pending_qty",
						label: __("Pending"),
						in_list_view: 1,
						read_only: 1,
						columns: 1,
					},
					{
						fieldtype: "Float",
						fieldname: "already_planned",
						label: __("Planned"),
						in_list_view: 1,
						read_only: 1,
						columns: 1,
					},
					{
						fieldtype: "Float",
						fieldname: "balance_qty",
						label: __("Balance"),
						in_list_view: 1,
						read_only: 1,
						columns: 1,
						description: __("Remaining after split; shows 0 if split exceeds pending."),
					},
					{
						fieldtype: "Data",
						fieldname: "split_quantities",
						label: __("Split Qty"),
						in_list_view: 1,
						columns: 2,
						description: __("e.g. 2,1,1,1"),
						onchange() {
							refresh_split_row(this.grid_row);
						},
					},
					{
						fieldtype: "Data",
						fieldname: "stock_uom",
						label: __("UOM"),
						hidden: 1,
					},
					{
						fieldtype: "Data",
						fieldname: "warehouse",
						label: __("Warehouse"),
						hidden: 1,
					},
					{
						fieldtype: "Data",
						fieldname: "bom_no",
						label: __("BOM"),
						hidden: 1,
					},
					{
						fieldtype: "Data",
						fieldname: "custom_drawing_no",
						label: __("Drawing No"),
						hidden: 1,
					},
					{
						fieldtype: "Data",
						fieldname: "material_request_item",
						label: __("MR Item"),
						hidden: 1,
					},
				],
			},
		],
		primary_action_label: __("Create Production Plan(s)"),
		primary_action(values) {
			const items = values.items || [];
			const has_split = items.some((row) => (row.split_quantities || "").trim());
			if (!has_split) {
				frappe.msgprint(__("Enter split quantities for at least one item."));
				return;
			}

			frappe.call({
				method: "bartakke_erp.bartakke_erp.api.mr_production_plan.create_split_production_plans",
				args: {
					material_request: frm.doc.name,
					items,
				},
				freeze: true,
				freeze_message: __("Creating Production Plan(s)..."),
				callback(res) {
					if (res.exc || !res.message) {
						return;
					}
					const { plans, count } = res.message;
					d.hide();
					frappe.show_alert({
						message: __("{0} Production Plan(s) created", [count]),
						indicator: "green",
					});
					if (plans && plans.length === 1) {
						frappe.set_route("Form", "Production Plan", plans[0]);
					} else if (plans && plans.length > 1) {
						frappe.msgprint({
							title: __("Production Plans Created"),
							message: plans.map((n) => `<a href="/app/production-plan/${encodeURIComponent(n)}">${frappe.utils.escape_html(n)}</a>`).join("<br>"),
						});
					}
					frm.reload_doc();
				},
			});
		},
	});

	d.show();
	d.get_close_btn().show();

	const grid = d.fields_dict.items.grid;
	(grid.grid_rows || []).forEach((grid_row) => {
		grid_row.doc.balance_qty = flt(grid_row.doc.pending_qty);
		grid_row.refresh_field("balance_qty");
	});
	refresh_split_preview(d);
}

function refresh_split_preview(dialog) {
	const grid = dialog.fields_dict.items?.grid;
	let max_plans = 0;
	const lines = [];

	(grid?.grid_rows || []).forEach((grid_row) => {
		const doc = grid_row.doc;
		const pending = flt(doc.pending_qty);
		const splits = parse_split_string(doc.split_quantities);
		const sum = splits.reduce((a, b) => a + b, 0);
		if (splits.length) {
			max_plans = Math.max(max_plans, splits.length);
		}
		if (doc.split_quantities && sum > pending + 0.0001) {
			lines.push(
				`${doc.item_code}: ${__("split total")} ${sum} &gt; ${__("pending balance")} ${pending}`
			);
		}
	});

	const el = dialog.$wrapper.find("#mr-pp-split-preview");
	if (lines.length) {
		el.html(`<span class="text-danger">${lines.join("<br>")}</span>`);
	} else if (max_plans) {
		el.html(__("Will create <b>{0}</b> Production Plan(s).", [max_plans]));
	} else {
		el.html(__("Enter splits to preview plan count."));
	}
}

function parse_split_string(raw) {
	if (!raw) {
		return [];
	}
	return String(raw)
		.replace(/;/g, ",")
		.split(",")
		.map((s) => s.trim())
		.filter((s) => s.length)
		.map((s) => flt(s))
		.filter((n) => n > 0);
}
