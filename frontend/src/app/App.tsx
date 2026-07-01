import { BrowserRouter } from "react-router-dom";

import { AppProviders } from "./AppProviders";
import { AppRoutes } from "./routes";

export function App() {
  return (
    <AppProviders>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AppProviders>
  );
}
