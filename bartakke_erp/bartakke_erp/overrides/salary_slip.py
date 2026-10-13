import frappe
from frappe.utils import add_days, date_diff, flt, getdate
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip, verify_lwp_days_corrected

# Salary Structure Assignment amounts of "exclude holidays" structures (BEPL-Wages)
# are monthly figures for a 26 working-day month, i.e. per-day wage = amount / 26.
BEPL_WORKING_DAYS_PER_MONTH = 26


def count_working_days(start_date, end_date):
	"""Days between start_date and end_date (both inclusive) excluding Sundays."""
	start_date, end_date = getdate(start_date), getdate(end_date)
	days = date_diff(end_date, start_date) + 1
	if days <= 0:
		return 0
	return sum(1 for i in range(days) if add_days(start_date, i).weekday() != 6)


class OverrideSalarySlip(SalarySlip):
	"""For salary structures with `custom_exclude_holidays` set, payment days are
	working days (Sundays excluded) minus LWP, and components are prorated on a
	26-day month.

	This is applied before HRMS computes the components, so earnings, formula based
	deductions (PF, ESIC, PT), gross and net pay are all computed from the same payment
	days, on save as well as on submit.
	"""

	def excludes_holidays(self):
		return bool(
			self.salary_structure
			and frappe.get_cached_value("Salary Structure", self.salary_structure, "custom_exclude_holidays")
		)

	def get_working_days_details(self, lwp=None, for_preview=0, lwp_days_corrected=None):
		super().get_working_days_details(
			lwp=lwp, for_preview=for_preview, lwp_days_corrected=lwp_days_corrected
		)
		if for_preview or not self.excludes_holidays():
			return

		# actual_start_date / actual_end_date account for joining and relieving dates
		payment_days = count_working_days(self.actual_start_date, self.actual_end_date) - flt(
			self.leave_without_pay
		)
		if frappe.db.get_single_value("Payroll Settings", "payroll_based_on") == "Attendance":
			payment_days -= flt(self.absent_days)

		if (
			lwp_days_corrected
			and lwp_days_corrected > 0
			and verify_lwp_days_corrected(self.employee, self.start_date, self.end_date, lwp_days_corrected)
		):
			payment_days += lwp_days_corrected

		self.total_working_days = count_working_days(self.start_date, self.end_date)
		self.payment_days = max(payment_days, 0)

	def set_depends_on_payment_days_from_structure(self):
		"""Salary Detail.depends_on_payment_days is fetched from the Salary Component on
		every save, so a slip row created from the structure flips to the component's flag
		when re-saved or submitted, and the same slip prorates differently each time.
		Keep the flag the structure row was created with."""
		if not self.salary_structure:
			return

		structure = frappe.get_cached_doc("Salary Structure", self.salary_structure)
		flags = {d.salary_component: d.depends_on_payment_days for d in structure.earnings + structure.deductions}
		for row in self.earnings + self.deductions:
			if not row.additional_salary and row.salary_component in flags:
				row.depends_on_payment_days = flags[row.salary_component]

	def calculate_net_pay(self, skip_tax_breakup_computation: bool = False):
		self.set_depends_on_payment_days_from_structure()

		if not self.excludes_holidays():
			return super().calculate_net_pay(skip_tax_breakup_computation=skip_tax_breakup_computation)

		# HRMS prorates by payment_days / total_working_days; prorate on a 26-day month
		# instead while keeping the actual working days on the slip.
		total_working_days = self.total_working_days
		self.total_working_days = BEPL_WORKING_DAYS_PER_MONTH
		try:
			super().calculate_net_pay(skip_tax_breakup_computation=skip_tax_breakup_computation)
		finally:
			self.total_working_days = total_working_days
