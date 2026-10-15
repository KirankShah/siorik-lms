# Periodic Exam calendar verification checklist

> **Not independently verified:** every BS month length and BS↔Gregorian conversion below comes from the pinned `nepali-datetime==1.0.8.5` library. The repository lookup table was copied from that same library, so agreement between the two is not independent evidence. An authorised reviewer must compare every row with an official Patro and enter initials/date in the blank column before production use.

The application treats cycle windows as Kathmandu-local calendar days. The first day starts at `00:00 Asia/Kathmandu`; the exclusive instant after the listed final day is also `00:00 Asia/Kathmandu`. Quarterly, half-yearly and yearly cycles use the Nepali fiscal year beginning on Shrawan 1.

## Computed cycle boundaries

| Frequency | Cycle | Start (BS) | Start (AD) | End (BS) | End (AD) | Verified against official Patro (initials/date) |
|---|---|---|---|---|---|---|
| Monthly | 2083 Baishakh | 2083-01-01 | 2026-04-14 | 2083-01-31 | 2026-05-14 | |
| Monthly | 2083 Jestha | 2083-02-01 | 2026-05-15 | 2083-02-31 | 2026-06-14 | |
| Monthly | 2083 Asar | 2083-03-01 | 2026-06-15 | 2083-03-32 | 2026-07-16 | |
| Monthly | 2083 Shrawan | 2083-04-01 | 2026-07-17 | 2083-04-31 | 2026-08-16 | |
| Monthly | 2083 Bhadra | 2083-05-01 | 2026-08-17 | 2083-05-31 | 2026-09-16 | |
| Monthly | 2083 Asoj | 2083-06-01 | 2026-09-17 | 2083-06-31 | 2026-10-17 | |
| Monthly | 2083 Kartik | 2083-07-01 | 2026-10-18 | 2083-07-30 | 2026-11-16 | |
| Monthly | 2083 Mangsir | 2083-08-01 | 2026-11-17 | 2083-08-29 | 2026-12-15 | |
| Monthly | 2083 Poush | 2083-09-01 | 2026-12-16 | 2083-09-30 | 2027-01-14 | |
| Monthly | 2083 Magh | 2083-10-01 | 2027-01-15 | 2083-10-29 | 2027-02-12 | |
| Monthly | 2083 Falgun | 2083-11-01 | 2027-02-13 | 2083-11-30 | 2027-03-14 | |
| Monthly | 2083 Chaitra | 2083-12-01 | 2027-03-15 | 2083-12-30 | 2027-04-13 | |
| Monthly | 2084 Baishakh | 2084-01-01 | 2027-04-14 | 2084-01-31 | 2027-05-14 | |
| Monthly | 2084 Jestha | 2084-02-01 | 2027-05-15 | 2084-02-31 | 2027-06-14 | |
| Monthly | 2084 Asar | 2084-03-01 | 2027-06-15 | 2084-03-32 | 2027-07-16 | |
| Monthly | 2084 Shrawan | 2084-04-01 | 2027-07-17 | 2084-04-31 | 2027-08-16 | |
| Monthly | 2084 Bhadra | 2084-05-01 | 2027-08-17 | 2084-05-31 | 2027-09-16 | |
| Monthly | 2084 Asoj | 2084-06-01 | 2027-09-17 | 2084-06-30 | 2027-10-16 | |
| Monthly | 2084 Kartik | 2084-07-01 | 2027-10-17 | 2084-07-30 | 2027-11-15 | |
| Monthly | 2084 Mangsir | 2084-08-01 | 2027-11-16 | 2084-08-30 | 2027-12-15 | |
| Monthly | 2084 Poush | 2084-09-01 | 2027-12-16 | 2084-09-29 | 2028-01-13 | |
| Monthly | 2084 Magh | 2084-10-01 | 2028-01-14 | 2084-10-30 | 2028-02-12 | |
| Monthly | 2084 Falgun | 2084-11-01 | 2028-02-13 | 2084-11-30 | 2028-03-13 | |
| Monthly | 2084 Chaitra | 2084-12-01 | 2028-03-14 | 2084-12-30 | 2028-04-12 | |
| Quarterly | FY 2083/84 Q1 | 2083-04-01 | 2026-07-17 | 2083-06-31 | 2026-10-17 | |
| Quarterly | FY 2083/84 Q2 | 2083-07-01 | 2026-10-18 | 2083-09-30 | 2027-01-14 | |
| Quarterly | FY 2083/84 Q3 | 2083-10-01 | 2027-01-15 | 2083-12-30 | 2027-04-13 | |
| Quarterly | FY 2083/84 Q4 | 2084-01-01 | 2027-04-14 | 2084-03-32 | 2027-07-16 | |
| Quarterly | FY 2084/85 Q1 | 2084-04-01 | 2027-07-17 | 2084-06-30 | 2027-10-16 | |
| Quarterly | FY 2084/85 Q2 | 2084-07-01 | 2027-10-17 | 2084-09-29 | 2028-01-13 | |
| Quarterly | FY 2084/85 Q3 | 2084-10-01 | 2028-01-14 | 2084-12-30 | 2028-04-12 | |
| Quarterly | FY 2084/85 Q4 | 2085-01-01 | 2028-04-13 | 2085-03-31 | 2028-07-15 | |
| Half-yearly | FY 2083/84 H1 | 2083-04-01 | 2026-07-17 | 2083-09-30 | 2027-01-14 | |
| Half-yearly | FY 2083/84 H2 | 2083-10-01 | 2027-01-15 | 2084-03-32 | 2027-07-16 | |
| Half-yearly | FY 2084/85 H1 | 2084-04-01 | 2027-07-17 | 2084-09-29 | 2028-01-13 | |
| Half-yearly | FY 2084/85 H2 | 2084-10-01 | 2028-01-14 | 2085-03-31 | 2028-07-15 | |
| Yearly | FY 2083/84 | 2083-04-01 | 2026-07-17 | 2084-03-32 | 2027-07-16 | |
| Yearly | FY 2084/85 | 2084-04-01 | 2027-07-17 | 2085-03-31 | 2028-07-15 | |

The quarterly starts explicitly cover Shrawan 1, Kartik 1, Magh 1 and Baishakh 1. Q4, H2 and the yearly cycle cross into the following BS year as shown.

## BS month lengths

| BS year | Month | Month number | Days | Verified against official Patro (initials/date) |
|---|---|---:|---:|---|
| 2083 | Baishakh | 1 | 31 | |
| 2083 | Jestha | 2 | 31 | |
| 2083 | Asar | 3 | 32 | |
| 2083 | Shrawan | 4 | 31 | |
| 2083 | Bhadra | 5 | 31 | |
| 2083 | Asoj | 6 | 31 | |
| 2083 | Kartik | 7 | 30 | |
| 2083 | Mangsir | 8 | 29 | |
| 2083 | Poush | 9 | 30 | |
| 2083 | Magh | 10 | 29 | |
| 2083 | Falgun | 11 | 30 | |
| 2083 | Chaitra | 12 | 30 | |
| 2084 | Baishakh | 1 | 31 | |
| 2084 | Jestha | 2 | 31 | |
| 2084 | Asar | 3 | 32 | |
| 2084 | Shrawan | 4 | 31 | |
| 2084 | Bhadra | 5 | 31 | |
| 2084 | Asoj | 6 | 30 | |
| 2084 | Kartik | 7 | 30 | |
| 2084 | Mangsir | 8 | 30 | |
| 2084 | Poush | 9 | 29 | |
| 2084 | Magh | 10 | 30 | |
| 2084 | Falgun | 11 | 30 | |
| 2084 | Chaitra | 12 | 30 | |
