import { BarChart, LineChart, RadarChart } from "echarts/charts";
import { GridComponent, RadarComponent, TooltipComponent } from "echarts/components";
import { init, use as registerEChartsModules } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

registerEChartsModules([BarChart, LineChart, RadarChart, GridComponent, RadarComponent, TooltipComponent, CanvasRenderer]);

export { init };
