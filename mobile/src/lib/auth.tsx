import * as React from "react";

import { apiRequest, clearTokens, getAccessToken, setTokens } from "./api";
import { registerForPush, unregisterForPush } from "./push";

export interface AppUser {
  id: number;
  email: string;
  full_name: string;
  role: string; // student | teacher | parent | institution_admin | super_admin
  institution_id: number | null;
  must_change_password?: boolean;
}

interface LoginResponse {
  user: AppUser | null;
  must_change_password: boolean;
  two_factor_required: boolean;
  challenge: string | null;
  access_token: string | null;
  refresh_token: string | null;
}

interface MeResponse {
  user: AppUser;
}

export type SignInResult =
  | { kind: "ok"; mustChangePassword: boolean; user: AppUser }
  | { kind: "2fa"; challenge: string };

type AuthStatus = "loading" | "authed" | "guest";

interface AuthContextValue {
  status: AuthStatus;
  user: AppUser | null;
  signIn: (email: string, password: string) => Promise<SignInResult>;
  verifyTwoFactor: (challenge: string, code: string) => Promise<SignInResult>;
  signOut: () => Promise<void>;
  reload: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

async function finishLogin(res: LoginResponse): Promise<SignInResult> {
  if (res.two_factor_required && res.challenge) {
    return { kind: "2fa", challenge: res.challenge };
  }
  if (res.access_token) {
    await setTokens(res.access_token, res.refresh_token);
  }
  return {
    kind: "ok",
    mustChangePassword: res.must_change_password,
    user: res.user as AppUser,
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = React.useState<AuthStatus>("loading");
  const [user, setUser] = React.useState<AppUser | null>(null);

  const bootstrap = React.useCallback(async () => {
    const token = await getAccessToken();
    if (!token) {
      setUser(null);
      setStatus("guest");
      return;
    }
    try {
      const me = await apiRequest<MeResponse>("/api/v2/me");
      setUser(me.user);
      setStatus("authed");
    } catch {
      // token geçersiz/expired + refresh de başarısız → misafir
      await clearTokens();
      setUser(null);
      setStatus("guest");
    }
  }, []);

  React.useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  // Authed olunca push token'ını kaydet (best-effort — cihazda/build'de çalışır).
  React.useEffect(() => {
    if (status === "authed") void registerForPush();
  }, [status]);

  const signIn = React.useCallback(async (email: string, password: string): Promise<SignInResult> => {
    const res = await apiRequest<LoginResponse>("/api/v2/auth/login", {
      method: "POST",
      auth: false,
      body: { email, password, mobile: true },
    });
    const result = await finishLogin(res);
    if (result.kind === "ok") {
      setUser(result.user);
      setStatus("authed");
    }
    return result;
  }, []);

  const verifyTwoFactor = React.useCallback(
    async (challenge: string, code: string): Promise<SignInResult> => {
      const res = await apiRequest<LoginResponse>("/api/v2/auth/2fa/verify", {
        method: "POST",
        auth: false,
        body: { challenge, code, mobile: true },
      });
      const result = await finishLogin(res);
      if (result.kind === "ok") {
        setUser(result.user);
        setStatus("authed");
      }
      return result;
    },
    [],
  );

  const signOut = React.useCallback(async () => {
    await unregisterForPush(); // token hâlâ geçerliyken sil
    try {
      await apiRequest("/api/v2/auth/logout", { method: "POST", auth: true });
    } catch {
      // sunucu hatası önemli değil — yerel token'ı temizle
    }
    await clearTokens();
    setUser(null);
    setStatus("guest");
  }, []);

  const value = React.useMemo<AuthContextValue>(
    () => ({ status, user, signIn, verifyTwoFactor, signOut, reload: bootstrap }),
    [status, user, signIn, verifyTwoFactor, signOut, bootstrap],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
