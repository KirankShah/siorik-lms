"""Pinned BS month lengths used to verify nepali-datetime at runtime/tests.

2083-2090 is the supported business range. The adjacent years are retained
only so fiscal periods at either edge can be represented without guessing.
Values are copied from nepali-datetime 1.0.8.5's calendar_bs.csv.
"""

SUPPORTED_FIRST_YEAR = 2083
SUPPORTED_LAST_YEAR = 2090

BS_MONTH_LENGTHS = {
    2082: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2083: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2084: (31, 31, 32, 31, 31, 30, 30, 30, 29, 30, 30, 30),
    2085: (31, 32, 31, 32, 30, 31, 30, 30, 29, 30, 30, 30),
    2086: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2087: (31, 31, 32, 31, 31, 31, 30, 29, 30, 30, 30, 30),
    2088: (30, 31, 32, 32, 30, 31, 30, 30, 29, 30, 30, 30),
    2089: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2090: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2091: (31, 31, 32, 31, 31, 31, 30, 30, 29, 30, 30, 30),
}
