* Parallel mode: open rounds 1 and 2 at the same time for two independent teams,
  so the freeze window is shorter and the first count does not anchor the
  second one.
* Hit/miss accuracy per counter and per location, in the spirit of Oracle's
  Cycle Count Hit/Miss Analysis.
* Per-user deviation limits (as Dynamics 365 does on the *Work users* page), so
  a count outside a junior counter's limit goes straight to review.
* Glue module reading the tolerance from ``stock_inventory_discrepancy``
  thresholds (``_tolerance_value_for`` is the hook).
* Counting in packaging units with conversion on entry.
* Barcode entry through ``stock_barcodes``.

Known limitation: a counter who also holds ``stock.group_stock_user`` can still
read the on hand quantity from the product form or the quant list. Full
blindness requires a counting-only profile; the restricted fields on the count
line only guarantee that the count screen itself reveals nothing.
