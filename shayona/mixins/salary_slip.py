import frappe


class SalarySlipMixin:
    def attendance_hour_based_salary(self):
        STANDARD_HOURS_PER_DAY = 9.0

        if self.employee and self.start_date and self.end_date:
            period_start_date = frappe.utils.getdate(self.start_date)
            period_end_date = frappe.utils.getdate(self.end_date)

            actual_start_date = period_start_date
            actual_end_date = period_end_date

            employee_details = frappe.db.get_value(
                "Employee",
                self.employee,
                [
                    "date_of_joining",
                    "relieving_date",
                ],
                as_dict=True,
            )

            if employee_details:
                if (
                    employee_details.date_of_joining
                    and frappe.utils.getdate(employee_details.date_of_joining)
                    > actual_start_date
                ):
                    actual_start_date = frappe.utils.getdate(
                        employee_details.date_of_joining
                    )

                if (
                    employee_details.relieving_date
                    and frappe.utils.getdate(employee_details.relieving_date)
                    < actual_end_date
                ):
                    actual_end_date = frappe.utils.getdate(
                        employee_details.relieving_date
                    )

            if actual_start_date > actual_end_date:
                frappe.throw(
                    "Employee has no applicable payroll dates "
                    "inside this Salary Slip period."
                )

            # Resolve the employee/company Holiday List through
            # the standard Salary Slip backend method.
            holiday_dates = self.get_holidays_for_employee(
                actual_start_date,
                actual_end_date,
            )

            holiday_count = 0

            for holiday_date in holiday_dates:
                holiday_count += 1

            total_calendar_days = (
                frappe.utils.date_diff(
                    actual_end_date,
                    actual_start_date,
                )
                + 1
            )

            expected_working_days = total_calendar_days - holiday_count

            if expected_working_days <= 0:
                frappe.throw(
                    "Expected Working Days cannot be zero. "
                    "Please verify the Holiday List and payroll dates."
                )

            expected_working_hours = (
                frappe.utils.flt(expected_working_days) * STANDARD_HOURS_PER_DAY
            )

            # Sum only submitted Attendance records.
            attendance_rows = frappe.get_all(
                "Attendance",
                filters={
                    "employee": self.employee,
                    "selfstatus": 1,
                    "attendance_date": [
                        "between",
                        [
                            actual_start_date,
                            actual_end_date,
                        ],
                    ],
                },
                fields=[
                    "attendance_date",
                    "working_hours",
                ],
                order_by="attendance_date asc",
            )

            actual_attendance_hours = 0.0

            for attendance in attendance_rows:
                actual_attendance_hours += frappe.utils.flt(attendance.working_hours)

            # Find the applicable submitted Salary Structure Assignment.
            assignment_filters = {
                "employee": self.employee,
                "selfstatus": 1,
                "from_date": [
                    "<=",
                    actual_start_date,
                ],
            }

            if self.salary_structure:
                assignment_filters["salary_structure"] = self.salary_structure

            assignments = frappe.get_all(
                "Salary Structure Assignment",
                filters=assignment_filters,
                fields=[
                    "name",
                    "salary_structure",
                    "from_date",
                    "base",
                ],
                order_by="from_date desc",
            )

            selected_assignment = None

            for assignment in assignments:
                structure_details = frappe.db.get_value(
                    "Salary Structure",
                    assignment.salary_structure,
                    [
                        "selfstatus",
                        "is_active",
                        "payroll_frequency",
                    ],
                    as_dict=True,
                )

                structure_is_valid = (
                    structure_details
                    and structure_details.selfstatus == 1
                    and structure_details.is_active == "Yes"
                )

                frequency_is_valid = (
                    not self.payroll_frequency
                    or not structure_details.payroll_frequency
                    or structure_details.payroll_frequency == self.payroll_frequency
                )

                if structure_is_valid and frequency_is_valid:
                    selected_assignment = assignment
                    break

            if not selected_assignment:
                frappe.throw(
                    "No applicable submitted Salary Structure "
                    "Assignment was found for employee "
                    + frappe.bold(self.employee)
                    + "."
                )

            monthly_base_salary = frappe.utils.flt(selected_assignment.base)

            if monthly_base_salary <= 0:
                frappe.throw(
                    "Base Salary must be greater than zero in "
                    "Salary Structure Assignment "
                    + frappe.bold(selected_assignment.name)
                    + "."
                )

            dynamic_hourly_rate = monthly_base_salary / expected_working_hours

            regular_hours = min(
                actual_attendance_hours,
                expected_working_hours,
            )

            overtime_hours = max(
                actual_attendance_hours - expected_working_hours,
                0,
            )

            if not self.salary_structure:
                self.salary_structure = selected_assignment.salary_structure

            self.custom_standard_hours_per_day = STANDARD_HOURS_PER_DAY

            self.custom_expected_working_days = frappe.utils.flt(
                expected_working_days,
                2,
            )

            self.custom_expected_working_hours = frappe.utils.flt(
                expected_working_hours,
                6,
            )

            self.custom_total_attendance_hours = frappe.utils.flt(
                actual_attendance_hours,
                6,
            )

            self.custom_dynamic_hourly_rate = frappe.utils.flt(
                dynamic_hourly_rate,
                6,
            )

            self.custom_regular_hours = frappe.utils.flt(
                regular_hours,
                6,
            )

            self.custom_overtime_hours = frappe.utils.flt(
                overtime_hours,
                6,
            )
