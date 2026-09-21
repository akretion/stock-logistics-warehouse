# Copyright 2026 Akretion - Renato Lima
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Shared selections between ``res.company`` and ``stock.inventory``.

Kept in a dedicated module so both can import them without a circular
dependency.
"""

TOLERANCE_TYPES = [
    ("exact", "Exact match"),
    ("qty", "Quantity"),
    ("percent", "Percentage"),
    ("value", "Value"),
]

UNCOUNTED_POLICIES = [
    ("block", "Block the closing of the round"),
    ("zero", "Treat as counted zero"),
    ("theoretical", "Keep the theoretical quantity"),
]

FIRST_ROUND_CRITERIA = [
    ("theoretical", "Accept when it matches the theoretical quantity"),
    ("none", "Always require two converging counts"),
]
