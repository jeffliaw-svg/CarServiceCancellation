"""End-to-end demo: build a case, estimate refunds, draft the letters.

Run from the repository root:  python examples/demo.py
"""

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from refunds import (  # noqa: E402
    AddOnProduct,
    CaseStore,
    ProductType,
    RefundCase,
    Seller,
    Vehicle,
    estimate_case,
    generate_authorization,
    generate_letters_for_case,
    parse_contract_file,
    total_estimated_refund,
    write_letters,
    write_letters_pdf,
    write_pdf,
)


def build_sample_case() -> RefundCase:
    seller = Seller(
        legal_name="Jordan A. Rivera",
        address_lines=["123 Maple Street", "Springfield, IL 62704"],
        email="jordan.rivera@example.com",
        phone="(555) 010-2345",
    )
    vehicle = Vehicle(
        vin="1HGCM82633A004352",
        year=2023,
        make="Honda",
        model="Accord",
        selling_dealer="Springfield Honda",
        dealer_address_lines=["4500 Auto Mall Drive", "Springfield, IL 62711"],
        purchase_date=date(2023, 3, 15),
        odometer_at_purchase=12,
        odometer_at_sale=31_400,
    )
    products = [
        AddOnProduct(
            product_type=ProductType.VEHICLE_SERVICE_CONTRACT,
            administrator_name="Zurich",
            contract_number="VSC-7781234",
            price=2_695.00,
            term_months=72,
            term_miles=75_000,
            start_date=date(2023, 3, 15),
            start_odometer=12,
            cancellation_fee=50.00,
        ),
        AddOnProduct(
            product_type=ProductType.GAP,
            administrator_name="JM&A Group",
            contract_number="GAP-553021",
            price=895.00,
            term_months=72,
            start_date=date(2023, 3, 15),
        ),
        AddOnProduct(
            product_type=ProductType.TIRE_AND_WHEEL,
            administrator_name="Safe-Guard Products International",
            contract_number="TW-2210045",
            price=799.00,
            term_months=60,
            start_date=date(2023, 3, 15),
            cancellation_fee=25.00,
        ),
    ]
    return RefundCase(
        seller=seller,
        vehicle=vehicle,
        sale_date=date(2025, 11, 1),
        products=products,
        authorization_signed=True,
    )


def show_contract_parsing() -> None:
    fixture = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "sample_contract.txt"
    )
    parsed = parse_contract_file(fixture)
    print("Parsed sample retail installment contract")
    print("-" * 60)
    print(f"  Detected VIN: {parsed.detected_vin}")
    for product in parsed.products:
        print(
            f"  {product.product_type.value:<28} "
            f"{product.administrator_name or '(unknown admin)':<32} "
            f"${product.price:,.2f}"
        )
    for warning in parsed.warnings:
        print(f"  ! {warning}")
    print()


def main() -> None:
    show_contract_parsing()

    case = build_sample_case()
    today = date(2026, 5, 20)

    print(f"Case {case.case_id} -- {case.seller.legal_name}")
    print(f"Vehicle: {case.vehicle.description} (VIN {case.vehicle.vin})")
    print(f"Sold: {case.sale_date}\n")

    print("Estimated pro-rata refunds")
    print("-" * 60)
    for est in estimate_case(case):
        product = est.product
        if est.can_estimate:
            print(
                f"  {product.product_type.value:<34} "
                f"${est.net_refund:>10,.2f}"
            )
        else:
            print(f"  {product.product_type.value:<34} {'(no estimate)':>11}")
    print("-" * 60)
    print(f"  {'TOTAL estimated refund':<34} ${total_estimated_refund(case):>10,.2f}\n")

    letters = generate_letters_for_case(case, today=today, service_name="RefundRoute")
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    paths = write_letters(letters, out_dir)
    pdf_paths = write_letters_pdf(letters, out_dir)

    print(f"Drafted {len(letters)} letter(s) -> {out_dir}")
    for letter, txt_path, pdf_path in zip(letters, paths, pdf_paths):
        print(
            f"\n  To: {letter.recipient_name}  "
            f"({os.path.basename(txt_path)}, {os.path.basename(pdf_path)})"
        )
        for warning in letter.warnings:
            print(f"    ! {warning}")

    auth_text = generate_authorization(case, today=today, service_name="RefundRoute")
    auth_path = os.path.join(out_dir, f"{case.case_id}_authorization.txt")
    with open(auth_path, "w", encoding="utf-8") as handle:
        handle.write(auth_text)
    auth_pdf_path = write_pdf(
        auth_text, os.path.join(out_dir, f"{case.case_id}_authorization.pdf")
    )
    print(
        f"\nDrafted authorization -> {os.path.basename(auth_path)}, "
        f"{os.path.basename(auth_pdf_path)}"
    )

    store = CaseStore(os.path.join(out_dir, "cases"))
    store.save(case)
    print(f"Saved case to store -> {store.path_for(case.case_id)}")
    print(f"Cases in store: {store.list_ids()}")

    print("\n" + "=" * 60)
    print("Sample letter (first):")
    print("=" * 60)
    print(letters[0].body)

    print("=" * 60)
    print("Authorization document:")
    print("=" * 60)
    print(auth_text)


if __name__ == "__main__":
    main()
