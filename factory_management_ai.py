def plan_today_advanced(jobs, inventory, staff_count, hours_per_staff):
    # Workday + break time settings
    work_start_str = "09:00"
    break_start_str = "13:00"
    break_end_str = "14:00"

    work_start = datetime.combine(date.today(), datetime.strptime(work_start_str, "%H:%M").time())
    break_start = datetime.combine(date.today(), datetime.strptime(break_start_str, "%H:%M").time())
    break_end = datetime.combine(date.today(), datetime.strptime(break_end_str, "%H:%M").time())

    # Each staff has its own timeline
    staff_free = [work_start for _ in range(staff_count)]
    staff_end = [work_start + timedelta(hours=hours_per_staff) for _ in range(staff_count)]
    staff_used = [0.0 for _ in range(staff_count)]

    # Snapshot of inventory for simulation (no real subtraction in DB)
    inv_snapshot = []
    for item in inventory:
        inv_snapshot.append({
            "Item": item["Item"],
            "Category": item["Category"],
            "Size": str(item["Size"]),
            "Quantity": item["Quantity"],
        })

    def find_inventory(cat, name, size):
        for inv in inv_snapshot:
            if (
                inv["Category"] == cat
                and inv["Item"] == name
                and inv["Size"] == str(size)
                and inv["Quantity"] > 0
            ):
                return inv
        return None

    tasks = []

    # Sort jobs by due date
    sorted_jobs = sorted(jobs, key=lambda j: j["due"])

    for job in sorted_jobs:
        for proc in job["processes"]:
            hours = float(proc["hours"])
            if hours <= 0:
                continue

            required_workers = max(1, int(proc.get("workers", 1)))

            # --- Material check ---
            mat_status = "OK"
            inv_match = None
            if proc.get("material_category") and proc.get("material_item") and proc.get("material_size"):
                inv_match = find_inventory(
                    proc["material_category"],
                    proc["material_item"],
                    proc["material_size"],
                )
                if inv_match is None:
                    mat_status = "NO MATERIAL"

            if mat_status == "NO MATERIAL":
                tasks.append({
                    "Job": job["name"],
                    "Process": proc["name"],
                    "Machine": proc.get("machine", ""),
                    "Workers": required_workers,
                    "Hours": hours,
                    "Staff": "",
                    "Start": "",
                    "End": "",
                    "Status": "BLOCKED: No material",
                })
                continue

            # --- Find a group of staff that can work together ---
            if required_workers > staff_count:
                # Impossible: not enough staff in company
                tasks.append({
                    "Job": job["name"],
                    "Process": proc["name"],
                    "Machine": proc.get("machine", ""),
                    "Workers": required_workers,
                    "Hours": hours,
                    "Staff": "",
                    "Start": "",
                    "End": "",
                    "Status": "NOT SCHEDULED: Need more staff than available",
                })
                continue

            # Sort staff by when they are free
            staff_indices = list(range(staff_count))
            staff_indices.sort(key=lambda i: staff_free[i])

            group = staff_indices[:required_workers]
            # Earliest time when all in the group are free
            start_time = max(staff_free[i] for i in group)
            if start_time < work_start:
                start_time = work_start

            # If it would cross lunch, push whole task after lunch
            if start_time < break_start and start_time + timedelta(hours=hours) > break_start:
                start_time = break_end

            end_time = start_time + timedelta(hours=hours)

            # Check capacity of each staff in the group
            can_schedule = True
            for i in group:
                if start_time >= staff_end[i] or end_time > staff_end[i]:
                    can_schedule = False
                    break

            if not can_schedule:
                tasks.append({
                    "Job": job["name"],
                    "Process": proc["name"],
                    "Machine": proc.get("machine", ""),
                    "Workers": required_workers,
                    "Hours": hours,
                    "Staff": "",
                    "Start": "",
                    "End": "",
                    "Status": "NOT SCHEDULED: No capacity",
                })
                continue

            # Simulated material consumption (1 unit per process)
            if inv_match is not None:
                inv_match["Quantity"] -= 1

            # Assign task to all staff in the group
            for i in group:
                staff_free[i] = end_time
                staff_used[i] += hours

            staff_str = ", ".join(str(i + 1) for i in group)

            tasks.append({
                "Job": job["name"],
                "Process": proc["name"],
                "Machine": proc.get("machine", ""),
                "Workers": required_workers,
                "Hours": hours,
                "Staff": staff_str,  # e.g. "1, 2, 3"
                "Start": start_time.strftime("%I:%M %p"),
                "End": end_time.strftime("%I:%M %p"),
                "Status": "SCHEDULED",
            })

    total_used = sum(staff_used)
    total_capacity = staff_count * hours_per_staff
    return tasks, total_used, total_capacity
