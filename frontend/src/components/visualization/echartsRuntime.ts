import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { init, use as registerEChartsModules } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

registerEChartsModules([BarChart, LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

export { init };
