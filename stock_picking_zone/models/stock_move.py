# Copyright 2019 Camptocamp (https://www.camptocamp.com)

from itertools import chain
from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_assign(self):
        super()._action_assign()
        if not self.env.context.get('exclude_apply_zone'):
            moves = self._split_per_zone()
            moves._apply_move_location_zone()

    def _split_per_zone(self):
        move_to_assign_ids = set()
        new_move_per_location = {}
        for move in self:
            if move.state not in ('assigned', 'partially_available'):
                continue

            pick_type_model = self.env['stock.picking.type']

            # Group move lines per source location, some may need an additional
            # operations while others not. Store the number of products to
            # take from each location, so we'll be able to split the move
            # if needed.
            move_lines = {}
            for move_line in move.move_line_ids:
                location = move_line.location_id
                move_lines[location] = sum(move_line.mapped('product_uom_qty'))

            # We'll split the move to have one move per different zones where
            # we have to take products
            zone_quantities = {}
            for source_location, qty in move_lines.items():
                zone = pick_type_model._find_zone_for_location(source_location)
                zone_quantities.setdefault(zone, 0.0)
                zone_quantities[zone] += qty

            if len(zone_quantities) == 1:
                # The whole quantity can be taken from only one zone (a
                # non-zone being equal to a zone here), nothing to split.
                continue

            move._do_unreserve()
            move_to_assign_ids.add(move.id)
            zone_location = zone.default_location_src_id
            for zone, qty in zone_quantities.items():
                # if zone is False-ish, we take in a location which is
                # not a zone
                if zone:
                    # split returns the same move if the qty is the same
                    new_move_id = move._split(qty)
                    new_move_per_location.setdefault(zone_location.id, [])
                    new_move_per_location[zone_location.id].append(new_move_id)

        # it is important to assign the zones first
        for location_id, new_move_ids in new_move_per_location.items():
            new_moves = self.browse(new_move_ids)
            new_moves.with_context(
                # Prevent to call _apply_move_location_zone, will be called
                # when all lines are processed.
                exclude_apply_zone=True,
                # Force reservation of quants in the zone they were
                # reserved in at the origin (so we keep the same quantities
                # at the same places)
                gather_in_location_id=location_id,
            )._action_assign()

        # reassign the moves which have been unreserved for the split
        moves_to_assign = self.browse(move_to_assign_ids)
        if moves_to_assign:
            moves_to_assign._action_assign()
        new_moves = self.browse(chain.from_iterable(
            new_move_per_location.values()
        ))
        return self + new_moves

    def _apply_move_location_zone(self):
        for move in self:
            if move.state not in ('assigned', 'partially_available'):
                continue

            pick_type_model = self.env['stock.picking.type']

            # Group move lines per source location, some may need an additional
            # operations while others not. Store the number of products to
            # take from each location, so we'll be able to split the move
            # if needed.
            # At this point, we should not have lines with different zones,
            # they have been split in _split_per_zone(), so we can take the
            # first one
            source = move.move_line_ids[0].location_id
            zone = pick_type_model._find_zone_for_location(source)
            if not zone:
                continue
            if (move.picking_type_id == zone and
                    move.location_dest_id == zone.default_location_dest_id):
                # already done
                continue

            move._do_unreserve()
            move.write({
                'location_dest_id': zone.default_location_dest_id.id,
                'picking_type_id': zone.id,
            })
            move._insert_middle_moves()
            move._assign_picking()
            move._action_assign()

    def _insert_middle_moves(self):
        self.ensure_one()
        dest_moves = self.move_dest_ids
        dest_location = self.location_dest_id
        for dest_move in dest_moves:
            final_location = dest_move.location_id
            if dest_location == final_location:
                # shortcircuit to avoid a query checking if it is a child
                continue
            child_locations = self.env['stock.location'].search([
                ('id', 'child_of', final_location.id)
            ])
            if dest_location in child_locations:
                # normal behavior, we don't need a move between A and B
                continue
            # Insert move between the source and destination for the new
            # operation
            middle_move_values = self._prepare_middle_move_values(
                final_location
            )
            middle_move = self.copy(middle_move_values)
            dest_move.write({
                'move_orig_ids': [(3, self.id), (4, middle_move.id)],
            })
            self.write({
                'move_dest_ids': [(3, dest_move.id), (4, middle_move.id)],
            })
            middle_move._action_confirm(merge=False)

    def _prepare_middle_move_values(self, destination):
        return {
            'picking_id': False,
            'location_id': self.location_id.id,
            'location_dest_id': destination.id,
            'state': 'waiting',
            'picking_type_id': self.picking_id.picking_type_id.id,
        }