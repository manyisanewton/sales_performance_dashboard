import datetime

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, add_months, flt, get_first_day, getdate, nowdate

HOLIDAY_LIST_NAME = "Kenya Holiday list 2026"


class SalesTargets(Document):
    def validate(self):
        self.apply_target_level_rules()
        self.set_department_from_employee()
        self.set_parent_department()
        self.set_owner_display()
        self.set_achieved_total()
        self.set_carryover_targets()
        self.update_progress_fields()

    def apply_target_level_rules(self):
        if self.target_level == "Company":
            self.department = None
            self.parent_department = None
            self.employee = None
        elif self.target_level == "Department":
            self.company = None
            self.employee = None
        elif self.target_level == "Individual":
            self.company = None

    def set_department_from_employee(self):
        if self.target_level != "Individual" or not self.employee:
            return

        if self.department:
            return

        department = frappe.get_value("Employee", self.employee, "department")
        if department:
            self.department = department

    def set_parent_department(self):
        if not self.department:
            self.parent_department = None
            return

        parent_department = frappe.get_value("Department", self.department, "parent_department")
        self.parent_department = parent_department

    def set_owner_display(self):
        if self.target_level == "Company":
            self.owner_display = self.company or ""
        elif self.target_level == "Department":
            self.owner_display = self.department or ""
        elif self.target_level == "Individual":
            self.owner_display = self.employee or ""
        else:
            self.owner_display = ""

    def update_progress_fields(self):
        achieved_total = self.achieved_total or 0
        self.yearly_progress = self.calculate_progress(achieved_total, self.yearly_target)
        self.quarterly_progress = self.calculate_progress(achieved_total, self.quarterly_target)
        self.monthly_progress = self.calculate_progress(achieved_total, self.monthly_target)
        self.weekly_progress = self.calculate_progress(achieved_total, self.weekly_target)
        self.daily_progress = self.calculate_progress(achieved_total, self.daily_target)

    def set_achieved_total(self):
        if not self.start_date or not self.end_date:
            self.achieved_total = 0
            return

        self.achieved_total = self.get_achieved_between(self.start_date, self.end_date)

    def set_carryover_targets(self):
        if not self.start_date or not self.end_date:
            self.daily_target_current = 0
            self.monthly_target_current = 0
            self.quarterly_target_current = 0
            self.yearly_target_current = 0
            return

        current_date = self.get_effective_current_date()
        self.daily_target_current = self.get_daily_target_current(current_date)
        self.monthly_target_current = self.get_monthly_target_current(current_date)
        self.quarterly_target_current = self.get_quarterly_target_current(current_date)
        self.yearly_target_current = self.get_yearly_target_current(current_date)

    def get_effective_current_date(self):
        current_date = getdate(nowdate())
        start_date = getdate(self.start_date)
        end_date = getdate(self.end_date)
        if current_date < start_date:
            return start_date
        if current_date > end_date:
            return end_date
        return current_date

    def get_daily_target_current(self, current_date):
        if not self.daily_target or self.target_level != "Individual":
            return 0

        start_date = getdate(self.start_date)
        if current_date < start_date:
            return flt(self.daily_target)

        achieved_to_date = self.get_achieved_between(start_date, current_date)
        days_elapsed = self.count_working_days(start_date, current_date)
        return max(0, flt(self.daily_target) * days_elapsed - achieved_to_date)

    def get_monthly_target_current(self, current_date):
        if not self.monthly_target:
            return 0

        start_date = getdate(self.start_date)
        current_month_start = get_first_day(current_date)
        if current_month_start <= start_date:
            months_elapsed = 1
        else:
            months_elapsed = self.count_months_between(start_date, current_month_start) + 1

        achieved_to_date = self.get_achieved_between(start_date, current_date)
        return max(0, flt(self.monthly_target) * months_elapsed - achieved_to_date)

    def get_quarterly_target_current(self, current_date):
        if not self.quarterly_target:
            return 0

        start_date = getdate(self.start_date)
        current_quarter_start = self.get_quarter_start(current_date)
        if current_quarter_start <= start_date:
            quarters_elapsed = 1
        else:
            quarters_elapsed = self.count_quarters_between(start_date, current_quarter_start) + 1

        achieved_to_date = self.get_achieved_between(start_date, current_date)
        return max(0, flt(self.quarterly_target) * quarters_elapsed - achieved_to_date)

    def get_yearly_target_current(self, current_date):
        if not self.yearly_target:
            return 0

        start_date = getdate(self.start_date)
        current_year_start = datetime.date(current_date.year, 1, 1)
        if current_year_start <= start_date:
            years_elapsed = 1
        else:
            years_elapsed = current_year_start.year - start_date.year + 1

        achieved_to_date = self.get_achieved_between(start_date, current_date)
        return max(0, flt(self.yearly_target) * years_elapsed - achieved_to_date)

    def count_months_between(self, start_date, end_date):
        start = getdate(start_date)
        end = getdate(end_date)
        return (end.year - start.year) * 12 + (end.month - start.month)

    def count_quarters_between(self, start_date, end_date):
        months = self.count_months_between(start_date, end_date)
        return months // 3

    def get_quarter_start(self, current_date):
        current = getdate(current_date)
        quarter_month = ((current.month - 1) // 3) * 3 + 1
        return datetime.date(current.year, quarter_month, 1)

    def count_working_days(self, start_date, end_date):
        start = getdate(start_date)
        end = getdate(end_date)
        if end < start:
            return 0

        holidays = set(self.get_holidays_between(start, end))
        days = 0
        current = start
        while current <= end:
            if current.weekday() != 6 and current not in holidays:
                days += 1
            current = add_days(current, 1)
        return days

    def get_holidays_between(self, start_date, end_date):
        if not HOLIDAY_LIST_NAME:
            return []

        return frappe.get_all(
            "Holiday",
            filters={
                "parent": HOLIDAY_LIST_NAME,
                "holiday_date": ("between", [start_date, end_date]),
            },
            pluck="holiday_date",
        )

    def get_achieved_between(self, start_date, end_date):
        if not start_date or not end_date:
            return 0

        if self.target_level == "Company":
            return self.get_company_achieved_between(start_date, end_date)
        if self.target_level == "Department":
            return self.get_department_achieved_between(start_date, end_date)
        if self.target_level == "Individual":
            return self.get_individual_achieved_between(start_date, end_date)
        return 0

    def get_company_achieved_between(self, start_date, end_date):
        conditions = ["docstatus = 1", "posting_date between %s and %s"]
        values = [start_date, end_date]
        if self.company:
            conditions.append("company = %s")
            values.append(self.company)

        query = f"""
            select sum(coalesce(grand_total, 0))
            from `tabSales Invoice`
            where {' and '.join(conditions)}
        """
        return flt(frappe.db.sql(query, values)[0][0])

    def get_department_achieved_between(self, start_date, end_date):
        if not self.department:
            return 0

        employees = frappe.get_all(
            "Employee",
            filters={"department": self.department},
            pluck="name",
        )
        if not employees:
            return 0

        sales_people = frappe.get_all(
            "Sales Person",
            filters={"employee": ("in", employees)},
            pluck="name",
        )
        return self.get_sales_team_achieved_between(start_date, end_date, sales_people)

    def get_individual_achieved_between(self, start_date, end_date):
        if not self.employee:
            return 0

        sales_person = frappe.get_value("Sales Person", {"employee": self.employee})
        return self.get_sales_team_achieved_between(
            start_date,
            end_date,
            [sales_person] if sales_person else [],
        )

    def get_sales_team_achieved_between(self, start_date, end_date, sales_people):
        if not sales_people:
            return 0

        placeholders = ", ".join(["%s"] * len(sales_people))
        values = [start_date, end_date, *sales_people]
        query = f"""
            select sum(coalesce(st.allocated_amount, 0))
            from `tabSales Team` st
            join `tabSales Invoice` si on si.name = st.parent
            where st.parenttype = 'Sales Invoice'
              and si.docstatus = 1
              and si.posting_date between %s and %s
              and st.sales_person in ({placeholders})
        """
        return flt(frappe.db.sql(query, values)[0][0])

    @staticmethod
    def calculate_progress(achieved, target):
        target_value = flt(target)
        if target_value <= 0:
            return 0

        progress = (flt(achieved) / target_value) * 100
        return min(progress, 100)
