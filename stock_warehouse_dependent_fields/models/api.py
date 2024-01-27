from odoo import api

from .fields import monkey_patch


@monkey_patch(api.Environment)
def cache_key(self, field):
    key = cache_key.super(self, field)
    if field.warehouse_dependent and key == (None,):
        key = (self.user._get_default_warehouse_id().id,)
    return key
