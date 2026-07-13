import { useEffect, useRef } from "react";
import type { EChartsCoreOption, EChartsType } from "echarts/core";

import type { ProfileDimensionKey, ProfileDimensionView } from "../../features/profile/profileViewModel";
import { radarDimensionIndexFromPoint } from "../../features/profile/profileRadarGeometry";

type ProfileConfidenceRadarProps = {
  dimensions: ProfileDimensionView[];
  selectedKey: ProfileDimensionKey | null;
  onSelect: (key: ProfileDimensionKey) => void;
};

type RadarPalette = {
  accent: string;
  accentSoft: string;
  text: string;
  muted: string;
  border: string;
  surface: string;
};

function reducedMotionEnabled() {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function buildOption(dimensions: ProfileDimensionView[], selectedKey: ProfileDimensionKey | null, palette: RadarPalette): EChartsCoreOption {
  const reduceMotion = reducedMotionEnabled();
  return {
    animation: !reduceMotion,
    animationDuration: reduceMotion ? 0 : 520,
    animationDurationUpdate: reduceMotion ? 0 : 420,
    tooltip: {
      trigger: "item",
      formatter: () => dimensions.map((item) => `${item.label}：${item.confidence}%`).join("<br/>")
    },
    radar: {
      center: ["50%", "51%"],
      radius: "64%",
      startAngle: 90,
      clockwise: false,
      splitNumber: 4,
      indicator: dimensions.map((item) => ({ name: item.shortLabel, max: 100 })),
      axisName: {
        color: palette.muted,
        fontSize: 13,
        formatter: (name: string) => {
          const selected = dimensions.find((item) => item.key === selectedKey)?.shortLabel;
          return name === selected ? `{selected|${name}}` : name;
        },
        rich: {
          selected: { color: palette.accent, fontWeight: 800 }
        }
      },
      axisLine: { lineStyle: { color: palette.border, opacity: 0.7 } },
      splitLine: { lineStyle: { color: palette.border, opacity: 0.75 } },
      splitArea: {
        areaStyle: {
          color: [palette.surface, palette.accentSoft],
          opacity: 0.42
        }
      }
    },
    series: [{
      name: "画像可信度",
      type: "radar",
      symbol: "circle",
      symbolSize: 6,
      data: [{ value: dimensions.map((item) => item.confidence), name: "画像可信度" }],
      lineStyle: { color: palette.accent, width: 2.5 },
      itemStyle: { color: palette.accent, borderColor: palette.surface, borderWidth: 2 },
      areaStyle: { color: palette.accent, opacity: 0.13 }
    }]
  };
}

export function ProfileConfidenceRadar({ dimensions, selectedKey, onSelect }: ProfileConfidenceRadarProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const dimensionsRef = useRef(dimensions);
  const selectedKeyRef = useRef(selectedKey);
  const onSelectRef = useRef(onSelect);
  const paletteRef = useRef<RadarPalette | null>(null);

  useEffect(() => {
    dimensionsRef.current = dimensions;
    selectedKeyRef.current = selectedKey;
    onSelectRef.current = onSelect;
    if (chartRef.current && paletteRef.current) {
      chartRef.current.setOption(buildOption(dimensions, selectedKey, paletteRef.current), { notMerge: false });
    }
  }, [dimensions, onSelect, selectedKey]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || (typeof navigator !== "undefined" && /jsdom/i.test(navigator.userAgent))) return;
    let observer: ResizeObserver | null = null;
    let cancelled = false;
    let clickHandler: ((event: unknown) => void) | null = null;

    void import("../visualization/echartsRuntime").then((echarts) => {
      if (cancelled || !hostRef.current) return;
      const styles = getComputedStyle(hostRef.current);
      const palette: RadarPalette = {
        accent: styles.getPropertyValue("--accent").trim() || "#0b8f7f",
        accentSoft: styles.getPropertyValue("--accent-soft").trim() || "#dcefeb",
        text: styles.getPropertyValue("--text").trim() || "#17201e",
        muted: styles.getPropertyValue("--text-muted").trim() || "#66736f",
        border: styles.getPropertyValue("--wide-workspace-divider").trim() || "rgba(29, 58, 50, 0.14)",
        surface: styles.getPropertyValue("--wide-workspace-control").trim() || "#fafcfb"
      };
      paletteRef.current = palette;
      const chart = echarts.init(hostRef.current, undefined, { renderer: "canvas" });
      chartRef.current = chart;
      chart.setOption(buildOption(dimensionsRef.current, selectedKeyRef.current, palette));
      clickHandler = (event: unknown) => {
        if (!hostRef.current || typeof event !== "object" || event === null) return;
        const point = event as { offsetX?: number; offsetY?: number };
        if (typeof point.offsetX !== "number" || typeof point.offsetY !== "number") return;
        const index = radarDimensionIndexFromPoint(
          { x: point.offsetX, y: point.offsetY },
          hostRef.current.clientWidth,
          hostRef.current.clientHeight,
          dimensionsRef.current.length,
        );
        if (index === null) return;
        const dimension = dimensionsRef.current[index];
        if (dimension) onSelectRef.current(dimension.key);
      };
      chart.getZr().on("click", clickHandler);
      if (typeof ResizeObserver !== "undefined") {
        observer = new ResizeObserver(() => chart.resize());
        observer.observe(hostRef.current);
      }
    }).catch(() => undefined);

    return () => {
      cancelled = true;
      observer?.disconnect();
      if (clickHandler) chartRef.current?.getZr().off("click", clickHandler);
      chartRef.current?.dispose();
      chartRef.current = null;
      paletteRef.current = null;
    };
  }, []);

  return <div ref={hostRef} className="profile-radar-canvas" role="img" aria-label="八维画像可信度雷达图" />;
}
