"use client";

import React, { createContext, useCallback, useContext, useState } from "react";
import { ToastProvider as RadixToastProvider, ToastViewport, Toast } from "@/components/ui/toast";

type ToastVariant = "default" | "error" | "success";

type ToastContextType = {
  toast: (message: string, variant?: ToastVariant) => void;
};

const ToastContext = createContext<ToastContextType | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [variant, setVariant] = useState<ToastVariant>("default");

  const toast = useCallback((msg: string, v: ToastVariant = "default") => {
    setMessage(msg);
    setVariant(v);
    setOpen(true);
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      <RadixToastProvider>
        {children}
        <ToastViewport />
        <Toast
          variant={variant}
          open={open}
          onOpenChange={setOpen}
          duration={variant === "error" ? 5000 : 3000}
        >
          {message}
        </Toast>
      </RadixToastProvider>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) return { toast: () => {} };
  return ctx;
}
