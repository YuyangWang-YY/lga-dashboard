import { RouterProvider } from "react-router";
import { router } from "./routes";
import { SimulationProvider } from "./context/SimulationContext";
import { ConfigProvider } from "./context/ConfigContext";
import PasswordGate from "./components/PasswordGate";

export default function App() {
  return (
    <PasswordGate>
      <SimulationProvider>
        <ConfigProvider>
          <RouterProvider router={router} />
        </ConfigProvider>
      </SimulationProvider>
    </PasswordGate>
  );
}
