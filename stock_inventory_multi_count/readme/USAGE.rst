#. Go to *Inventory > Operations > Inventory Adjustments* and create an
   adjustment as usual (locations, product selection).
#. Set **Count Mode** to *Blind multi count* and review the count settings.
#. Click *Begin Adjustments*. Round 1 is created with one line per quant and the
   theoretical quantity is frozen on each line.
#. Assign the counters on the round, then either print the *Count Sheet* (no
   quantities on it), let the counters type their counts in *Count Lines*, or
   import a file with *Import Counts*.
#. Click *Close Current Round*. Lines within tolerance are adjusted immediately;
   the divergent ones open round 2.
#. Repeat. When the maximum number of rounds is reached, the adjustment moves to
   *Arbitration*: a stock manager picks the final quantity and justifies it.

Notes:

* A line counted zero is not the same as a line nobody counted. Use the
  *Counted* flag to tell them apart.
* Stock found where the system expected none can be added as a new count line;
  the quant is created when the line is applied.
* If a quant moves between the moment a round is created and the moment it is
  closed, the line is not applied: it is sent back for a recount instead of
  overwriting a legitimate movement.
