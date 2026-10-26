"""Sign users in from the identity headers of the Pegasus gateway.

The gateway authenticates every request with Entra and sets these headers,
overwriting whatever a client sends. Requests without them, such as health
checks, fall through to the normal Frappe login.

Site config `pegasus_auth`:

	{"roles": {"<Entra object ID>": ["System Manager", "HR Manager"]}}

Listed users become System Users and get these roles on every sign-in. Roles
are only added, never removed. Everyone else is created as an Employee Self
Service user and gets that role once HR links them to an Employee.
"""

import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

EMAIL_HEADER = "X-Auth-Request-Email"
NAME_HEADER = "X-Auth-Request-User"
OID_HEADER = "X-Auth-Request-Oid"

# Set on logout. Without it the headers would sign the user straight back in,
# so the next page load goes to the gateway logout instead.
LOGOUT_COOKIE = "pegasus_logout"
GATEWAY_LOGOUT = "/oauth2/logout"

ESS = "Employee Self Service"


def authenticate():
	request = frappe.request
	if (
		request.cookies.get(LOGOUT_COOKIE)
		and request.method == "GET"
		and not request.path.startswith("/api/")
	):
		response = redirect(GATEWAY_LOGOUT)
		response.delete_cookie(LOGOUT_COOKIE)
		raise HTTPException(response=response)

	email = (frappe.get_request_header(EMAIL_HEADER) or "").strip().lower()
	if not email or frappe.session.user == email:
		return

	oid = (frappe.get_request_header(OID_HEADER) or "").strip()
	display_name = (frappe.get_request_header(NAME_HEADER) or "").strip()

	frappe.set_user("Administrator")
	user = ensure_user(email, oid, display_name)
	if not user:
		frappe.set_user("Guest")
		return

	# login_as writes "Logged In" and the home page into the response, which
	# belongs to whatever the request was for.
	response = dict(frappe.local.response)
	frappe.local.login_manager.login_as(user)
	frappe.local.response.clear()
	frappe.local.response.update(response)


def ensure_user(email: str, oid: str, display_name: str) -> str | None:
	"""Create or update the user for this sign-in. None if the user is disabled."""
	roles = (frappe.conf.get("pegasus_auth") or {}).get("roles", {}).get(oid, [])

	name = frappe.db.get_value("User", {"email": email})
	if name:
		user = frappe.get_doc("User", name)
	else:
		first_name, _, last_name = display_name.rpartition(" ")
		user = frappe.new_doc("User")
		user.update(
			{
				"email": email,
				"first_name": first_name or last_name or email.split("@")[0],
				"last_name": last_name if first_name else "",
				"send_welcome_email": 0,
				"user_type": "System User" if roles else ESS,
			}
		)
		user.insert(ignore_permissions=True)

	if not user.enabled:
		return None

	if roles:
		if user.user_type != "System User":
			user.user_type = "System User"
			user.save(ignore_permissions=True)
		user.add_roles(*roles)
	elif user.user_type == ESS and not user.get("roles"):
		# Saving assigns the role once HR has linked the user to an Employee.
		user.save(ignore_permissions=True)

	return user.name


def on_logout(login_manager):
	if getattr(frappe.local, "request", None) and frappe.get_request_header(EMAIL_HEADER):
		frappe.local.cookie_manager.set_cookie(LOGOUT_COOKIE, "1", max_age=300, httponly=True)
