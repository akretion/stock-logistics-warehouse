# -*- coding: utf-8 -*-
#  licence AGPL version 3 or later
#  Copyright (C) 2020 Akretion (http://www.akretion.com).

from openerp import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("Put a default warehouse in users")
    users = env["res.users"].search([("warehouse_id", "=", False)])
    wh = env["stock.warehouse"].search([], limit=1, order="id asc")
    users.write({"warehouse_id": wh.id})
