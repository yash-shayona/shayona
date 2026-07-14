import frappe


class AttendanceMixin:
    def attendance_effective_hours_calculate(self):
        IDEAL_BREAK_HOURS = 35 / 60

        if self.employee and self.get("shift") and self.in_time and self.out_time:
            checkins = frappe.get_all(
                "Employee Checkin",
                filters={
                    "employee": self.employee,
                    "shift": self.shift,
                    "time": [
                        "between",
                        [self.in_time, self.out_time],
                    ],
                    "skip_auto_attendance": 0,
                    "offshift": 0,
                },
                fields=[
                    "name",
                    "time",
                    "custom_action_type",
                ],
                order_by="time asc",
            )

            if not checkins:
                frappe.throw(
                    "No Employee Checkins found for calculating "
                    "effective working hours."
                )

            entry_time = None
            exit_time = None
            break_start_time = None

            # total_break_hours = 0
            total_break_seconds = 0
            valid_break_count = 0

            for checkin in checkins:
                action_type = checkin.custom_action_type
                checkin_time = frappe.utils.get_datetime(checkin.time)

                if not action_type:
                    frappe.throw(
                        "Action Type is missing in Employee Checkin "
                        "{0}.".format(checkin.name)
                    )

                if exit_time:
                    frappe.throw(
                        "Employee Checkin {0} is present after Exit.".format(
                            checkin.name
                        )
                    )

                if action_type == "Entry":
                    if entry_time:
                        frappe.throw(
                            "More than one Entry found for this " "attendance."
                        )

                    if break_start_time:
                        frappe.throw("Entry cannot be recorded during a break.")

                    entry_time = checkin_time

                elif action_type == "Break Start":
                    if not entry_time:
                        frappe.throw("Break Start cannot be before Entry.")

                    if break_start_time:
                        frappe.throw(
                            "Break Start found without completing "
                            "the previous break."
                        )

                    break_start_time = checkin_time

                elif action_type == "Break End":
                    if not entry_time:
                        frappe.throw("Break End cannot be before Entry.")

                    if not break_start_time:
                        frappe.throw("Break End found without Break Start.")

                    if checkin_time <= break_start_time:
                        frappe.throw("Break End must be after Break Start.")

                    break_duration_seconds = (
                        checkin_time - break_start_time
                    ).total_seconds()

                    total_break_seconds += break_duration_seconds
                    valid_break_count += 1
                    break_start_time = None

                elif action_type == "Exit":
                    if not entry_time:
                        frappe.throw("Exit cannot be before Entry.")

                    if break_start_time:
                        frappe.throw("Break Start exists, but Break End " "is missing.")

                    if exit_time:
                        frappe.throw("More than one Exit found for this " "attendance.")

                    exit_time = checkin_time

                else:
                    frappe.throw(
                        "Invalid Action Type {0} in Employee "
                        "Checkin {1}.".format(
                            action_type,
                            checkin.name,
                        )
                    )

            if not entry_time:
                frappe.throw("Entry Employee Checkin is required.")

            if not exit_time:
                frappe.throw("Exit Employee Checkin is required.")

            if break_start_time:
                frappe.throw("Break Start exists, but Break End is missing.")

            if exit_time <= entry_time:
                frappe.throw("Exit time must be after Entry time.")

            MINIMUM_LOGIN_FOR_BREAK_SECONDS = 7 * 60 * 60
            MINIMUM_BREAK_FOR_POLICY_SECONDS = 10 * 60
            ALLOCATED_BREAK_SECONDS = 35 * 60
            NO_BREAK_DEDUCTION_SECONDS = 30 * 60

            total_login_seconds = (exit_time - entry_time).total_seconds()

            break_outstanding_seconds = 0
            break_exceed_seconds = 0
            fixed_break_deduction_seconds = 0

            # Case 1:
            # Total Login is below 7 hours.
            if total_login_seconds < MINIMUM_LOGIN_FOR_BREAK_SECONDS:

                # No break:
                # Final Login remains equal to Total Login.
                if total_break_seconds <= 0:
                    final_login_seconds = total_login_seconds

                # Break exists:
                # Deduct the complete actual break duration.
                else:
                    final_login_seconds = total_login_seconds - total_break_seconds

            # Case 2:
            # Total Login is 7 hours or more.
            else:

                # Actual Break is 0 to below 10 minutes.
                # Apply a fixed 30-minute deduction.
                if total_break_seconds < MINIMUM_BREAK_FOR_POLICY_SECONDS:
                    fixed_break_deduction_seconds = NO_BREAK_DEDUCTION_SECONDS

                    final_login_seconds = (
                        total_login_seconds - fixed_break_deduction_seconds
                    )

                # Actual Break is 10 to below 35 minutes.
                elif total_break_seconds < ALLOCATED_BREAK_SECONDS:
                    break_outstanding_seconds = (
                        ALLOCATED_BREAK_SECONDS - total_break_seconds
                    )

                    final_login_seconds = (
                        total_login_seconds + break_outstanding_seconds
                    )

                # Actual Break is exactly 35 minutes.
                elif total_break_seconds == ALLOCATED_BREAK_SECONDS:
                    final_login_seconds = total_login_seconds

                # Actual Break is more than 35 minutes.
                else:
                    break_exceed_seconds = total_break_seconds - ALLOCATED_BREAK_SECONDS

                    final_login_seconds = total_login_seconds - break_exceed_seconds

            final_login_seconds = max(
                final_login_seconds,
                0,
            )

            effective_hours = final_login_seconds / 3600

            self.in_time = entry_time
            self.out_time = exit_time
            self.working_hours = round(
                effective_hours,
                6,
            )

            self.custom_total_break_seconds = int(round(total_break_seconds))

            self.custom_break_count = int(valid_break_count)

            thresholds = frappe.db.get_value(
                "Shift Type",
                self.shift,
                [
                    "working_hours_threshold_for_absent",
                    "working_hours_threshold_for_half_day",
                ],
                as_dict=True,
            )

            absent_threshold = 0
            half_day_threshold = 0

            if thresholds:
                absent_threshold = thresholds.working_hours_threshold_for_absent or 0

                half_day_threshold = (
                    thresholds.working_hours_threshold_for_half_day or 0
                )

            if absent_threshold and effective_hours < absent_threshold:
                self.status = "Absent"

            elif half_day_threshold and effective_hours < half_day_threshold:
                self.status = "Half Day"

            else:
                self.status = "Present"
