# -*- coding: utf-8 -*-
# Copyright 2019-2020 Camptocamp (https://www.camptocamp.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from openerp import fields, models, api


def _default_sequence(model):
    maxrule = model.search([], order="sequence desc", limit=1)
    if maxrule:
        return maxrule.sequence + 10
    else:
        return 0


class StockRouting(models.Model):
    _name = "stock.routing"
    _description = "Stock Routing"
    _order = "sequence, id"

    _rec_name = "location_id"

    location_id = fields.Many2one(
        comodel_name="stock.location",
        required=True,
        unique=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=lambda self: self._default_sequence())
    active = fields.Boolean(default=True)
    rule_ids = fields.One2many(
        comodel_name="stock.routing.rule", inverse_name="routing_id"
    )

    _sql_constraints = [
        (
            "location_id_uniq",
            "unique(location_id)",
            "A routing configuration already exists for this location",
        )
    ]

    @api.multi
    def _default_sequence(self):
        return _default_sequence(self)

    @api.model
    def _routing_rule_for_moves(self, moves):
        """Return a routing rule for moves

        :param move: recordset of the move
        :return: dict {move: {rule: move_lines}}
        """

        result = {move: {} for move in moves}
        valid_rules_for_move = set()
        for quant in moves.mapped("reserved_quant_ids"):
            move = quant.reservation_id
            location = quant.location_id
            location_tree = location._location_parent_tree()
            candidate_routings = self.search([("location_id", "in", location_tree.ids)])

            result.setdefault(move, [])
            # the first location is the current move line's source or dest
            # location, then we climb up the tree of locations
            for loc in location_tree:
                # and search the first allowed rule in the routing
                routing = candidate_routings.filtered(lambda r: r.location_id == loc)
                rules = routing.rule_ids
                # find the first valid rule
                found = False
                for rule in rules:
                    if not (
                        (move, rule) in valid_rules_for_move
                        or rule._is_valid_for_moves(move)
                    ):
                        continue
                    # memorize the result so we don't compute it for
                    # every move line
                    valid_rules_for_move.add((move, rule))
                    if rule in result[move]:
                        result[move][rule] |= quant
                    else:
                        result[move][rule] = quant
                    found = True
                    break
                if found:
                    break
            else:
                empty_rule = self.env["stock.routing.rule"].browse()
                if empty_rule in result[move]:
                    result[move][empty_rule] |= quant
                else:
                    result[move][empty_rule] = quant
        return result
