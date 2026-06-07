import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Footer, Logo, Reveal } from "../components/site";

const STEPS = [
  {
    n: "01",
    title: "Tell us about the sale",
    body: "Your legal name, the vehicle's VIN, and the date you sold it. That is the entire form.",
  },
  {
    n: "02",
    title: "Upload your paperwork",
    body: "Add the purchase contract and the bill of sale. We read every add-on product line by line.",
  },
  {
    n: "03",
    title: "Confirm and prepare",
    body: "We show your estimated refunds. Confirm each service, and we draft the letters and authorization for you to print, sign, and mail.",
  },
];

const RECOVER = [
  ["Vehicle Service Contract", "Extended warranty / VSC coverage"],
  ["GAP Waiver", "Often refundable by law on early payoff"],
  ["Tire & Wheel", "Road-hazard tire and wheel plans"],
  ["Prepaid Maintenance", "Bundled oil-change and service plans"],
  ["Appearance Protection", "Paint, fabric, and interior packages"],
  ["Key Replacement", "Lost-key and remote coverage"],
  ["Theft Protection", "VIN etch and anti-theft products"],
  ["And more", "Any add-on itemized on your contract"],
];

const FAQ = [
  {
    q: "How do you know what I bought?",
    a: "We read it off your retail installment contract -- the one document that itemizes every add-on product, its price, and its term. You upload it; we do the rest.",
  },
  {
    q: "Do I still have to mail things myself?",
    a: "Yes. We generate print-ready letters, a signed authorization, and a step-by-step checklist. You print, sign, enclose your bill of sale, and send them by certified mail. That paper trail is what protects you.",
  },
  {
    q: "How much can I actually get back?",
    a: "It depends on how much of each contract was unused when you sold the car. A multi-year service contract cancelled early can refund several hundred to a couple thousand dollars. The figures we show are estimates. The provider (the company that administers your contract) calculates the final amount.",
  },
  {
    q: "Are you a law firm?",
    a: "No. RefundRoute is not a law firm and does not give legal advice. Cancelling an add-on after you sell the car is a routine contractual right -- you simply authorize us to prepare the request on your behalf.",
  },
  {
    q: "What happens to my contract after I upload it?",
    a: "Your documents and details are stored privately on our server while your case is active so you can come back and finish. We read them with our own software and a vetted OCR provider; we don't sell, share, or train on anything you upload. You can email hello@refundroute.example to delete your case at any time, and we delete it automatically 90 days after you finish.",
  },
];

function Nav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 14);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${
        scrolled
          ? "border-b border-line bg-paper/85 backdrop-blur-md"
          : "border-b border-transparent"
      }`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Logo />
        <nav className="hidden items-center gap-8 text-sm font-medium md:flex">
          <a href="#how" className="text-muted hover:text-ink">
            How it works
          </a>
          <a href="#recover" className="text-muted hover:text-ink">
            What we recover
          </a>
          <a href="#pricing" className="text-muted hover:text-ink">
            Pricing
          </a>
          <a href="#faq" className="text-muted hover:text-ink">
            FAQ
          </a>
        </nav>
        <Link to="/start" className="btn btn-primary !px-5 !py-2.5 !text-sm">
          Start a claim
        </Link>
      </div>
    </header>
  );
}

function EstimateCard() {
  const rows = [
    ["Vehicle Service Contract", "$1,512"],
    ["GAP Waiver", "$502"],
    ["Tire & Wheel", "$353"],
  ];
  return (
    <motion.div
      animate={{ y: [0, -12, 0] }}
      transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
      className="relative w-full max-w-sm"
    >
      <div className="absolute -right-5 -top-5 rounded-full bg-accent px-4 py-2 text-xs font-semibold text-white shadow-lg">
        Sample estimate
      </div>
      <div className="rounded-3xl border border-line bg-surface p-7 shadow-[0_30px_60px_-30px_rgba(20,17,15,0.35)]">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted">
          Estimated refunds
        </p>
        <div className="mt-5 space-y-4">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-center justify-between">
              <span className="text-sm text-ink/80">{label}</span>
              <span className="font-display text-lg">{value}</span>
            </div>
          ))}
        </div>
        <div className="mt-5 border-t border-line pt-5">
          <div className="flex items-end justify-between">
            <span className="text-sm font-semibold">Estimated total</span>
            <span className="font-display text-3xl text-accent">$2,367</span>
          </div>
        </div>
        <div className="mt-6 rounded-xl bg-accent-soft px-4 py-3 text-xs text-accent-deep">
          3 letters drafted &middot; you print, sign, and mail them
        </div>
        <p className="mt-3 text-center text-[11px] text-muted">
          Illustrative example. Your amounts depend on your contract.
        </p>
      </div>
    </motion.div>
  );
}

export default function Landing() {
  return (
    <div className="overflow-x-hidden">
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <Nav />

      <main id="main">
      {/* Hero */}
      <section className="relative px-6 pb-24 pt-36 md:pt-44">
        <div
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(60% 50% at 75% 0%, rgba(12,107,81,0.10), transparent 70%)",
          }}
        />
        <div className="mx-auto grid max-w-6xl items-center gap-14 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <motion.span
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3.5 py-1.5 text-xs font-medium text-muted"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              For people who just sold a car
            </motion.span>

            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.05 }}
              className="font-display mt-6 text-5xl leading-[1.05] md:text-6xl"
            >
              Get back the money you&rsquo;re still owed.
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.12 }}
              className="mt-6 max-w-xl text-lg leading-relaxed text-muted"
            >
              When you sell a car, the service contracts, GAP, and tire plans
              you paid for are still running. You are owed a pro-rata refund of
              the unused portion. RefundRoute finds it and drafts the letters
              to claim it.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.19 }}
              className="mt-9 flex flex-wrap items-center gap-3"
            >
              <Link to="/start" className="btn btn-primary">
                See what you&rsquo;re owed &rarr;
              </Link>
              <a href="#how" className="btn btn-ghost">
                See how it works
              </a>
            </motion.div>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.7, delay: 0.3 }}
              className="mt-6 text-sm text-muted"
            >
              One short form &middot; one document &middot; we prepare the paperwork
            </motion.p>
          </div>

          <div className="flex justify-center lg:justify-end">
            <EstimateCard />
          </div>
        </div>
      </section>

      {/* Problem strip */}
      <section className="border-y border-line bg-surface">
        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-14 sm:grid-cols-3">
          {[
            ["$1,000+", "Commonly left unclaimed on a single vehicle sale"],
            ["6 +", "Add-on products a dealer may bundle into one contract"],
            ["Pro rata", "Refunds owed for every unused month and mile"],
          ].map(([big, small], i) => (
            <Reveal key={big} delay={i * 0.08}>
              <p className="font-display text-4xl text-accent">{big}</p>
              <p className="mt-2 text-sm leading-relaxed text-muted">{small}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <p className="text-xs font-semibold uppercase tracking-widest text-accent">
              How it works
            </p>
            <h2 className="font-display mt-3 max-w-2xl text-4xl md:text-5xl">
              Three steps between you and your refund.
            </h2>
          </Reveal>
          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {STEPS.map((step, i) => (
              <Reveal key={step.n} delay={i * 0.1}>
                <div className="h-full rounded-3xl border border-line bg-surface p-8">
                  <span className="font-display text-3xl text-accent/40">
                    {step.n}
                  </span>
                  <h3 className="mt-4 text-xl font-semibold">{step.title}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-muted">
                    {step.body}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* What we recover */}
      <section id="recover" className="border-y border-line bg-sand px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <p className="text-xs font-semibold uppercase tracking-widest text-accent">
              What we recover
            </p>
            <h2 className="font-display mt-3 max-w-2xl text-4xl md:text-5xl">
              Every add-on the dealer sold you.
            </h2>
            <p className="mt-4 max-w-xl text-muted">
              If it was itemized on your purchase contract and you sold the car
              early, it is very likely refundable.
            </p>
          </Reveal>
          <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {RECOVER.map(([title, body], i) => (
              <Reveal key={title} delay={(i % 4) * 0.07}>
                <div className="h-full rounded-2xl border border-line bg-surface p-6">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-soft">
                    <span className="h-2 w-2 rounded-full bg-accent" />
                  </div>
                  <h3 className="mt-4 font-semibold">{title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">
                    {body}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="px-6 py-24">
        <div className="mx-auto max-w-3xl text-center">
          <Reveal>
            <p className="text-xs font-semibold uppercase tracking-widest text-accent">
              Pricing
            </p>
            <h2 className="font-display mt-3 text-4xl md:text-5xl">
              Free during the closed beta.
            </h2>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="mt-10 rounded-3xl border border-line bg-surface p-10 text-left shadow-[0_30px_60px_-40px_rgba(20,17,15,0.4)]">
              <div className="flex items-baseline gap-2">
                <span className="font-display text-6xl">$0</span>
                <span className="text-muted">while we&rsquo;re in beta</span>
              </div>
              <p className="mt-4 text-muted">
                Starting a claim is free today. Before any future fee, we will
                show you what it costs and ask you to confirm — never as a
                surprise at the end.
              </p>
              <ul className="mt-7 space-y-3 text-sm">
                {[
                  "Line-by-line reading of your contract",
                  "A pro-rata refund estimate for every product",
                  "Certified-mail letters, drafted and ready to print",
                  "A signed authorization and a mailing checklist",
                  "Ready-to-send email drafts where accepted",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3">
                    <span className="mt-0.5 text-accent">&#10003;</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <Link
                to="/start"
                className="btn btn-primary mt-8 w-full"
              >
                Start a claim &rarr;
              </Link>
              <p className="mt-4 text-center text-xs text-muted">
                Refund figures are estimates. The provider calculates the
                final amount.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="border-t border-line bg-surface px-6 py-24">
        <div className="mx-auto max-w-3xl">
          <Reveal>
            <h2 className="font-display text-4xl md:text-5xl">
              Questions, answered.
            </h2>
          </Reveal>
          <div className="mt-10 divide-y divide-line border-y border-line">
            {FAQ.map((item, i) => (
              <Reveal key={item.q} delay={i * 0.05}>
                <details className="group py-5">
                  <summary className="flex items-center justify-between gap-4 text-lg font-medium">
                    {item.q}
                    <span className="text-2xl text-accent transition-transform duration-200 group-open:rotate-45">
                      +
                    </span>
                  </summary>
                  <p className="mt-3 text-sm leading-relaxed text-muted">
                    {item.a}
                  </p>
                </details>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* CTA band */}
      <section className="px-6 py-20">
        <Reveal>
          <div className="mx-auto max-w-6xl overflow-hidden rounded-[2rem] bg-ink px-8 py-16 text-center text-paper">
            <h2 className="font-display mx-auto max-w-2xl text-4xl md:text-5xl">
              You already paid for it. Go get it back.
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-paper/70">
              Start a claim now -- it takes a few minutes, and the paperwork is
              waiting for you at the end.
            </p>
            <Link
              to="/start"
              className="btn btn-light mt-8"
            >
              Start a claim &rarr;
            </Link>
          </div>
        </Reveal>
      </section>

      </main>

      <Footer />
    </div>
  );
}
