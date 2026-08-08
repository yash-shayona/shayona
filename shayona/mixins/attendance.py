import frappe


class AttendanceMixin:
    def attendance_effective_hours_calculate(self):
        # Attendance - Before Submit Server Script
        #
        # Complete portal sequence:
        # Apply custom break policy and calculate effective hours.
        #
        # Incomplete or invalid portal sequence:
        # Submit Attendance as Present with 0 working hours
        # and mark Hours Calculation Status as Needs Review.

        if self.employee and self.get("shift") and self.attendance_date:
            validation_errors = []

            entry_time = None
            exit_time = None
            break_start_time = None

            total_break_seconds = 0
            valid_break_count = 0

            # ----------------------------------------------------
            # ATTENDANCE DATE RANGE
            # ----------------------------------------------------

            attendance_day_start = frappe.utils.get_datetime(
                str(frappe.utils.getdate(self.attendance_date)) + " 00:00:00"
            )

            attendance_day_end = frappe.utils.add_days(
                attendance_day_start,
                1,
            )

            # ----------------------------------------------------
            # FETCH ALL CHECKINS OF THIS EMPLOYEE AND SHIFT
            # ----------------------------------------------------
            #
            # Do not filter between self.in_time and self.out_time.
            #
            # Example:
            # Entry       10:00 IN
            # Break Start 13:00 OUT
            # Break End   13:20 IN
            # Exit missing
            #
            # Native HRMS may set self.out_time as 13:00.
            # If we query only until self.out_time, Break End at
            # 13:20 will not be fetched.

            checkins = frappe.get_all(
                "Employee Checkin",
                filters=[
                    [
                        "Employee Checkin",
                        "employee",
                        "=",
                        self.employee,
                    ],
                    [
                        "Employee Checkin",
                        "shift",
                        "=",
                        self.shift,
                    ],
                    [
                        "Employee Checkin",
                        "shift_start",
                        ">=",
                        attendance_day_start,
                    ],
                    [
                        "Employee Checkin",
                        "shift_start",
                        "<",
                        attendance_day_end,
                    ],
                    [
                        "Employee Checkin",
                        "attendance",
                        "is",
                        "not set",
                    ],
                    [
                        "Employee Checkin",
                        "skip_auto_attendance",
                        "=",
                        0,
                    ],
                    [
                        "Employee Checkin",
                        "offshift",
                        "=",
                        0,
                    ],
                ],
                fields=[
                    "name",
                    "time",
                    "log_type",
                    "shift_start",
                    "custom_action_type",
                ],
                order_by="time asc",
            )

            if not checkins:
                validation_errors.append(
                    "No Employee Checkins were found for " "hours calculation."
                )

            # Expected relationship between portal action
            # and standard HRMS Log Type.
            expected_log_types = {
                "Entry": "IN",
                "Break Start": "OUT",
                "Break End": "IN",
                "Exit": "OUT",
            }

            # ----------------------------------------------------
            # VALIDATE CHECKIN SEQUENCE
            # ----------------------------------------------------

            for checkin in checkins:
                action_type = checkin.custom_action_type

                checkin_time = frappe.utils.get_datetime(checkin.time)

                # Action Type is required for custom calculation.
                if not action_type:
                    validation_errors.append(
                        "Action Type is missing in Employee "
                        "Checkin " + str(checkin.name) + "."
                    )

                    continue

                # No checkin should be present after Exit.
                if exit_time:
                    validation_errors.append(
                        "Employee Checkin "
                        + str(checkin.name)
                        + " is present after Exit."
                    )

                    continue

                # Validate custom Action Type against
                # standard HRMS Log Type.
                expected_log_type = expected_log_types.get(action_type)

                if expected_log_type and checkin.log_type != expected_log_type:
                    validation_errors.append(
                        "Employee Checkin "
                        + str(checkin.name)
                        + " has Action Type "
                        + str(action_type)
                        + ", but Log Type should be "
                        + str(expected_log_type)
                        + "."
                    )

                # ------------------------------------------------
                # ENTRY
                # ------------------------------------------------

                if action_type == "Entry":
                    if entry_time:
                        validation_errors.append("More than one Entry was found.")

                        continue

                    if break_start_time:
                        validation_errors.append(
                            "Entry was recorded during an " "incomplete break."
                        )

                        continue

                    entry_time = checkin_time

                # ------------------------------------------------
                # BREAK START
                # ------------------------------------------------

                elif action_type == "Break Start":
                    if not entry_time:
                        validation_errors.append(
                            "Break Start was recorded before " "Entry."
                        )

                        continue

                    if break_start_time:
                        validation_errors.append(
                            "Another Break Start was recorded "
                            "before completing the previous "
                            "break."
                        )

                        continue

                    break_start_time = checkin_time

                # ------------------------------------------------
                # BREAK END
                # ------------------------------------------------

                elif action_type == "Break End":
                    if not entry_time:
                        validation_errors.append(
                            "Break End was recorded before " "Entry."
                        )

                        continue

                    if not break_start_time:
                        validation_errors.append(
                            "Break End was found without a " "Break Start."
                        )

                        continue

                    if checkin_time <= break_start_time:
                        validation_errors.append(
                            "Break End must be after " "Break Start."
                        )

                        continue

                    break_duration_seconds = (
                        checkin_time - break_start_time
                    ).total_seconds()

                    total_break_seconds += break_duration_seconds

                    valid_break_count += 1
                    break_start_time = None

                # ------------------------------------------------
                # EXIT
                # ------------------------------------------------

                elif action_type == "Exit":
                    if not entry_time:
                        validation_errors.append("Exit was recorded before Entry.")

                        continue

                    exit_time = checkin_time

                # ------------------------------------------------
                # INVALID ACTION TYPE
                # ------------------------------------------------

                else:
                    validation_errors.append(
                        "Invalid Action Type "
                        + str(action_type)
                        + " in Employee Checkin "
                        + str(checkin.name)
                        + "."
                    )

            # ----------------------------------------------------
            # FINAL SEQUENCE VALIDATIONS
            # ----------------------------------------------------

            if not entry_time:
                validation_errors.append("Entry Employee Checkin is missing.")

            if break_start_time:
                validation_errors.append(
                    "Break Start exists, but Break End " "is missing."
                )

            if not exit_time:
                validation_errors.append("Exit Employee Checkin is missing.")

            if entry_time and exit_time and exit_time <= entry_time:
                validation_errors.append("Exit time must be after Entry time.")

            # ----------------------------------------------------
            # REMOVE DUPLICATE VALIDATION MESSAGES
            # ----------------------------------------------------

            unique_validation_errors = []

            for validation_error in validation_errors:
                if validation_error not in unique_validation_errors:
                    unique_validation_errors.append(validation_error)

            validation_errors = unique_validation_errors

            # ----------------------------------------------------
            # INVALID OR INCOMPLETE CHECKIN SEQUENCE
            # ----------------------------------------------------

            if validation_errors:
                self.custom_hours_calculation_status = "Needs Review"

                self.custom_hours_calculation_message = "; ".join(validation_errors)

                # Do not preserve partial native HRMS hours.
                self.working_hours = 0

                # Employee should remain Present because payroll
                # calculation is based on working hours.
                self.status = "Present"

                # Store only actual custom Entry and Exit.
                #
                # Break Start must not be treated as final Exit.
                self.in_time = entry_time
                self.out_time = exit_time

                # Preserve successfully completed break details,
                # even though the overall sequence needs review.
                self.custom_total_break_seconds = int(round(total_break_seconds))

                self.custom_break_count = int(valid_break_count)

            # ----------------------------------------------------
            # VALID AND COMPLETE CHECKIN SEQUENCE
            # ----------------------------------------------------

            else:
                MINIMUM_LOGIN_FOR_BREAK_SECONDS = 7 * 60 * 60

                MINIMUM_BREAK_FOR_POLICY_SECONDS = 10 * 60

                ALLOCATED_BREAK_SECONDS = 35 * 60

                NO_BREAK_DEDUCTION_SECONDS = 30 * 60

                # Gross duration from Entry to Exit.
                total_login_seconds = (exit_time - entry_time).total_seconds()

                break_outstanding_seconds = 0
                break_exceed_seconds = 0
                fixed_break_deduction_seconds = 0

                # --------------------------------------------
                # CASE 1:
                # Total login is below 7 hours.
                # --------------------------------------------

                if total_login_seconds < MINIMUM_LOGIN_FOR_BREAK_SECONDS:
                    # No break:
                    # Final login remains total login.
                    if total_break_seconds <= 0:
                        final_login_seconds = total_login_seconds

                    # Break exists:
                    # Deduct the complete actual break.
                    else:
                        final_login_seconds = total_login_seconds - total_break_seconds

                # --------------------------------------------
                # CASE 2:
                # Total login is 7 hours or more.
                # --------------------------------------------

                else:
                    # Actual break is below 10 minutes:
                    # Apply fixed 30-minute deduction.
                    if total_break_seconds < MINIMUM_BREAK_FOR_POLICY_SECONDS:
                        fixed_break_deduction_seconds = NO_BREAK_DEDUCTION_SECONDS

                        final_login_seconds = (
                            total_login_seconds - fixed_break_deduction_seconds
                        )

                    # Actual break is 10 to below 35 minutes:
                    # Add remaining allocated break time.
                    elif total_break_seconds < ALLOCATED_BREAK_SECONDS:
                        break_outstanding_seconds = (
                            ALLOCATED_BREAK_SECONDS - total_break_seconds
                        )

                        final_login_seconds = (
                            total_login_seconds + break_outstanding_seconds
                        )

                    # Actual break is exactly 35 minutes.
                    elif total_break_seconds == ALLOCATED_BREAK_SECONDS:
                        final_login_seconds = total_login_seconds

                    # Actual break is more than 35 minutes:
                    # Deduct only the excess break.
                    else:
                        break_exceed_seconds = (
                            total_break_seconds - ALLOCATED_BREAK_SECONDS
                        )

                        final_login_seconds = total_login_seconds - break_exceed_seconds

                final_login_seconds = max(
                    final_login_seconds,
                    0,
                )

                effective_hours = final_login_seconds / 3600

                # Store custom calculated values.
                self.in_time = entry_time
                self.out_time = exit_time

                self.working_hours = round(
                    effective_hours,
                    6,
                )

                self.custom_total_break_seconds = int(round(total_break_seconds))

                self.custom_break_count = int(valid_break_count)

                self.custom_hours_calculation_status = "Valid"

                self.custom_hours_calculation_message = ""

                # ------------------------------------------------
                # RECALCULATE ATTENDANCE STATUS USING
                # CUSTOM EFFECTIVE HOURS
                # ------------------------------------------------

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
                    absent_threshold = (
                        thresholds.working_hours_threshold_for_absent or 0
                    )

                    half_day_threshold = (
                        thresholds.working_hours_threshold_for_half_day or 0
                    )

                if absent_threshold and effective_hours < absent_threshold:
                    self.status = "Absent"

                elif half_day_threshold and effective_hours < half_day_threshold:
                    self.status = "Half Day"

                else:
                    self.status = "Present"
