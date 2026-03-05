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
        freeze: true,
        freeze_message: __('Rebuilding BOM items...'),
        callback(r) {
            if (!r.message) return;

            frm.clear_table('items');

            const items = r.message; 
            const item_codes = Object.keys(items);

            frappe.db.get_list('Item', {
                fields: [
                    'name',
                    'item_name',
                    'item_group',
                    'stock_uom',
                    'custom_drawing_no'
                ],
                filters: {
                    name: ['in', item_codes]
                },
                limit: item_codes.length
            }).then(res => {
                const item_map = {};
                res.forEach(d => {
                    item_map[d.name] = d;
                });

                item_codes.forEach(item_code => {
                    let row = frm.add_child('items');
                    row.item_code  = item_code;
                    row.item_name  = item_map[item_code]?.item_name || '';
                    row.custom_item_group = item_map[item_code]?.item_group || '';
                    row.uom        = item_map[item_code]?.stock_uom || '';
                    row.custom_drawing_number    = item_map[item_code]?.drawing || '';
                    row.qty        = items[item_code] || 1;
                    row.rate       = 0;
                });

                frm.refresh_field('items');
            });
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