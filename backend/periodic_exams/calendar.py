from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import nepali_datetime

from .calendar_data import BS_MONTH_LENGTHS, SUPPORTED_FIRST_YEAR, SUPPORTED_LAST_YEAR

KATHMANDU = ZoneInfo('Asia/Kathmandu')


class CalendarRangeError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class BSDate:
    year: int
    month: int
    day: int = 1


@dataclass(frozen=True)
class PeriodBoundary:
    frequency: str
    start_bs: BSDate
    end_exclusive_bs: BSDate
    starts_at: datetime
    ends_at: datetime
    start_date_ad: date
    end_date_ad: date
    end_bs: BSDate
    fiscal_year_start_bs: int
    period_number: int
    display_label: str


FREQUENCIES = ('MONTHLY', 'QUARTERLY', 'HALF_YEARLY', 'YEARLY')
MONTH_NAMES = (
    'Baishakh', 'Jestha', 'Asar', 'Shrawan', 'Bhadra', 'Asoj',
    'Kartik', 'Mangsir', 'Poush', 'Magh', 'Falgun', 'Chaitra',
)


def month_length(year: int, month: int) -> int:
    if year < SUPPORTED_FIRST_YEAR or year > SUPPORTED_LAST_YEAR:
        raise CalendarRangeError(f'BS year {year} is outside the supported 2083-2090 range.')
    if month < 1 or month > 12:
        raise ValueError('BS month must be between 1 and 12.')
    return BS_MONTH_LENGTHS[year][month - 1]


def _validate_boundary_date(value: BSDate) -> None:
    lengths = BS_MONTH_LENGTHS.get(value.year)
    if lengths is None:
        raise CalendarRangeError('Required boundary is outside the verified lookup table.')
    if value.month < 1 or value.month > 12:
        raise ValueError('BS month must be between 1 and 12.')
    if value.day < 1 or value.day > lengths[value.month - 1]:
        raise ValueError('Invalid day for BS month.')


def _bs_to_ad(value: BSDate) -> date:
    _validate_boundary_date(value)
    return nepali_datetime.date(value.year, value.month, value.day).to_datetime_date()


def ad_to_bs(value: date) -> BSDate:
    converted = nepali_datetime.date.from_datetime_date(value)
    if converted.year < SUPPORTED_FIRST_YEAR or converted.year > SUPPORTED_LAST_YEAR:
        raise CalendarRangeError('Gregorian date converts outside the supported BS range.')
    return BSDate(converted.year, converted.month, converted.day)


def _add_bs_months(value: BSDate, months: int) -> BSDate:
    absolute = value.year * 12 + value.month - 1 + months
    return BSDate(absolute // 12, absolute % 12 + 1, 1)


def _period_start(frequency: str, current: BSDate) -> tuple[BSDate, int, int]:
    if frequency not in FREQUENCIES:
        raise ValueError('Unsupported frequency.')
    fiscal_year = current.year if current.month >= 4 else current.year - 1
    fiscal_offset = (current.year - fiscal_year) * 12 + current.month - 4
    if frequency == 'MONTHLY':
        return BSDate(current.year, current.month, 1), fiscal_offset + 1, fiscal_year
    size = {'QUARTERLY': 3, 'HALF_YEARLY': 6, 'YEARLY': 12}[frequency]
    period_number = fiscal_offset // size + 1
    return _add_bs_months(BSDate(fiscal_year, 4, 1), (period_number - 1) * size), period_number, fiscal_year


def period_for(frequency: str, instant: datetime) -> PeriodBoundary:
    if instant.tzinfo is None:
        raise ValueError('A timezone-aware instant is required.')
    local = instant.astimezone(KATHMANDU)
    current = ad_to_bs(local.date())
    start_bs, period_number, fiscal_year = _period_start(frequency, current)
    months = {'MONTHLY': 1, 'QUARTERLY': 3, 'HALF_YEARLY': 6, 'YEARLY': 12}[frequency]
    end_exclusive_bs = _add_bs_months(start_bs, months)
    start_ad = _bs_to_ad(start_bs)
    end_exclusive_ad = _bs_to_ad(end_exclusive_bs)
    end_ad = end_exclusive_ad - timedelta(days=1)
    end_bs_date = nepali_datetime.date.from_datetime_date(end_ad)
    end_bs = BSDate(end_bs_date.year, end_bs_date.month, end_bs_date.day)
    starts_at = datetime.combine(start_ad, time.min, KATHMANDU).astimezone(timezone.utc)
    ends_at = datetime.combine(end_exclusive_ad, time.min, KATHMANDU).astimezone(timezone.utc)
    if frequency == 'MONTHLY':
        label = f'{start_bs.year} {MONTH_NAMES[start_bs.month - 1]}'
    else:
        short = {'QUARTERLY': 'Q', 'HALF_YEARLY': 'H', 'YEARLY': 'FY'}[frequency]
        suffix = '' if frequency == 'YEARLY' else str(period_number)
        label = f'{fiscal_year}/{str(fiscal_year + 1)[-2:]} {short}{suffix}'.strip()
    return PeriodBoundary(
        frequency=frequency,
        start_bs=start_bs,
        end_exclusive_bs=end_exclusive_bs,
        starts_at=starts_at,
        ends_at=ends_at,
        start_date_ad=start_ad,
        end_date_ad=end_ad,
        end_bs=end_bs,
        fiscal_year_start_bs=fiscal_year,
        period_number=period_number,
        display_label=label,
    )


def next_full_period_start(frequency: str, instant: datetime) -> datetime:
    period = period_for(frequency, instant)
    local = instant.astimezone(KATHMANDU)
    if instant == period.starts_at and local.time() == time.min:
        return period.starts_at
    return period.ends_at


def first_full_period_start_on_or_after(frequency: str, instant: datetime) -> datetime:
    period = period_for(frequency, instant)
    return period.starts_at if instant <= period.starts_at else period.ends_at
