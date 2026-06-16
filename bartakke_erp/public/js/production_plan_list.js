frappe.listview_settings["Production Plan"] = {
	onload(listview) {
		listview.page.add_action_item(__("Lot Generation"), function () {
			const selected = listview.get_checked_items();

			if (!selected.length) {
				frappe.msgprint(__("Please select at least one Work Order"));
				return;
			}

			const names = selected.map((doc) => doc.name);

			frappe.call({
				method: "bartakke_erp.bartakke_erp.api.wo.get_work_order_po_items",
				args: {
					work_orders: names,
				},
				freeze: true,
				freeze_message: __("Loading PO items..."),
				callback(r) {
					const rows = r.message || [];
					if (!rows.length) {
						frappe.msgprint(__("No PO items found for selected Work Orders"));
						return;
					}

					const tableData = rows.map((row) => ({
						selected: 1,
						work_order_no: row.work_order_no,
						item_code: row.item_code,
						item_name: row.item_name || row.item_code,
						planned_qty: row.planned_qty,
						stock_uom: row.stock_uom || "",
						production_plan_item: row.name,
					}));

					const dialog = new frappe.ui.Dialog({
						title: __("Select PO Items for Lot Generation"),
						size: "large",
						fields: [
							{
								fieldtype: "HTML",
								fieldname: "work_order_summary",
								options: `<div style="margin-bottom:12px;"><b>${__(
									"Selected Work Orders"
								)}:</b> ${frappe.utils.escape_html(names.join(", "))}</div>`,
							},
							{
								fieldtype: "HTML",
								fieldname: "select_actions",
								options: `<style>
									.lot-generation-po-items-grid .row-check {
										display: none !important;
									}
								</style>
								<div style="margin-bottom:8px;">
									<button type="button" class="btn btn-xs btn-default" data-action="select-all">${__(
										"Select All"
									)}</button>
									<button type="button" class="btn btn-xs btn-default" data-action="unselect-all">${__(
										"Unselect All"
									)}</button>
								</div>`,
							},
							{
								fieldname: "items",
								fieldtype: "Table",
								label: __("PO Items"),
								cannot_add_rows: true,
								cannot_delete_rows: true,
								in_place_edit: true,
								data: tableData,
								fields: [
									{
										fieldname: "selected",
										fieldtype: "Check",
										label: __("Select"),
										in_list_view: 1,
										columns: 1,
									},
									{
										fieldname: "work_order_no",
										fieldtype: "Data",
										label: __("Work Order"),
										in_list_view: 1,
										read_only: 1,
										columns: 2,
									},
									{
										fieldname: "item_name",
										fieldtype: "Data",
										label: __("Item Name"),
										in_list_view: 1,
										read_only: 1,
										columns: 5,
									},
									{
										fieldname: "planned_qty",
										fieldtype: "Float",
										label: __("Qty"),
										in_list_view: 1,
										read_only: 1,
										columns: 1,
									},
									{
										fieldname: "production_plan_item",
										fieldtype: "Data",
										hidden: 1,
									},
								],
							},
						],
						primary_action_label: __("Generate Lot"),
						primary_action() {
							const grid = dialog.fields_dict.items.grid;
							const selected_items = (grid.data || [])
								.filter((row) => row.selected)
								.map((row) => ({
									work_order_no: row.work_order_no,
									production_plan_item: row.production_plan_item,
								}));

							if (!selected_items.length) {
								frappe.msgprint(__("Please select at least one item"));
								return;
							}

							frappe.call({
								method:
									"bartakke_erp.bartakke_erp.api.wo.create_production_tracking_for_items",
								args: {
									work_orders: names,
									selected_items,
								},
								freeze: true,
								callback(createResp) {
									if (!createResp.message) {
										return;
									}

									dialog.hide();
									frappe.msgprint(
										__("Production Process Tracking Created: {0}", [
											createResp.message,
										])
									);
									frappe.set_route(
										"Form",
										"Production Process Tracking",
										createResp.message
									);
								},
							});
						},
					});

					dialog.show();

					const grid = dialog.fields_dict.items.grid;
					grid.wrapper.addClass("lot-generation-po-items-grid");

					const hide_builtin_row_checks = () => {
						grid.wrapper.find(".row-check").hide();
					};

					const original_refresh = grid.refresh.bind(grid);
					grid.refresh = function (...args) {
						const result = original_refresh(...args);
						hide_builtin_row_checks();
						return result;
					};
					hide_builtin_row_checks();

					const set_all_selected = (selected) => {
						(grid.data || []).forEach((row) => {
							row.selected = selected ? 1 : 0;
						});
						grid.refresh();
					};

					dialog.$wrapper.on("click", "[data-action='select-all']", () => {
						set_all_selected(1);
					});
					dialog.$wrapper.on("click", "[data-action='unselect-all']", () => {
						set_all_selected(0);
					});
				},
			});
		});
	},
};
