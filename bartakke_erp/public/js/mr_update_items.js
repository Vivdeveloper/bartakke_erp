/* Material Request → Update Items (API: mr_update_items) */

frappe.provide("bartakke_erp.update_items");

const API = "bartakke_erp.bartakke_erp.api.mr_update_items";

bartakke_erp.update_items.Dialog = class {
	constructor(frm) {
		this.frm = frm;
		this.source_rows = [];
		this._by_name = {};
	}

	show() {
		frappe.call({
			method: `${API}.get_update_items_rows`,
			args: { material_request: this.frm.doc.name },
			freeze: true,
			freeze_message: __("Loading..."),
			callback: (r) => {
				if (!r.exc) {
					this.source_rows = r.message || [];
					this._by_name = Object.fromEntries(
						this.source_rows.filter((row) => row.name).map((row) => [row.name, row])
					);
					this._open_dialog();
				}
			},
		});
	}

	_open_dialog() {
		const me = this;
		this.dialog = new frappe.ui.Dialog({
			title: __("Update Items"),
			size: "large",
			fields: [
				{
					fieldtype: "Table",
					fieldname: "items",
					label: __("Items"),
					cannot_add_rows: false,
					cannot_delete_rows: false,
					description: __(
						"Qty must be greater than 0. Remove a row to delete. Cannot reduce below planned qty."
					),
					data: me.source_rows.map((r) => ({ ...r })),
					on_add_row: () => me._default_qty_on_new_row(),
					fields: me.get_columns(),
				},
			],
			primary_action_label: __("Update"),
			primary_action: () => me.save(),
		});
		this.dialog.show();
	}

	get grid() {
		return this.dialog?.fields_dict?.items?.grid;
	}

	get_columns() {
		const me = this;
		const col = (df) => Object.assign({ in_list_view: 1 }, df);
		return [
			col({
				fieldtype: "Link",
				fieldname: "item_code",
				label: __("Item"),
				options: "Item",
				columns: 2,
				get_query: () => ({
					query: "erpnext.controllers.queries.item_query",
					filters: { include_item_in_manufacturing: 1 },
				}),
				onchange() {
					me.fetch_item(this.grid_row);
				},
			}),
			col({ fieldtype: "Data", fieldname: "item_name", label: __("Item Name"), read_only: 1, columns: 2 }),
			col({
				fieldtype: "Link",
				fieldname: "bom_no",
				label: __("BOM No"),
				options: "BOM",
				read_only: 1,
				columns: 2,
			}),
			col({
				fieldtype: "Float",
				fieldname: "qty",
				label: __("Qty"),
				columns: 1,
				default: 1,
				onchange() {
					me._qty_hint(this.grid_row?.doc);
				},
			}),
			{ fieldtype: "Float", fieldname: "planned_qty", hidden: 1, read_only: 1 },
			col({ fieldtype: "Data", fieldname: "stock_uom", label: __("UOM"), read_only: 1, columns: 1 }),
			{ fieldtype: "Data", fieldname: "name", hidden: 1 },
		];
	}

	_planned_qty(doc) {
		if (doc?.name && this._by_name[doc.name]) {
			return flt(this._by_name[doc.name].planned_qty);
		}
		const src = this.source_rows.find((r) => r.item_code === doc?.item_code);
		return src ? flt(src.planned_qty) : flt(doc?.planned_qty);
	}

	_qty_error(doc, for_save) {
		if (!doc?.item_code) return null;
		const qty = flt(doc.qty);
		const planned = this._planned_qty(doc);
		if (qty <= 0) {
			return for_save
				? __("Quantity must be greater than 0 for item {0}. Remove the row to delete a line.", [
						doc.item_code,
					])
				: __("Quantity must be greater than 0");
		}
		if (planned > 0 && qty < planned) {
			return for_save
				? __("Quantity for {0} cannot be less than planned quantity {1}.", [doc.item_code, planned])
				: __("Qty cannot be less than planned quantity {0}", [planned]);
		}
		return null;
	}

	_qty_hint(doc) {
		const msg = this._qty_error(doc, false);
		if (msg) frappe.show_alert({ message: msg, indicator: "orange" }, 4);
	}

	_default_qty_on_new_row() {
		setTimeout(() => {
			const gr = (this.grid?.grid_rows || []).slice(-1)[0];
			if (gr?.doc && flt(gr.doc.qty) <= 0) {
				gr.doc.qty = 1;
				gr.refresh_field("qty");
			}
		}, 50);
	}

	_row_payload(doc, idx) {
		const src = this.source_rows[idx] || {};
		let name = doc.name || src.name;
		if (!name && doc.item_code) {
			const matches = this.source_rows.filter((r) => r.item_code === doc.item_code);
			if (matches.length === 1) name = matches[0].name;
		}
		return {
			name,
			item_code: doc.item_code,
			bom_no: doc.bom_no || src.bom_no,
			qty: flt(doc.qty),
		};
	}

	collect_items() {
		return (this.grid?.grid_rows || [])
			.map((gr, i) => this._row_payload({ ...gr.doc }, i))
			.filter((r) => r.item_code && flt(r.qty) > 0);
	}

	async fetch_item(grid_row) {
		const doc = grid_row?.doc;
		if (!doc?.item_code) return;

		if ((this.grid?.grid_rows || []).some((gr) => gr !== grid_row && gr.doc?.item_code === doc.item_code)) {
			frappe.msgprint(__("Item {0} is already in the list.", [doc.item_code]));
			Object.assign(doc, { item_code: "", item_name: "", stock_uom: "", bom_no: "", planned_qty: 0 });
			["item_code", "item_name", "stock_uom", "bom_no", "qty"].forEach((f) => grid_row.refresh_field(f));
			return;
		}

		try {
			const d = await frappe.xcall(`${API}.get_item_row_details`, {
				material_request: this.frm.doc.name,
				item_code: doc.item_code,
			});
			const src = this.source_rows.find((r) => r.item_code === doc.item_code);
			const planned_qty = src ? flt(src.planned_qty) : 0;
			Object.assign(doc, {
				item_name: d.item_name,
				stock_uom: d.stock_uom,
				bom_no: d.bom_no || "",
				planned_qty,
				qty: flt(doc.qty) > 0 ? flt(doc.qty) : 1,
			});
			if (!doc.name && src?.name) doc.name = src.name;
			["item_name", "stock_uom", "bom_no", "qty"].forEach((f) => grid_row.refresh_field(f));
			if (!d.bom_no) {
				frappe.msgprint({
					title: __("Update Items"),
					message: __("No active BOM for item {0}", [doc.item_code]),
					indicator: "orange",
				});
			}
		} catch (e) {
			frappe.msgprint({
				title: __("Update Items"),
				message: e.message || __("Could not fetch item details."),
				indicator: "red",
			});
		}
	}

	save() {
		const rows = (this.grid?.grid_rows || []).map((gr) => gr.doc).filter((d) => d?.item_code);
		for (const doc of rows) {
			const err = this._qty_error(doc, true);
			if (err) {
				frappe.msgprint({ title: __("Update Items"), message: err, indicator: "orange" });
				return;
			}
		}

		const items = this.collect_items();
		if (!items.length) {
			frappe.msgprint(__("Add at least one item with quantity greater than 0."));
			return;
		}

		frappe.call({
			method: `${API}.update_items`,
			args: { material_request: this.frm.doc.name, items },
			freeze: true,
			freeze_message: __("Saving..."),
			callback: (r) => {
				if (!r.exc) {
					this.dialog.hide();
					this.frm.reload_doc();
				}
			},
		});
	}
};

function show_update_items_dialog(frm) {
	new bartakke_erp.update_items.Dialog(frm).show();
}
