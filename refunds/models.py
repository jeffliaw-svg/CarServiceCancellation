"""Core domain model for vehicle F&I add-on refund cases.

The intake from the customer is deliberately minimal (legal name, VIN,
sale date). Everything else on these objects is filled in from a single
uploaded document -- the retail installment sales contract / buyer's
order -- which itemizes every add-on product that was sold.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class ProductType(str, Enum):
    """The cancellable F&I add-on products typically sold at the dealership."""

    VEHICLE_SERVICE_CONTRACT = "Vehicle Service Contract"
    GAP = "GAP Waiver"
    TIRE_AND_WHEEL = "Tire & Wheel Protection"
    PREPAID_MAINTENANCE = "Prepaid Maintenance Plan"
    APPEARANCE_PROTECTION = "Paint & Fabric Appearance Protection"
    KEY_REPLACEMENT = "Key Replacement Coverage"
    THEFT_PROTECTION = "Theft Protection / VIN Etch"
    OTHER = "Other Add-On Product"


class CancellationRoute(str, Enum):
    """Who a cancellation request must be addressed to."""

    ADMINISTRATOR = "administrator"  # cancel directly with the product administrator
    DEALER = "dealer"               # administrator requires the selling dealer to submit
    EITHER = "either"               # route uncertain -- verify per contract


class CaseStatus(str, Enum):
    INTAKE = "intake"
    AWAITING_AUTHORIZATION = "awaiting_authorization"
    READY_TO_SEND = "ready_to_send"
    LETTERS_SENT = "letters_sent"
    AWAITING_REFUND = "awaiting_refund"
    CLOSED = "closed"


@dataclass
class Administrator:
    """A company that administers an add-on product, and how to reach it.

    The verified mailing address + cancellation route is the proprietary
    asset of this service; everything seeded in the registry starts as
    unverified until a human confirms it.
    """

    name: str
    address_lines: list[str]
    attn: str = "Cancellations Department"
    cancellation_route: CancellationRoute = CancellationRoute.ADMINISTRATOR
    phone: str = ""
    address_verified: bool = False  # True only once a human confirms the address
    source: str = ""                # provenance of the address (URL / description)
    verified_on: str = ""           # ISO date a human verified it
    notes: str = ""


@dataclass
class Seller:
    """The customer -- the person who sold the vehicle and is owed the refund."""

    legal_name: str
    address_lines: list[str]
    email: str = ""
    phone: str = ""


@dataclass
class Vehicle:
    vin: str
    year: int | None = None
    make: str = ""
    model: str = ""
    selling_dealer: str = ""
    dealer_address_lines: list[str] = field(default_factory=list)
    purchase_date: date | None = None
    odometer_at_purchase: int | None = None
    odometer_at_sale: int | None = None

    @property
    def description(self) -> str:
        parts = [str(self.year) if self.year else "", self.make, self.model]
        return " ".join(p for p in parts if p).strip() or "vehicle"


@dataclass
class AddOnProduct:
    """One cancellable add-on product, as itemized on the purchase contract."""

    product_type: ProductType
    administrator_name: str
    contract_number: str
    price: float
    term_months: int | None = None
    term_miles: int | None = None
    start_date: date | None = None      # coverage start; defaults to vehicle purchase date
    start_odometer: int | None = None   # odometer at coverage start
    cancellation_fee: float = 0.0


@dataclass
class RefundCase:
    seller: Seller
    vehicle: Vehicle
    sale_date: date
    products: list[AddOnProduct] = field(default_factory=list)
    authorization_signed: bool = False
    status: CaseStatus = CaseStatus.INTAKE
    case_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
