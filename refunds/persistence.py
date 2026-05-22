"""JSON-backed persistence for refund cases.

Refund cases are dataclasses with nested objects, `date` fields, and
string enums. This module serializes them to plain JSON and back, and
provides a directory-backed `CaseStore` so cases survive between runs.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone

from .models import (
    AddOnProduct,
    CaseStatus,
    ProductType,
    RefundCase,
    Seller,
    Vehicle,
)

_CASE_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


def _date_to_str(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _str_to_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def seller_to_dict(seller: Seller) -> dict:
    return {
        "legal_name": seller.legal_name,
        "address_lines": list(seller.address_lines),
        "email": seller.email,
        "phone": seller.phone,
    }


def seller_from_dict(data: dict) -> Seller:
    return Seller(
        legal_name=data["legal_name"],
        address_lines=list(data.get("address_lines", [])),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
    )


def vehicle_to_dict(vehicle: Vehicle) -> dict:
    return {
        "vin": vehicle.vin,
        "year": vehicle.year,
        "make": vehicle.make,
        "model": vehicle.model,
        "selling_dealer": vehicle.selling_dealer,
        "dealer_address_lines": list(vehicle.dealer_address_lines),
        "purchase_date": _date_to_str(vehicle.purchase_date),
        "odometer_at_purchase": vehicle.odometer_at_purchase,
        "odometer_at_sale": vehicle.odometer_at_sale,
    }


def vehicle_from_dict(data: dict) -> Vehicle:
    return Vehicle(
        vin=data["vin"],
        year=data.get("year"),
        make=data.get("make", ""),
        model=data.get("model", ""),
        selling_dealer=data.get("selling_dealer", ""),
        dealer_address_lines=list(data.get("dealer_address_lines", [])),
        purchase_date=_str_to_date(data.get("purchase_date")),
        odometer_at_purchase=data.get("odometer_at_purchase"),
        odometer_at_sale=data.get("odometer_at_sale"),
    )


def product_to_dict(product: AddOnProduct) -> dict:
    return {
        "product_type": product.product_type.value,
        "administrator_name": product.administrator_name,
        "contract_number": product.contract_number,
        "price": product.price,
        "term_months": product.term_months,
        "term_miles": product.term_miles,
        "start_date": _date_to_str(product.start_date),
        "start_odometer": product.start_odometer,
        "cancellation_fee": product.cancellation_fee,
    }


def product_from_dict(data: dict) -> AddOnProduct:
    return AddOnProduct(
        product_type=ProductType(data["product_type"]),
        administrator_name=data["administrator_name"],
        contract_number=data.get("contract_number", ""),
        price=data["price"],
        term_months=data.get("term_months"),
        term_miles=data.get("term_miles"),
        start_date=_str_to_date(data.get("start_date")),
        start_odometer=data.get("start_odometer"),
        cancellation_fee=data.get("cancellation_fee", 0.0),
    )


def case_to_dict(case: RefundCase) -> dict:
    return {
        "case_id": case.case_id,
        "status": case.status.value,
        "sale_date": _date_to_str(case.sale_date),
        "authorization_signed": case.authorization_signed,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "seller": seller_to_dict(case.seller),
        "vehicle": vehicle_to_dict(case.vehicle),
        "products": [product_to_dict(p) for p in case.products],
    }


def case_from_dict(data: dict) -> RefundCase:
    case = RefundCase(
        seller=seller_from_dict(data["seller"]),
        vehicle=vehicle_from_dict(data["vehicle"]),
        sale_date=_str_to_date(data["sale_date"]),
        products=[product_from_dict(p) for p in data.get("products", [])],
        authorization_signed=data.get("authorization_signed", False),
        status=CaseStatus(data.get("status", CaseStatus.INTAKE.value)),
        case_id=data["case_id"],
    )
    if data.get("created_at"):
        case.created_at = data["created_at"]
    if data.get("updated_at"):
        case.updated_at = data["updated_at"]
    return case


class CaseStore:
    """A directory of refund cases, one `<case_id>.json` file per case."""

    def __init__(self, root: str) -> None:
        self.root = root
        os.makedirs(root, exist_ok=True)
        os.chmod(root, 0o700)

    @staticmethod
    def _check_id(case_id: str) -> None:
        if not case_id or not _CASE_ID_RE.fullmatch(case_id):
            raise ValueError(f"Invalid case id: {case_id!r}")

    def path_for(self, case_id: str) -> str:
        self._check_id(case_id)
        return os.path.join(self.root, f"{case_id}.json")

    def exists(self, case_id: str) -> bool:
        return os.path.isfile(self.path_for(case_id))

    def save(self, case: RefundCase) -> str:
        path = self.path_for(case.case_id)
        case.updated_at = datetime.now(timezone.utc).isoformat()
        # Atomic + private: a concurrent reader never sees a partial file.
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(case_to_dict(case), handle, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        return path

    def load(self, case_id: str) -> RefundCase:
        path = self.path_for(case_id)
        if not os.path.isfile(path):
            raise KeyError(f"No case with id {case_id!r}")
        with open(path, encoding="utf-8") as handle:
            return case_from_dict(json.load(handle))

    def list_ids(self) -> list[str]:
        return sorted(
            name[:-5]
            for name in os.listdir(self.root)
            if name.endswith(".json")
        )

    def list_cases(self) -> list[RefundCase]:
        return [self.load(case_id) for case_id in self.list_ids()]

    def delete(self, case_id: str) -> bool:
        path = self.path_for(case_id)
        if os.path.isfile(path):
            os.remove(path)
            return True
        return False
