Go to *Inventory > Configuration > Settings > Blind Multi Count* to set the
defaults applied to new inventory adjustments:

#. **Maximum Count Rounds** -- how many rounds before arbitration (default 3).
#. **First Round Criterion** -- accept a first count that matches the
   theoretical quantity, or always require two converging counts.
#. **Tolerance Type / Tolerance** -- exact, quantity, percentage or value.
#. **Uncounted Lines Policy** -- block the closing, treat as zero, or keep the
   theoretical quantity.
#. **Require a Different Counter per Round**.
#. **Create Zero Quantity Moves** -- off by default; the count line is already
   the audit trail.

Each inventory adjustment keeps its own copy of these settings, editable while
it is in draft.

Give the *Inventory Counter* group to the users who only enter counts. They will
see the rounds they are assigned to and never the theoretical quantity.
