# The next 50 enhancements

This list is the merged output of a three-agent audit of the customer-facing
product: a senior product designer (UX flow, micro-interactions, mobile,
delight), an accessibility / inclusive-design expert, and a content
strategist / customer-empathy specialist. Duplicates between agents were
collapsed; items already shipped (mobile drag-drop, in-flow camera, QR
phone-handoff, plain-language confirmation copy, prefers-reduced-motion
plumbing, per-case access tokens, the closed-beta gate, the operator
console with the resolution workflow) are not repeated here.

Severity is the agent's call: **H** = launch-blocking or trust-killing,
**M** = important polish, **L** = nice-to-have.

## Trust & first impressions

1. **[H] Add a "who we are."** No founder/team/location is anywhere; a
   stressed user handing over name + VIN + contract has no one to vet.
   Add a short About strip on the landing page with a real name and
   contact, and a one-line credit in the wizard header.
2. **[H] Social proof / track record.** No testimonials, no "users have
   recovered $X" counter, no "as seen in." For a skeptical reader this
   is the single biggest conversion killer; add 2–3 anonymized stories
   and a modest running total.
3. **[H] Resolve the pricing contradiction.** Landing says `$49 per
   claim packet`; the wizard says "Starting a claim is free — you will
   see any fee before you download your packet." Pick one truth and
   mirror it everywhere; if there is no payment step yet, soften the
   landing copy until there is.
4. **[H] Pricing terms in plain English.** When is the charge taken,
   what happens if no products are recoverable, is it refundable. One
   sentence on the landing, one sentence above the generate button.
5. **[M] Vary the CTA copy.** "Start a claim →" appears five times on
   the landing. Use "See what you're owed →" on the hero (lower
   commitment for a cold visitor) and reserve "Start a claim" for the
   pricing / final bands.
6. **[M] Data-handling specifics.** "Stored privately, never sold or
   shared" is vague. Say where, for how long, when documents are
   deleted, and link to a real privacy page.
7. **[M] Soften the authorization document.** A nine-section
   `LIMITED AUTHORIZATION AND POWER OF ATTORNEY` with `Principal` and
   `attorney-in-fact` reads as intimidating boilerplate. Add a plain
   preamble at the top: *"This one-page form lets us ask the companies
   on your behalf. It does not let us touch your money — refunds go
   directly to you."* Keep the legal body unchanged below it.

## Intake step

8. **[H] Hide the access-code field behind a toggle.** A "Have a beta
   code?" expander would let newcomers from the landing page reach the
   form without thinking the code is a hard prerequisite.
9. **[H] Reframe "authorized agent" on the letter.** The seller's
   signature is currently captioned `(by [Service Name], as authorized
   agent)`, which reads as a third party signing for them. Rewrite as
   *"Prepared with assistance from RefundRoute, on the Principal's
   behalf."*
10. **[M] Split the address into proper fields.** Street / City / State
    (select) / ZIP. A multiline textarea is cramped on a phone and
    cannot be validated.
11. **[M] VIN validation.** 17 characters, no I/O/Q. Inline soft
    warning, not a hard block.
12. **[M] Sale-date bounds.** `min={today − 5y}` `max={today}` to catch
    typo'd years.
13. **[L] Phone field correctness.** `type="tel" inputMode="numeric"`
    plus light formatting; same pass: `autoComplete="name"`,
    `"street-address"`, `"email"` on the others.

## Documents step

14. **[H] "I don't have it handy" branch.** The pasted-text fallback is
    a small green link. Add a prominent path: *"Don't have the
    contract handy? We'll email you a resume link."* Pauses the case
    and lets them return.
15. **[H] Upload progress.** Large phone-photo PDFs base64'd into JSON
    can take 10–30 seconds on cellular while the "Choose file" button
    silently dims. Show an indeterminate bar and byte/time hint.
16. **[M] "Found N products" deserves a dollar number.** When parsing
    succeeds, animate in a chip: *"Estimated $2,367 across 3 products —
    Review →"*
17. **[M] Bill of sale: required or honestly optional.** "Recommended"
    invites skipping a document every letter says is enclosed. Either
    require it, or explain the trade-off ("each letter will say a copy
    is enclosed; if you skip this we'll mark it 'to follow'").
18. **[M] Pick one name for the post-flow checklist.** The landing
    promises a "mailing checklist," the wizard says "Mailing
    checklist," the file is the "instruction sheet" on each packet.
    One word, everywhere.

## Confirm step

19. **[H] Show the estimate detail by default.** "How we estimated
    this" is collapsed — the exact thing a money-anxious user wants to
    see. Open it by default on the first visit per session.
20. **[H] Reweight the toggle.** "Yes, this is mine" should be primary
    accent; "Not mine" should be a smaller tertiary link. Equal weight
    invites accidental rejection.
21. **[H] Stepper dots are clickable.** Completed dots become focusable
    buttons that navigate backward (without wiping state) — needed for
    fixing a typo'd VIN noticed at step 3.
22. **[M] Disabled "Generate" should help.** Clicking the disabled CTA
    scrolls to and pulses the first undecided card.
23. **[M] "TBD" → "Amount set by the provider."** Cold jargon next to
    real dollar figures.
24. **[M] Warmer flagged-field copy.** Replace *"Our document readers
    didn't fully agree"* with *"We weren't 100% sure on the price —
    please check your paperwork and confirm."* Same for the "Needs
    your decision" pill.
25. **[M] Sticky running total on mobile.** The dark summary bar is at
    the bottom of the list, so toggling "Not mine" can't be observed
    against the total. Make it `sticky bottom-0` on small screens.

## Generate & post-actions

26. **[H] Stepped progress during generation.** PDF assembly is
    server-side and slow. Show a checklist that ticks off
    *"Drafting letter 1 of 3 → preparing authorization → bundling
    packet."*
27. **[H] A visual "Print → Sign → Mail" pipeline after generation.**
    Each step a checkbox the user ticks. The current grey "Before you
    mail" note blends in and gets missed.
28. **[H] "What happens next."** The flow ends at "download .zip"; the
    user doesn't know when to expect a reply or what a denial looks
    like. Add a panel with typical timelines, what a refusal looks
    like, and when to follow up.
29. **[M] Verify addresses before generation, not after.** The current
    flow generates the packet then warns the operator-curated
    addresses "should be confirmed." Either confirm at packet-time
    (link to each company's contact page) or before generating.
30. **[L] Celebration moment.** A single one-shot motion burst plus a
    headline *"Up to $2,367 in motion"* is a tiny ritual that turns a
    stressed user into an advocate.

## Cross-device & resume

31. **[H] Magic resume link by email.** localStorage breaks across
    devices; a user filling on a laptop and finishing on a phone loses
    the case. Email a `case_id`+token magic link at the end of step 1.
32. **[M] Graceful resume failure.** When the server-side case is gone,
    clear storage silently and route to step 1 with one neutral line:
    *"We couldn't find your earlier claim."*
33. **[M] "Start over" should confirm.** Too easy to tap by mistake on
    mobile near the logo. Rename to *"Discard and restart"* and add a
    confirm dialog.

## Loading, errors, feedback

34. **[H] Error banner — scroll into view and focus.** After tapping
    Continue, the page can look frozen on mobile because the error is
    above the fold and there is no focus shift. `guard` should
    `scrollTo(0)` on error and move focus to the alert region.
35. **[M] Slow-API affordance.** After ~800 ms of a pending action, fade
    a translucent shimmer over the active card.
36. **[M] Smooth scrolling respects reduced motion.** The CSS
    `scroll-behavior: smooth` and the JS `scrollTo({behavior:"smooth"})`
    override the user's reduced-motion preference. Branch on
    `matchMedia('(prefers-reduced-motion: reduce)')`.
37. **[L] Animated FAQ disclosure.** `<details>` on iOS Safari toggles
    instantly with no animation, making the page feel jumpy. Replace
    with a small framer-motion height animation.

## Mobile & responsive

38. **[H] Mobile stepper label.** Below `sm` the stepper is four
    numbered dots with no labels. Show the current step's label below
    the dots: *"Step 2 of 4 — Documents."*
39. **[M] Hamburger/sheet nav on landing.** Phone users currently can't
    jump to Pricing / FAQ.
40. **[M] Operator resolution overlay on small screens.** The 42vh
    contract pane is unusable on a 360 × 640 phone. Add a mobile tab
    pattern (Contract / Fields) or stack both panes full-height.

## Accessibility

41. **[H] Skip link and `<main>` landmark on every page.** Screen-
    reader users currently have to tab through the fixed nav on every
    Landing visit.
42. **[H] Treat `CaseOverlay` as a real dialog.** `role="dialog"`,
    `aria-modal`, `aria-labelledby`, focus trap, Escape closes,
    return-focus on close. Today screen readers don't announce it and
    keyboard users can tab into the page behind.
43. **[H] Programmatic form labels.** `<Label>` should render a
    `<label htmlFor=…>` paired to an input `id=…`. Currently labels
    are visual-only.
44. **[H] Announce step transitions.** A polite `aria-live` region
    saying *"Step 3 of 4: Confirm each service"* and a focus move to
    the new `<h1>` (`tabIndex={-1}` then `.focus()`).
45. **[M] Touch targets to 44 px.** Several toggles (Yes/Not mine,
    Refresh, Sign out, "Change") are 28–32 px tall; below WCAG 2.5.5.
46. **[M] Required / invalid field semantics.** `aria-required`,
    `aria-invalid`, error message via `aria-describedby`. Validate on
    blur, not only on submit.
47. **[M] Live regions on the operator console.** The Recent and
    Needs-review lists should be `aria-live="polite"` so Refresh
    announces what changed.

## Copy consistency & jargon

48. **[H] One name for the company.** Landing/FAQ uses "administrator,"
    the confirm step mixes "administrator" and "provider," the letter
    uses "Administrator" and sometimes "dealership." Pick one
    customer-facing word (recommend **provider**); reserve
    "administrator" for the formal letter.
49. **[M] First-use glosses for jargon.** "pro-rata (the unused
    portion of what you paid)" on first mention; "retail installment
    contract (the long contract from the dealer that lists every
    add-on)"; drop "F&I" from any customer-visible copy.
50. **[M] Standardize the estimate disclaimer.** Today the landing,
    confirm step, and letter each say it differently. One sentence,
    everywhere: *"This is an estimate. The company will calculate the
    final amount."*
