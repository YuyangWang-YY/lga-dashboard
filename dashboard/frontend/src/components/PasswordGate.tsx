import { useState, useEffect, type ReactNode } from "react";

const STORAGE_KEY = "lga_auth";
const APP_PASSWORD = import.meta.env.VITE_APP_PASSWORD as string | undefined;

interface Props {
  children: ReactNode;
}

export default function PasswordGate({ children }: Props) {
  const [unlocked, setUnlocked] = useState(false);
  const [input, setInput] = useState("");
  const [error, setError] = useState(false);
  const [shake, setShake] = useState(false);

  // If no password is configured (local dev), skip gate
  useEffect(() => {
    if (!APP_PASSWORD) {
      setUnlocked(true);
      return;
    }
    if (sessionStorage.getItem(STORAGE_KEY) === APP_PASSWORD) {
      setUnlocked(true);
    }
  }, []);

  if (unlocked) return <>{children}</>;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (input === APP_PASSWORD) {
      sessionStorage.setItem(STORAGE_KEY, input);
      setUnlocked(true);
    } else {
      setError(true);
      setShake(true);
      setInput("");
      setTimeout(() => setShake(false), 500);
    }
  }

  return (
    <div
      style={{ background: "#050505" }}
      className="min-h-screen flex items-center justify-center px-4"
    >
      <div className="w-full max-w-sm">
        {/* Logo / title */}
        <div className="text-center mb-8">
          <p className="text-xs uppercase tracking-widest text-neutral-500 mb-1">
            LaGuardia Airport
          </p>
          <h1 className="text-2xl font-semibold text-white">
            LGA Delay Predictions
          </h1>
          <p className="mt-2 text-sm text-neutral-400">
            Enter the access password to continue
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div
            className={`transition-transform ${shake ? "animate-[shake_0.4s_ease]" : ""}`}
          >
            <input
              type="password"
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                setError(false);
              }}
              placeholder="Password"
              autoFocus
              className={[
                "w-full px-4 py-3 rounded-lg text-sm text-white placeholder-neutral-500",
                "bg-neutral-900 border outline-none transition-colors",
                error
                  ? "border-red-500 focus:border-red-400"
                  : "border-neutral-700 focus:border-[#00B4E2]",
              ].join(" ")}
            />
            {error && (
              <p className="mt-1.5 text-xs text-red-400">Incorrect password.</p>
            )}
          </div>

          <button
            type="submit"
            className="w-full py-3 rounded-lg text-sm font-medium text-white bg-[#00B4E2] hover:bg-[#00a0cc] active:bg-[#008fb8] transition-colors"
          >
            Access Dashboard
          </button>
        </form>
      </div>

      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20%       { transform: translateX(-6px); }
          40%       { transform: translateX(6px); }
          60%       { transform: translateX(-4px); }
          80%       { transform: translateX(4px); }
        }
      `}</style>
    </div>
  );
}
