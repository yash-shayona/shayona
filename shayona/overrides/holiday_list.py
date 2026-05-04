from frappe.utils import getdate

SATURDAY_RULE_FIELD = "custom_saturday_weekly_off_rule"
SATURDAY_WEEKLY_OFF_RULES = {
    "1st and 3rd saturday": {1, 3},
    "1st & 3rd saturday": {1, 3},
    "first_third": {1, 3},
    "2nd and 4th saturday": {2, 4},
    "2nd & 4th saturday": {2, 4},
    "second_fourth": {2, 4},
}


def before_save(doc, method=None):
    apply_saturday_weekly_off_rule(doc)


def apply_saturday_weekly_off_rule(doc):
    if doc.weekly_off != "Saturday":
        return

    selected_rule = normalize_rule_value(doc.get(SATURDAY_RULE_FIELD))
    if selected_rule not in SATURDAY_WEEKLY_OFF_RULES:
        return

    if not doc.holidays:
        return

    allowed_week_numbers = SATURDAY_WEEKLY_OFF_RULES[selected_rule]
    filtered_holidays = []

    for holiday in doc.holidays:
        holiday_date = getdate(holiday.holiday_date)

        if not should_exclude_saturday_weekly_off(holiday_date, holiday.weekly_off, allowed_week_numbers):
            filtered_holidays.append(holiday)

    doc.set("holidays", filtered_holidays)
    reindex_holiday_rows(doc)
    doc.total_holidays = len(filtered_holidays)


def should_exclude_saturday_weekly_off(holiday_date, weekly_off, allowed_week_numbers):
    if not weekly_off:
        return False

    # Monday=0 ... Saturday=5
    if holiday_date.weekday() != 5:
        return False

    week_number = (holiday_date.day - 1) // 7 + 1
    return week_number not in allowed_week_numbers


def normalize_rule_value(value):
    return (value or "").strip().lower()


def reindex_holiday_rows(doc):
    for idx, holiday in enumerate(doc.holidays, start=1):
        holiday.idx = idx
