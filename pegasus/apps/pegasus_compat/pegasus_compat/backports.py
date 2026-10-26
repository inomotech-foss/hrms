"""Postgres fixes from ERPNext develop that are not in version-16.

apply() runs before every request and job and replaces the functions in their
ERPNext modules, so every caller gets them: API calls and link searches, which
call the method path directly and ignore override_whitelisted_methods. Remove
a fix once the ERPNext version in apps.json contains it.
"""

import frappe
from frappe.query_builder import Case, Criterion, DocType
from frappe.query_builder.functions import Concat, Length, Locate, Lower, Substring
from frappe.utils import nowdate
from pypika import Order


def apply(*args, **kwargs):
	from erpnext.controllers import queries

	queries.item_query = item_query


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_query(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict | str | None,
	as_dict: bool = False,
):
	"""Item link search: version-16 behaviour, built with the query builder.

	version-16 writes MariaDB SQL by hand (IF(), "..." as a string, a
	'0000-00-00' date, unquoted tabItem), which Postgres rejects. Rewritten
	like ERPNext develop, which has no Company Restriction or
	get_allowed_items_condition in version-16.
	"""
	from erpnext.selling.doctype.party_specific_item.party_specific_item import (
		get_restricted_items_condition,
	)
	from erpnext.stock.doctype.item.item_search import get_item_search_candidates

	doctype = "Item"
	filters = frappe.parse_json(filters)

	restricted_items_condition = None
	if filters and isinstance(filters, dict):
		if filters.get("customer") or filters.get("supplier"):
			party_type = "Customer" if filters.get("customer") else "Supplier"
			party = filters.get("customer") or filters.get("supplier")
			restricted_items_condition = get_restricted_items_condition(party_type, party)

			if filters.get("customer"):
				del filters["customer"]
			else:
				del filters["supplier"]
		else:
			filters.pop("customer", None)
			filters.pop("supplier", None)

	item = DocType(doctype)
	meta = frappe.get_meta(doctype, cached=True)
	searchfields = meta.get_search_fields()

	query_select = [item[field] for field in searchfields if field not in ["name", "description"]]
	if "description" in searchfields:
		query_select.append(
			Case()
			.when(Length(item.description) > 40, Concat(Substring(item.description, 1, 40), "..."))
			.else_(item.description)
			.as_("description")
		)

	fields_to_process = list(
		dict.fromkeys(searchfields + [searchfield or "name", "item_code", "item_group", "item_name"])
	)
	db_fields = [f.fieldname for f in meta.fields] + ["name"]
	search_str = f"%{txt}%"
	search_conditions = []
	searched_fields = []
	for fieldname in fields_to_process:
		if fieldname in db_fields:
			search_conditions.append(_like(item[fieldname], search_str))
			searched_fields.append(fieldname)

	barcode = DocType("Item Barcode")
	search_conditions.append(
		item.item_code.isin(frappe.qb.from_(barcode).select(barcode.parent).where(_like(barcode.barcode, search_str)))
	)

	# Scan descriptions only below 50000 items.
	if frappe.db.estimate_count(doctype) < 50000:
		search_conditions.append(_like(item.description, search_str))
		searched_fields.append("description")

	candidates = get_item_search_candidates(txt, searched_fields)
	if candidates is not None and not candidates:
		return [] if as_dict else ()

	needle = Lower(txt.replace("%", ""))
	query = (
		frappe.qb.get_query(doctype, fields=["name"], filters=filters, ignore_permissions=False)
		.select(*query_select)
		.where(item.docstatus < 2)
		.where(item.disabled == 0)
		.where(item.has_variants == 0)
		.where((item.end_of_life > nowdate()) | item.end_of_life.isnull())
		.where(Criterion.any(search_conditions))
		.orderby(
			Case()
			.when(Locate(needle, Lower(item.name)) > 0, Locate(needle, Lower(item.name)))
			.else_(99999)
		)
		.orderby(
			Case()
			.when(Locate(needle, Lower(item.item_name)) > 0, Locate(needle, Lower(item.item_name)))
			.else_(99999)
		)
		.orderby(item.idx, order=Order.desc)
		.orderby(item.name)
		.orderby(item.item_name)
		.limit(page_len)
		.offset(start)
	)

	if candidates is not None:
		query = query.where(item.name.isin(candidates))

	if restricted_items_condition is not None:
		restricted = frappe.qb.from_(item).select(item.name).where(restricted_items_condition)
		query = query.where(item.name.notin(restricted))

	return query.run(as_dict=as_dict)


def _like(field, pattern):
	"""LIKE is case-insensitive in MariaDB but not in Postgres."""
	return field.ilike(pattern) if frappe.db.db_type == "postgres" else field.like(pattern)
