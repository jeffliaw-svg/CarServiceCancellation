"""Pro-rata refund estimation.

The estimate uses the standard consumer-unfavorable convention: the
"earned" (non-refundable) portion is the GREATER of the elapsed time
fraction and the elapsed mileage fraction. The administrator computes
the binding figure from the contract; this is only a quote for the
letter and for setting customer expectations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .models import AddOnProduct, RefundCase

DAYS_PER_MONTH = 30.4375  # 365.25 / 12


@dataclass
class RefundEstimate:
    product: AddOnProduct
    remaining_fraction: float
    gross_refund: float
    cancellation_fee: float
    net_refund: float
    basis: str
    can_estimate: bool = True
    warnings: list[str] = field(default_factory=list)


def months_between(start: date, end: date) -> float:
    return (end - start).days / DAYS_PER_MONTH


def _clamp_fraction(value: float) -> float:
    return max(0.0, min(1.0, value))


def estimate_refund(product: AddOnProduct, case: RefundCase) -> RefundEstimate:
    """Estimate the pro-rata refund owed on `product` for a vehicle sold on
    `case.sale_date`."""

    warnings: list[str] = []

    start = product.start_date or case.vehicle.purchase_date
    if start is None:
        return RefundEstimate(
            product=product,
            remaining_fraction=0.0,
            gross_refund=0.0,
            cancellation_fee=product.cancellation_fee,
            net_refund=0.0,
            basis="no coverage start date available",
            can_estimate=False,
            warnings=["Coverage start date (or vehicle purchase date) is missing."],
        )

    sale_date = case.sale_date
    if sale_date < start:
        warnings.append("Sale date is before coverage start date -- check the inputs.")

    # Elapsed time fraction.
    time_fraction: float | None = None
    if product.term_months:
        time_fraction = _clamp_fraction(months_between(start, sale_date) / product.term_months)
    else:
        warnings.append("Term in months is missing; time-based proration skipped.")

    # Elapsed mileage fraction.
    mileage_fraction: float | None = None
    start_odo = product.start_odometer
    if start_odo is None:
        start_odo = case.vehicle.odometer_at_purchase
    end_odo = case.vehicle.odometer_at_sale
    if product.term_miles and start_odo is not None and end_odo is not None:
        miles_used = end_odo - start_odo
        if miles_used < 0:
            warnings.append("Sale odometer is below start odometer -- check the inputs.")
        mileage_fraction = _clamp_fraction(miles_used / product.term_miles)

    fractions = {
        name: value
        for name, value in (("time", time_fraction), ("mileage", mileage_fraction))
        if value is not None
    }

    if not fractions:
        return RefundEstimate(
            product=product,
            remaining_fraction=0.0,
            gross_refund=0.0,
            cancellation_fee=product.cancellation_fee,
            net_refund=0.0,
            basis="no term (months or miles) available",
            can_estimate=False,
            warnings=warnings
            + ["No term in months or miles -- cannot estimate a refund."],
        )

    # Consumer-unfavorable convention: earned portion is the greater elapsed fraction.
    elapsed_name = max(fractions, key=lambda key: fractions[key])
    elapsed_fraction = fractions[elapsed_name]
    remaining_fraction = 1.0 - elapsed_fraction

    gross_refund = round(product.price * remaining_fraction, 2)
    net_refund = round(max(0.0, gross_refund - product.cancellation_fee), 2)

    if len(fractions) == 1:
        basis = f"the elapsed {elapsed_name} fraction"
    else:
        basis = (
            f"the greater of the elapsed time and mileage fractions "
            f"(here, {elapsed_name})"
        )

    return RefundEstimate(
        product=product,
        remaining_fraction=remaining_fraction,
        gross_refund=gross_refund,
        cancellation_fee=product.cancellation_fee,
        net_refund=net_refund,
        basis=basis,
        can_estimate=True,
        warnings=warnings,
    )


def estimate_case(case: RefundCase) -> list[RefundEstimate]:
    return [estimate_refund(product, case) for product in case.products]


def total_estimated_refund(case: RefundCase) -> float:
    return round(
        sum(e.net_refund for e in estimate_case(case) if e.can_estimate), 2
    )
