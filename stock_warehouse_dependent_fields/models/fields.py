from odoo import fields


def monkey_patch(cls):
    """Return a method decorator to monkey-patch the given class."""

    def decorate(func):
        name = func.__name__
        func.super = getattr(cls, name, None)
        setattr(cls, name, func)
        return func

    return decorate


#
# Implement sparse fields by monkey-patching fields.Field
#

fields.Field.__doc__ += """

        .. _field-warehouse_dependent:

        .. rubric:: Warehouse Dependent fields

"""
fields.Field.warehouse_dependent = None


@monkey_patch(fields.Field)
def _get_attrs(self, model_class, name):
    attrs = _get_attrs.super(self, model_class, name)
    if attrs.get("warehouse_dependent"):
        # hack to make it behave like company dependent (in models.py)
        # but we replace the compute/inverse method with the wh one.
        attrs["company_dependent"] = True
        attrs["store"] = False
        attrs["compute_sudo"] = attrs.get("compute_sudo", False)
        attrs["copy"] = attrs.get("copy", False)
        attrs["default"] = attrs.get("default", self._default_warehouse_dependent)
        attrs["compute"] = self._compute_warehouse_dependent
        if not attrs.get("readonly"):
            attrs["inverse"] = self._inverse_warehouse_dependent
        attrs["search"] = self._search_warehouse_dependent
        attrs["_depends_context"] = attrs.get("_depends_context", ()) + (
            "force_warehouse",
        )
    return attrs


@monkey_patch(fields.Field)
def _compute_warehouse_dependent(self, records):
    # read property as superuser, as the current user may not have access

    Property = records.env["ir.property"].sudo()
    values = Property._get_multi_wh(self.name, self.model_name, records.ids)
    for record in records:
        record[self.name] = values.get(record.id)


@monkey_patch(fields.Field)
def _inverse_warehouse_dependent(self, records):
    # update property as superuser, as the current user may not have access
    Property = records.env["ir.property"].sudo()
    values = {
        record.id: self.convert_to_write(record[self.name], record)
        for record in records
    }
    Property._set_multi_wh(self.name, self.model_name, values)


@monkey_patch(fields.Field)
def _search_warehouse_dependent(self, records, operator, value):
    Property = records.env["ir.property"].sudo()
    return Property.search_multi_wh(self.name, self.model_name, operator, value)


@monkey_patch(fields.Field)
def _default_warehouse_dependent(self, model):
    return model.env["ir.property"]._get_wh(self.name, self.model_name)
