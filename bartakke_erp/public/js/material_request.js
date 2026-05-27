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
