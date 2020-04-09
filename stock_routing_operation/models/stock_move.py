# -*- coding: utf-8 -*-
# Copyright 2019-2020 Camptocamp (https://www.camptocamp.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
import uuid
from itertools import chain

from psycopg2 import sql

from openerp import fields, models, api

# TODO check product_qty / product_uom_qty


class StockMove(models.Model):
    _inherit = "stock.move"

    routing_rule_id = fields.Many2one(
        comodel_name="stock.routing.rule",
        copy=False,
        help="Technical field. Store the routing rule that has been"
        " selected for the move.",
    )

    @api.multi
    def action_assign(self):
        if self.env.context.get("exclude_apply_routing_operation"):
            super(StockMove, self).action_assign()
        else:
            # these methods will call _action_assign in a savepoint
            # and modify the routing if necessary
            moves = self._split_and_apply_routing()
            super(StockMove, moves).action_assign()

    def _split_and_apply_routing(self):
        """Apply routing rules

        * calls super()._action_assign() (in a savepoint) on moves not yet
          available to compute the routing rules
        * split the moves if their move lines have different source or
          destination locations and need routing
        * apply the routing rules (pull and push)

        Important: if you inherit this method to skip the routing for some
        moves, the method has to return the moves in ``self`` so they are
        assigned.
        """
        moves_routing = self._prepare_routing_pull()
        if not moves_routing:
            return self
        # apply the routing
        moves = self._routing_splits(moves_routing)
        moves._apply_routing_rule_pull()
        return moves

    def _prepare_routing_pull(self):
        """Prepare pull routing rules for moves

        When a move has move lines with different routing rules or lines with
        routing rules and lines without, on the source/dest location, we have
        to split the moves. This method assigns the moves in a savepoint to
        compute the routing rules according the move lines.

        If no routing has to be applied, the savepoint is released.
        If routing must be applied on at least one move, the savepoint is
        rollbacked and will be called after the routing rules have been applied.

        Return the computed routing rules for the next step, which will be
        to split the moves.
        """
        if not self:
            return self

        savepoint_name = uuid.uuid1().hex
        # pylint: disable=sql-injection
        self.env.cr.execute(
            sql.SQL("SAVEPOINT {}").format(sql.Identifier(savepoint_name))
        )
        super(StockMove, self).action_assign()

        moves_routing = self._routing_compute_rules()

        if not any(rule for routing in moves_routing.values() for rule in routing):
            # no routing to apply, so the reservations done by _action_assign
            # are valid and we can resolve to a normal flow
            # self.env["base"].flush()
            # pylint: disable=sql-injection
            # FIXME is commit needed??
            self.env.cr.execute(
                sql.SQL("RELEASE SAVEPOINT {}").format(sql.Identifier(savepoint_name))
            )
            return {}

        # rollback _action_assign, it'll be called again after the routing
        self.env.clear()
        # pylint: disable=sql-injection
        self.env.cr.execute(
            sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(savepoint_name))
        )
        return moves_routing

    @api.multi
    def _routing_compute_rules(self):
        """Compute routing pull rules

        Called in a savepoint (_prepare_routing_pull).
        Return a dictionary {move: {rule: reserved quantity}}. The rule for a quantity
        can be an empty recordset, which means no routing rule.
        """
        move_routing_rules = self.env["stock.routing"]._routing_rule_for_moves(self)
        moves_routing = {}
        no_routing_rule = self.env["stock.routing.rule"].browse()
        for move in self:
            if move.state not in ("assigned", "partially_available"):
                continue

            # Group move lines per their rule, some may need an additional
            # operations while others not. Store the number of products to
            # take from each location, so we'll be able to split the move
            # if needed.
            routing_rules = move_routing_rules[move]
            moves_routing[move] = {
                rule: sum(quants.mapped("qty"))
                for rule, quants in routing_rules.items()
            }
#            if move.state == "partially_available":
#                # consider unreserved quantity as without routing, so it will
#                # be split if another part of the quantity need a routing
#                moves_routing[move].setdefault(no_routing_rule, 0)
#                moves_routing[move][no_routing_rule] += (
#                    move.product_uom_qty - move.reserved_availability
#                )
        return moves_routing

    @api.multi
    def _routing_splits(self, moves_routing):
        """Split moves according to routing rules

        This method splits the move in as many routing pull rules they have.

        This method writes "routing_rule_id" on the moves, this rule will be
        used by ``_apply_routing_rule_pull`` / ``_apply_routing_rule_push``
        """
        new_move_per_location = {}
        for move, routing_quantities in moves_routing.items():
            for routing_rule, qty in routing_quantities.items():
                # When the rule is empty, it means we have no routing
                # operation for the move, so we have nothing to do,
                # it will behave as normally.
                if not routing_rule:
                    continue
                routing_location = routing_rule.location_src_id
                # If we have a routing operation, the move may have several
                # lines with different routing operations (or lines with
                # a routing operation, lines without). We split the lines
                # according to these.
                # The _split() method returns the same move if the qty
                # is the same than the move's qty, so we don't need to
                # explicitly check if we really need to split or not.
                new_move_id = move.split(move, qty)
                new_move = self.env["stock.move"].browse(new_move_id)
                new_move.routing_rule_id = routing_rule
                new_move_per_location.setdefault(routing_location.id, [])
                new_move_per_location[routing_location.id].append(new_move_id)

        new_moves = self.browse(chain.from_iterable(new_move_per_location.values()))
        return self + new_moves

    @api.multi
    def _apply_routing_rule_pull(self):
        """Apply routing operations

        When a move has a routing operation configured on its location and the
        destination of the move does not match the destination of the routing
        operation, this method updates the move's destination and it's picking
        type with the routing operation ones and creates a new chained move
        after it.
        """
        pickings_to_check_for_emptiness = self.env["stock.picking"]
        for move in self:
            routing_rule = move.routing_rule_id
            if not routing_rule.method == "pull":
                continue

            if move.picking_id.picking_type_id == routing_rule.picking_type_id:
                # already correct
                continue

            # we expect all the lines to go to the same destination for
            # pull routing rules

            original_source = move.location_id
            original_destination = move.location_dest_id
            current_picking_type = move.picking_id.picking_type_id
            # TODO
            move = move.with_context(prefetch_fields=False)
            if self.env["stock.location"].search(
                [
                    ("id", "=", routing_rule.location_dest_id.id),
                    ("id", "child_of", move.location_dest_id.id),
                ]
            ):
                # The destination of the move, as a parent of the destination
                # of the routing, goes to the correct place, but is not precise
                # enough: set the new destination to match the rule's one
                move.write({
                    'location_id': routing_rule.location_src_id.id,
                    'location_dest_id': routing_rule.location_dest_id.id,
                    'picking_type_id': routing_rule.picking_type_id.id,
                })

            elif not self.env["stock.location"].search(
                [
                    ("id", "=", routing_rule.location_dest_id.id),
                    ('parent_right', '>=', move.location_dest_id.parent_right),
                    ('parent_left', '<=', move.location_dest_id.parent_left),
                ]
            ):
                # The destination of the move is unrelated (nor identical, nor
                # a parent or a child) to the routing destination: in this case
                # we have to add a routing move before the current move to
                # route the goods in the correct place
                move.write({
                    'location_id': routing_rule.location_src_id.id,
                    'location_dest_id': routing_rule.location_dest_id.id,
                    'picking_type_id': routing_rule.picking_type_id.id,
                })
                # create a copy of the move with the current picking type and
                # going to its original destination: it will be assigned to the
                # same picking as the original picking of our move
                move._insert_routing_moves(
                    current_picking_type, original_source, original_destination
                )
            else:
                move.write({
                    'location_id': routing_rule.location_src_id.id,
                    'picking_type_id': routing_rule.picking_type_id.id,
                })


            pickings_to_check_for_emptiness |= move.picking_id
            move.with_context(old_picking=move.picking_id.id)._picking_assign(
                move.group_id.id, move.location_id.id, move.location_dest_id.id)
#            move.action_assign()

        pickings_to_check_for_emptiness._routing_operation_handle_empty()

    @api.multi
    def _insert_routing_moves(self, picking_type, location, destination):
        """Create a chained move for the source routing operation"""
        self.ensure_one()
        # Insert move between the source and destination for the new
        # operation
        routing_move_values = self._prepare_routing_move_values(
            picking_type, location, destination
        )
        routing_move = self.copy(routing_move_values)

        # modify the chain to include the new move
        self.write(
            {'move_dest_id': routing_move.id}
        )
        routing_move.action_confirm()

    @api.multi
    def _prepare_routing_move_values(self, picking_type, source, destination):
        return {
            "picking_id": False,
            "location_id": source.id,
            "location_dest_id": destination.id,
            "state": "waiting",
            "picking_type_id": picking_type.id,
            "move_dest_id": self.move_dest_id.id,
        }
