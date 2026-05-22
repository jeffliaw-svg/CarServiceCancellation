import { useEffect, useState } from "react";
import { api } from "../api";
import type { CaseView, OperatorOverview } from "../types";
import { Logo } from "../components/site";

const KEY_STORAGE = "refundroute_operator_key";

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

function DetailOverlay({
  view,
  onClose,
}: {
  view: CaseView;
  onClose: () => void;
}) {
  const packets = view.generated.filter((g) => g.kind === "packet").length;
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-4 sm:p-10"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-3xl border border-line bg-surface p-7"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="font-display text-2xl">{view.seller.legal_name}</h3>
            <p className="text-xs text-muted">
              Case {view.case_id} · {view.status}
            </p>
          </div>
          <button
            className="btn btn-ghost !px-3 !py-1.5 !text-xs"
            onClick={onClose}
          >
            Close
          </button>
        </div>

        <dl className="mt-5 grid grid-cols-1 gap-x-8 text-sm sm:grid-cols-2">
          <Fact label="Vehicle" value={view.vehicle.description} />
          <Fact label="VIN" value={view.vehicle.vin} />
          <Fact label="Sold" value={view.sale_date} />
          <Fact label="Purchased" value={view.vehicle.purchase_date || "—"} />
          <Fact label="Started" value={when(view.created_at)} />
          <Fact label="Last activity" value={when(view.updated_at)} />
        </dl>
        {view.extraction_method && (
          <p className="mt-3 text-xs text-muted">
            Read by: {view.extraction_method}
          </p>
        )}

        <h4 className="mt-6 text-sm font-semibold">
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
                  {p.estimate.can_estimate
                    ? money(p.estimate.net_refund)
                    : "TBD"}
                </span>
              </div>
              <p className="text-xs text-muted">
                {p.administrator}
                {p.contract_number ? ` · ${p.contract_number}` : ""}
              </p>
              {p.review_fields.length > 0 && (
                <p className="mt-1 text-xs text-amber-700">
                  Flagged for review: {p.review_fields.join(", ")}
                </p>
              )}
            </div>
          ))}
        </div>

        {packets > 0 && (
          <p className="mt-4 text-sm text-muted">
            {packets} mailing packet{packets === 1 ? "" : "s"} generated.
          </p>
        )}
        {view.parse_warnings.length > 0 && (
          <div className="mt-4 rounded-xl bg-sand px-4 py-3 text-xs text-muted">
            {view.parse_warnings.map((w) => (
              <p key={w}>· {w}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

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

        {overview.needs_review.length > 0 && (
          <section className="mt-12">
            <h2 className="font-display text-2xl">Needs review</h2>
            <p className="mt-1 text-sm text-muted">
              The document readers disagreed on these — check before the
              letters are relied on.
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
          </section>
        )}

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
        <DetailOverlay view={detail} onClose={() => setDetail(null)} />
      )}
    </div>
  );
}
