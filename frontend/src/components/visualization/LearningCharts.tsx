import { useEffect, useMemo, useRef } from "react";
import type { EChartsCoreOption, EChartsType } from "echarts/core";

import type { CourseMasteryPoint } from "../../api/courses";

type ChartPalette = {
  accent: string;
  text: string;
  muted: string;
  border: string;
  warning: string;
};

type EChartCanvasProps = {
  label: string;
  optionFactory: (palette: ChartPalette) => EChartsCoreOption;
};

function EChartCanvas({ label, optionFactory }: EChartCanvasProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || (typeof navigator !== "undefined" && /jsdom/i.test(navigator.userAgent))) return;
    let chart: EChartsType | null = null;
    let observer: ResizeObserver | null = null;
    let cancelled = false;

    void import("./echartsRuntime").then((echarts) => {
      if (cancelled || !hostRef.current) return;
      const styles = getComputedStyle(hostRef.current);
      const palette: ChartPalette = {
        accent: styles.getPropertyValue("--accent").trim() || "#0b8f7f",
        text: styles.getPropertyValue("--text").trim() || "#17201e",
        muted: styles.getPropertyValue("--text-muted").trim() || "#66736f",
        border: styles.getPropertyValue("--border").trim() || "#d8e0dd",
        warning: styles.getPropertyValue("--warning").trim() || "#c86b4a"
      };
      chart = echarts.init(hostRef.current, undefined, { renderer: "canvas" });
      chart.setOption(optionFactory(palette));
      if (typeof ResizeObserver !== "undefined") {
        observer = new ResizeObserver(() => chart?.resize());
        observer.observe(hostRef.current);
      }
    }).catch(() => undefined);

    return () => {
      cancelled = true;
      observer?.disconnect();
      chart?.dispose();
    };
  }, [optionFactory]);

  return <div ref={hostRef} className="learning-echart" role="img" aria-label={label} />;
}

export function MasteryOverviewChart({ points }: { points: CourseMasteryPoint[] }) {
  const visiblePoints = useMemo(() => points.slice(0, 12), [points]);
  const optionFactory = useMemo(
    () => (palette: ChartPalette): EChartsCoreOption => ({
      animation: typeof window.matchMedia !== "function" || !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      grid: { left: 18, right: 22, top: 14, bottom: 16, containLabel: true },
      xAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLabel: { color: palette.muted, fontSize: 13 },
        splitLine: { lineStyle: { color: palette.border, opacity: 0.55 } }
      },
      yAxis: {
        type: "category",
        data: visiblePoints.map((point) => point.title),
        axisLabel: { color: palette.text, fontSize: 13, width: 130, overflow: "truncate" },
        axisTick: { show: false },
        axisLine: { show: false }
      },
      tooltip: {
        trigger: "axis",
        formatter: "{b}：{c} 分",
        textStyle: { fontSize: 13 }
      },
      series: [
        {
          type: "bar",
          data: visiblePoints.map((point) => ({
            value: point.score,
            itemStyle: { color: point.status === "weak" ? palette.warning : palette.accent }
          })),
          barMaxWidth: 18,
          itemStyle: { borderRadius: [0, 3, 3, 0] },
          label: { show: true, position: "right", color: palette.muted, fontSize: 13, formatter: "{c}" }
        }
      ]
    }),
    [visiblePoints]
  );

  return <EChartCanvas label="知识点掌握度柱状图" optionFactory={optionFactory} />;
}

export function PracticeTrendChart({ scores }: { scores: number[] }) {
  const optionFactory = useMemo(
    () => (palette: ChartPalette): EChartsCoreOption => ({
      animation: typeof window.matchMedia !== "function" || !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      grid: { left: 18, right: 18, top: 18, bottom: 20, containLabel: true },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: scores.map((_, index) => `第 ${index + 1} 次`),
        axisLabel: { color: palette.muted, fontSize: 13 },
        axisLine: { lineStyle: { color: palette.border } }
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLabel: { color: palette.muted, fontSize: 13 },
        splitLine: { lineStyle: { color: palette.border, opacity: 0.55 } }
      },
      tooltip: { trigger: "axis", textStyle: { fontSize: 13 } },
      series: [
        {
          type: "line",
          data: scores,
          smooth: 0.25,
          symbolSize: 7,
          lineStyle: { color: palette.accent, width: 3 },
          itemStyle: { color: palette.accent },
          areaStyle: { color: palette.accent, opacity: 0.08 }
        }
      ]
    }),
    [scores]
  );

  return <EChartCanvas label="最近练习得分趋势图" optionFactory={optionFactory} />;
}
