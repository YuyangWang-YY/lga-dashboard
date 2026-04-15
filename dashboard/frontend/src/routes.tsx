import { createBrowserRouter } from "react-router";
import DashboardLayout from "./components/DashboardLayout";
import OverviewTab from "./components/OverviewTab";
import FlightsTab from "./components/FlightsTab";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: DashboardLayout,
    children: [
      { index: true, Component: OverviewTab },
      { path: "terminal-a", Component: OverviewTab },
      { path: "terminal-b", Component: OverviewTab },
      { path: "terminal-c", Component: OverviewTab },
      { path: "arrivals", Component: FlightsTab },
      { path: "departures", Component: FlightsTab },
    ],
  },
]);