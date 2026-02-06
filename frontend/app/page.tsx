import Link from "next/link";
import { Activity, MapPin, Users } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-emerald-50 to-background">
      <header className="border-b bg-background/80 backdrop-blur">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <span className="text-xl font-bold text-primary">PaceTrail</span>
          <nav className="flex gap-4">
            <Link href="/login">
              <Button variant="ghost">Log in</Button>
            </Link>
            <Link href="/signup">
              <Button>Sign up</Button>
            </Link>
          </nav>
        </div>
      </header>
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-16 text-center">
        <h1 className="text-4xl md:text-6xl font-bold tracking-tight text-foreground max-w-3xl">
          Track your runs. Share your rides. Stay motivated.
        </h1>
        <p className="mt-6 text-lg text-muted-foreground max-w-xl">
          PaceTrail is your companion for every run, ride, and walk. Upload GPX, see your stats, and connect with friends.
        </p>
        <div className="mt-10 flex flex-wrap gap-4 justify-center">
          <Link href="/signup">
            <Button size="lg" className="text-base px-8">
              Get started free
            </Button>
          </Link>
          <Link href="/login">
            <Button size="lg" variant="outline" className="text-base px-8">
              I have an account
            </Button>
          </Link>
        </div>
        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl text-left">
          <div className="p-6 rounded-xl border bg-card">
            <Activity className="h-10 w-10 text-primary mb-3" />
            <h3 className="font-semibold text-lg">Activities</h3>
            <p className="text-muted-foreground text-sm mt-1">Upload GPX/TCX or paste a route. Get distance, pace, elevation, and calories.</p>
          </div>
          <div className="p-6 rounded-xl border bg-card">
            <MapPin className="h-10 w-10 text-primary mb-3" />
            <h3 className="font-semibold text-lg">Maps & splits</h3>
            <p className="text-muted-foreground text-sm mt-1">View your route on a map and see per-km splits and elevation profile.</p>
          </div>
          <div className="p-6 rounded-xl border bg-card">
            <Users className="h-10 w-10 text-primary mb-3" />
            <h3 className="font-semibold text-lg">Social feed</h3>
            <p className="text-muted-foreground text-sm mt-1">Follow friends, like and comment on activities, and keep the motivation high.</p>
          </div>
        </div>
      </main>
      <footer className="border-t py-6 text-center text-sm text-muted-foreground">
        PaceTrail — Built for runners and riders
      </footer>
    </div>
  );
}
