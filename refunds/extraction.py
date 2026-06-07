"""Redundant, cross-checked document extraction.

A single OCR/LLM pass over a messy F&I contract makes mistakes. This
module runs several *independent* extractors over the same document and
reconciles them field by field:

  - a field where every extractor agrees is accepted with high
    confidence;
  - a field where a strict majority agrees is accepted as medium;
  - a field they genuinely dispute goes to a `ConflictResolver` -- a
    separate model call that sees the document and the rival values --
    and, if even that is unsure, the field is flagged for the customer.

Independence is what makes this work. Two calls to the *same* model at
low temperature tend to repeat each other's systematic mistakes, so they
agree on the wrong answer. Different vendors (Claude, Gemini) have
different vision stacks and fail differently, so a real error usually
surfaces as a disagreement -- which is exactly what triggers review.
When only one vendor is available the ensemble still decorrelates as far
as it can, by running that model twice with different prompts.
"""

from __future__ import annotations

import abc
import base64
import json
import os
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .contract_parser import classify_product_type, parse_contract_file
from .models import AddOnProduct, ProductType
from .ocr import OcrDependencyError

HIGH, MEDIUM, LOW = "high", "medium", "low"

_PRODUCT_SHAPE = (
    '{"product_type": string, "administrator": string, "contract_number": '
    'string, "price": number, "term_months": number|null, "term_miles": '
    'number|null, "cancellation_fee": number|null}'
)

_EXTRACTION_PROMPT = (
    "You are extracting the add-on products from a vehicle purchase document "
    "(a retail installment sales contract or buyer's order). Return ONLY a "
    "JSON object -- no prose, no code fences -- with exactly this shape:\n"
    '{"vin": string|null, "purchase_date": "YYYY-MM-DD"|null, "products": ['
    + _PRODUCT_SHAPE
    + "]}\n"
    "Include every optional add-on / F&I product line: service contracts, "
    "GAP, tire & wheel, prepaid maintenance, appearance protection, key "
    "replacement, theft protection, and so on. Dealer paperwork often "
    "contains multiple copies of the SAME form -- customer copy, dealer "
    "copy, lender copy, with identical form numbers and identical figures. "
    "Return each product only ONCE, even when its form appears on several "
    "pages. For cancellation_fee, give "
    "the cancellation or administrative fee only if the document states "
    "one. Copy figures exactly as printed. Use null where a value is "
    "genuinely absent. Do not guess."
)

_EXTRACTION_PROMPT_ALT = (
    "Carefully read this car purchase contract. Identify every optional "
    "add-on or F&I product the buyer was charged for. For each product, "
    "record its name, the company that administers it, its contract or "
    "agreement number, the dollar price, the term in months and in miles, "
    "and any stated cancellation fee. Also record the vehicle VIN and the "
    "contract date. Reply with only a JSON object of this exact form:\n"
    '{"vin": string|null, "purchase_date": "YYYY-MM-DD"|null, "products": ['
    + _PRODUCT_SHAPE
    + "]}\n"
    "Important: dealer PDFs are often padded with duplicate copies of the "
    "same one-page form (customer / dealer / lender). If you see the same "
    "form number, price, and term twice, list that product only once. "
    "Transcribe every figure exactly as it appears; use null when something "
    "is not stated."
)

_RESOLVER_PROMPT = (
    "Look closely at this vehicle purchase document. For the \"{product}\" "
    "add-on product, several automated readers disagree on the field "
    "\"{field}\". The candidate values are: {candidates}. Decide the correct "
    "value by reading the document carefully. Respond with ONLY a JSON "
    'object: {{"value": <the correct value>, "confident": <true or false>}}. '
    "Set confident to false if the document is genuinely illegible for this "
    "field."
)

_OCR_TRANSCRIBE_PROMPT = (
    "Transcribe every line of text in this vehicle purchase document exactly "
    "as printed, preserving the line and column layout. Output only the "
    "transcription, with no commentary."
)


# ----------------------------------------------------------------------
# data types
# ----------------------------------------------------------------------


@dataclass
class ProductFields:
    """One extractor's reading of a single add-on product (loose/raw)."""

    product_type: str = ""
    administrator: str = ""
    contract_number: str = ""
    price: float | None = None
    term_months: int | None = None
    term_miles: int | None = None
    cancellation_fee: float | None = None


@dataclass
class DocumentExtraction:
    """One extractor's full reading of a document (or its failure)."""

    source: str
    products: list[ProductFields] = field(default_factory=list)
    vin: str | None = None
    purchase_date: str | None = None
    error: str | None = None


@dataclass
class ReconciledProduct:
    product: AddOnProduct
    confidence: dict[str, str]      # field name -> HIGH | MEDIUM | LOW
    review_fields: list[str]        # fields the customer should double-check
    # for each review field, the distinct readings and who produced them
    field_candidates: dict[str, list] = field(default_factory=dict)


@dataclass
class EnsembleResult:
    products: list[ReconciledProduct]
    vin: str | None
    purchase_date: str | None
    extractor_names: list[str]
    warnings: list[str]


@dataclass
class ResolverVerdict:
    value: object
    confident: bool


# ----------------------------------------------------------------------
# normalisation helpers
# ----------------------------------------------------------------------


def _norm_text(raw: object) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _norm_contract(raw: object) -> str | None:
    text = _norm_text(raw)
    return text.upper() if text else None


def _norm_price(raw: object) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return round(float(raw), 2)
    text = str(raw).strip().replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def _norm_int(raw: object) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    match = re.search(r"\d+", str(raw).replace(",", ""))
    return int(match.group()) if match else None


_FIELD_SPECS = [
    ("administrator", _norm_text, lambda value: value.lower()),
    ("contract_number", _norm_contract, lambda value: value),
    ("price", _norm_price, lambda value: value),
    ("term_months", _norm_int, lambda value: value),
    ("term_miles", _norm_int, lambda value: value),
    ("cancellation_fee", _norm_price, lambda value: value),
]

# Fields routinely absent on a legitimate contract (a time-only product
# has no mileage term; many contracts state no separate cancellation
# fee). Their absence is treated as agreement, not a gap to review.
_OPTIONAL_FIELDS = {"term_miles", "cancellation_fee"}


def _parse_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("model output contained no JSON object")
    return json.loads(text[start : end + 1])


def _vote_scalar(values: list[object]) -> str | None:
    present = [v for v in (_norm_text(value) for value in values) if v]
    if not present:
        return None
    counts: dict[str, int] = {}
    for value in present:
        counts[value] = counts.get(value, 0) + 1
    return max(counts, key=lambda key: counts[key])


# ----------------------------------------------------------------------
# vision models (used by the LLM extractors and the resolver)
# ----------------------------------------------------------------------

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
_GEMINI_MEDIA = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class GeminiVisionModel:
    """Google Gemini vision model -- a second, independent vendor.

    Stdlib-only (the Generative Language API is a plain HTTPS request).
    Needs a `GEMINI_API_KEY`. The model id is configurable; verify the
    current id for your account if the default is rejected.
    """

    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get(
            "GEMINI_API_KEY", ""
        )
        self.model = model
        self.timeout = timeout

    def _media_type(self, path: str) -> str:
        lower = path.lower()
        for extension, media_type in _GEMINI_MEDIA.items():
            if lower.endswith(extension):
                return media_type
        raise ValueError(
            f"GeminiVisionModel cannot handle {path!r}; expected a PDF or a "
            f"PNG/JPEG/WebP image."
        )

    def _build_payload(self, path: str, prompt: str) -> dict:
        media_type = self._media_type(path)
        with open(path, "rb") as handle:
            data = base64.b64encode(handle.read()).decode("ascii")
        return {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": media_type, "data": data}},
                        {"text": prompt},
                    ]
                }
            ]
        }

    def _post(self, payload: dict) -> dict:
        request = urllib.request.Request(
            _GEMINI_URL.format(model=self.model),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "content-type": "application/json",
                "x-goog-api-key": self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OcrDependencyError(
                f"Gemini API request failed ({exc.code}): {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise OcrDependencyError(
                f"Could not reach the Gemini API: {exc.reason}"
            ) from exc

    def complete(self, path: str, prompt: str) -> str:
        if not self.api_key:
            raise OcrDependencyError(
                "GeminiVisionModel needs an API key. Set the GEMINI_API_KEY "
                "environment variable, or pass api_key=..."
            )
        response = self._post(self._build_payload(path, prompt))
        candidates = response.get("candidates") or []
        if not candidates:
            raise OcrDependencyError("The Gemini API returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "\n".join(
            part.get("text", "") for part in parts if "text" in part
        ).strip()
        if not text:
            raise OcrDependencyError("The Gemini API returned no text.")
        return text


# ----------------------------------------------------------------------
# extractors
# ----------------------------------------------------------------------


class DocumentExtractor(abc.ABC):
    """An independent reader that turns a document into structured fields."""

    name: str

    @abc.abstractmethod
    def extract(self, path: str) -> DocumentExtraction:
        """Read `path`; never raise -- failures return error-tagged results."""


def _extraction_from_json(name: str, data: dict) -> DocumentExtraction:
    products: list[ProductFields] = []
    for item in data.get("products") or []:
        if not isinstance(item, dict):
            continue
        products.append(
            ProductFields(
                product_type=str(item.get("product_type") or ""),
                administrator=str(item.get("administrator") or ""),
                contract_number=str(item.get("contract_number") or ""),
                price=_norm_price(item.get("price")),
                term_months=_norm_int(item.get("term_months")),
                term_miles=_norm_int(item.get("term_miles")),
                cancellation_fee=_norm_price(item.get("cancellation_fee")),
            )
        )
    vin = data.get("vin")
    purchase_date = data.get("purchase_date")
    return DocumentExtraction(
        source=name,
        products=products,
        vin=str(vin) if vin else None,
        purchase_date=str(purchase_date) if purchase_date else None,
    )


class LLMDocumentExtractor(DocumentExtractor):
    """Structured extraction via a vision model that returns JSON."""

    def __init__(
        self,
        model: object,
        *,
        name: str | None = None,
        prompt: str = _EXTRACTION_PROMPT,
    ) -> None:
        self.model = model
        self.name = name or getattr(model, "name", "llm")
        self.prompt = prompt

    def extract(self, path: str) -> DocumentExtraction:
        try:
            raw = self.model.complete(path, self.prompt)  # type: ignore[attr-defined]
            return _extraction_from_json(self.name, _parse_json_object(raw))
        except Exception as exc:  # noqa: BLE001
            return DocumentExtraction(source=self.name, error=str(exc))


class RegexDocumentExtractor(DocumentExtractor):
    """The rule-based parser as an ensemble member.

    A genuinely different mechanism from the LLMs -- it never
    hallucinates, it only garbles -- so it adds real error diversity.
    """

    def __init__(
        self, *, ocr: object | None = None, name: str = "rule-based parser"
    ) -> None:
        self.ocr = ocr
        self.name = name

    def extract(self, path: str) -> DocumentExtraction:
        try:
            parsed = parse_contract_file(path, ocr=self.ocr)  # type: ignore[arg-type]
            products = [
                ProductFields(
                    product_type=product.product_type.value,
                    administrator=product.administrator_name,
                    contract_number=product.contract_number,
                    price=product.price,
                    term_months=product.term_months,
                    term_miles=product.term_miles,
                )
                for product in parsed.products
            ]
            return DocumentExtraction(
                source=self.name,
                products=products,
                vin=parsed.detected_vin,
                purchase_date=(
                    parsed.detected_purchase_date.isoformat()
                    if parsed.detected_purchase_date
                    else None
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return DocumentExtraction(source=self.name, error=str(exc))


# ----------------------------------------------------------------------
# conflict resolution
# ----------------------------------------------------------------------


class ConflictResolver(abc.ABC):
    @abc.abstractmethod
    def resolve(
        self, path: str, product_type: str, field_name: str, candidates: list
    ) -> ResolverVerdict:
        """Adjudicate a single disputed field."""


class NullConflictResolver(ConflictResolver):
    """Fallback resolver: never resolves -- every conflict is flagged."""

    def resolve(
        self, path: str, product_type: str, field_name: str, candidates: list
    ) -> ResolverVerdict:
        return ResolverVerdict(value=candidates[0], confident=False)


class LLMConflictResolver(ConflictResolver):
    """Resolves a disputed field with a fresh, focused vision-model call."""

    def __init__(self, model: object) -> None:
        self.model = model

    def resolve(
        self, path: str, product_type: str, field_name: str, candidates: list
    ) -> ResolverVerdict:
        prompt = _RESOLVER_PROMPT.format(
            product=product_type,
            field=field_name,
            candidates=", ".join(repr(c) for c in candidates),
        )
        try:
            raw = self.model.complete(path, prompt)  # type: ignore[attr-defined]
            data = _parse_json_object(raw)
            return ResolverVerdict(
                value=data.get("value"), confident=bool(data.get("confident"))
            )
        except Exception:  # noqa: BLE001
            return ResolverVerdict(value=candidates[0], confident=False)


# ----------------------------------------------------------------------
# reconciliation
# ----------------------------------------------------------------------


def _reconcile_field(
    path: str,
    product_type: ProductType,
    field_name: str,
    normalizer,
    keyfn,
    members: list[tuple[str, ProductFields]],
    resolver: ConflictResolver,
) -> tuple[object, str, list[dict]]:
    """Return (chosen value, confidence, candidates) for one field.

    `candidates` lists each distinct reading with the readers that
    produced it -- the operator console uses it to resolve disputes.
    """
    pairs: list[tuple[str, object]] = []
    for source, fields in members:
        normalized = normalizer(getattr(fields, field_name))
        if normalized is not None and normalized != "":
            pairs.append((source, normalized))

    if not pairs:
        # No reader reported this field. For a routinely-optional field
        # that is genuine absence; for a required field (e.g. the price)
        # it means every reader missed it -- flag it for the customer.
        return None, (HIGH if field_name in _OPTIONAL_FIELDS else LOW), []

    groups: dict[object, list[tuple[str, object]]] = {}
    for source, value in pairs:
        groups.setdefault(keyfn(value), []).append((source, value))
    candidates = [
        {"value": group[0][1], "sources": [src for src, _ in group]}
        for group in groups.values()
    ]

    winner_key = max(groups, key=lambda key: len(groups[key]))
    winner = groups[winner_key][0][1]
    present = len(pairs)
    agree = len(groups[winner_key])

    if present == 1:
        return winner, LOW, candidates
    if agree == present:
        return winner, HIGH, candidates
    if agree * 2 > present:
        return winner, MEDIUM, candidates

    # Genuine disagreement -- send the distinct candidates to the resolver.
    distinct = [group[0][1] for group in groups.values()]
    verdict = resolver.resolve(path, product_type.value, field_name, distinct)
    resolved = normalizer(verdict.value)
    if resolved is None or resolved == "":
        resolved = winner
    return resolved, (MEDIUM if verdict.confident else LOW), candidates


def _best_anchor(
    fields: ProductFields, anchors: list[ProductFields], used: set[int]
) -> int | None:
    """Pick the anchor slot a product best matches, by contract # then price."""
    available = [i for i in range(len(anchors)) if i not in used]
    if not available:
        return None
    contract = _norm_contract(fields.contract_number)
    if contract:
        for index in available:
            if _norm_contract(anchors[index].contract_number) == contract:
                return index
    price = _norm_price(fields.price)
    if price is not None:
        priced = [
            (index, _norm_price(anchors[index].price)) for index in available
        ]
        priced = [(i, p) for i, p in priced if p is not None]
        if priced:
            return min(priced, key=lambda item: abs(item[1] - price))[0]
    return available[0]


def _split_same_type(
    per_source: dict[str, list[ProductFields]], slots: int
) -> list[list[tuple[str, ProductFields]]]:
    """Split several same-type products from each reader into aligned buckets."""
    ordered = sorted(per_source.items(), key=lambda item: -len(item[1]))
    buckets: list[list[tuple[str, ProductFields]]] = [[] for _ in range(slots)]
    seed_source, seed_products = ordered[0]
    anchors: list[ProductFields] = []
    for index, fields in enumerate(seed_products):
        buckets[index].append((seed_source, fields))
        anchors.append(fields)
    for source, products in ordered[1:]:
        used: set[int] = set()
        for fields in products:
            index = _best_anchor(fields, anchors, used)
            if index is None:
                buckets.append([(source, fields)])
                anchors.append(fields)
            else:
                buckets[index].append((source, fields))
                used.add(index)
    return buckets


def _dedupe_within_reader(
    products: list[ProductFields],
) -> list[ProductFields]:
    """Collapse same-form-twice readings from a single reader.

    Dealer PDFs frequently bundle the customer / dealer / lender copies of
    the same one-page form, so an LLM looking at every page emits the same
    product two or three times. We treat two of one reader's products as
    the same physical form when their classified type plus their price
    match AND either their contract number matches OR their term in
    months and miles match -- a deliberately conservative signature, so
    two genuinely distinct products of the same type (different contract
    numbers AND different terms) are still kept apart.
    """

    def round_price(value: float | None) -> float | None:
        return round(value, 2) if value is not None else None

    def norm(text: str) -> str:
        return re.sub(r"\s+", "", text or "").upper()

    kept: list[ProductFields] = []
    seen_keys: list[tuple] = []
    for fields in products:
        product_type = classify_product_type(fields.product_type or "")
        price = round_price(fields.price)
        contract = norm(fields.contract_number)
        key_a = (product_type, contract, price) if contract else None
        key_b = (
            (product_type, fields.term_months, fields.term_miles, price)
            if fields.term_months or fields.term_miles
            else None
        )
        if (key_a and key_a in seen_keys) or (key_b and key_b in seen_keys):
            continue
        if key_a:
            seen_keys.append(key_a)
        if key_b:
            seen_keys.append(key_b)
        kept.append(fields)
    return kept


def _cluster_products(
    succeeded: list[DocumentExtraction],
) -> list[tuple[ProductType, list[tuple[str, ProductFields]]]]:
    """Group products across extractions into one cluster per real product.

    Products are grouped by type. The common case -- at most one product
    of a type per reader -- yields a single cluster. When a reader reports
    several products of the same type, the group is split so two distinct
    same-type products are never merged into one.
    """
    by_type: dict[ProductType, list[tuple[str, ProductFields]]] = {}
    for extraction in succeeded:
        for fields in _dedupe_within_reader(extraction.products):
            product_type = classify_product_type(fields.product_type or "")
            by_type.setdefault(product_type, []).append(
                (extraction.source, fields)
            )

    clusters: list[tuple[ProductType, list[tuple[str, ProductFields]]]] = []
    for product_type, members in by_type.items():
        per_source: dict[str, list[ProductFields]] = {}
        for source, fields in members:
            per_source.setdefault(source, []).append(fields)
        slots = max((len(items) for items in per_source.values()), default=1)
        if slots <= 1:
            clusters.append((product_type, members))
        else:
            for bucket in _split_same_type(per_source, slots):
                clusters.append((product_type, bucket))
    return clusters


def reconcile(
    path: str, extractions: list[DocumentExtraction], resolver: ConflictResolver
) -> EnsembleResult:
    """Combine independent extractions into one cross-checked result."""
    succeeded = [e for e in extractions if e.error is None]
    failed = [e for e in extractions if e.error is not None]
    warnings = [
        f"{e.source} could not read the document: {e.error}" for e in failed
    ]
    names = [e.source for e in succeeded]

    if not succeeded:
        return EnsembleResult(
            [], None, None, names,
            warnings + ["No reader could process this document."],
        )
    if len(succeeded) == 1:
        warnings.append(
            f"Only one reader ({succeeded[0].source}) processed this "
            f"document, so nothing could be cross-checked -- please review "
            f"every field carefully."
        )

    total = len(succeeded)
    products: list[ReconciledProduct] = []
    for product_type, members in _cluster_products(succeeded):
        chosen: dict[str, object] = {}
        confidence: dict[str, str] = {}
        candidates_by_field: dict[str, list] = {}
        for field_name, normalizer, keyfn in _FIELD_SPECS:
            value, level, candidates = _reconcile_field(
                path, product_type, field_name, normalizer, keyfn,
                members, resolver,
            )
            chosen[field_name] = value
            confidence[field_name] = level
            candidates_by_field[field_name] = candidates

        reporting_sources = {source for source, _ in members}
        if total >= 2 and len(reporting_sources) * 2 <= total:
            warnings.append(
                f"The {product_type.value} was reported by only "
                f"{len(reporting_sources)} of {total} readers -- confirm it "
                f"really is on your contract."
            )

        fee = chosen.get("cancellation_fee")
        product = AddOnProduct(
            product_type=product_type,
            administrator_name=str(chosen.get("administrator") or ""),
            contract_number=str(chosen.get("contract_number") or ""),
            price=float(chosen["price"]) if chosen.get("price") is not None else 0.0,
            term_months=chosen.get("term_months"),  # type: ignore[arg-type]
            term_miles=chosen.get("term_miles"),  # type: ignore[arg-type]
            cancellation_fee=float(fee) if fee is not None else 0.0,
        )
        review = [name for name, level in confidence.items() if level == LOW]
        field_candidates = {name: candidates_by_field[name] for name in review}
        products.append(
            ReconciledProduct(product, confidence, review, field_candidates)
        )

    return EnsembleResult(
        products=products,
        vin=_vote_scalar([e.vin for e in succeeded]),
        purchase_date=_vote_scalar([e.purchase_date for e in succeeded]),
        extractor_names=names,
        warnings=warnings,
    )


# ----------------------------------------------------------------------
# the ensemble
# ----------------------------------------------------------------------


class EnsembleExtractor:
    """Runs independent extractors in parallel and reconciles them."""

    def __init__(
        self,
        extractors: list[DocumentExtractor],
        *,
        resolver: ConflictResolver | None = None,
        max_workers: int = 4,
    ) -> None:
        if not extractors:
            raise ValueError("EnsembleExtractor needs at least one extractor.")
        self.extractors = list(extractors)
        self.resolver = resolver or NullConflictResolver()
        self.max_workers = max_workers

    def extract(self, path: str) -> EnsembleResult:
        workers = min(self.max_workers, len(self.extractors))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            extractions = list(
                pool.map(lambda extractor: extractor.extract(path), self.extractors)
            )
        return reconcile(path, extractions, self.resolver)


def _ocr_from_model(model: object):
    """Adapt a vision model into an OCR text source for the rule parser."""
    if hasattr(model, "extract_text"):
        return model  # an OcrAdapter is already callable
    return lambda path: model.complete(path, _OCR_TRANSCRIBE_PROMPT)


def build_default_ensemble() -> EnsembleExtractor | None:
    """Build an ensemble from whatever model API keys are configured.

    The ensemble always has at least three independent readers:

      - two structured LLM extractors -- one per vendor when both
        Anthropic and Gemini keys are present (the strongest
        decorrelation), otherwise two passes of the one vendor with
        different prompts;
      - the deterministic rule-based parser, which transcribes the
        document and parses it with regular expressions. It never invents
        a product, so it is a genuine cross-check on LLM hallucination.

    No keys -> None.
    """
    models: list[object] = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        from .ocr import AnthropicVisionOcr

        models.append(AnthropicVisionOcr())
    if os.environ.get("GEMINI_API_KEY"):
        models.append(GeminiVisionModel())
    if not models:
        return None

    extractors: list[DocumentExtractor] = []
    if len(models) >= 2:
        for model in models:
            extractors.append(
                LLMDocumentExtractor(model, name=getattr(model, "name", "llm"))
            )
    else:
        only = models[0]
        base = getattr(only, "name", "llm")
        extractors.append(
            LLMDocumentExtractor(
                only, name=f"{base} (reading A)", prompt=_EXTRACTION_PROMPT
            )
        )
        extractors.append(
            LLMDocumentExtractor(
                only, name=f"{base} (reading B)", prompt=_EXTRACTION_PROMPT_ALT
            )
        )

    extractors.append(
        RegexDocumentExtractor(
            ocr=_ocr_from_model(models[0]), name="rule-based parser"
        )
    )
    return EnsembleExtractor(
        extractors, resolver=LLMConflictResolver(models[0])
    )
