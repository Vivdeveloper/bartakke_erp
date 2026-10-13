from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

from bartakke_erp.bartakke_erp.overrides.salary_slip import (
	BEPL_WORKING_DAYS_PER_MONTH,
	OverrideSalarySlip,
	count_working_days,
)


class TestCountWorkingDays(UnitTestCase):
	def test_excludes_sundays(self):
		self.assertEqual(count_working_days("2026-09-01", "2026-09-30"), 26)  # 4 Sundays
		self.assertEqual(count_working_days("2026-10-01", "2026-10-31"), 27)  # 4 Sundays
		self.assertEqual(count_working_days("2027-02-01", "2027-02-28"), 24)  # 4 Sundays
		self.assertEqual(count_working_days("2026-08-01", "2026-08-31"), 26)  # 5 Sundays

	def test_partial_and_empty_ranges(self):
		self.assertEqual(count_working_days("2026-09-16", "2026-09-30"), 13)  # mid-month joiner
		self.assertEqual(count_working_days("2026-09-06", "2026-09-06"), 0)  # a single Sunday
		self.assertEqual(count_working_days("2026-09-30", "2026-09-01"), 0)


def make_slip(**kwargs):
	slip = frappe.new_doc("Salary Slip")
	slip.__class__ = OverrideSalarySlip
	slip.update({"salary_structure": "BEPL-Wages", "total_working_days": 27, "payment_days": 27, **kwargs})
	return slip


class TestOverrideSalarySlip(UnitTestCase):
	def test_structure_flag_wins_over_component_flag(self):
		slip = make_slip()
		basic = slip.append("earnings", {"salary_component": "Basic", "depends_on_payment_days": 0})
		lic = slip.append("deductions", {"salary_component": "Personal LIC", "depends_on_payment_days": 1})
		bonus = slip.append(
			"earnings", {"salary_component": "Bonus", "depends_on_payment_days": 0, "additional_salary": "AS-1"}
		)
		structure = SimpleNamespace(
			earnings=[SimpleNamespace(salary_component="Basic", depends_on_payment_days=1)],
			deductions=[SimpleNamespace(salary_component="Personal LIC", depends_on_payment_days=0)],
		)
		with patch.object(frappe, "get_cached_doc", return_value=structure):
			slip.set_depends_on_payment_days_from_structure()

		self.assertEqual(basic.depends_on_payment_days, 1)
		self.assertEqual(lic.depends_on_payment_days, 0)
		self.assertEqual(bonus.depends_on_payment_days, 0)  # additional salary rows are left alone

	def test_exclude_holidays_structure_prorates_on_26_days(self):
		slip = make_slip()
		seen = {}

		def fake_calculate_net_pay(doc, skip_tax_breakup_computation=False):
			seen["total_working_days"] = doc.total_working_days

		with (
			patch.object(OverrideSalarySlip, "excludes_holidays", return_value=True),
			patch.object(OverrideSalarySlip, "set_depends_on_payment_days_from_structure"),
			patch.object(SalarySlip, "calculate_net_pay", fake_calculate_net_pay),
		):
			slip.calculate_net_pay()

		self.assertEqual(seen["total_working_days"], BEPL_WORKING_DAYS_PER_MONTH)
		self.assertEqual(slip.total_working_days, 27)  # actual working days are kept on the slip

	def test_other_structures_prorate_on_actual_days(self):
		slip = make_slip(salary_structure="BEPL-Staff", total_working_days=30)
		seen = {}

		def fake_calculate_net_pay(doc, skip_tax_breakup_computation=False):
			seen["total_working_days"] = doc.total_working_days

		with (
			patch.object(OverrideSalarySlip, "excludes_holidays", return_value=False),
			patch.object(OverrideSalarySlip, "set_depends_on_payment_days_from_structure"),
			patch.object(SalarySlip, "calculate_net_pay", fake_calculate_net_pay),
		):
			slip.calculate_net_pay()

		self.assertEqual(seen["total_working_days"], 30)
