app_name = "pegasus_compat"
app_title = "Pegasus Compat"
app_publisher = "INOMO"
app_description = "Postgres fixes backported from newer ERPNext for Pegasus"
app_license = "gpl-3.0"
required_apps = ["frappe", "erpnext"]

# Hooks are cached in Redis, so a process may never import this app. These
# run in every request and background job and install the backports there.
before_request = ["pegasus_compat.backports.apply"]
before_job = ["pegasus_compat.backports.apply"]
