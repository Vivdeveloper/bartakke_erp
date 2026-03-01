frappe.ui.form.on('BOM', {
	refresh(frm) {
		// your code here
        console.log('refresh')
	}
})

frappe.ui.form.on('BOM Assembly Item', {
    item_code(frm, cdt, cdn) {

        let row = locals[cdt][cdn];

        // existing item codes
        let existing_items = (frm.doc.items || []).map(i => i.item_code);

        frm.call({
            method: 'bartakke_erp.bartakke_erp.api.bom.update_assembly_items',
            args: {
                doc: frm.doc,
            },
            callback: (r) => {
                if (!r.message) return;

                Object.entries(r.message).forEach(([item_code, qty]) => {

                    // only add if matches row item AND not already present
                    if (item_code === row.item_code && !existing_items.includes(item_code)) {
                        let child = frm.add_child('items');
                        child.item_code = item_code;
                        frappe.db.get_value("Item", { name: item_code }, "stock_uom", (r) => {
                            console.log('itttt', r.stock_uom)
                            child.uom = r.stock_uom;
                        });
                        child.qty = qty;
                    }
                });

                frm.refresh_field('items');
            }
        });
    },
    qty(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        let existing_items = (frm.doc.items || []).map(i => i.item_code);

        frm.call({
            method: 'bartakke_erp.bartakke_erp.api.bom.update_assembly_items',
            args: {
                doc: frm.doc,
            },
            callback: (r) => {
                if (!r.message) return;

                Object.entries(r.message).forEach(([item_code, qty]) => {

                    // only add if matches row item AND not already present
                    if (item_code === row.item_code && !existing_items.includes(item_code)) {
                        let child = frm.add_child('items');
                        child.item_code = item_code;
                        child.qty = qty;
                    }
                    else {
                        frm.doc.items.map((i)=>{
                            if (item_code == i.item_code){
                                i.qty = qty
                            }
                            frappe.db.get_value("Item", { name: item_code }, "stock_uom", (r) => {
                            console.log('itttt', r.stock_uom)
                            i.uom = r.stock_uom;
                        });
                            console.log('qqqty', qty, row)
                            
                        })
                        
                    }
                });

                frm.refresh_field('items');
            }
        });
    }
});

frappe.ui.form.on('BOM Sub Assembly Item', {
    item_code(frm, cdt, cdn) {

        let row = locals[cdt][cdn];

        // existing item codes
        let existing_items = (frm.doc.items || []).map(i => i.item_code);

        frm.call({
            method: 'bartakke_erp.bartakke_erp.api.bom.update_sub_assembly_items',
            args: {
                doc: frm.doc,
            },
            callback: (r) => {
                if (!r.message) return;

                Object.entries(r.message).forEach(([item_code, qty]) => {

                    // only add if matches row item AND not already present
                    if (item_code === row.item_code && !existing_items.includes(item_code)) {
                        let child = frm.add_child('items');
                        child.item_code = item_code;
                        frappe.db.get_value("Item", { name: item_code }, "stock_uom", (r) => {
                            console.log('itttt', r.stock_uom)
                            child.uom = r.stock_uom;
                        });
                        child.qty = qty;
                    }
                });

                frm.refresh_field('items');
            }
        });
    },
    qty(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        let existing_items = (frm.doc.items || []).map(i => i.item_code);

        frm.call({
            method: 'bartakke_erp.bartakke_erp.api.bom.update_sub_assembly_items',
            args: {
                doc: frm.doc,
            },
            callback: (r) => {
                if (!r.message) return;

                Object.entries(r.message).forEach(([item_code, qty]) => {

                    // only add if matches row item AND not already present
                    if (item_code === row.item_code && !existing_items.includes(item_code)) {
                        let child = frm.add_child('items');
                        child.item_code = item_code;
                        child.qty = qty;
                    }
                    else {
                        frm.doc.items.map((i)=>{
                            if (item_code == i.item_code){
                                i.qty = qty
                            }
                            frappe.db.get_value("Item", { name: item_code }, "stock_uom", (r) => {
                            console.log('itttt', r.stock_uom)
                            i.uom = r.stock_uom;
                        });
                            console.log('qqqty', qty, row)
                            
                        })
                        
                    }
                });

                frm.refresh_field('items');
            }
        });
    }
});

frappe.ui.form.on('BOM Hardware Item', {
    item_code(frm, cdt, cdn) {

        let row = locals[cdt][cdn];

        // existing item codes
        let existing_items = (frm.doc.items || []).map(i => i.item_code);

        frm.call({
            method: 'bartakke_erp.bartakke_erp.api.bom.update_hardware_items',
            args: {
                doc: frm.doc,
            },
            callback: (r) => {
                if (!r.message) return;

                Object.entries(r.message).forEach(([item_code, qty]) => {

                    // only add if matches row item AND not already present
                    if (item_code === row.item_code && !existing_items.includes(item_code)) {
                        let child = frm.add_child('items');
                        child.item_code = item_code;
                        frappe.db.get_value("Item", { name: item_code }, "stock_uom", (r) => {
                            console.log('itttt', r.stock_uom)
                            child.uom = r.stock_uom;
                        });
                        child.qty = qty;
                    }
                });

                frm.refresh_field('items');
            }
        });
    },
    qty(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        let existing_items = (frm.doc.items || []).map(i => i.item_code);

        frm.call({
            method: 'bartakke_erp.bartakke_erp.api.bom.update_hardware_items',
            args: {
                doc: frm.doc,
            },
            callback: (r) => {
                if (!r.message) return;

                Object.entries(r.message).forEach(([item_code, qty]) => {

                    // only add if matches row item AND not already present
                    if (item_code === row.item_code && !existing_items.includes(item_code)) {
                        let child = frm.add_child('items');
                        child.item_code = item_code;
                        child.qty = qty;
                    }
                    else {
                        frm.doc.items.map((i)=>{
                            if (item_code == i.item_code){
                                i.qty = qty
                            }
                            frappe.db.get_value("Item", { name: item_code }, "stock_uom", (r) => {
                            console.log('itttt', r.stock_uom)
                            i.uom = r.stock_uom;
                        });
                            console.log('qqqty', qty, row)
                            
                        })
                        
                    }
                });

                frm.refresh_field('items');
            }
        });
    }
});