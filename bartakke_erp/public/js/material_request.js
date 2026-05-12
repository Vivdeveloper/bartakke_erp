frappe.ui.form.on("Material Request", {
	refresh: function(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.material_request_type === 'Manufacture') {
			// Add Update Items button
			frm.add_custom_button(__('Update Items'), function() {
				show_update_items_dialog(frm);
			});

			// Check if there are pending items before showing the button
			frappe.call({
				method: 'bartakke_erp.bartakke_erp.api.material_request.get_pending_items_for_production_plan',
				args: {
					material_request: frm.doc.name
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						const can_create = r.message.every((item) => !!item.resolved_bom);
						let pending_info = r.message
							.map((item) => {
								let line = `${item.item_code}: ${item.pending_qty} of ${item.requested_qty} ${item.stock_uom} pending`;
								if (item.resolved_bom) {
									line += ` — ${__('BOM')}: ${item.resolved_bom}`;
								} else {
									line += ` — ${__('No active BOM')}`;
								}
								return line;
							})
							.join('\n');
						if (!can_create) {
							pending_info += `\n\n${__('Create Work Order is not available until every pending line has an active BOM.')}`;
						}

						frm.add_custom_button(__('Production Plan'), function() {
							const msg = {
								title: __('Pending Items for Work Order'),
								message: pending_info.replace(/\n/g, '<br>'),
							};
							if (can_create) {
								msg.primary_action = {
									label: __('Create Work Order'),
									action: function() {
										frappe.call({
											method: 'bartakke_erp.bartakke_erp.api.material_request.create_production_plan',
											args: {
												material_request: frm.doc.name,
											},
											freeze: true,
											freeze_message: __('Creating Production Plan...'),
											callback(r) {
												if (!r.exc && r.message) {
													frappe.msgprint(__('Production Plan {0} created', [r.message]));
													frappe.set_route('Form', 'Production Plan', r.message);
												}
											},
										});
									},
								};
							}
							frappe.msgprint(msg);
						}, __('Create'));

						// Add indicator
						frm.dashboard.add_indicator(__('Pending Production Plan: {0} items', [r.message.length]), 'orange');
					} else {
						// All items are already planned
						frm.dashboard.add_indicator(__('All items planned in Production Plans'), 'green');
					}
				}
			});
		}
	},

	// async before_workflow_action(frm) {
	// 	if (frm.doc.workflow_state === "Draft") {
	// 		await frm.trigger("raise_work_orders");
	// 	}
	// },

	// async raise_work_orders(frm) {
	// 	return frappe.call({
	// 		method: 'bartakke_erp.bartakke_erp.api.material_request.create_production_plan',
	// 		args: {
	// 			material_request: frm.doc.name
	// 		},
	// 		callback: function (r) {
	// 			if (r.message) {
	// 				frappe.msgprint(__('Work Order {0} created', [r.message]));
	// 			}
	// 		}
	// 	});
	// }

});

function fetch_update_items_dialog_row(frm, grid_row) {
	const doc = grid_row && grid_row.doc;
	if (!doc || !doc.item_code) {
		return;
	}
	doc.rate = 0;
	doc.uom = "";
	frappe.call({
		method: "erpnext.stock.get_item_details.get_item_details",
		args: {
			args: {
				item_code: doc.item_code,
				from_warehouse: doc.from_warehouse,
				warehouse: doc.warehouse,
				doctype: "Material Request",
				buying_price_list:
					frm.doc.buying_price_list || frappe.defaults.get_default("buying_price_list"),
				currency: frappe.defaults.get_default("Currency"),
				name: frm.doc.name,
				qty: doc.qty || 1,
				stock_qty: doc.stock_qty,
				company: frm.doc.company,
				conversion_rate: 1,
				material_request_type: frm.doc.material_request_type,
				plc_conversion_rate: 1,
				rate: doc.rate,
				uom: doc.uom,
				conversion_factor: doc.conversion_factor,
				project: doc.project,
			},
			overwrite_warehouse: true,
		},
		callback(r) {
			if (r.exc || !r.message) {
				return;
			}
			const d = doc;
			const msg = r.message;
			const allow = [
				"actual_qty",
				"projected_qty",
				"min_order_qty",
				"item_name",
				"stock_uom",
				"uom",
				"conversion_factor",
				"stock_qty",
				"warehouse",
				"description",
				"bom_no",
			];
			Object.keys(msg).forEach((key) => {
				if (msg[key] === undefined || msg[key] === null) {
					return;
				}
				if (!d[key] || allow.includes(key)) {
					d[key] = msg[key];
				}
			});
			if (msg.stock_uom) {
				d.stock_uom = msg.stock_uom;
			}
			if (!frappe.utils.flt(d.qty)) {
				d.qty = 1;
			}
			["item_code", "item_name", "warehouse", "qty", "stock_uom"].forEach((fn) => {
				grid_row.refresh_field(fn);
			});
		},
	});
}

function assert_dialog_unique_item_codes(items) {
	const seen = new Set();
	for (const row of items || []) {
		const ic = (row.item_code || '').trim();
		if (!ic) {
			continue;
		}
		if (seen.has(ic)) {
			frappe.throw({
				title: __('Update Items'),
				message: __('Each item can appear only once. Duplicate: {0}', [ic]),
			});
		}
		seen.add(ic);
	}
}

function show_update_items_dialog(frm) {
	let table_data = [];
	(frm.doc.items || []).forEach((item) => {
		table_data.push({
			name: item.name,
			item_code: item.item_code,
			item_name: item.item_name,
			qty: item.qty,
			warehouse: item.warehouse || frm.doc.set_warehouse || '',
			stock_uom: item.stock_uom,
		});
	});
	const original_mr_item_names = new Set(table_data.map((r) => r.name).filter(Boolean));

	let d = new frappe.ui.Dialog({
		title: __('Update Items'),
		size: 'large',
		fields: [
			{
				fieldtype: 'Table',
				fieldname: 'items',
				label: __('Items'),
				cannot_add_rows: false,
				cannot_delete_rows: false,
				description: __(
					'Add or remove rows. Each item only once. Lines on a Production Plan cannot be removed; change quantity only for those.'
				),
				data: table_data,
				fields: [
					{
						fieldtype: 'Link',
						fieldname: 'item_code',
						label: __('Item'),
						options: 'Item',
						in_list_view: 1,
						reqd: 0,
						columns: 2,
						get_query() {
							return {
								query: 'erpnext.controllers.queries.item_query',
								filters: { include_item_in_manufacturing: 1 },
							};
						},
						onchange() {
							if (!this.grid_row) {
								return;
							}
							const doc = this.grid_row.doc;
							if (!doc.item_code) {
								return;
							}
							const nm = doc.name ? String(doc.name) : '';
							const is_new_row =
								Boolean(doc.__islocal) ||
								!nm ||
								nm.startsWith('new-') ||
								!original_mr_item_names.has(nm);
							if (!is_new_row) {
								return;
							}
							const data = this.grid_row.grid.df.data || [];
							const ic = (doc.item_code || '').trim();
							const others = data.filter((r) => r !== doc && (r.item_code || '').trim() === ic);
							if (others.length) {
								frappe.msgprint({
									title: __('Duplicate item'),
									message: __('This item is already on another row. Each item is allowed only once.'),
									indicator: 'orange',
								});
								doc.item_code = '';
								doc.item_name = '';
								doc.stock_uom = '';
								this.grid_row.refresh_field('item_code');
								this.grid_row.refresh_field('item_name');
								this.grid_row.refresh_field('stock_uom');
								return;
							}
							fetch_update_items_dialog_row(frm, this.grid_row);
						},
					},
					{
						fieldtype: 'Data',
						fieldname: 'item_name',
						label: __('Item Name'),
						in_list_view: 1,
						read_only: 1,
						columns: 2,
					},
					{
						fieldtype: 'Link',
						fieldname: 'warehouse',
						label: __('Warehouse'),
						options: 'Warehouse',
						in_list_view: 1,
						reqd: 0,
						columns: 2,
						get_query: function () {
							return { filters: { company: frm.doc.company } };
						},
					},
					{
						fieldtype: 'Float',
						fieldname: 'qty',
						label: __('Qty'),
						in_list_view: 1,
						columns: 1,
					},
					{
						fieldtype: 'Data',
						fieldname: 'stock_uom',
						label: __('UOM'),
						in_list_view: 1,
						read_only: 1,
						columns: 1,
					},
					{
						fieldtype: 'Data',
						fieldname: 'name',
						label: __('Name'),
						hidden: 1,
					},
				],
			},
		],
		primary_action_label: __('Update'),
		primary_action(values) {
			const items = values.items || [];
			assert_dialog_unique_item_codes(items);
			for (const row of items) {
				const nm = row.name ? String(row.name) : '';
				const isNewRow =
					Boolean(row.__islocal) ||
					!nm ||
					nm.startsWith('new-') ||
					!original_mr_item_names.has(nm);
				if (!isNewRow) {
					continue;
				}
				if (!row.item_code || !frappe.utils.flt(row.qty)) {
					continue;
				}
				if (!row.warehouse) {
					frappe.throw({
						title: __('Update Items'),
						message: __('Set Warehouse for new item {0}', [row.item_code]),
					});
				}
			}

			frappe.call({
				method: 'bartakke_erp.bartakke_erp.api.material_request.update_material_request_qty',
				args: {
					material_request: frm.doc.name,
					items: items,
				},
				freeze: true,
				freeze_message: __('Saving...'),
				callback(r) {
					if (!r.exc && r.message) {
						d.hide();
						frm.reload_doc();
					}
				},
			});
		},
	});

	d.show();
}