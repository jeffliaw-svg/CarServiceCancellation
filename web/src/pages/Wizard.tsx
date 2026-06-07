import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Link } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { api, moneyExact, type Intake } from "../api";
import type { CaseView } from "../types";
import { Logo } from "../components/site";

const STORAGE_KEY = "refundroute_case";

const STEP_LABELS = [
  "Your details",
  "Documents",
  "Confirm services",
  "Your letters",
];

const HEADING_ID = "wizard-heading";

const FIELD_LABEL: Record<string, string> = {
  price: "the price",
  contract_number: "the contract number",
  administrator: "the provider",
  term_months: "the term in months",
  term_miles: "the term in miles",
};

const fieldLabel = (name: string) => FIELD_LABEL[name] ?? name;

type Guard = <T>(fn: () => Promise<T>) => Promise<T | undefined>;

interface StepProps {
  view: CaseView | null;
  token: string | null;
  setView: (v: CaseView) => void;
  advance: (v: CaseView, next: number) => void;
  guard: Guard;
  busy: boolean;
}

/* ------------------------------------------------------------------ */

function Stepper({
  step,
  onNavigate,
}: {
  step: number;
  onNavigate: (n: number) => void;
}) {
  return (
    <nav aria-label="Wizard progress" className="flex items-center">
      {STEP_LABELS.map((label, i) => {
        const n = i + 1;
        const done = n < step;
        const current = n === step;
        const dotClass = `flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
          done
            ? "bg-accent text-white"
            : current
              ? "bg-ink text-white"
              : "bg-sand text-muted"
        }`;
        const labelClass = `hidden text-sm sm:block ${
          current ? "font-medium text-ink" : "text-muted"
        }`;
        return (
          <div key={label} className="flex items-center">
            {done ? (
              <button
                type="button"
                onClick={() => onNavigate(n)}
                className="group flex items-center gap-2 rounded-full focus:outline-none"
                aria-label={`Go back to step ${n}: ${label}`}
              >
                <span
                  className={`${dotClass} transition group-hover:bg-accent-deep`}
                >
                  ✓
                </span>
                <span className={`${labelClass} group-hover:text-ink`}>
                  {label}
                </span>
              </button>
            ) : (
              <div
                className="flex items-center gap-2"
                aria-current={current ? "step" : undefined}
              >
                <div className={dotClass}>{n}</div>
                <span className={labelClass}>{label}</span>
              </div>
            )}
            {n < STEP_LABELS.length && (
              <div className="mx-3 h-px w-5 bg-line sm:w-8" aria-hidden="true" />
            )}
          </div>
        );
      })}
    </nav>
  );
}

function Panel({
  step,
  children,
}: {
  step: number;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      key={step}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

function Heading({ kicker, title, lead }: { kicker: string; title: string; lead: string }) {
  return (
    <div className="mb-8">
      <p className="text-xs font-semibold uppercase tracking-widest text-accent">
        {kicker}
      </p>
      <h1
        id={HEADING_ID}
        tabIndex={-1}
        className="font-display mt-2 text-3xl outline-none md:text-4xl"
      >
        {title}
      </h1>
      <p className="mt-3 max-w-xl text-muted">{lead}</p>
    </div>
  );
}

function Label({
  htmlFor,
  children,
}: {
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className="mb-1.5 block text-sm font-medium text-ink"
    >
      {children}
    </label>
  );
}

/* ------------------------------------------------------------------ */

function StepIntake({ advance, guard, busy }: StepProps) {
  const [legalName, setLegalName] = useState("");
  const [address, setAddress] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [vin, setVin] = useState("");
  const [saleDate, setSaleDate] = useState("");
  const [accessCode, setAccessCode] = useState(
    () => localStorage.getItem("refundroute_access_code") || "",
  );
  // Hide the access-code field behind a disclosure so cold visitors from
  // the landing page don't think the code is a hard prerequisite. The
  // disclosure opens automatically if a code is already on file.
  const [codeOpen, setCodeOpen] = useState(() => !!accessCode);

  const codeId = useId();
  const nameId = useId();
  const addrId = useId();
  const emailId = useId();
  const phoneId = useId();
  const vinId = useId();
  const dateId = useId();

  const ready =
    legalName.trim() && address.trim() && vin.trim() && saleDate.trim();

  async function submit() {
    const intake: Intake = {
      legal_name: legalName.trim(),
      address_lines: address
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean),
      email: email.trim(),
      phone: phone.trim(),
      vin: vin.trim(),
      sale_date: saleDate,
    };
    const v = await guard(() => api.createCase(intake, accessCode.trim()));
    if (v) {
      if (accessCode.trim()) {
        localStorage.setItem("refundroute_access_code", accessCode.trim());
      }
      advance(v, 2);
    }
  }

  return (
    <Panel step={1}>
      <Heading
        kicker="Step 1 of 4"
        title="Tell us about the sale"
        lead="Just enough to identify you and the vehicle. Everything else comes from your contract."
      />
      <div className="mb-6 rounded-2xl border border-line bg-accent-soft px-5 py-4 text-sm text-accent-deep">
        <p className="font-semibold">Your information stays private.</p>
        <ul className="mt-2 space-y-1">
          <li>
            We use your details only to prepare and address your refund
            requests.
          </li>
          <li>
            Your documents sit on our private server while your case is
            active. We never sell, share, or train on them, and we delete
            your case 90 days after you finish (or sooner on request).
          </li>
          <li>
            Starting a claim is free during the closed beta. If we add a
            fee later, you&rsquo;ll see and confirm it before you download
            your packet — never as a surprise at the end.
          </li>
        </ul>
        <p className="mt-2 text-xs text-accent-deep/80">
          RefundRoute is not a law firm and does not give legal advice.
        </p>
      </div>
      <div className="rounded-3xl border border-line bg-surface p-7">
        <div className="grid gap-5">
          <div>
            {codeOpen ? (
              <>
                <Label htmlFor={codeId}>Beta access code</Label>
                <input
                  id={codeId}
                  className="field"
                  value={accessCode}
                  onChange={(e) => setAccessCode(e.target.value)}
                  placeholder="Closed-beta access code"
                  autoComplete="off"
                  autoFocus
                />
                <p className="mt-1.5 text-xs text-muted">
                  Enter the code you were given. Don&rsquo;t have one?{" "}
                  <button
                    type="button"
                    className="font-medium text-accent hover:underline"
                    onClick={() => {
                      setAccessCode("");
                      setCodeOpen(false);
                    }}
                  >
                    Skip this
                  </button>
                  .
                </p>
              </>
            ) : (
              <button
                type="button"
                className="text-xs font-medium text-accent hover:underline"
                onClick={() => setCodeOpen(true)}
              >
                Have a beta code?
              </button>
            )}
          </div>
          <div>
            <Label htmlFor={nameId}>Your full legal name</Label>
            <input
              id={nameId}
              className="field"
              value={legalName}
              onChange={(e) => setLegalName(e.target.value)}
              placeholder="As it appears on the contract"
              autoComplete="name"
              aria-required="true"
            />
          </div>
          <div>
            <Label htmlFor={addrId}>Mailing address</Label>
            <textarea
              id={addrId}
              className="field"
              rows={2}
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder={"Street address\nCity, State ZIP"}
              autoComplete="street-address"
              aria-required="true"
            />
            <p className="mt-1.5 text-xs text-muted">
              Refund checks will be mailed here.
            </p>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <Label htmlFor={emailId}>Email (optional)</Label>
              <input
                id={emailId}
                className="field"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
              />
            </div>
            <div>
              <Label htmlFor={phoneId}>Phone (optional)</Label>
              <input
                id={phoneId}
                className="field"
                type="tel"
                inputMode="numeric"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="(555) 010-2345"
                autoComplete="tel"
              />
            </div>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <Label htmlFor={vinId}>Vehicle VIN</Label>
              <input
                id={vinId}
                className="field"
                value={vin}
                onChange={(e) => setVin(e.target.value.toUpperCase())}
                placeholder="1HGCM82633A004352"
                autoComplete="off"
                aria-required="true"
              />
              <p className="mt-1.5 text-xs text-muted">
                The 17-character number on your contract and registration.
              </p>
            </div>
            <div>
              <Label htmlFor={dateId}>Date you sold the vehicle</Label>
              <input
                id={dateId}
                className="field"
                type="date"
                value={saleDate}
                onChange={(e) => setSaleDate(e.target.value)}
                aria-required="true"
              />
            </div>
          </div>
        </div>
        <button
          className="btn btn-primary mt-7 w-full"
          disabled={!ready || busy}
          onClick={submit}
        >
          {busy ? "Saving…" : "Continue →"}
        </button>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileRow({
  title,
  hint,
  accept,
  fileName,
  onPick,
  busy,
  allowCamera,
}: {
  title: string;
  hint: string;
  accept: string;
  fileName?: string;
  onPick: (file: File) => Promise<void> | void;
  busy: boolean;
  allowCamera?: boolean;
}) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState<{ name: string; size: number } | null>(
    null,
  );
  const cameraRef = useRef<HTMLInputElement | null>(null);

  async function handlePick(file: File) {
    setUploading({ name: file.name, size: file.size });
    try {
      await onPick(file);
    } finally {
      setUploading(null);
    }
  }

  const locked = uploading !== null || busy;

  return (
    <div>
      <label
        className={`file-row flex cursor-pointer items-center justify-between gap-4 rounded-2xl border-2 border-dashed bg-paper px-5 py-4 transition ${
          dragging
            ? "border-accent bg-accent-soft"
            : "border-line hover:border-accent"
        } ${locked ? "pointer-events-none opacity-60" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!dragging) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files?.[0];
          if (file) handlePick(file);
        }}
      >
        <div>
          <p className="font-medium">{title}</p>
          <p className="text-xs text-muted">
            {fileName ? `Selected: ${fileName}` : `${hint} Drop a file here or click to choose.`}
          </p>
        </div>
        <span className="btn btn-ghost !px-4 !py-2 !text-xs" aria-hidden="true">
          {fileName ? "Replace" : "Choose file"}
        </span>
        <input
          type="file"
          accept={accept}
          aria-label={title}
          className="file-input"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handlePick(file);
          }}
        />
      </label>
      {uploading && (
        <div
          aria-live="polite"
          className="mt-2 rounded-xl border border-line bg-surface px-4 py-3"
        >
          <div className="flex items-center justify-between gap-3 text-xs text-muted">
            <span className="truncate">
              Uploading <span className="font-medium text-ink">{uploading.name}</span> · {formatBytes(uploading.size)}
            </span>
            <span>Reading your contract…</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-sand">
            <div className="indeterminate h-full w-1/3 rounded-full bg-accent" />
          </div>
        </div>
      )}
      {allowCamera && !uploading && (
        <div className="mt-2">
          <button
            type="button"
            disabled={busy}
            className="inline-flex min-h-11 items-center gap-1.5 px-1 text-xs font-medium text-accent hover:underline disabled:opacity-50"
            onClick={() => cameraRef.current?.click()}
          >
            <span aria-hidden="true">📷</span> Take a photo instead
          </button>
          <input
            ref={cameraRef}
            type="file"
            accept="image/*"
            capture="environment"
            aria-label={`Take a photo of ${title}`}
            className="file-input"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handlePick(file);
            }}
          />
        </div>
      )}
    </div>
  );
}

function PhoneHandoff({
  caseId,
  token,
  step,
}: {
  caseId: string;
  token: string | null;
  step: number;
}) {
  const [open, setOpen] = useState(false);
  if (!token) return null;
  const url = `${window.location.origin}/start?resume=${encodeURIComponent(
    `${caseId}.${token}.${step}`,
  )}`;
  return (
    <div className="rounded-2xl border border-line bg-paper px-5 py-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-medium">On a laptop? Switch to your phone.</p>
          <p className="text-xs text-muted">
            Use your phone's camera to snap the contract, then come back here.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost !px-4 !py-2 !text-xs"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Hide" : "Show QR code"}
        </button>
      </div>
      {open && (
        <div className="mt-4 flex flex-col items-center gap-4 sm:flex-row sm:items-start">
          <div className="rounded-xl border border-line bg-surface p-3">
            <QRCodeSVG value={url} size={156} />
          </div>
          <div className="text-xs text-muted sm:max-w-xs">
            <p className="font-medium text-ink">Scan with your phone camera.</p>
            <p className="mt-1">
              You will land on the same step with your case ready to go. Keep
              this code on your own screen -- anyone who scans it could resume
              your case.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}


function StepDocuments({
  view,
  token,
  setView,
  advance,
  guard,
  busy,
}: StepProps) {
  const [contractName, setContractName] = useState<string>();
  const [billName, setBillName] = useState<string>();
  const [pasted, setPasted] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  if (!view) return null;

  const products = view.products;

  async function uploadContractFile(file: File) {
    const v = await guard(() =>
      api.uploadFile(view!.case_id, token, file, "contract"),
    );
    if (v) {
      setView(v);
      setContractName(file.name);
    }
  }

  async function uploadPasted() {
    const v = await guard(() =>
      api.uploadText(view!.case_id, token, pasted, "contract"),
    );
    if (v) {
      setView(v);
      setContractName("pasted text");
    }
  }

  async function uploadBill(file: File) {
    const v = await guard(() =>
      api.uploadFile(view!.case_id, token, file, "bill_of_sale"),
    );
    if (v) {
      setView(v);
      setBillName(file.name);
    }
  }

  return (
    <Panel step={2}>
      <Heading
        kicker="Step 2 of 4"
        title="Add your paperwork"
        lead="Upload the retail installment contract (or buyer's order). It lists every add-on product we can recover."
      />
      <div className="space-y-5 rounded-3xl border border-line bg-surface p-7">
        <FileRow
          title="Purchase contract"
          hint="A PDF, a photo, or a text file -- the document that itemizes your add-ons."
          accept=".txt,.text,.pdf,.png,.jpg,.jpeg,.webp"
          fileName={contractName}
          onPick={uploadContractFile}
          busy={busy}
          allowCamera
        />
        <div className="rounded-2xl border border-line bg-paper px-5 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium">
                Don&rsquo;t have the contract handy?
              </p>
              <p className="mt-0.5 text-xs text-muted">
                You can paste the itemized add-on section in as text — works
                just as well as a photo.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-ghost min-h-11 !py-2 !text-xs"
              onClick={() => setShowPaste((s) => !s)}
            >
              {showPaste ? "Hide" : "Paste text instead"}
            </button>
          </div>
          {showPaste && (
            <div className="mt-4">
              <textarea
                className="field font-mono text-xs"
                rows={6}
                value={pasted}
                onChange={(e) => setPasted(e.target.value)}
                placeholder="Paste the itemized add-on section of your contract here…"
              />
              <button
                className="btn btn-primary mt-3 !py-2 !text-xs"
                disabled={!pasted.trim() || busy}
                onClick={uploadPasted}
              >
                Read pasted text
              </button>
            </div>
          )}
        </div>

        <FileRow
          title="Bill of sale (recommended)"
          hint="Proof you sold the vehicle. Enclosed with every letter."
          accept=".txt,.text,.pdf,.png,.jpg,.jpeg"
          fileName={billName}
          onPick={uploadBill}
          busy={busy}
          allowCamera
        />

        <PhoneHandoff caseId={view.case_id} token={token} step={2} />

        {view.parse_warnings.length > 0 && (
          <div className="rounded-xl bg-sand px-4 py-3 text-xs text-muted">
            {view.parse_warnings.map((w) => (
              <p key={w}>&middot; {w}</p>
            ))}
          </div>
        )}

        {products.length > 0 && (
          <div className="rounded-xl bg-accent-soft px-4 py-3 text-sm text-accent-deep">
            Found <strong>{products.length}</strong> add-on{" "}
            {products.length === 1 ? "product" : "products"} on your contract.
            {view.extraction_method && (
              <span className="block text-xs text-accent-deep/70">
                {view.extraction_method}
              </span>
            )}
          </div>
        )}

        <button
          className="btn btn-primary w-full"
          disabled={products.length === 0 || busy}
          onClick={() => advance(view, 3)}
        >
          {products.length === 0
            ? "Upload a contract to continue"
            : "Review what you are owed →"}
        </button>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */

function StepConfirm({ view, token, advance, guard, busy }: StepProps) {
  // A flagged product starts undecided (null) so the user must actively
  // check it; a cleanly-read product starts confirmed.
  const [decisions, setDecisions] = useState<(boolean | null)[]>(() =>
    view
      ? view.products.map((p) => (p.review_fields.length === 0 ? true : null))
      : [],
  );
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [pulsingIndex, setPulsingIndex] = useState<number | null>(null);
  if (!view) return null;

  const decide = (index: number, value: boolean) =>
    setDecisions((current) =>
      current.map((v, j) => (j === index ? value : v)),
    );

  const total = view.products.reduce(
    (sum, p, i) =>
      decisions[i] === true && p.estimate.can_estimate
        ? sum + p.estimate.net_refund
        : sum,
    0,
  );
  const keptCount = decisions.filter((d) => d === true).length;
  const undecided = decisions.some((d) => d === null);
  const submitDisabled = undecided || keptCount === 0 || busy;

  function scrollToFirstUndecided() {
    const idx = decisions.findIndex((d) => d === null);
    if (idx < 0) return;
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    cardRefs.current[idx]?.scrollIntoView({
      behavior: reduce ? "auto" : "smooth",
      block: "center",
    });
    setPulsingIndex(idx);
    window.setTimeout(() => setPulsingIndex(null), 1300);
  }

  async function submit() {
    if (submitDisabled) {
      if (undecided) scrollToFirstUndecided();
      return;
    }
    const keep = view!.products
      .filter((_, i) => decisions[i] === true)
      .map((p) => p.index);
    const v = await guard(() => api.confirm(view!.case_id, token, keep));
    if (v) advance(v, 4);
  }

  return (
    <Panel step={3}>
      <Heading
        kicker="Step 3 of 4"
        title="Confirm each service"
        lead="Here is what we read from your contract. Confirm the ones that are yours. Anything we flagged for review starts unanswered -- check it against your paperwork first."
      />
      {view.rules_notes.length > 0 && (
        <div className="mb-6 rounded-2xl border border-line bg-accent-soft px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-accent-deep">
            In your state
          </p>
          {view.rules_notes.map((note) => (
            <p key={note.topic} className="mt-2 text-sm text-accent-deep">
              <strong>{note.topic}:</strong> {note.rule}
            </p>
          ))}
        </div>
      )}
      <div className="space-y-4">
        {view.products.map((p, i) => {
          const decision = decisions[i];
          const border =
            decision === true
              ? "border-accent"
              : decision === false
                ? "border-line opacity-60"
                : "border-amber-300";
          return (
            <div
              key={p.index}
              ref={(el) => {
                cardRefs.current[i] = el;
              }}
              className={`rounded-2xl border bg-surface p-6 transition ${border} ${
                pulsingIndex === i ? "pulse-amber" : ""
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="max-w-xl">
                  <h3 className="text-lg font-semibold">{p.product_type}</h3>
                  <p className="mt-0.5 text-xs text-muted">
                    {p.administrator}
                    {p.contract_number ? ` · Contract ${p.contract_number}` : ""}
                  </p>
                  <p className="mt-3 text-[15px] font-medium leading-relaxed text-ink">
                    {p.headline}
                  </p>
                  <details open className="group mt-2">
                    <summary className="text-xs font-medium text-accent hover:underline">
                      How we estimated this
                      <span className="ml-1 inline-block transition-transform group-open:rotate-90">
                        &rsaquo;
                      </span>
                    </summary>
                    <p className="mt-2 text-sm leading-relaxed text-muted">
                      {p.detail}
                    </p>
                  </details>
                </div>
                <div className="text-right">
                  <p className="text-xs uppercase tracking-widest text-muted">
                    Est. refund
                  </p>
                  <p className="font-display text-2xl text-accent">
                    {p.estimate.can_estimate
                      ? moneyExact(p.estimate.net_refund)
                      : "TBD"}
                  </p>
                </div>
              </div>
              {p.review_fields.length > 0 && (
                <div className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-xs text-amber-800">
                  We weren&rsquo;t 100% sure on{" "}
                  <strong>{p.review_fields.map(fieldLabel).join(", ")}</strong>{" "}
                  for this product — please check your paperwork and confirm.
                </div>
              )}
              <div
                className="mt-5 flex flex-wrap items-center gap-3"
                role="group"
                aria-label={`Is the ${p.product_type} yours?`}
              >
                <button
                  className={`btn min-h-11 !py-2.5 !text-xs ${
                    decision === true ? "btn-primary" : "btn-ghost"
                  }`}
                  aria-pressed={decision === true}
                  aria-label={`Yes, the ${p.product_type} is mine`}
                  onClick={() => decide(i, true)}
                >
                  {decision === true ? "✓ Confirmed" : "Yes, this is mine"}
                </button>
                <button
                  type="button"
                  className={`min-h-11 px-2 py-2 text-xs font-medium underline-offset-2 hover:underline ${
                    decision === false ? "text-ink" : "text-muted"
                  }`}
                  aria-pressed={decision === false}
                  aria-label={`No, the ${p.product_type} is not mine`}
                  onClick={() => decide(i, false)}
                >
                  {decision === false ? "✓ Not mine" : "Not mine"}
                </button>
                {decision === null && (
                  <span className="text-xs font-medium text-amber-700">
                    Needs your decision
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="sticky bottom-0 z-10 mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-ink px-6 py-5 text-paper shadow-[0_-12px_30px_-20px_rgba(20,17,15,0.5)]">
        <div>
          <p className="text-xs uppercase tracking-widest text-paper/60">
            Estimated total across {keptCount} confirmed service
            {keptCount === 1 ? "" : "s"}
          </p>
          <p className="font-display text-3xl">{moneyExact(total)}</p>
        </div>
        <button
          className={`btn btn-light ${submitDisabled ? "opacity-60" : ""}`}
          aria-disabled={submitDisabled}
          onClick={submit}
        >
          {busy
            ? "Saving…"
            : undecided
              ? "Answer every service above"
              : "Generate my letters →"}
        </button>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */

const KIND_LABEL: Record<string, string> = {
  letter: "Certified-mail letter",
  email: "Email draft",
  authorization: "Authorization to sign",
  checklist: "Mailing checklist",
  bundle: "Everything, zipped",
};

const PIPELINE_STORAGE = "refundroute_pipeline";

function GenerateProgress({ count }: { count: number }) {
  const stages = [
    `Drafting ${count} letter${count === 1 ? "" : "s"}`,
    "Preparing your authorization",
    "Writing your mailing checklist",
    "Bundling everything up",
  ];
  const [stage, setStage] = useState(0);
  useEffect(() => {
    if (stage >= stages.length - 1) return;
    const t = window.setTimeout(() => setStage((s) => s + 1), 1100);
    return () => window.clearTimeout(t);
  }, [stage, stages.length]);

  return (
    <div className="rounded-3xl border border-line bg-surface p-8">
      <p className="text-xs font-semibold uppercase tracking-widest text-accent">
        Drafting your packet
      </p>
      <ul className="mt-5 space-y-3" aria-live="polite">
        {stages.map((label, i) => {
          const done = i < stage;
          const active = i === stage;
          return (
            <li key={label} className="flex items-center gap-3 text-sm">
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
                  done
                    ? "bg-accent text-white"
                    : active
                      ? "bg-ink text-white"
                      : "bg-sand text-muted"
                }`}
                aria-hidden="true"
              >
                {done ? "✓" : i + 1}
              </span>
              <span
                className={
                  done ? "text-muted" : active ? "font-medium text-ink" : "text-muted"
                }
              >
                {label}
              </span>
              {active && (
                <span className="ml-2 inline-flex h-1.5 w-16 overflow-hidden rounded-full bg-sand">
                  <span className="indeterminate h-full w-1/3 rounded-full bg-accent" />
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

type PipelineStep = "print" | "sign" | "mail";

function MailingPipeline({ caseId }: { caseId: string }) {
  const storageKey = `${PIPELINE_STORAGE}_${caseId}`;
  const [checked, setChecked] = useState<Record<PipelineStep, boolean>>(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) return JSON.parse(raw);
    } catch {
      /* ignore */
    }
    return { print: false, sign: false, mail: false };
  });

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(checked));
  }, [storageKey, checked]);

  const steps: { key: PipelineStep; title: string; body: string }[] = [
    {
      key: "print",
      title: "Print the packet",
      body: "Use letter-size paper. The mailing checklist sits on top.",
    },
    {
      key: "sign",
      title: "Sign the authorization",
      body: "One signature on the authorization page. Notary only if your packet says so.",
    },
    {
      key: "mail",
      title: "Mail each letter Certified",
      body: "USPS Certified Mail with Return Receipt for every letter. Keep the green slips.",
    },
  ];

  function toggle(key: PipelineStep) {
    setChecked((current) => ({ ...current, [key]: !current[key] }));
  }

  return (
    <div className="rounded-2xl border border-line bg-surface p-6">
      <p className="text-xs font-semibold uppercase tracking-widest text-accent">
        Your next 20 minutes
      </p>
      <ol className="mt-4 grid gap-3 sm:grid-cols-3">
        {steps.map((step, index) => {
          const isChecked = checked[step.key];
          return (
            <li key={step.key}>
              <button
                type="button"
                onClick={() => toggle(step.key)}
                aria-pressed={isChecked}
                className={`flex h-full w-full flex-col rounded-2xl border p-4 text-left transition ${
                  isChecked
                    ? "border-accent bg-accent-soft"
                    : "border-line bg-paper hover:border-accent"
                }`}
              >
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${
                      isChecked ? "bg-accent text-white" : "bg-sand text-muted"
                    }`}
                    aria-hidden="true"
                  >
                    {isChecked ? "✓" : index + 1}
                  </span>
                  <span>{step.title}</span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-muted">
                  {step.body}
                </p>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function WhatHappensNext() {
  return (
    <details className="group rounded-2xl border border-line bg-surface p-6" open>
      <summary className="flex cursor-pointer items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-accent">
            What happens next
          </p>
          <p className="mt-1 text-sm font-semibold">
            How long this usually takes, and what to expect.
          </p>
        </div>
        <span className="text-2xl text-accent transition-transform group-open:rotate-45" aria-hidden="true">
          +
        </span>
      </summary>
      <div className="mt-4 space-y-4 text-sm leading-relaxed text-muted">
        <div>
          <p className="font-medium text-ink">Week 1</p>
          <p>
            Your Certified Mail letters arrive. The provider opens a file and
            requests anything they still need (often: a clean copy of the bill
            of sale, or a payoff letter from the lender).
          </p>
        </div>
        <div>
          <p className="font-medium text-ink">Weeks 2–6</p>
          <p>
            Most providers acknowledge the cancellation in writing within 2–3
            weeks. A check (or a credit to the lender on a financed contract)
            usually follows within 4–6 weeks. Tire and Wheel and prepaid
            maintenance tend to be the fastest; multi-year vehicle service
            contracts can take the longest.
          </p>
        </div>
        <div>
          <p className="font-medium text-ink">If you get a denial or a stall</p>
          <p>
            A common refusal is &ldquo;you must cancel through the selling
            dealer.&rdquo; That is sometimes true and sometimes a deflection;
            forward the letter to{" "}
            <a className="text-accent hover:underline" href="mailto:hello@refundroute.example">
              hello@refundroute.example
            </a>{" "}
            and we&rsquo;ll tell you whether to push back or re-mail to the
            dealer.
          </p>
        </div>
        <div>
          <p className="font-medium text-ink">After 30 days of silence</p>
          <p>
            Send a polite follow-up referencing your Certified Mail tracking
            number. If 60 days pass with no response, that&rsquo;s the point at
            which most state insurance departments will accept a complaint.
          </p>
        </div>
      </div>
    </details>
  );
}

function StepGenerate({ view, token, setView, guard, busy }: StepProps) {
  if (!view) return null;
  const done = view.generated.length > 0;

  async function generate() {
    const v = await guard(() => api.generate(view!.case_id, token));
    if (v) setView(v);
  }

  if (!done) {
    return (
      <Panel step={4}>
        <Heading
          kicker="Step 4 of 4"
          title="Generate your refund packet"
          lead="We will draft a certified-mail letter for each confirmed service, plus an authorization for you to sign and a mailing checklist."
        />
        {busy ? (
          <GenerateProgress count={view.products.length} />
        ) : (
          <div className="rounded-3xl border border-line bg-surface p-8 text-center">
            <p className="mx-auto max-w-md text-muted">
              {view.products.length} letter
              {view.products.length === 1 ? "" : "s"} ready to be drafted for{" "}
              <strong className="text-ink">{view.seller.legal_name}</strong>.
            </p>
            <button
              className="btn btn-primary mt-6"
              onClick={generate}
            >
              Generate my letters
            </button>
          </div>
        )}
      </Panel>
    );
  }

  const bundle = view.generated.find((g) => g.kind === "bundle");
  const rest = view.generated.filter((g) => g.kind !== "bundle");

  return (
    <Panel step={4}>
      <Heading
        kicker="All done"
        title="Your refund packet is ready"
        lead="Download everything, print it, sign the authorization, and send each letter by USPS Certified Mail."
      />
      {bundle && (
        <a
          href={api.fileUrl(view.case_id, bundle.name, token)}
          className="mb-5 flex items-center justify-between rounded-2xl bg-accent px-6 py-5 text-white"
        >
          <div>
            <p className="font-semibold">Download the full packet</p>
            <p className="text-sm text-white/80">{bundle.description}</p>
          </div>
          <span className="btn btn-light !py-2 !text-xs">Download .zip</span>
        </a>
      )}
      <div className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
        {rest.map((g) => (
          <a
            key={g.name}
            href={api.fileUrl(view.case_id, g.name, token)}
            className="flex items-center justify-between gap-4 px-6 py-4 hover:bg-paper"
          >
            <div>
              <p className="font-medium">
                {KIND_LABEL[g.kind] ?? g.kind}
              </p>
              <p className="text-xs text-muted">{g.description}</p>
            </div>
            <span className="text-sm font-medium text-accent">Download</span>
          </a>
        ))}
      </div>

      <div className="mt-6">
        <MailingPipeline caseId={view.case_id} />
      </div>

      <div className="mt-6">
        <WhatHappensNext />
      </div>

      <div className="mt-6 rounded-2xl bg-sand px-6 py-5 text-xs leading-relaxed text-muted">
        Provider addresses came from public sources and should be double-checked
        before you mail. Refund figures are estimates. The provider calculates
        the final amount.
      </div>

      <div className="mt-6 text-center">
        <Link to="/" className="text-sm font-medium text-accent hover:underline">
          Back to home
        </Link>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */

export default function Wizard() {
  const [step, setStep] = useState(1);
  const [view, setView] = useState<CaseView | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const errorRef = useRef<HTMLDivElement | null>(null);
  const [resuming, setResuming] = useState(() => {
    if (typeof window === "undefined") return false;
    return (
      !!localStorage.getItem(STORAGE_KEY) ||
      new URLSearchParams(window.location.search).has("resume")
    );
  });

  // Resume a case after a refresh, a closed tab, the back button, or a
  // phone-handoff QR scan (URL "?resume=caseId.token.step"). Both paths
  // converge on the same localStorage record.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const resumeParam = params.get("resume");
    if (resumeParam) {
      const [caseId, tok, stepStr] = resumeParam.split(".");
      if (caseId && tok) {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            caseId,
            token: tok,
            step: parseInt(stepStr || "2", 10) || 2,
          }),
        );
        window.history.replaceState({}, "", "/start");
      }
    }

    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) {
      setResuming(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const stored = JSON.parse(saved) as {
          caseId: string;
          token: string;
          step: number;
        };
        const restored = await api.getCase(stored.caseId, stored.token);
        if (cancelled) return;
        setView(restored);
        setToken(stored.token);
        setStep(stored.step || 1);
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      } finally {
        if (!cancelled) setResuming(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (view && token) {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ caseId: view.case_id, token, step }),
      );
    }
  }, [view, token, step]);

  const guard: Guard = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      return undefined;
    } finally {
      setBusy(false);
    }
  };

  function advance(v: CaseView, next: number) {
    setView(v);
    if (v.access_token) setToken(v.access_token);
    setStep(next);
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  }

  function navigateBack(target: number) {
    if (target >= step) return;
    setStep(target);
  }

  function startOver() {
    if (view && !window.confirm("Discard this claim and start over?")) return;
    localStorage.removeItem(STORAGE_KEY);
    setView(null);
    setToken(null);
    setStep(1);
    setError(null);
  }

  // After a step change, move keyboard focus to the new heading so screen
  // readers announce the step and so Tab order picks up from the top of
  // the new panel.
  useEffect(() => {
    const t = window.setTimeout(() => {
      const h = document.getElementById(HEADING_ID) as HTMLElement | null;
      h?.focus({ preventScroll: true });
    }, 60);
    return () => window.clearTimeout(t);
  }, [step]);

  // When a fetch fails after a Continue tap, the error banner can sit
  // above the fold on mobile and the page looks frozen. Scroll it into
  // view and move focus so screen readers announce it.
  useEffect(() => {
    if (!error) return;
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    errorRef.current?.scrollIntoView({
      behavior: reduce ? "auto" : "smooth",
      block: "center",
    });
    errorRef.current?.focus();
  }, [error]);

  const stepProps: StepProps = { view, token, setView, advance, guard, busy };

  if (resuming) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-muted">Resuming your claim…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <a href="#wizard-main" className="skip-link">
        Skip to main content
      </a>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <Logo />
          {view ? (
            <button
              className="min-h-11 px-2 text-xs font-medium text-muted hover:text-ink"
              onClick={startOver}
            >
              Discard and restart
            </button>
          ) : (
            <span className="text-xs text-muted">Secure refund workup</span>
          )}
        </div>
      </header>

      <main id="wizard-main" className="mx-auto max-w-3xl px-6 py-10">
        <div className="mb-3 flex justify-center">
          <Stepper step={step} onNavigate={navigateBack} />
        </div>
        <p className="mb-8 text-center text-xs font-medium text-muted sm:hidden">
          Step {step} of {STEP_LABELS.length} — {STEP_LABELS[step - 1]}
        </p>

        <div aria-live="polite" aria-atomic="true" className="sr-only">
          Step {step} of {STEP_LABELS.length}: {STEP_LABELS[step - 1]}
        </div>

        {error && (
          <div
            ref={errorRef}
            tabIndex={-1}
            role="alert"
            className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 outline-none"
          >
            {error}
          </div>
        )}

        <AnimatePresence mode="wait">
          {step === 1 && <StepIntake key="s1" {...stepProps} />}
          {step === 2 && <StepDocuments key="s2" {...stepProps} />}
          {step === 3 && <StepConfirm key="s3" {...stepProps} />}
          {step === 4 && <StepGenerate key="s4" {...stepProps} />}
        </AnimatePresence>
      </main>
    </div>
  );
}
