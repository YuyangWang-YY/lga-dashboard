import { createContext, useContext, useState, type ReactNode } from "react";

type SlideOutContextType = {
  isOpen: boolean;
  selectedFlightId: string | null;
  openSlideOut: (flightId: string) => void;
  closeSlideOut: () => void;
};

const SlideOutContext = createContext<SlideOutContextType | undefined>(undefined);

export function SlideOutProvider({ children }: { children: ReactNode }) {
  const [selectedFlightId, setSelectedFlightId] = useState<string | null>(null);

  const openSlideOut = (flightId: string) => {
    setSelectedFlightId(flightId);
  };

  const closeSlideOut = () => {
    setSelectedFlightId(null);
  };

  return (
    <SlideOutContext.Provider
      value={{
        isOpen: selectedFlightId !== null,
        selectedFlightId,
        openSlideOut,
        closeSlideOut,
      }}
    >
      {children}
    </SlideOutContext.Provider>
  );
}

export function useSlideOut() {
  const context = useContext(SlideOutContext);
  if (!context) {
    throw new Error("useSlideOut must be used within a SlideOutProvider");
  }
  return context;
}
