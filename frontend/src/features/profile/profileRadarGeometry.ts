type RadarPoint = {
  x: number;
  y: number;
};

export function radarDimensionIndexFromPoint(
  point: RadarPoint,
  width: number,
  height: number,
  dimensionCount: number,
) {
  if (dimensionCount <= 0 || width <= 0 || height <= 0) return null;
  const dx = point.x - width / 2;
  const dy = point.y - height * 0.51;
  const distance = Math.hypot(dx, dy);
  const referenceSize = Math.min(width, height);
  if (distance < referenceSize * 0.05 || distance > referenceSize * 0.48) return null;
  const counterClockwiseFromTop = (Math.atan2(-dx, -dy) + Math.PI * 2) % (Math.PI * 2);
  return Math.round(counterClockwiseFromTop / (Math.PI * 2 / dimensionCount)) % dimensionCount;
}
