// Every number the product shows passes through here. Nothing renders a raw
// float, a raw fraction, or a bare identifier.
//
// Precision is deliberate and not uniform. Published policy figures keep two
// decimals because the case study, the KPI pack and the portfolio manifest
// quote them at two and the three must agree. Exploratory figures the reader
// is scanning rather than citing get one, because a default rate carried to
// three decimals off a single three-month sample implies a precision the data
// does not have.

const INR = new Intl.NumberFormat("en-IN");

export const count = (value) => INR.format(Math.round(value));

// Indian rupees in crore, the unit a policy reader works in at this book size.
// Grouped, because a book this size runs to four digits of crore and
// "₹1267.36 cr" makes the reader count columns.
const CRORE = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const crore = (value) =>
  `${value < 0 ? "−" : ""}₹${CRORE.format(Math.abs(value / 10_000_000))} cr`;

export const lakh = (value) => `₹${(value / 100_000).toFixed(2)} lakh`;

export const rupees = (value) => `₹${INR.format(Math.round(value))}`;

// A fraction (0.1517) rendered as a percentage. `cited` keeps the two decimals
// a published figure is quoted at; everything else reads at one.
export const rate = (value, cited = false) => `${(value * 100).toFixed(cited ? 2 : 1)}%`;

// A value already expressed in percentage points (74.75), not a fraction.
export const points = (value, digits = 1) => `${value.toFixed(digits)}%`;

// Take the absolute value BEFORE formatting. Math.abs on an already-formatted
// string coerces it back to a number and silently drops the trailing zero, so
// a +4.0 pp gap printed as "+4 pp".
export const signedPoints = (value, digits = 1) =>
  `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value * 100).toFixed(digits)} pp`;

// A difference between two rates, in percentage points. Distinct from `points`,
// which renders a value that genuinely is a percentage of something.
export const pointsDelta = (value, digits = 1) => `${Math.abs(value * 100).toFixed(digits)} points`;

// 100 is the portfolio average. Shown as a whole number because the reader is
// comparing magnitudes, not citing a coefficient.
export const index = (value) => Math.round(value).toString();

export const score = (value) => (value == null ? "Not scored" : `${(value * 100).toFixed(1)}%`);

export const ordinal = (value) => {
  const rounded = Math.round(value * 100);
  const suffix = rounded % 10 === 1 && rounded % 100 !== 11 ? "st"
    : rounded % 10 === 2 && rounded % 100 !== 12 ? "nd"
      : rounded % 10 === 3 && rounded % 100 !== 13 ? "rd" : "th";
  return `${rounded}${suffix}`;
};

export const psi = (value) => value.toFixed(3);

// PSI reads against fixed industry thresholds rather than against the other
// values on screen, so a stable book cannot be made to look unstable by having
// its largest number highlighted.
export const psiVerdict = (value) =>
  value < 0.1 ? { label: "Stable", tone: "good" }
    : value < 0.25 ? { label: "Moderate shift", tone: "watch" }
      : { label: "Material shift", tone: "alert" };
