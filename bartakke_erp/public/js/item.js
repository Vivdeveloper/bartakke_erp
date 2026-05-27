frappe.ui.form.on("Item", {
    refresh(frm) {
        frm._drawing_counter_item_group = frm.doc.item_group || "";
        frm._drawing_counter_sf_code = frm.doc.custom_sf_code || "";
    },

    custom_add_drawing(frm) {
        if (!frm.doc.custom_drawing_no) {
            suggest_drawing_no(frm);
        }
    },

    item_group(frm) {
        const cur = frm.doc.item_group || "";

        if (frm._drawing_counter_item_group === undefined) {
            frm._drawing_counter_item_group = cur;
            return;
        }

        const prev = frm._drawing_counter_item_group;
        if (cur === prev) {
            return;
        }

        frm._drawing_counter_item_group = cur;

        if (!cur) {
            frm.set_value("custom_drawing_no", "");
            return;
        }

        suggest_drawing_no(frm, { overwrite: true });
    },

    custom_sf_code(frm) {
        const cur = frm.doc.custom_sf_code || "";

        if (frm._drawing_counter_sf_code === undefined) {
            frm._drawing_counter_sf_code = cur;
            return;
        }

        const prev = frm._drawing_counter_sf_code;
        if (cur === prev) {
            return;
        }

        frm._drawing_counter_sf_code = cur;

        if (!cur || frm.doc.custom_drawing_no) {
            return;
        }

        suggest_drawing_no(frm);
    },

    after_save(frm) {
        frappe.call({
            method: "bartakke_erp.bartakke_erp.api.item.get_revision",
            args: { doc: frm.doc },
            callback(r) {
                if (r.message) {
                    frm.set_value("custom_revision", r.message);
                }
            },
        });
    },
});

function suggest_drawing_no(frm, opts = {}) {
    const overwrite = opts.overwrite || false;

    if (!frm.doc.item_group) {
        if (overwrite) {
            frm.set_value("custom_drawing_no", "");
        }
        return;
    }

    frappe.call({
        method: "bartakke_erp.bartakke_erp.api.item.get_drawing",
        args: { doc: frm.doc },
        callback(r) {
            if (r.message !== undefined && r.message !== null && r.message !== "") {
                if (overwrite || !frm.doc.custom_drawing_no) {
                    frm.set_value("custom_drawing_no", r.message);
                }
            } else if (overwrite) {
                frm.set_value("custom_drawing_no", "");
            }
        },
    });
}
