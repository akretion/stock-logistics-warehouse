from odoo import api, fields, models
from odoo.osv.expression import TERM_OPERATORS_NEGATION

from odoo.addons.base.models.ir_property import TYPE2CLEAN, TYPE2FIELD


class Property(models.Model):
    _inherit = "ir.property"

    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", index=True)

    def init(self):
        # Ensure there is at most one active variant for each combination.
        self.env.cr.execute("DROP INDEX IF EXISTS ir_property_unique_index")
        query = """
            CREATE UNIQUE INDEX IF NOT EXISTS ir_property_unique_wh_index
            ON %s (fields_id, COALESCE(warehouse_id, 0), COALESCE(res_id, ''),
            COALESCE(company_id, 0))
        """
        self.env.cr.execute(query % self._table)

    @api.model
    def _set_default_wh(self, name, model, value, warehouse=False):
        """Set the given field's generic value for the given warehouse.

        :param name: the field's name
        :param model: the field's model name
        :param value: the field's value
        :param warehouse: the company (record or id)
        """
        field_id = self.env["ir.model.fields"]._get(model, name).id
        warehouse_id = int(warehouse) if warehouse else False
        prop = self.sudo().search(
            [
                ("fields_id", "=", field_id),
                ("warehouse_id", "=", warehouse_id),
                ("res_id", "=", False),
            ]
        )
        if prop:
            prop.write({"value": value})
        else:
            prop.create(
                {
                    "fields_id": field_id,
                    "warehouse_id": warehouse_id,
                    "res_id": False,
                    "name": name,
                    "value": value,
                    "type": self.env[model]._fields[name].type,
                }
            )

    @api.model
    def _get_wh(self, name, model, res_id=False):
        """Get the given field's generic value for the record.

        :param name: the field's name
        :param model: the field's model name
        :param res_id: optional resource, format: "<id>" (int) or
                       "<model>,<id>" (str)
        """
        if not res_id:
            t, v = self._get_default_property_wh(name, model)
            if not v or t != "many2one":
                return v
            return self.env[v[0]].browse(v[1])

        p = self._get_property_wh(name, model, res_id=res_id)
        if p:
            return p.get_by_record()
        return False

    def _get_default_property_wh(self, name, model):
        prop = self._get_property_wh(name, model, res_id=False)
        if not prop:
            return None, False
        v = prop.get_by_record()
        if prop.type != "many2one":
            return prop.type, v
        return "many2one", v and (v._name, v.id)

    def _get_property_wh(self, name, model, res_id):
        domain = self._get_domain_wh(name, model)
        if domain is not None:
            if res_id and isinstance(res_id, int):
                res_id = "%s,%s" % (model, res_id)
            domain = [("res_id", "=", res_id)] + domain
            # make the search with warehouse_id asc to make sure that properties
            # specific to a warehouse are given first
            return self.sudo().search(domain, limit=1, order="warehouse_id")
        return self.sudo().browse(())

    def _get_domain_wh(self, prop_name, model):
        field_id = self.env["ir.model.fields"]._get(model, prop_name).id
        if not field_id:
            return None
        warehouse_id = self._get_warehouse_id()
        return [
            ("fields_id", "=", field_id),
            ("warehouse_id", "in", [warehouse_id, False]),
        ]

    @api.model
    def _get_warehouse_id(self):
        warehouse_id = self.env.context.get(
            "force_warehouse", self.env.user._get_default_warehouse_id().id
        )
        return warehouse_id

    @api.model
    def _get_multi_wh(self, name, model, ids):
        """Read the property field `name` for the records of model `model` with
        the given `ids`, and return a dictionary mapping `ids` to their
        corresponding value.
        """
        if not ids:
            return {}

        field = self.env[model]._fields[name]
        field_id = self.env["ir.model.fields"]._get(model, name).id
        warehouse_id = self._get_warehouse_id()

        if field.type == "many2one":
            comodel = self.env[field.comodel_name]
            model_pos = len(model) + 2
            value_pos = len(comodel._name) + 2
            # retrieve values: both p.res_id and p.value_reference are formatted
            # as "<rec._name>,<rec.id>"; the purpose of the LEFT JOIN is to
            # return the value id if it exists, NULL otherwise
            query = """
                SELECT substr(p.res_id, %s)::integer, r.id
                FROM ir_property p
                LEFT JOIN {} r ON substr(p.value_reference, %s)::integer=r.id
                WHERE p.fields_id=%s
                    AND (p.warehouse_id=%s OR p.warehouse IS NULL)
                    AND (p.res_id IN %s OR p.res_id IS NULL)
                ORDER BY p.warehouse_id NULLS FIRST
            """.format(
                comodel._table
            )
            params = [model_pos, value_pos, field_id, warehouse_id]
            clean = comodel.browse

        elif field.type in TYPE2FIELD:
            model_pos = len(model) + 2
            # retrieve values: p.res_id is formatted as "<rec._name>,<rec.id>"
            query = """
                SELECT substr(p.res_id, %s)::integer, p.{}
                FROM ir_property p
                WHERE p.fields_id=%s
                    AND (p.warehouse_id=%s OR p.warehouse_id IS NULL)
                    AND (p.res_id IN %s OR p.res_id IS NULL)
                ORDER BY p.warehouse_id NULLS FIRST
            """.format(
                TYPE2FIELD[field.type]
            )
            params = [model_pos, field_id, warehouse_id]
            clean = TYPE2CLEAN[field.type]

        else:
            return dict.fromkeys(ids, False)

        # retrieve values
        cr = self.env.cr
        result = {}
        refs = {"%s,%s" % (model, id) for id in ids}
        for sub_refs in cr.split_for_in_conditions(refs):
            cr.execute(query, params + [sub_refs])
            result.update(cr.fetchall())

        # determine all values and format them
        default = result.get(None, None)
        return {id: clean(result.get(id, default)) for id in ids}

    @api.model
    def _set_multi_wh(self, name, model, values, default_value=None):
        """Assign the property field `name` for the records of model `model`
        with `values` (dictionary mapping record ids to their value).
        If the value for a given record is the same as the default
        value, the property entry will not be stored, to avoid bloating
        the database.
        If `default_value` is provided, that value will be used instead
        of the computed default value, to determine whether the value
        for a record should be stored or not.
        """

        def clean(value):
            return value.id if isinstance(value, models.BaseModel) else value

        if not values:
            return

        if default_value is None:
            domain = self._get_domain_wh(name, model)
            if domain is None:
                raise Exception()
            # retrieve the default value for the field
            default_value = clean(self._get_wh(name, model))

        # retrieve the properties corresponding to the given record ids
        field_id = self.env["ir.model.fields"]._get(model, name).id
        warehouse_id = self._get_warehouse_id()
        refs = {("%s,%s" % (model, id)): id for id in values}
        props = self.sudo().search(
            [
                ("fields_id", "=", field_id),
                ("warehouse_id", "=", warehouse_id),
                ("res_id", "in", list(refs)),
            ]
        )

        # modify existing properties
        for prop in props:
            id = refs.pop(prop.res_id)  # pylint: disable=W0622
            value = clean(values[id])
            if value == default_value:
                # avoid prop.unlink(), as it clears the record cache that can
                # contain the value of other properties to set on record!
                self._cr.execute("DELETE FROM ir_property WHERE id=%s", [prop.id])
            elif value != clean(prop.get_by_record()):
                prop.write({"value": value})

        # create new properties for records that do not have one yet
        vals_list = []
        for ref, id in refs.items():
            value = clean(values[id])
            if value != default_value:
                vals_list.append(
                    {
                        "fields_id": field_id,
                        "warehouse_id": warehouse_id,
                        "res_id": ref,
                        "name": name,
                        "value": value,
                        "type": self.env[model]._fields[name].type,
                    }
                )
        self.sudo().create(vals_list)

    @api.model
    def search_multi_wh(self, name, model, operator, value):  # noqa: C901
        """Return a domain for the records that match the given condition."""
        default_matches = False
        negate = False

        # For "is set" and "is not set", same logic for all types
        if operator == "in" and False in value:
            operator = "not in"
            negate = True
        elif operator == "not in" and False not in value:
            operator = "in"
            negate = True
        elif operator in ("!=", "not like", "not ilike") and value:
            operator = TERM_OPERATORS_NEGATION[operator]
            negate = True
        elif operator == "=" and not value:
            operator = "!="
            negate = True

        field = self.env[model]._fields[name]

        if field.type == "many2one":

            def makeref(value):
                return value and f"{field.comodel_name},{value}"

            if operator in ("=", "!=", "<=", "<", ">", ">="):
                value = makeref(value)
            elif operator in ("in", "not in"):
                value = [makeref(v) for v in value]
            elif operator in (
                "=like",
                "=ilike",
                "like",
                "not like",
                "ilike",
                "not ilike",
            ):
                # most probably inefficient... but correct
                target = self.env[field.comodel_name]
                target_names = target.name_search(value, operator=operator, limit=None)
                target_ids = [n[0] for n in target_names]
                operator, value = "in", [makeref(v) for v in target_ids]

        elif field.type in ("integer", "float"):
            # No record is created in ir.property if the field's type is float or
            # integer with a value equal to 0. Then to match with the records that are
            # linked to a property field equal to 0, the negation of the operator must
            # be taken  to compute the goods and the domain returned to match the
            # searched records is just the opposite.
            value = float(value) if field.type == "float" else int(value)
            if operator == ">=" and value <= 0:
                operator = "<"
                negate = True
            elif operator == ">" and value < 0:
                operator = "<="
                negate = True
            elif operator == "<=" and value >= 0:
                operator = ">"
                negate = True
            elif operator == "<" and value > 0:
                operator = ">="
                negate = True

        elif field.type == "boolean":
            # the value must be mapped to an integer value
            value = int(value)

        # retrieve the properties that match the condition
        domain = self._get_domain_wh(name, model)
        if domain is None:
            raise Exception()
        props = self.search(domain + [(TYPE2FIELD[field.type], operator, value)])

        # retrieve the records corresponding to the properties that match
        good_ids = []
        for prop in props:
            if prop.res_id:
                __, res_id = prop.res_id.split(",")
                good_ids.append(int(res_id))
            else:
                default_matches = True

        if default_matches:
            # exclude all records with a property that does not match
            props = self.search(domain + [("res_id", "!=", False)])
            all_ids = {int(res_id.split(",")[1]) for res_id in props.mapped("res_id")}
            bad_ids = list(all_ids - set(good_ids))
            if negate:
                return [("id", "in", bad_ids)]
            else:
                return [("id", "not in", bad_ids)]
        elif negate:
            return [("id", "not in", good_ids)]
        else:
            return [("id", "in", good_ids)]
