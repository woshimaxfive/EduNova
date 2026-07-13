import { describe, expect, it } from "vitest";

import { radarDimensionIndexFromPoint } from "../../features/profile/profileRadarGeometry";

describe("radarDimensionIndexFromPoint", () => {
  const width = 336;
  const height = 238;
  const centerX = width / 2;
  const centerY = height * 0.51;
  const radius = Math.min(width, height) * 0.32;

  it("maps all eight ECharts counter-clockwise axes to the matching dimension", () => {
    for (let index = 0; index < 8; index += 1) {
      const angle = Math.PI / 2 + index * Math.PI / 4;
      const point = {
        x: centerX + radius * Math.cos(angle),
        y: centerY - radius * Math.sin(angle)
      };
      expect(radarDimensionIndexFromPoint(point, width, height, 8)).toBe(index);
    }
  });

  it("ignores the empty center and points outside the radar label area", () => {
    expect(radarDimensionIndexFromPoint({ x: centerX, y: centerY }, width, height, 8)).toBeNull();
    expect(radarDimensionIndexFromPoint({ x: width, y: height }, width, height, 8)).toBeNull();
  });

  it("selects the nearest axis on either side of an angular boundary", () => {
    const pointAt = (angle: number) => ({
      x: centerX + radius * Math.cos(angle),
      y: centerY - radius * Math.sin(angle)
    });
    expect(radarDimensionIndexFromPoint(pointAt(Math.PI / 2 + Math.PI / 8 - 0.01), width, height, 8)).toBe(0);
    expect(radarDimensionIndexFromPoint(pointAt(Math.PI / 2 + Math.PI / 8 + 0.01), width, height, 8)).toBe(1);
  });
});
