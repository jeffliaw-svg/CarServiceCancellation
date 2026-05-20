import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

const EASE = [0.22, 1, 0.36, 1] as const;

export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 26 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.7, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

export function Logo({ className = "" }: { className?: string }) {
  return (
    <Link to="/" className={`flex items-center gap-2.5 ${className}`}>
      <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true">
        <circle cx="16" cy="16" r="15" fill="var(--color-accent)" />
        <path
          d="M16 8.5a7.5 7.5 0 1 1-6.6 3.95"
          fill="none"
          stroke="#fff"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
        <path
          d="M9.4 7.2v5.4h5.4"
          fill="none"
          stroke="#fff"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="text-[1.15rem] font-semibold tracking-tight">
        Refund<span className="text-accent">Route</span>
      </span>
    </Link>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-14 md:grid-cols-[1.4fr_1fr_1fr]">
        <div>
          <Logo />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
            We help people who have sold a car reclaim the pro-rata refunds
            they are owed on cancelled service contracts and add-ons.
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-muted">
            Product
          </p>
          <ul className="mt-4 space-y-2.5 text-sm">
            <li>
              <a href="/#how" className="hover:text-accent">
                How it works
              </a>
            </li>
            <li>
              <a href="/#recover" className="hover:text-accent">
                What we recover
              </a>
            </li>
            <li>
              <a href="/#pricing" className="hover:text-accent">
                Pricing
              </a>
            </li>
            <li>
              <Link to="/start" className="hover:text-accent">
                Start a claim
              </Link>
            </li>
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-muted">
            The fine print
          </p>
          <p className="mt-4 text-sm leading-relaxed text-muted">
            RefundRoute is not a law firm and does not provide legal advice.
            Refund figures are estimates; each administrator calculates the
            binding amount under the terms of your contract.
          </p>
        </div>
      </div>
      <div className="border-t border-line">
        <div className="mx-auto max-w-6xl px-6 py-6 text-xs text-muted">
          &copy; {new Date().getFullYear()} RefundRoute. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
