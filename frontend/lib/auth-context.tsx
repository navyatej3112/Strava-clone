"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { authApi, usersApi, setAccessToken, getAccessToken, type User } from "./api";

type AuthContextType = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name: string, bio?: string) => Promise<void>;
  logout: () => void | Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refreshUser = useCallback(async () => {
    try {
      const u = await usersApi.me();
      setUser(u);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    setAccessToken(null);
    authApi
      .refresh()
      .then(() => usersApi.me())
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      await authApi.login({ email, password });
      const u = await usersApi.me();
      setUser(u);
      router.push("/feed");
    },
    [router]
  );

  const signup = useCallback(
    async (email: string, password: string, name: string, bio?: string) => {
      await authApi.signup({ email, password, name, bio });
      await login(email, password);
    },
    [login]
  );

  const logout = useCallback(async () => {
    await authApi.logout();
    setUser(null);
    router.push("/");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
