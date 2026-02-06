"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, User, LogOut, Home, Bell, Search, Trophy, Route } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { usersApi, notificationsApi, type UserPublic } from "@/lib/api";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState<UserPublic[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const searchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) return;
    notificationsApi.unreadCount().then((r) => setUnreadCount(r.count)).catch(() => {});
  }, [user, pathname]);

  useEffect(() => {
    if (!searchQ.trim()) {
      setSearchResults([]);
      return;
    }
    const t = setTimeout(() => {
      usersApi.search(searchQ, 8).then(setSearchResults).catch(() => setSearchResults([]));
    }, 200);
    return () => clearTimeout(t);
  }, [searchQ]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setSearchOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading…</div>
      </div>
    );
  }
  if (!user) {
    router.replace("/login");
    return null;
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="container mx-auto flex h-14 items-center gap-4 px-4">
          <Link href="/feed" className="text-lg font-bold text-primary shrink-0">
            PaceTrail
          </Link>
          <div className="flex-1 max-w-md relative" ref={searchRef}>
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search users…"
              className="pl-9"
              value={searchQ}
              onChange={(e) => {
                setSearchQ(e.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => searchQ && setSearchOpen(true)}
            />
            {searchOpen && searchResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 rounded-md border bg-card shadow-lg py-1 z-20">
                {searchResults.map((u) => (
                  <Link
                    key={u.id}
                    href={`/profile/${u.id}`}
                    className="block px-3 py-2 hover:bg-muted text-sm"
                    onClick={() => setSearchOpen(false)}
                  >
                    {u.name}
                  </Link>
                ))}
              </div>
            )}
          </div>
          <nav className="flex items-center gap-1 shrink-0">
            <Link href="/activities/new">
              <Button variant="default" size="sm">
                <Plus className="h-4 w-4 mr-1" />
                Create
              </Button>
            </Link>
            <Link href="/notifications" className="relative">
              <Button variant={pathname === "/notifications" ? "secondary" : "ghost"} size="sm">
                <Bell className="h-4 w-4" />
                {unreadCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 h-4 w-4 rounded-full bg-primary text-primary-foreground text-xs flex items-center justify-center">
                    {unreadCount > 99 ? "99+" : unreadCount}
                  </span>
                )}
              </Button>
            </Link>
            <Link href="/feed">
              <Button variant={pathname === "/feed" ? "secondary" : "ghost"} size="sm">
                <Home className="h-4 w-4 mr-1" />
                Feed
              </Button>
            </Link>
            <Link href="/leaderboard">
              <Button variant={pathname === "/leaderboard" ? "secondary" : "ghost"} size="sm">
                <Trophy className="h-4 w-4 mr-1" />
                Leaderboard
              </Button>
            </Link>
            <Link href="/segments">
              <Button variant={pathname?.startsWith("/segments") ? "secondary" : "ghost"} size="sm">
                <Route className="h-4 w-4 mr-1" />
                Segments
              </Button>
            </Link>
            <Link href="/profile">
              <Button variant={pathname === "/profile" ? "secondary" : "ghost"} size="sm">
                <User className="h-4 w-4 mr-1" />
                Profile
              </Button>
            </Link>
            <Button variant="ghost" size="sm" onClick={() => void logout()}>
              <LogOut className="h-4 w-4" />
            </Button>
          </nav>
        </div>
      </header>
      <main className="flex-1 container mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
