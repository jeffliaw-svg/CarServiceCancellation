import { useEffect, useState } from "react";
import { api } from "../api";
import type { CaseView, Candidate, OperatorOverview } from "../types";
import { Logo } from "../components/site";

const KEY_STORAGE = "refundroute_operator_key";

const FIELD_LABEL: Record<string, string> = {
  price: "Price",
  contract_number: "Contract number",
  administrator: "Administrator",
  term_months: "Term (months)",
  term_miles: "Term (miles)",
  cancellation_fee: "Cancellation fee",
};

function money(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function when(iso: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatValue(field: string, value: string | number): string {
  if (field === "price" || field === "cancellation_fee") {
    const n = typeof value === "number" ? value : Number(value);
    if (Number.isFinite(n)) {
      return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
    }
  }
  return String(value);
}

function reviewSummary(review: Record<string, string[]>): string {
  return Object.entries(review)
    .map(([product, fields]) => `${product}: ${fields.join(", ")}`)
    .join("   ·   ");
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border p-5 ${
        accent ? "border-amber-300 bg-amber-50" : "border-line bg-surface"
      }`}
    >
      <p className="font-display text-3xl">{value}</p>
      <p className="mt-1 text-xs uppercase tracking-widest text-muted">
        {label}
      </p>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-line py-1">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}

/* -- the contract viewer (left pane) ---------------------------------- */

function ContractViewer({
  url,
  name,
}: {
  url: string | null;
  name?: string;
}) {
  if (!url) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-sm text-muted">
        No contract document is on file for this case.
      </div>
    );
  }
  const isImage = /\.(png|jpe?g|webp|gif)$/i.test(name || "");
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2 text-xs text-muted">
        <span className="truncate">{name || "Contract"}</span>
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="shrink-0 font-medium text-accent hover:underline"
        >
          Open in new tab
        </a>
      </div>
      <div className="flex-1 overflow-auto bg-paper">
        {isImage ? (
          <img src={url} alt="Customer contract" className="w-full" />
        ) : (
          <iframe src={url} title="Customer contract" className="h-full w-full" />
        )}
      </div>
    </div>
  );
}

/* -- one disputed field (right pane) ---------------------------------- */

function FieldCard({
  field,
  candidates,
  decision,
  onDecide,
}: {
  field: string;
  candidates: Candidate[];
  decision: string | number | undefined;
  onDecide: (value: string | number | undefined) => void;
}) {
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState("");
  const label = FIELD_LABEL[field] ?? field;

  if (decision !== undefined) {
    return (
      <div className="rounded-xl border border-accent bg-accent-soft p-3">
        <div className="flex items-center justify-between gap-3 text-sm">
          <span>
            <span className="text-accent">&#10003;</span> {label}:{" "}
            <strong>{formatValue(field, decision)}</strong>
          </span>
          <button
            className="shrink-0 text-xs font-medium text-accent hover:underline"
            onClick={() => onDecide(undefined)}
          >
            Change
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-4">
      <p className="text-sm font-medium">{label}</p>
      <p className="text-xs text-amber-800">The readers disagreed.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {candidates.map((candidate, index) => (
          <button
            key={index}
            onClick={() => onDecide(candidate.value)}
            className="rounded-lg border border-line bg-surface px-3 py-2 text-left transition hover:border-accent"
          >
            <span className="text-sm font-medium">
              {formatValue(field, candidate.value)}
            </span>
            <span className="block text-[11px] text-muted">
              {candidate.sources.join(", ")}
            </span>
          </button>
        ))}
        {!typing && (
          <button
            onClick={() => setTyping(true)}
            className="rounded-lg border border-dashed border-line px-3 py-2 text-sm text-muted transition hover:border-accent"
          >
            Type the correct value
          </button>
        )}
      </div>
      {typing && (
        <div className="mt-3 flex gap-2">
          <input
            className="field"
            autoFocus
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="Enter value from the contract"
            onKeyDown={(e) => {
              if (e.key === "Enter" && typed.trim()) onDecide(typed.trim());
            }}
          />
          <button
            className="btn btn-primary !py-2 !text-xs"
            disabled={!typed.trim()}
            onClick={() => onDecide(typed.trim())}
          >
            Set
          </button>
        </div>
      )}
    </div>
  );
}

/* -- read-only detail for an unflagged case --------------------------- */

function ReadOnlyDetail({ view }: { view: CaseView }) {
  const packets = view.generated.filter((g) => g.kind === "packet").length;
  return (
    <div>
      <dl className="grid grid-cols-1 gap-x-8 text-sm">
        <Fact label="Vehicle" value={view.vehicle.description} />
        <Fact label="VIN" value={view.vehicle.vin} />
        <Fact label="Sold" value={view.sale_date} />
        <Fact label="Started" value={when(view.created_at)} />
        <Fact label="Last activity" value={when(view.updated_at)} />
      </dl>
      <h4 className="mt-5 text-sm font-semibold">
        Products ({view.products.length})
      </h4>
      <div className="mt-2 space-y-2">
        {view.products.map((p) => (
          <div
            key={p.index}
            className="rounded-xl border border-line bg-paper p-3 text-sm"
          >
            <div className="flex items-center justify-between">
              <span className="font-medium">{p.product_type}</span>
              <span className="text-accent">
                {p.estimate.can_estimate ? money(p.estimate.net_refund) : "TBD"}
              </span>
            </div>
            <p className="text-xs text-muted">
              {p.administrator}
              {p.contract_number ? ` · ${p.contract_number}` : ""}
            </p>
          </div>
        ))}
      </div>
      {packets > 0 && (
        <p className="mt-4 text-sm text-muted">
          {packets} mailing packet{packets === 1 ? "" : "s"} generated.
        </p>
      )}
      {view.resolution && (
        <p className="mt-3 text-xs text-accent">
          Resolved by the operator on {when(view.resolution.resolved_at)}.
        </p>
      )}
    </div>
  );
}

/* -- the case overlay (resolution or read-only) ----------------------- */

function CaseOverlay({
  view,
  operatorKey,
  onClose,
  onResolved,
}: {
  view: CaseView;
  operatorKey: string;
  onClose: () => void;
  onResolved: () => void;
}) {
  const flagged: { productType: string; field: string }[] = [];
  for (const [productType, fields] of Object.entries(view.review_detail)) {
    for (const field of Object.keys(fields)) {
      flagged.push({ productType, field });
    }
  }
  const isFlagged = flagged.length > 0;

  const [decisions, setDecisions] = useState<Record<string, string | number>>(
    {},
  );
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const keyOf = (productType: string, field: string) =>
    `${productType}::${field}`;
  const resolvedCount = flagged.filter(
    (f) => decisions[keyOf(f.productType, f.field)] !== undefined,
  ).length;
  const allResolved = isFlagged && resolvedCount === flagged.length;

  function decide(
    productType: string,
    field: string,
    value: string | number | undefined,
  ) {
    setDecisions((current) => {
      const next = { ...current };
      if (value === undefined) delete next[keyOf(productType, field)];
      else next[keyOf(productType, field)] = value;
      return next;
    });
  }

  async function apply() {
    setBusy(true);
    setError(null);
    try {
      const corrections = flagged.map((f) => ({
        product_type: f.productType,
        field: f.field,
        value: decisions[keyOf(f.productType, f.field)],
      }));
      await api.operatorResolve(view.case_id, operatorKey, corrections);
      setDone(true);
      setTimeout(onResolved, 1100);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not apply.");
      setBusy(false);
    }
  }

  const contractDoc = view.documents.find((d) => d.kind === "contract");
  const contractUrl = contractDoc
    ? api.operatorFileUrl(view.case_id, contractDoc.name, operatorKey)
    : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-3 sm:p-6"
      onClick={onClose}
    >
      <div
        className="flex w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-line bg-surface lg:h-[85vh] lg:flex-row"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="h-[42vh] border-b border-line lg:h-auto lg:w-7/12 lg:border-b-0 lg:border-r">
          <ContractViewer url={contractUrl} name={contractDoc?.original_name} />
        </div>

        <div className="flex min-h-0 flex-1 flex-col lg:w-5/12">
          <div className="flex items-start justify-between gap-3 border-b border-line p-5">
            <div>
              <h3 className="font-display text-xl">
                {view.seller.legal_name}
              </h3>
              <p className="text-xs text-muted">
                {isFlagged
                  ? `${flagged.length} field${
                      flagged.length === 1 ? "" : "s"
                    } to resolve before this case is trusted`
                  : `Case ${view.case_id} · ${view.status}`}
              </p>
            </div>
            <button
              className="btn btn-ghost !px-3 !py-1.5 !text-xs"
              onClick={onClose}
            >
              Close
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {done ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent text-xl text-white">
                  &#10003;
                </div>
                <h4 className="font-display mt-4 text-xl">Case resolved.</h4>
                <p className="mt-1 text-sm text-muted">
                  {view.seller.legal_name}&rsquo;s case is corrected and back
                  on track.
                </p>
              </div>
            ) : isFlagged ? (
              <div className="space-y-5">
                {Object.entries(view.review_detail).map(
                  ([productType, fields]) => (
                    <div key={productType}>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted">
                        {productType}
                      </p>
                      <div className="space-y-2">
                        {Object.entries(fields).map(([field, candidates]) => (
                          <FieldCard
                            key={field}
                            field={field}
                            candidates={candidates}
                            decision={decisions[keyOf(productType, field)]}
                            onDecide={(value) =>
                              decide(productType, field, value)
                            }
                          />
                        ))}
                      </div>
                    </div>
                  ),
                )}
              </div>
            ) : (
              <ReadOnlyDetail view={view} />
            )}
          </div>

          {isFlagged && !done && (
            <div className="border-t border-line p-5">
              {error && (
                <p role="alert" className="mb-2 text-xs text-red-700">
                  {error}
                </p>
              )}
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs text-muted">
                  {resolvedCount} of {flagged.length} resolved
                </span>
                <button
                  className="btn btn-primary !py-2 !text-sm"
                  disabled={!allResolved || busy}
                  onClick={apply}
                >
                  {busy ? "Applying…" : "Apply corrections"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* -- gate ------------------------------------------------------------- */

function Gate({
  value,
  onChange,
  onSubmit,
  error,
  busy,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  error: string | null;
  busy: boolean;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm rounded-3xl border border-line bg-surface p-8">
        <Logo />
        <h1 className="font-display mt-6 text-2xl">Operator console</h1>
        <p className="mt-2 text-sm text-muted">
          Enter your operator key to continue.
        </p>
        {error && (
          <div
            role="alert"
            className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </div>
        )}
        <input
          className="field mt-4"
          type="password"
          value={value}
          autoComplete="off"
          placeholder="Operator key"
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSubmit();
          }}
        />
        <button
          className="btn btn-primary mt-4 w-full"
          disabled={!value.trim() || busy}
          onClick={onSubmit}
        >
          {busy ? "Checking…" : "Open console"}
        </button>
      </div>
    </div>
  );
}

/* -- the console ------------------------------------------------------ */

export default function Operator() {
  const [key, setKey] = useState(
    () => localStorage.getItem(KEY_STORAGE) || "",
  );
  const [overview, setOverview] = useState<OperatorOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [detail, setDetail] = useState<CaseView | null>(null);

  async function load(candidate: string) {
    setBusy(true);
    setError(null);
    try {
      const data = await api.operatorOverview(candidate);
      setOverview(data);
      localStorage.setItem(KEY_STORAGE, candidate);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the console.");
      setOverview(null);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (key) load(key);
    // load once on mount with any stored key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function openCase(id: string) {
    try {
      setDetail(await api.operatorCase(id, key));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open that case.");
    }
  }

  function signOut() {
    localStorage.removeItem(KEY_STORAGE);
    setKey("");
    setOverview(null);
    setError(null);
  }

  if (!overview) {
    return (
      <Gate
        value={key}
        onChange={setKey}
        onSubmit={() => load(key)}
        error={error}
        busy={busy}
      />
    );
  }

  const totals = overview.totals;
  const base = Math.max(totals.started, 1);

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Logo />
            <span className="text-sm text-muted">Operator console</span>
          </div>
          <div className="flex items-center gap-4 text-xs font-medium">
            <button
              className="text-muted hover:text-ink"
              onClick={() => load(key)}
            >
              Refresh
            </button>
            <button className="text-muted hover:text-ink" onClick={signOut}>
              Sign out
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-6 py-10">
        {error && (
          <div
            role="alert"
            className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Started" value={totals.started} />
          <StatCard label="Documents read" value={totals.documents_read} />
          <StatCard label="Confirmed" value={totals.services_confirmed} />
          <StatCard
            label="Letters generated"
            value={totals.letters_generated}
          />
          <StatCard
            label="Needs review"
            value={totals.needs_review}
            accent={totals.needs_review > 0}
          />
        </div>

        <section className="mt-12">
          <h2 className="font-display text-2xl">Funnel</h2>
          <p className="mt-1 text-sm text-muted">
            Where customers reach, and where they drop off.
          </p>
          <div className="mt-4 space-y-3">
            {overview.funnel.map((stage, index) => (
              <div
                key={stage.stage}
                className="rounded-2xl border border-line bg-surface p-4"
              >
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">
                    {index + 1}. {stage.stage}
                  </span>
                  <span className="text-muted">{stage.reached} reached</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-sand">
                  <div
                    className="h-full rounded-full bg-accent"
                    style={{
                      width: `${Math.round((stage.reached / base) * 100)}%`,
                    }}
                  />
                </div>
                {stage.stalled_here > 0 && (
                  <p className="mt-2 text-xs text-amber-700">
                    {stage.stalled_here} abandoned at this step
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>

        <section className="mt-12">
          <h2 className="font-display text-2xl">Needs review</h2>
          {overview.needs_review.length > 0 ? (
            <>
              <p className="mt-1 text-sm text-muted">
                The document readers disagreed on these — open one to
                resolve it.
              </p>
              <div className="mt-4 space-y-3">
                {overview.needs_review.map((item) => (
                  <button
                    key={item.case_id}
                    onClick={() => openCase(item.case_id)}
                    className="block w-full rounded-2xl border border-amber-300 bg-amber-50 p-4 text-left transition hover:border-amber-400"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{item.seller}</span>
                      <span className="text-xs text-muted">
                        {item.case_id} · {item.stage}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-amber-800">
                      {reviewSummary(item.review)}
                    </p>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <div className="mt-4 rounded-2xl border border-line bg-surface p-8 text-center">
              <p className="font-display text-xl">All clear.</p>
              <p className="mt-1 text-sm text-muted">
                No cases are waiting on a reader disagreement.
              </p>
            </div>
          )}
        </section>

        <section className="mt-12">
          <h2 className="font-display text-2xl">Recent submissions</h2>
          <div className="mt-4 overflow-hidden rounded-2xl border border-line bg-surface">
            {overview.recent.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-muted">
                No cases yet.
              </p>
            ) : (
              overview.recent.map((row) => (
                <button
                  key={row.case_id}
                  onClick={() => openCase(row.case_id)}
                  className="flex w-full items-center justify-between gap-4 border-b border-line px-5 py-3 text-left transition last:border-b-0 hover:bg-paper"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium">{row.seller}</p>
                    <p className="truncate text-xs text-muted">
                      {row.vehicle} · {row.vin}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-4 text-xs sm:gap-6">
                    <span className="hidden text-muted sm:inline">
                      {when(row.created_at)}
                    </span>
                    <span className="w-28 text-muted">{row.stage}</span>
                    <span className="w-14 text-right">
                      {row.products} svc
                    </span>
                    <span className="w-20 text-right font-medium text-accent">
                      {money(row.estimated_total)}
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>
        </section>

        <p className="mt-10 text-center text-xs text-muted">
          Updated {when(overview.generated_at)}
        </p>
      </div>

      {detail && (
        <CaseOverlay
          view={detail}
          operatorKey={key}
          onClose={() => setDetail(null)}
          onResolved={() => {
            setDetail(null);
            load(key);
          }}
        />
      )}
    </div>
  );
}
