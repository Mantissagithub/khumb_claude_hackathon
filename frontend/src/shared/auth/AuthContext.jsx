import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { login as apiLogin, logout as apiLogout, me } from "@/shared/authApi";
import { supabase } from "@/shared/supabase";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // { username, role, name }
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    // Hydrate from any persisted Supabase session, then react to changes.
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        if (active) setLoading(false);
        return;
      }
      me()
        .then((u) => active && setUser(u))
        .catch(() => apiLogout())
        .finally(() => active && setLoading(false));
    });

    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) setUser(null);
    });
    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  async function signIn(username, password) {
    const data = await apiLogin(username, password);
    setUser({ username, role: data.role, name: data.name });
    return data;
  }

  async function signOut() {
    await apiLogout();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

// Gate: requires a logged-in staff user. Optionally restrict by role.
// `loginPath` lets each app (operator → /ops/login, admin → /admin/login) point
// at its own sign-in screen.
export function RequireAuth({ children, role, loginPath = "/ops/login" }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="grid min-h-svh place-items-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to={loginPath} replace state={{ from: location }} />;
  if (role && user.role !== role) return <Navigate to="/ops" replace />;
  return children;
}
