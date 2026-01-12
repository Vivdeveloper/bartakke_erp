frappe.ui.form.on('Material Request', {
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
						// Show button with pending quantity info
						let pending_info = r.message.map(item =>
							`${item.item_code}: ${item.pending_qty} of ${item.requested_qty} ${item.stock_uom} pending`
						).join('\n');

						frm.add_custom_button(__('Production Plan'), function() {
							// Show pending items before creating
							frappe.msgprint({
								title: __('Pending Items for Production Plan'),
								message: pending_info.replace(/\n/g, '<br>'),
								primary_action: {
									label: __('Create Production Plan'),
									action: function() {
										frappe.call({
											method: 'bartakke_erp.bartakke_erp.api.material_request.create_production_plan',
											args: {
												material_request: frm.doc.name
											},
											callback: function(r) {
												if (r.message) {
													frappe.msgprint(__('Production Plan {0} created', [r.message]));
													frappe.set_route('Form', 'Production Plan', r.message);
												}
											}
										});
									}
								}
							});
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
	}
});

function show_update_items_dialog(frm) {
	// Prepare data for table
	let table_data = [];
	frm.doc.items.forEach(item => {
		table_data.push({
			name: item.name,
			item_code: item.item_code,
			item_name: item.item_name,
			qty: item.qty,
			stock_uom: item.stock_uom
		});
	});

	// Show dialog
	let d = new frappe.ui.Dialog({
		title: __('Update Items'),
		size: 'large',
		fields: [
			{
				fieldtype: 'Table',
				fieldname: 'items',
				label: __('Items'),
				cannot_add_rows: true,
				cannot_delete_rows: true,
				data: table_data,
				fields: [
					{
						fieldtype: 'Data',
						fieldname: 'item_code',
						label: __('Item Code'),
						in_list_view: 1,
						read_only: 1,
						columns: 3
					},
					{
						fieldtype: 'Data',
						fieldname: 'item_name',
						label: __('Item Name'),
						in_list_view: 1,
						read_only: 1,
						columns: 3
					},
					{
						fieldtype: 'Float',
						fieldname: 'qty',
						label: __('Qty'),
						in_list_view: 1,
						columns: 2
					},
					{
						fieldtype: 'Data',
						fieldname: 'stock_uom',
						label: __('UOM'),
						in_list_view: 1,
						read_only: 1,
						columns: 2
					},
					{
						fieldtype: 'Data',
						fieldname: 'name',
						label: __('Name'),
						hidden: 1
					}
				]
			}
		],
		primary_action_label: __('Update'),
		primary_action: function(values) {
			let items = values.items || [];

			frappe.call({
				method: 'bartakke_erp.bartakke_erp.api.material_request.update_material_request_qty',
				args: {
					material_request: frm.doc.name,
					items: items
				},
				callback: function(r) {
					if (r.message) {
						d.hide();
						frm.reload_doc();
					}
				}
			});
		}
	});

	d.show();
}