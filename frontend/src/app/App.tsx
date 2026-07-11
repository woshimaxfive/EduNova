import { BrowserRouter } from "react-router-dom";

import { AppProviders } from "./AppProviders";
import { AppRoutes } from "./routes";
import { AiJobProvider } from "../features/aiJobs/AiJobProvider";
import { AiJobTray } from "../components/feedback/AiJobTray";

export function App() {
  return (
    <AppProviders>
      <BrowserRouter>
        <AiJobProvider>
          <AppRoutes />
          <AiJobTray />
        </AiJobProvider>
      </BrowserRouter>
    </AppProviders>
  );
}
