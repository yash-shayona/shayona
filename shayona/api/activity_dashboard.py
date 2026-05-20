import frappe

# @frappe.whitelist()
# def get_activity_chart(user, date):
#     """
#     Returns 15-min slots for given user & date:
#     - active_time (in seconds)
#     - idle_time (in seconds)
#     - mouse_count
#     - keyboard_count
#     """

#     import datetime
#     from frappe.utils import get_datetime

#     # fetch child rows for this user + date
#     tracker = frappe.get_all(
#         "Activity Tracker",
#         filters={"employee": user, "date": date},
#         fields=["name"]
#     )

#     if not tracker:
#         return {"slots": []}

#     tracker_name = tracker[0].name

#     details = frappe.get_all(
#         "Activity Tracker Detail",
#         filters={"parent": tracker_name},
#         fields=["idle_time_sec", "mouse_count", "keyboard_count", "timestamp"]
#     )

#     interval = 60  # minutes
#     slots = {}

#     for row in details:
#         ts = get_datetime(row.timestamp)

#         # align to 15-minute slot
#         aligned_minute = (ts.minute // interval) * interval
#         slot_key = ts.replace(minute=aligned_minute, second=0, microsecond=0).strftime("%H:%M")

#         if slot_key not in slots:
#             slots[slot_key] = {
#                 "active": 0,
#                 "idle": 0,
#                 "mouse": 0,
#                 "keyboard": 0
#             }

#         if row.idle_time_sec > 0:
#             slots[slot_key]["idle"] += row.idle_time_sec
#         else:
#             slots[slot_key]["active"] += 10  # your event producer interval is fixed 10 seconds

#         slots[slot_key]["mouse"] += row.mouse_count
#         slots[slot_key]["keyboard"] += row.keyboard_count

#     # convert dict → array sorted by time
#     result = []
#     for k, v in sorted(slots.items()):
#         result.append({ "time": k, **v })

#     return {"slots": result}

@frappe.whitelist()
def get_activity_chart(user, date):
    """
    Returns hourly slots with 4-minute segments:
    - 1 hour = 15 segments (4 min each)
    - Each segment has: active_sec, idle_sec, no_data_sec
    """

    from frappe.utils import get_datetime
    
    # user and date are required
    if not user or not date:
        return {"labels": [], "segments": {}}

    tracker = frappe.get_all(
        "Activity Tracker",
        filters={"user": user, "date": date},
        fields=["name"]
    )
    if not tracker:
        return {"labels": [], "segments": {}}

    tracker_name = tracker[0].name

    details = frappe.get_all(
        "Activity Tracker Detail",
        filters={"parent": tracker_name},
        fields=["idle_time_sec", "mouse_count", "keyboard_count", "timestamp"]
    )

    SEGMENT_MIN = 4          # 4 minutes segment
    SEGMENT_SEC = 4 * 60     # 240 sec
    TOTAL_SEGMENTS = 15      # 60 / 4

    hourly_data = {}  # { "09:00": [ {active, idle, no_data}, x15 ] }

    for row in details:
        ts = get_datetime(row.timestamp)

        # ----- 1. Hour Key (09:00) -----
        hour_key = ts.replace(minute=0, second=0, microsecond=0).strftime("%H:%M")

        if hour_key not in hourly_data:
            hourly_data[hour_key] = {}
            
        # ----- 2. Segment index (0 to 14) -----
        segment_index = ts.minute // SEGMENT_MIN
           
        # Create this segment only if required 
        if segment_index not in hourly_data[hour_key]:
            hourly_data[hour_key][segment_index] = {
            "active": 0,
            "idle": 0,
            "no_data": SEGMENT_SEC,
            "timestamp": None
        }

        seg = hourly_data[hour_key][segment_index]

        # ----- 3. Deduct no_data -----
        seg["no_data"] = max(seg["no_data"] - 10, 0)  # event interval = 10 sec
        seg["timestamp"] = row.timestamp

        # ----- 4. Active or Idle -----
        if row.idle_time_sec > 0:
            seg["idle"] += row.idle_time_sec
        else:
            seg["active"] += 10    # event interval

    # ----- Sort and prepare output -----
    sorted_hours = sorted(hourly_data.keys())
    
    final_segments = {}
    for hour_key in sorted_hours:
        segments_dict = hourly_data[hour_key]
        sorted_indices = sorted(segments_dict.keys())
        final_segments[hour_key] = [segments_dict[i] for i in sorted_indices]

    return {
        "labels": sorted_hours,
        "segments": final_segments
    }

@frappe.whitelist()
def get_screenshot_gallery(user, date):
    if not user or not date:
        return None
    
    tracker_name = frappe.db.get_value(
        "Activity Tracker",
        {"user": user, "date": date},
        "name"
    )

    if not tracker_name:
        return {
            "status": False,
            "message": "No activity tracker found"
        }

    details = frappe.get_all(
        "Activity Tracker Detail",
        filters={
            "parent": tracker_name, 
            "parenttype": "Activity Tracker", 
            "screenshot": ["!=", ""],
        },
        fields=["name", "screenshot", "st_ts"],
        order_by="timestamp desc"
    )

    return {
        "status": True,
        "data": details
    }