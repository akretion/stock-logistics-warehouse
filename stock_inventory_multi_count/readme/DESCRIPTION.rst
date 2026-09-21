This module implements a blind, multi-round physical inventory count on top of
``stock_inventory``.

Operationally, a full physical inventory is not a single count. A first count is
made without the counters seeing the on hand quantity. The items whose count
agrees with the reference are reconciled and adjusted immediately; the divergent
ones are carried over to a new count round, given to a different counter. The
loop stops after a configurable number of rounds and what is still unresolved
goes to a supervisor for arbitration, with a mandatory justification.

Compared to chaining several inventory adjustments by hand, this module gives:

* **A real blind count.** The theoretical quantity is stored on the count line
  and restricted to stock managers at ORM level, so it disappears from the
  counter's list, exports and RPC calls.
* **The full count history in one place.** Theoretical, first count, second
  count and final quantity are readable side by side instead of being scattered
  across several adjustments.
* **A correct comparison.** From the second round on, the count is compared with
  the previous count, not with the system quantity. Two independent physical
  counts that agree win; the book value is never a tie breaker.
* **Tolerances.** Exact match, quantity, percentage or value, following what SAP
  and Oracle do. Strict equality on a large inventory sends thousands of
  irrelevant lines to recount.
* **A bounded loop.** ``Maximum rounds`` then arbitration, like Oracle's
  ``Maximum Automatic Recounts``.
