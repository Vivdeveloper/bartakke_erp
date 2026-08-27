# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, money_in_words


class ProformaInvoice(Document):
	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		total_qty = 0.0
		net_total = 0.0
		total_cgst = 0.0
		total_sgst = 0.0
		total_igst = 0.0

		for item in self.items:
			item.amount = flt(item.qty) * flt(item.rate)
			total_qty += flt(item.qty)
			net_total += flt(item.amount)
			total_cgst += item.amount * flt(item.cgst_rate) / 100
			total_sgst += item.amount * flt(item.sgst_rate) / 100
			total_igst += item.amount * flt(item.igst_rate) / 100

		self.total_qty = total_qty
		self.total = net_total
		self.net_total = net_total
		self.base_total = net_total

		# CGST/SGST/IGST rows are recomputed from each item's GST rate (same
		# math the print format uses). Other rows follow their own charge_type
		# ("On Net Total", "On Previous Row Total", "On Previous Row Amount");
		# "Actual" charges (e.g. Transport, Packing) are flat and left as-is.
		gst_totals = {"cgst": total_cgst, "sgst": total_sgst, "igst": total_igst}
		running_total = net_total
		total_taxes = 0.0

		for tax in self.taxes:
			if tax.gst_tax_type in gst_totals:
				tax.tax_amount = gst_totals[tax.gst_tax_type]
			elif tax.charge_type == "On Net Total":
				tax.tax_amount = net_total * flt(tax.rate) / 100
			elif tax.charge_type == "On Previous Row Total":
				ref_total = self.taxes[int(tax.row_id) - 1].total if tax.row_id else running_total
				tax.tax_amount = flt(ref_total) * flt(tax.rate) / 100
			elif tax.charge_type == "On Previous Row Amount":
				ref_amount = self.taxes[int(tax.row_id) - 1].tax_amount if tax.row_id else 0
				tax.tax_amount = flt(ref_amount) * flt(tax.rate) / 100

			tax.net_amount = net_total
			running_total += flt(tax.tax_amount)
			tax.total = running_total
			total_taxes += flt(tax.tax_amount)

		self.total_taxes_and_charges = total_taxes
		self.base_total_taxes_and_charges = total_taxes

		discount_base = net_total if self.apply_discount_on == "Net Total" else net_total + total_taxes
		if flt(self.additional_discount_percentage):
			self.discount_amount = discount_base * flt(self.additional_discount_percentage) / 100
		self.base_discount_amount = flt(self.discount_amount)

		if self.apply_discount_on == "Net Total":
			grand_total = (net_total - flt(self.discount_amount)) + total_taxes
		else:
			grand_total = net_total + total_taxes - flt(self.discount_amount)

		self.grand_total = grand_total
		self.base_grand_total = grand_total
		self.rounded_total = round(grand_total)
		self.base_rounded_total = self.rounded_total

		if self.company:
			company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
			self.in_words = money_in_words(grand_total, self.currency or company_currency)
			self.base_in_words = money_in_words(grand_total, company_currency)
