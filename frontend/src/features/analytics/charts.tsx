import {
  BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, LineElement, PointElement, Tooltip,
} from "chart.js";
import { Bar, Line } from "react-chartjs-2";

import type { TrendPoint } from "@/api/types";

import { C } from "./ui";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Tooltip, Legend);

const axis = {
  grid: { color: C.grid }, border: { display: false },
  ticks: { color: C.ink2, font: { size: 11 } },
};

/** On-time % per month: this office vs city average, with the 85% target as a reference line. Single y-axis. */
export function OnTimeTrend({ office, city, label }: { office: TrendPoint[]; city: TrendPoint[]; label: string }) {
  const labels = office.map((p) => p.label.replace(" 20", " '"));
  const v = (p: TrendPoint) => (p.on_time_rate == null ? null : Math.round(p.on_time_rate * 100));
  return (
    <Line
      aria-label={`On-time rate per month, ${label} vs city average`}
      data={{
        labels,
        datasets: [
          { label, data: office.map(v), borderColor: C.office, backgroundColor: C.office, borderWidth: 2, pointRadius: 3, spanGaps: true, tension: 0 },
          { label: "City average", data: city.map(v), borderColor: C.city, backgroundColor: C.city, borderWidth: 2, borderDash: [5, 4], pointRadius: 0, spanGaps: true, tension: 0 },
          { label: "Target 85%", data: labels.map(() => 85), borderColor: C.target, borderWidth: 1, borderDash: [2, 3], pointRadius: 0 },
        ],
      }}
      options={{
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 14, color: C.ink2 } },
          tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y ?? "—"}%` } },
        },
        scales: { x: { ...axis, grid: { display: false } }, y: { ...axis, min: 0, max: 100, ticks: { ...axis.ticks, callback: (t) => `${t}%` } } },
      }}
    />
  );
}

/** Cases received vs resolved per month (same unit, one axis). */
export function FlowBars({ office }: { office: TrendPoint[] }) {
  return (
    <Bar
      aria-label="Received and resolved per month"
      data={{
        labels: office.map((p) => p.label.replace(" 20", " '")),
        datasets: [
          { label: "Natanggap", data: office.map((p) => p.received), backgroundColor: C.received, borderRadius: 4, borderSkipped: "start", barPercentage: 0.8, categoryPercentage: 0.7 },
          { label: "Naresolba", data: office.map((p) => p.resolved), backgroundColor: C.resolved, borderRadius: 4, borderSkipped: "start", barPercentage: 0.8, categoryPercentage: 0.7 },
        ],
      }}
      options={{
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 14, color: C.ink2 } } },
        scales: { x: { ...axis, grid: { display: false } }, y: { ...axis, beginAtZero: true, ticks: { ...axis.ticks, precision: 0 } } },
      }}
    />
  );
}

/** Open-case age buckets (single series, sequential meaning: older = worse → darker). */
export function AgingBars({ data }: { data: { bucket: string; count: number }[] }) {
  const ramp = ["#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
  return (
    <Bar
      aria-label="Open cases by age"
      data={{ labels: data.map((d) => d.bucket), datasets: [{ label: "Bukas na kaso", data: data.map((d) => d.count), backgroundColor: ramp, borderRadius: 4, borderSkipped: "start" }] }}
      options={{
        indexAxis: "y", responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { ...axis, beginAtZero: true, ticks: { ...axis.ticks, precision: 0 } }, y: { ...axis, grid: { display: false } } },
      }}
    />
  );
}
