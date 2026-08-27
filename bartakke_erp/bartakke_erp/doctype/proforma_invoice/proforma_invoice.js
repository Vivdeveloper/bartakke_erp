// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.ui.form.on("Proforma Invoice", {
	setup(frm) {
		frm.calculate_totals = () => calculate_totals(frm);
	},
	discount_amount(frm) {
		calculate_totals(frm);
	},
	additional_discount_percentage(frm) {
		calculate_totals(frm);
	},
	apply_discount_on(frm) {
		calculate_totals(frm);
	},
	items_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "qty", 1);
	},
	items_remove(frm) {
		calculate_totals(frm);
	},
	taxes_add(frm) {
		calculate_totals(frm);
	},
	taxes_remove(frm) {
		calculate_totals(frm);
	},
});

frappe.ui.form.on("Proforma Invoice Item", {
	qty(frm, cdt, cdn) {
		update_amount(frm, cdt, cdn);
	},
	rate(frm, cdt, cdn) {
		update_amount(frm, cdt, cdn);
	},
	cgst_rate(frm) {
		calculate_totals(frm);
	},
	sgst_rate(frm) {
		calculate_totals(frm);
	},
	igst_rate(frm) {
		calculate_totals(frm);
	},
	items_remove(frm) {
		calculate_totals(frm);
	},
});

frappe.ui.form.on("Sales Taxes and Charges", {
	rate(frm) {
		if (frm.doctype === "Proforma Invoice") calculate_totals(frm);
	},
	tax_amount(frm) {
		if (frm.doctype === "Proforma Invoice") calculate_totals(frm);
	},
	charge_type(frm) {
		if (frm.doctype === "Proforma Invoice") calculate_totals(frm);
	},
});

function update_amount(frm, cdt, cdn) {
	let row = frappe.get_doc(cdt, cdn);
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
	calculate_totals(frm);
}

function calculate_totals(frm) {
	let total_qty = 0;
	let net_total = 0;
	let gst_totals = { cgst: 0, sgst: 0, igst: 0 };

	(frm.doc.items || []).forEach((item) => {
		total_qty += flt(item.qty);
		net_total += flt(item.amount);
		gst_totals.cgst += (flt(item.amount) * flt(item.cgst_rate)) / 100;
		gst_totals.sgst += (flt(item.amount) * flt(item.sgst_rate)) / 100;
		gst_totals.igst += (flt(item.amount) * flt(item.igst_rate)) / 100;
	});

	// CGST/SGST/IGST rows are recomputed from each item's GST rate (same math
	// the print format uses). Other rows follow their own charge_type
	// ("On Net Total", "On Previous Row Total", "On Previous Row Amount");
	// "Actual" charges (e.g. Transport, Packing) are flat and left as-is.
	let taxes = frm.doc.taxes || [];
	let running_total = net_total;
	let total_taxes = 0;

	taxes.forEach((tax) => {
		if (tax.gst_tax_type in gst_totals) {
			tax.tax_amount = gst_totals[tax.gst_tax_type];
		} else if (tax.charge_type === "On Net Total") {
			tax.tax_amount = (net_total * flt(tax.rate)) / 100;
		} else if (tax.charge_type === "On Previous Row Total") {
			let ref_total = tax.row_id ? flt(taxes[tax.row_id - 1].total) : running_total;
			tax.tax_amount = (ref_total * flt(tax.rate)) / 100;
		} else if (tax.charge_type === "On Previous Row Amount") {
			let ref_amount = tax.row_id ? flt(taxes[tax.row_id - 1].tax_amount) : 0;
			tax.tax_amount = (ref_amount * flt(tax.rate)) / 100;
		}

		tax.net_amount = net_total;
		running_total += flt(tax.tax_amount);
		tax.total = running_total;
		total_taxes += flt(tax.tax_amount);
	});

	let discount_base = frm.doc.apply_discount_on === "Net Total" ? net_total : net_total + total_taxes;
	let discount_amount = flt(frm.doc.discount_amount);
	if (flt(frm.doc.additional_discount_percentage)) {
		discount_amount = (discount_base * flt(frm.doc.additional_discount_percentage)) / 100;
	}

	let grand_total =
		frm.doc.apply_discount_on === "Net Total"
			? net_total - discount_amount + total_taxes
			: net_total + total_taxes - discount_amount;
	let rounded_total = Math.round(grand_total);

	frm.set_value("total_qty", total_qty);
	frm.set_value("total", net_total);
	frm.set_value("net_total", net_total);
	frm.set_value("base_total", net_total);
	frm.set_value("total_taxes_and_charges", total_taxes);
	frm.set_value("base_total_taxes_and_charges", total_taxes);
	frm.set_value("discount_amount", discount_amount);
	frm.set_value("base_discount_amount", discount_amount);
	frm.set_value("grand_total", grand_total);
	frm.set_value("base_grand_total", grand_total);
	frm.set_value("rounded_total", rounded_total);
	frm.set_value("base_rounded_total", rounded_total);
	frm.refresh_field("taxes");
}
