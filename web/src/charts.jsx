import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

// Validated with the dataviz palette checker against the #f4f6f9 chart surface:
// lightness band, chroma floor, protan/deutan/tritan separation, normal-vision
// separation and contrast all pass for the categorical pair and for the
// diverging poles. Do not substitute a hue here without re-running it.
export const PALETTE = {
  primary: "#0b67ad",    // observed, and the single-series default
  secondary: "#a86a00",  // predicted, the only second categorical hue
  low: "#0b67ad",        // diverging pole: below the portfolio average
  mid: "#7d8894",        // diverging midpoint, deliberately neutral
  high: "#a4331f",       // diverging pole: above the portfolio average
  grid: "#d7dee5",
  axis: "#5b6b7a",
  ink: "#17212b",
  muted: "#5b6b7a",
};

/** Container width, measured. Charts are sized from the real box rather than a
 *  viewBox stretch, so labels keep their intended size at every breakpoint. */
function useWidth() {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(node);
    setWidth(node.getBoundingClientRect().width);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

function useTooltip() {
  const [tip, setTip] = useState(null);
  const show = useCallback((x, y, content) => setTip({ x, y, content }), []);
  const hide = useCallback(() => setTip(null), []);
  return [tip, show, hide];
}

function Tooltip({ tip, width }) {
  if (!tip) return null;
  // Flip before the tooltip can leave the plot; a tip clipped at the right edge
  // is the same as no tip.
  const flip = tip.x > width - 150;
  return (
    <div
      className="chart-tip"
      style={{ left: `${tip.x}px`, top: `${tip.y}px`, transform: `translate(${flip ? "-100%" : "0"}, -50%)`, marginLeft: flip ? -10 : 10 }}
      role="status"
    >
      {tip.content}
    </div>
  );
}

/** Every chart states the question it answers, its units, and where it came
 *  from. A plot without those three is decoration. */
export function Figure({ question, units, source, note, children, actions }) {
  return (
    <figure className="figure">
      <figcaption>
        <div>
          <h3>{question}</h3>
          {units && <p className="figure-units">{units}</p>}
        </div>
        {actions}
      </figcaption>
      {children}
      {note && <p className="figure-note">{note}</p>}
      {source && <p className="figure-source">{source}</p>}
    </figure>
  );
}

export function Legend({ items }) {
  if (items.length < 2) return null;
  return (
    <ul className="legend">
      {items.map((item) => (
        <li key={item.label}>
          <span className="legend-mark" style={{ background: item.color }} aria-hidden="true" />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

function niceTicks(max, count = 4) {
  if (max <= 0) return [0];
  const raw = max / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((candidate) => candidate >= raw) ?? magnitude * 10;
  const ticks = [];
  for (let value = 0; value <= max + step / 2; value += step) ticks.push(value);
  return ticks;
}

/** Vertical columns for a single measure across an ordered set of categories.
 *  `tone` on a datum switches it to the diverging poles for good/bad readings. */
export function ColumnChart({ data, format, height = 240, valueLabels = true, ariaLabel }) {
  const [ref, width] = useWidth();
  const [tip, show, hide] = useTooltip();
  const pad = { top: 18, right: 8, bottom: 44, left: 52 };
  const plotWidth = Math.max(0, width - pad.left - pad.right);
  const plotHeight = height - pad.top - pad.bottom;
  const max = Math.max(...data.map((d) => d.value), 0);
  const ticks = niceTicks(max);
  const top = ticks[ticks.length - 1] || 1;
  const slot = data.length ? plotWidth / data.length : 0;
  // A 2px surface gap between adjacent fills so bars read as separate marks.
  const barWidth = Math.max(2, Math.min(46, slot - 8));

  return (
    <div className="chart" ref={ref}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          {ticks.map((tick) => {
            const y = pad.top + plotHeight - (tick / top) * plotHeight;
            return (
              <g key={tick}>
                <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke={PALETTE.grid} strokeWidth="1" />
                <text x={pad.left - 8} y={y + 4} textAnchor="end" className="chart-axis-text">{format(tick)}</text>
              </g>
            );
          })}
          {data.map((datum, i) => {
            const barHeight = top ? (datum.value / top) * plotHeight : 0;
            const x = pad.left + i * slot + (slot - barWidth) / 2;
            const y = pad.top + plotHeight - barHeight;
            const fill = datum.color ?? PALETTE.primary;
            return (
              <g key={datum.label}>
                <rect
                  x={x} y={y} width={barWidth} height={Math.max(barHeight, 1)} fill={fill} rx="3"
                  onMouseEnter={() => show(x + barWidth / 2, y, <><strong>{datum.label}</strong><span>{datum.tip ?? format(datum.value)}</span></>)}
                  onMouseLeave={hide}
                />
                {valueLabels && barWidth >= 22 && (
                  <text x={x + barWidth / 2} y={y - 6} textAnchor="middle" className="chart-value-text">{format(datum.value)}</text>
                )}
                <text x={x + barWidth / 2} y={height - pad.bottom + 16} textAnchor="middle" className="chart-axis-text">{datum.label}</text>
                {datum.sublabel && (
                  <text x={x + barWidth / 2} y={height - pad.bottom + 30} textAnchor="middle" className="chart-sub-text">{datum.sublabel}</text>
                )}
              </g>
            );
          })}
          <line x1={pad.left} x2={width - pad.right} y1={pad.top + plotHeight} y2={pad.top + plotHeight} stroke={PALETTE.axis} strokeWidth="1" />
        </svg>
      )}
      <Tooltip tip={tip} width={width} />
    </div>
  );
}

/** One or two series over a continuous x. Used for the gains curve, the
 *  calibration plot and the per-vintage outcome line.
 *
 *  `reference` draws the diagonal a gains or calibration chart is read against;
 *  without it the reader has nothing to judge the curve's shape by. */
export function LineChart({
  series, xFormat, yFormat, xLabel, yLabel, height = 260, reference = null,
  xDomain = [0, 1], yDomain = null, markers = true, ariaLabel,
}) {
  const [ref, width] = useWidth();
  const [tip, show, hide] = useTooltip();
  const pad = { top: 18, right: 16, bottom: 46, left: 56 };
  const plotWidth = Math.max(0, width - pad.left - pad.right);
  const plotHeight = height - pad.top - pad.bottom;
  const allY = series.flatMap((s) => s.points.map((p) => p.y));
  const yMax = yDomain ? yDomain[1] : Math.max(...allY, 0);
  const yMin = yDomain ? yDomain[0] : 0;
  const ticks = yDomain ? niceTicks(yMax).filter((t) => t >= yMin) : niceTicks(yMax);
  const top = Math.max(ticks[ticks.length - 1] || 1, yMax);
  const sx = (x) => pad.left + ((x - xDomain[0]) / (xDomain[1] - xDomain[0] || 1)) * plotWidth;
  const sy = (y) => pad.top + plotHeight - ((y - yMin) / (top - yMin || 1)) * plotHeight;

  return (
    <div className="chart" ref={ref}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={pad.left} x2={width - pad.right} y1={sy(tick)} y2={sy(tick)} stroke={PALETTE.grid} strokeWidth="1" />
              <text x={pad.left - 8} y={sy(tick) + 4} textAnchor="end" className="chart-axis-text">{yFormat(tick)}</text>
            </g>
          ))}
          {reference && (
            <>
              <line
                x1={sx(reference.from.x)} y1={sy(reference.from.y)}
                x2={sx(reference.to.x)} y2={sy(reference.to.y)}
                stroke={PALETTE.axis} strokeWidth="1.5" strokeDasharray="5 4"
              />
              <text x={sx(reference.to.x) - 6} y={sy(reference.to.y) - 8} textAnchor="end" className="chart-sub-text">
                {reference.label}
              </text>
            </>
          )}
          {series.map((s) => (
            <g key={s.label}>
              <path
                d={s.points.map((p, i) => `${i === 0 ? "M" : "L"}${sx(p.x)},${sy(p.y)}`).join(" ")}
                fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"
              />
              {markers && s.points.map((p) => (
                <circle
                  key={`${s.label}-${p.x}`} cx={sx(p.x)} cy={sy(p.y)} r="4.5"
                  fill={s.color} stroke="#f4f6f9" strokeWidth="2"
                  onMouseEnter={() => show(sx(p.x), sy(p.y), <><strong>{p.label ?? xFormat(p.x)}</strong><span>{s.label}: {yFormat(p.y)}</span></>)}
                  onMouseLeave={hide}
                />
              ))}
            </g>
          ))}
          <line x1={pad.left} x2={width - pad.right} y1={pad.top + plotHeight} y2={pad.top + plotHeight} stroke={PALETTE.axis} strokeWidth="1" />
          {series[0]?.points.map((p) => (
            <text key={`x-${p.x}`} x={sx(p.x)} y={height - pad.bottom + 18} textAnchor="middle" className="chart-axis-text">
              {p.tick ?? xFormat(p.x)}
            </text>
          ))}
          {xLabel && <text x={pad.left + plotWidth / 2} y={height - 6} textAnchor="middle" className="chart-sub-text">{xLabel}</text>}
          {yLabel && <text transform={`rotate(-90 12 ${pad.top + plotHeight / 2})`} x="12" y={pad.top + plotHeight / 2} textAnchor="middle" className="chart-sub-text">{yLabel}</text>}
        </svg>
      )}
      <Tooltip tip={tip} width={width} />
    </div>
  );
}

/** Horizontal bars diverging from a centre, for an index where 100 is the
 *  portfolio average. Direction carries the meaning, so the two poles are the
 *  validated diverging pair and every bar is also labelled with its value. */
export function DivergingBars({ data, center = 100, format, rowHeight = 30, ariaLabel }) {
  const [ref, width] = useWidth();
  const [tip, show, hide] = useTooltip();
  const labelWidth = 132;
  const pad = { top: 8, right: 56, bottom: 26 };
  const plotWidth = Math.max(0, width - labelWidth - pad.right);
  const spread = Math.max(...data.map((d) => Math.abs(d.value - center)), 1) * 1.15;
  const height = data.length * rowHeight + pad.top + pad.bottom;
  const midX = labelWidth + plotWidth / 2;
  const scale = (value) => (value / spread) * (plotWidth / 2);

  return (
    <div className="chart" ref={ref}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          {data.map((datum, i) => {
            const delta = datum.value - center;
            const y = pad.top + i * rowHeight;
            const barWidth = Math.abs(scale(delta));
            const x = delta >= 0 ? midX : midX - barWidth;
            const fill = Math.abs(delta) < 3 ? PALETTE.mid : delta > 0 ? PALETTE.high : PALETTE.low;
            return (
              <g key={datum.label}>
                <text x={labelWidth - 12} y={y + rowHeight / 2 + 4} textAnchor="end" className="chart-axis-text">{datum.label}</text>
                <rect
                  x={x} y={y + 6} width={Math.max(barWidth, 1)} height={rowHeight - 13} fill={fill} rx="3"
                  onMouseEnter={() => show(delta >= 0 ? x + barWidth : x, y + rowHeight / 2, <><strong>{datum.label}</strong><span>{datum.tip ?? format(datum.value)}</span></>)}
                  onMouseLeave={hide}
                />
                <text
                  x={delta >= 0 ? midX + barWidth + 8 : midX - barWidth - 8}
                  y={y + rowHeight / 2 + 4}
                  textAnchor={delta >= 0 ? "start" : "end"}
                  className="chart-value-text"
                >
                  {format(datum.value)}
                </text>
              </g>
            );
          })}
          <line x1={midX} x2={midX} y1={pad.top} y2={height - pad.bottom} stroke={PALETTE.axis} strokeWidth="1.5" />
          <text x={midX} y={height - 8} textAnchor="middle" className="chart-sub-text">{center} = portfolio average</text>
        </svg>
      )}
      <Tooltip tip={tip} width={width} />
    </div>
  );
}

/** Ranked share bars. Deliberately not a Pareto with a second y-axis: the
 *  cumulative share is a column in the table beside it, because two scales on
 *  one frame is the mistake that makes a concentration chart unreadable. */
export function RankedBars({ data, format, ariaLabel, rowHeight = 28 }) {
  const [ref, width] = useWidth();
  const [tip, show, hide] = useTooltip();
  const labelWidth = 108;
  const valueWidth = 62;
  const plotWidth = Math.max(0, width - labelWidth - valueWidth);
  const max = Math.max(...data.map((d) => d.value), 0) || 1;
  const height = data.length * rowHeight + 8;

  return (
    <div className="chart" ref={ref}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          {data.map((datum, i) => {
            const y = 4 + i * rowHeight;
            const barWidth = (datum.value / max) * plotWidth;
            return (
              <g key={datum.label}>
                <text x={labelWidth - 12} y={y + rowHeight / 2 + 4} textAnchor="end" className="chart-axis-text">{datum.label}</text>
                <rect
                  x={labelWidth} y={y + 5} width={Math.max(barWidth, 1)} height={rowHeight - 11}
                  fill={datum.color ?? PALETTE.primary} rx="3"
                  onMouseEnter={() => show(labelWidth + barWidth, y + rowHeight / 2, <><strong>{datum.label}</strong><span>{datum.tip ?? format(datum.value)}</span></>)}
                  onMouseLeave={hide}
                />
                <text x={labelWidth + barWidth + 8} y={y + rowHeight / 2 + 4} className="chart-value-text">{format(datum.value)}</text>
              </g>
            );
          })}
        </svg>
      )}
      <Tooltip tip={tip} width={width} />
    </div>
  );
}

/** Small multiple: one tiny line per dimension. Three separate single-series
 *  panels rather than three hues on one frame, because a third categorical hue
 *  could not clear the chroma floor against this surface. */
export function MiniLine({ points, format, height = 74, threshold = null, ariaLabel }) {
  const [ref, width] = useWidth();
  const pad = { top: 10, right: 10, bottom: 20, left: 10 };
  const plotWidth = Math.max(0, width - pad.left - pad.right);
  const plotHeight = height - pad.top - pad.bottom;
  const max = Math.max(...points.map((p) => p.y), threshold ?? 0) * 1.2 || 1;
  const sx = (i) => pad.left + (points.length > 1 ? (i / (points.length - 1)) * plotWidth : plotWidth / 2);
  const sy = (y) => pad.top + plotHeight - (y / max) * plotHeight;

  return (
    <div className="chart" ref={ref}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          {threshold != null && (
            <line x1={pad.left} x2={width - pad.right} y1={sy(threshold)} y2={sy(threshold)} stroke={PALETTE.axis} strokeWidth="1" strokeDasharray="4 3" />
          )}
          <path d={points.map((p, i) => `${i === 0 ? "M" : "L"}${sx(i)},${sy(p.y)}`).join(" ")} fill="none" stroke={PALETTE.primary} strokeWidth="2" strokeLinecap="round" />
          {points.map((p, i) => (
            <g key={p.label}>
              <circle cx={sx(i)} cy={sy(p.y)} r="3.5" fill={PALETTE.primary} stroke="#f4f6f9" strokeWidth="1.5" />
              <text x={sx(i)} y={height - 6} textAnchor="middle" className="chart-sub-text">{p.label}</text>
            </g>
          ))}
          <text x={width - pad.right} y={pad.top + 2} textAnchor="end" className="chart-value-text">{format(points[points.length - 1].y)}</text>
        </svg>
      )}
    </div>
  );
}

/** Escape hatch every chart needs: the numbers, as a table, for a reader who
 *  wants to check the plot or is not reading it visually at all. */
export function DataTable({ columns, rows, caption, open = false }) {
  const [expanded, setExpanded] = useState(open);
  useEffect(() => setExpanded(open), [open]);
  return (
    <details className="data-table" open={expanded} onToggle={(event) => setExpanded(event.currentTarget.open)}>
      <summary>{expanded ? "Hide" : "Show"} the numbers</summary>
      <p className="table-scroll-hint">Scroll horizontally to see all columns.</p>
      <div className="table-scroll" tabIndex="0" role="region" aria-label={`${caption ?? "Data"} table`}>
        <table>
          {caption && <caption>{caption}</caption>}
          <thead>
            <tr>{columns.map((column) => <th key={column.key} scope="col">{column.label}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row.key ?? i}>
                {columns.map((column) => <td key={column.key}>{column.render ? column.render(row) : row[column.key]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
