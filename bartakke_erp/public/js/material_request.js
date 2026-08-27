frappe.ui.form.on("Material Request", {
	refresh: function(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.material_request_type === 'Purchase') {
			frm.remove_custom_button(__('Purchase Order'), __('Create'));
			frm.add_custom_button(__('Purchase Order'), function() {
				open_make_purchase_order_dialog(frm);
			}, __('Create'));
		}

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

						frm.add_custom_button(__('Create Work Orders'), function() {
							if (!can_create) {
								frappe.msgprint({
									title: __('Pending Items for Work Order'),
									message: pending_info.replace(/\n/g, '<br>'),
									indicator: 'orange',
								});
								return;
							}
							open_mr_split_production_plan_dialog(frm);
						}, __('Create'));
					}
				}
			});
		}
	},
});

function open_make_purchase_order_dialog(frm) {
	frappe.call({
		method: 'bartakke_erp.bartakke_erp.api.material_request.get_pending_qty_for_purchase_order',
		args: {
			material_request: frm.doc.name,
		},
		freeze: true,
		callback: function(r) {
			let items = r.message || [];
			let rows = items.map((item) => {
				let pending_qty = flt(item.pending_qty);
				let already_created = pending_qty <= 0;

				return {
					name: item.name,
					select: already_created ? 0 : 1,
					item_code: item.item_code,
					item_name: item.item_name,
					qty: item.qty,
					uom: item.uom,
					pending_qty: already_created ? 0 : pending_qty,
					order_qty: already_created ? 0 : pending_qty,
					status: already_created ? __('Already Created') : __('Pending'),
				};
			});

			show_make_purchase_order_dialog(frm, rows);
		},
	});
}

function show_make_purchase_order_dialog(frm, rows) {
	let dialog = new frappe.ui.Dialog({
		title: __('Select Items for Purchase Order'),
		size: 'large',
		fields: [
			{
				fieldname: 'items',
				fieldtype: 'Table',
				label: __('Items'),
				cannot_add_rows: true,
				in_place_edit: false,
				data: rows,
				fields: [
					{
						fieldname: 'select',
						fieldtype: 'Check',
						label: __('Select'),
						in_list_view: 1,
					},
					{
						fieldname: 'item_code',
						fieldtype: 'Data',
						label: __('Item Code'),
						in_list_view: 1,
						read_only: 1,
					},
					{
						fieldname: 'item_name',
						fieldtype: 'Data',
						label: __('Item Name'),
						in_list_view: 1,
						read_only: 1,
					},
					{
						fieldname: 'qty',
						fieldtype: 'Float',
						label: __('Qty'),
						in_list_view: 1,
						read_only: 1,
					},
					{
						fieldname: 'pending_qty',
						fieldtype: 'Float',
						label: __('Pending Qty'),
						in_list_view: 1,
						read_only: 1,
					},
					{
						fieldname: 'order_qty',
						fieldtype: 'Float',
						label: __('Qty to Order'),
						in_list_view: 1,
					},
					{
						fieldname: 'status',
						fieldtype: 'Data',
						label: __('Status'),
						in_list_view: 1,
						read_only: 1,
					},
				],
			},
		],
		primary_action_label: __('Create Purchase Order'),
		primary_action() {
			let values = dialog.get_values();
			let selected = (values.items || []).filter(
				(d) => d.select && d.status !== __('Already Created')
			);

			if (!selected.length) {
				frappe.msgprint(__('Please select at least one pending item.'));
				return;
			}

			for (let d of selected) {
				if (!flt(d.order_qty) || flt(d.order_qty) <= 0) {
					frappe.msgprint(__('Please enter a valid Qty to Order for {0}.', [d.item_code]));
					return;
				}
				if (flt(d.order_qty) > flt(d.pending_qty)) {
					frappe.msgprint(__('Qty to Order for {0} cannot exceed Pending Qty of {1}.', [d.item_code, d.pending_qty]));
					return;
				}
			}

			let order_qty_by_row = {};
			selected.forEach((d) => {
				order_qty_by_row[d.name] = flt(d.order_qty);
			});

			frappe.call({
				method: 'frappe.model.mapper.make_mapped_doc',
				args: {
					method: 'erpnext.stock.doctype.material_request.material_request.make_purchase_order',
					source_name: frm.doc.name,
					selected_children: JSON.stringify({ items: selected.map((d) => d.name) }),
				},
				freeze: true,
				callback: function(r) {
					if (r.exc || !r.message) {
						return;
					}

					let target_doc = r.message;
					(target_doc.items || []).forEach((item) => {
						let order_qty = order_qty_by_row[item.material_request_item];
						if (order_qty !== undefined) {
							item.qty = order_qty;
							item.stock_qty = flt(item.qty) * (flt(item.conversion_factor) || 1);
							item.amount = flt(item.qty) * flt(item.rate);
						}
					});

					frappe.model.sync(target_doc);
					frappe.set_route('Form', target_doc.doctype, target_doc.name);
				},
			});

			dialog.hide();
		},
	});

	dialog.show();
}
