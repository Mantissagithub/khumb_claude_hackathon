import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { supabasePublic } from "@/shared/supabase";
import { currentPhone, signOutPublic } from "@/public/publicApi";

const PublicAuthContext = createContext(null);

export function PublicAuthProvider({ children }) {
  const [phone, setPhone] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    supabasePublic.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        if (active) setLoading(false);
        return;
      }
      currentPhone()
        .then((p) => active && setPhone(p))
        .finally(() => active && setLoading(false));
    });
    const { data: sub } = supabasePublic.auth.onAuthStateChange((_e, session) => {
      if (!session) setPhone(null);
      else setPhone(session.user?.user_metadata?.phone ?? null);
    });
    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  async function signOut() {
    await signOutPublic();
    setPhone(null);
  }

  return (
    <PublicAuthContext.Provider value={{ phone, loading, setPhone, signOut }}>
      {children}
    </PublicAuthContext.Provider>
  );
}

export const usePublicAuth = () => useContext(PublicAuthContext);

// Gate: requires a verified phone session; else redirect to /track (login).
export function RequirePhone({ children }) {
  const { phone, loading } = usePublicAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="grid min-h-svh place-items-center text-sm text-muted-foreground">Loading…</div>
    );
  }
  if (!phone) return <Navigate to="/track" replace state={{ from: location }} />;
  return children;
}
