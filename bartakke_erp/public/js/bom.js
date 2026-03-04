frappe.ui.form.on('BOM', {
	refresh(frm) {
		// your code here
        console.log('refresh')
	},
})

frappe.ui.form.on('BOM Assembly Item', {
    item_code(frm, cdt, cdn) {
        rebuild_bom_items(frm);
        duplicate_item_validation(
            frm,
            'custom_bom_assembly_items',
            cdt,
            cdn,
            'BOM Assembly Item'
        );
    },
    qty(frm) {
        rebuild_bom_items(frm);
    },
    custom_bom_assembly_items_remove(frm, cdt, cdn) {
        rebuild_bom_items(frm);
    }
});

frappe.ui.form.on('BOM Sub Assembly Item', {
    item_code(frm, cdt, cdn) {
        rebuild_bom_items(frm);
        duplicate_item_validation(
            frm,
            'custom_bom_sub_assembly_items',
            cdt,
            cdn,
            'BOM Sub Assembly Item'
        );
    },
    qty(frm) {
        rebuild_bom_items(frm);
    },
    custom_bom_sub_assembly_items_remove(frm, cdt, cdn) {
        rebuild_bom_items(frm);
    }
})

frappe.ui.form.on('BOM Hardware Item', {
    item_code(frm, cdt, cdn) {
        rebuild_bom_items(frm);
        duplicate_item_validation(
            frm,
            'custom_bom_hardware_items',
            cdt,
            cdn,
            'BOM Hardware Item'
        );
    },
    qty(frm) {
        rebuild_bom_items(frm);
    },
    custom_bom_hardware_items_remove(frm, cdt, cdn) {
        rebuild_bom_items(frm);
    }
})

function rebuild_bom_items(frm) {
    frm.call({
        method: 'bartakke_erp.bartakke_erp.api.bom.get_items',
        args: {
            doc: frm.doc,
        },
        callback(r) {
            if (!r.message) return;

            // clear once
            frm.clear_table('items');

            Object.entries(r.message).forEach(([item_code, qty]) => {
                let row = frm.add_child('items');
                row.item_code = item_code;
                row.qty = qty;

                frappe.db.get_value(
                    'Item',
                    item_code,
                    'stock_uom',
                    (res) => {
                        row.uom = res.stock_uom;
                        frm.refresh_field('items');
                    }
                );
            });

            frm.refresh_field('items');
        }
    });
}

function duplicate_item_validation(frm, table_field, cdt, cdn, label) {
    let row = locals[cdt][cdn];
    if (!row || !row.item_code) return;

    let duplicates = (frm.doc[table_field] || [])
        .filter(d => d.item_code === row.item_code);

    // >1 because current row is included
    if (duplicates.length > 1) {
        row.item_code = '';
        frappe.msgprint({
            title: __('Duplicate Item'),
            message: __('This item is already added'),
            indicator: 'red'
        });
    }
}