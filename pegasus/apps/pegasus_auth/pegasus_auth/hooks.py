app_name = "pegasus_auth"
app_title = "Pegasus Auth"
app_publisher = "INOMO"
app_description = "Sign in to Frappe with the Entra login of the Pegasus gateway"
app_license = "gpl-3.0"
required_apps = ["frappe"]

auth_hooks = ["pegasus_auth.auth.authenticate"]
on_logout = "pegasus_auth.auth.on_logout"
