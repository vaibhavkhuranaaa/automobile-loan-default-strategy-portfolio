# Product design contract

Status: `implementation review complete - human screenshot approval required`

## Product context

- Audience: a senior credit-policy analyst preparing a committee recommendation.
- Primary task: review the book, test one of three evaluated policy bands, document exceptions, and either advance or refuse the policy.
- Decision supported: bounded aggregate portfolio policy review. The product does not make an applicant decision.
- Success: the analyst can identify the evidence period, decision owner, current status, controlling exception, assumptions, result, and next action without interpretation help.

## Chosen visual world

The product is a risk-control workpaper, not a generic analytics dashboard. Its references are credit committee packs, audit schedules, underwriting spreads, and control ledgers. The interface should feel prepared for review: dated, ruled, traceable, and economical.

The signature element is the review register. It connects book, evidence period, owner, status, and use boundary before the first chart. Sections read as numbered exhibits and decision notes. Rules and alignment create hierarchy; rounded cards, decorative gradients, floating tiles, and promotional copy do not.

## Information hierarchy

1. Review identity: portfolio, evidence period, owner, status, use boundary.
2. Controlling decision or exception.
3. Primary evidence and operating assumptions.
4. Supporting exhibits and tables.
5. Provenance, limitations, and next action.

The first viewport must answer: what is under review, what is the standing decision, and what requires action. Model metrics support those answers; they do not lead the page.

## Shared shell

- A compact register header replaces the decorative brand bar.
- Flat workpaper tabs use an underline and `aria-current="page"`; deep links and browser navigation remain supported.
- The main page heading is visible and specific to the active view.
- A metadata strip states `Evidence: Aug-Oct 2018`, `Owner: Credit policy`, `Status: Review required`, and `Use: Portfolio + records`.
- The footer carries the data and decision boundary once. Implementation-stack names do not appear in the shell.
- Loading, empty, error, retry, stale-refresh, keyboard, and touch-target behavior remain shared requirements.

## Screen plan

### Portfolio review

Lead with book size, outcome movement, and model standing. Vintage and ranking exhibits follow. Technology evidence is secondary and must not compete with the portfolio conclusion.

### Risk review

Four explicit schedules cover ranking, segment risk, concentration, and distributional impact. Anonymized codes remain codes. The impact schedule is a screen, not a fair-lending opinion.

### Policy decision

Lead with the current refusal. Present the three evaluated bands as selectable register rows, then economic assumptions, capacity, the calculated decision, break-even conditions, and saved comparisons. Every result identifies whether it is observed evidence, an analyst input, or an estimate.

### Loan review

Shortlists identify loans worth opening. The peer comparison is empirical, not a second model, and no direct identifier or source row is exposed.

### Control monitoring

Lead with control status. Population stability is available for every vintage; calibration is shown only for the held-out month. Structural caveats remain first-class content.

## Visual system

- Typeface: operating-system sans; tabular numerals for all measures.
- Scale: 12, 14, 16, 22, and 32px. Large display type is not used.
- Surfaces: white paper on pale neutral canvas, dark ink, slate secondary text, dark blue action, rust exception, amber caution, and green acceptable state.
- Shape: square or 2px corners. Sections use horizontal rules and spacing instead of card containers or shadows.
- Metrics: compact register cells separated by rules, with label, value, and qualification aligned consistently.
- Charts: each is an exhibit with a direct noun-based title, units, scope, source, and table-view twin. One measure per axis and no color-only meaning.
- Tables: strong header rule, restrained row highlight, tabular numerals, and explicit mobile scroll affordance.
- Controls: native-feeling 44px targets, visible focus, direct labels, and no mystery icons.

## Language standard

Write like a senior analyst addressing a review committee.

- State the decision, evidence, exception, owner, and next action.
- Prefer `October default rate` to `How did default change?`.
- Prefer `Policy standing: refuse` to promotional or conversational phrasing.
- Do not use generic claims such as `unlock insights`, `smart`, `AI-powered`, or `seamless`.
- Do not imply fraud detection, observed P&L, protected-class analysis, or real-time production capability.
- Use `State code N` where the publisher supplied no lookup.

## Responsive and accessibility contract

- Capture each view at 1440px and 390px, including all four risk schedules.
- No document-level horizontal overflow. Wide tables may scroll inside labeled regions with a visible hint.
- Preserve one visible page-level heading, semantic landmarks, keyboard navigation, 44px controls, visible focus, reduced-motion behavior, and non-color status labels.
- Human approval of all current screenshots is required after any visual change.

## Evidence boundary

The source contains first-EMI default, not fraud. Economic results are assumption-led estimates. The review window is August to October 2018, calibration is historical, the label may include operational mandate failure, and no policy band clears zero at the published assumptions. The design must make these limits easier to see, never easier to ignore.
