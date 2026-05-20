# Copyright (c) 2025, Yash Solanki and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import get_datetime
from shayona.api.activity_dashboard import get_activity_chart

def execute(filters: dict | None = None):
	"""Return columns and data for the report.

	This is the main entry point for the report. It accepts the filters as a
	dictionary and should return columns and data. It is called by the framework
	every time the report is refreshed or a filter is updated.
	"""
	columns = get_columns()
	filters = auto_split_filters(filters)
	data = get_data(filters)
 
	chart = get_chart_data(filters)

	return columns, data, None, chart


def get_columns() -> list[dict]:
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	return [
		{
			"label": _("Activity Tracker"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Activity Tracker",
		},
		{
			"label": _("User"),
			"fieldname": "user",
			"fieldtype": "Link",
			"options": "User",
		},
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
		},
		{
			"label": _("Timesheet"),
			"fieldname": "timesheet",
			"fieldtype": "Link",
			"options": "Timesheet",
		},
		{
			"label": _("Date"),
			"fieldname": "date",
			"fieldtype": "Date",
		},
		{
			"label": _("Interval (15-min)"),
			"fieldname": "interval",
			"fieldtype": "DateTime",
		},
		{
			"label": _("Mouse Count"),
			"fieldname": "mouse_count",
			"fieldtype": "Int",
		},
		{
			"label": _("Keyboard Count"),
			"fieldname": "keyboard_count",
			"fieldtype": "Int",
		},
		{
			"label": _("Idle Time"),
			"fieldname": "idle_time",
			"fieldtype": "float",
		}
	]


def get_data(filters) -> list[list]:
	"""Return data for the report.

	The report data is a list of rows, with each row being a list of cell values.
	"""
	# print(filters)
	data = []
	interval = 15  # minutes
 
	activity_tracker = frappe.get_all(
     "Activity Tracker", 
     filters={**filters.get("at_filters")}, 
     fields=["*"],
     order_by="name desc"
     )
	
	for at in activity_tracker:
		at_details = frappe.get_all("Activity Tracker Detail",
  			filters={"parent": at.name, **filters.get("at_detail_filters")},
  	        fields=["*"],
  	        order_by="timestamp desc"
  	    )
  
		slot_data = {}   # { "09:15": {"mouse": 10, "keyboard": 20, "idle": 30} }
  
		for atd in at_details:
			ts = get_datetime(atd.timestamp)
			# align to 15-minute slot
			aligned_minute = (ts.minute // interval) * interval
			slot_key = ts.replace(minute=aligned_minute, second=0, microsecond=0).strftime("%H:%M:%S")
   
			if slot_key not in slot_data:
				slot_data[slot_key] = {"mouse_count": 0, "keyboard_count": 0, "idle_time_sec": 0}

			slot_data[slot_key]["mouse_count"] += atd.mouse_count
			slot_data[slot_key]["keyboard_count"] += atd.keyboard_count
			slot_data[slot_key]["idle_time_sec"] += atd.idle_time_sec
   
		for slot, values in sorted(slot_data.items()):
			data.append({
				"name": at.name,
				"user": at.user,
				"employee": at.employee,
				"timesheet": at.timesheet,
				"date": at.date,
				"interval": slot,
				"mouse_count": values["mouse_count"],
				"keyboard_count": values["keyboard_count"],
				"idle_time": values["idle_time_sec"],
			})
   
	return data

def get_conditions(filters):
	conditions = {}
 
	if filters.get("start_date"):
		# start_date = getdate(filters.get("start_date"))
		conditions["start_date"] = [">=", filters.get("start_date")]

	if filters.get("end_date"):
		# end_date = getdate(filters.get("end_date"))
		conditions["end_date"] = ["<=", filters.get("end_date")]

	return conditions

def auto_split_filters(filters):
    at_fields = set(frappe.get_meta("Activity Tracker").get_valid_columns())
    at_detail_fields = set(frappe.get_meta("Activity Tracker Detail").get_valid_columns())

    at_filters = {}
    at_detail_filters = {}
    
    if filters.get("date_range"):
        start_date, end_date = filters["date_range"]
        filters["date"] = ["between", [start_date, end_date]]

    for key, value in filters.items():
        if key in at_fields:
            at_filters[key] = value
        elif key in at_detail_fields:
            at_detail_filters[key] = value
            
    filters = {
		"at_filters": at_filters,
		"at_detail_filters": at_detail_filters,
	}

    return filters

def get_chart_data(filters):
    user = filters.get("at_filters").get("user")
    date = filters.get("at_filters").get("date")

    if not user or not date:
        return {}

    result = get_activity_chart(user, date)

    labels = []
    active_vals = []
    idle_vals = []
    nodata_vals = []

    # result["segments"] = {
    #     "00": [{...},{...}],  # segments for each hour
    #     "01": [{...},{...}],
    # }

    segments_by_hour = result.get("segments", {})

    for hour, seg_list in segments_by_hour.items():
        print(hour)
        for idx, seg in enumerate(seg_list):
            labels.append(hour if idx == 0 else "")

            active_vals.append(seg["active"])
            idle_vals.append(seg["idle"])
            nodata_vals.append(seg["no_data"])

    return {
        "data": {
            "labels": labels,      # many segments (each 4 min)
            "datasets": [
                {"name": "Active", "values": active_vals},
                {"name": "Idle", "values": idle_vals},
                {"name": "No Data", "values": nodata_vals},
            ]
        },
        "type": "bar",
        "colors": ["#2ecc71", "#e74c3c", "#95a5a6"],
        "barOptions": {"stacked": True},
        # "axisOptions": {"xAxisMode": "tick"},
        # "tooltipOptions": {
		# 	"formatTooltipY": """function(value){
		# 		if (value >= 60) {
        #         const mins = Math.floor(value / 60);
        #         const secs = value % 60;
        #         return mins + " min" + (secs ? (" " + secs + " sec") : "");
        #     }
		# 	return value + " sec";
		# 	}"""
		# }
    }