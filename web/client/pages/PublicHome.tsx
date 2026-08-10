import { ArrowRight, CalendarDays, ChartNoAxesCombined, CircleDollarSign, Trophy, Users, Waves, Zap } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

const features = [
  [Users, "Live Fantasy Drafts", "Build a roster from the college players you know best."],
  [ChartNoAxesCombined, "Weekly Matchups", "Follow your head-to-head matchup all week."],
  [Waves, "Player Projections", "Make lineup calls with clear player outlooks."],
  [CircleDollarSign, "Trades & Waivers", "Keep improving your team after draft night."],
  [Trophy, "League Competition", "Create a league, chase the standings, talk some trash."],
  [Zap, "Saturday Pick 6", "A weekly featured-player challenge when contests are live."],
] as const;

export default function PublicHome() {
  return <main className="min-h-screen overflow-x-hidden bg-[#071326] text-cfb-text-primary">
    <header className="sticky top-0 z-20 border-b border-white/10 bg-[#071326]/95 backdrop-blur">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6" aria-label="Public navigation">
        <Link to="/" className="font-display text-lg font-black uppercase tracking-tight text-white">College <span className="text-cfb-brand">Fantasy</span></Link>
        <div className="hidden items-center gap-6 text-sm font-bold text-cfb-text-secondary md:flex"><a href="#features">Features</a><a href="#how-it-works">How It Works</a></div>
        <div className="flex items-center gap-2"><Button asChild variant="ghost" className="px-3"><Link to="/login">Sign In</Link></Button><Button asChild className="px-3 sm:px-5"><Link to="/login?flow=beta">Join Beta</Link></Button></div>
      </nav>
    </header>
    <section className="relative mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-[1.05fr_.95fr] lg:items-center">
      <div className="absolute -left-40 top-0 h-80 w-80 rounded-full bg-cfb-brand/15 blur-3xl" aria-hidden="true" />
      <div className="relative"><p className="cfb-micro-label text-cfb-brand">Power 4 college football fantasy</p><h1 className="mt-4 max-w-3xl font-display text-5xl font-black leading-[.95] tracking-[-.05em] sm:text-6xl lg:text-7xl">College Football Fantasy Is Finally Here</h1><p className="mt-6 max-w-2xl text-lg font-medium leading-8 text-cfb-text-secondary">Draft real college football players, build your roster, compete every week, and prove you know college football better than everyone else.</p><div className="mt-8 flex flex-wrap gap-3"><Button asChild className="h-12 px-6"><Link to="/login?flow=beta">Join the Beta <ArrowRight className="ml-2 h-4 w-4" /></Link></Button><Button asChild variant="outline" className="h-12 px-6"><Link to="/login">Sign In</Link></Button></div></div>
      <div className="relative border border-cfb-border-strong bg-[#101f3a] p-5 shadow-[0_0_60px_rgba(34,211,238,.12)] sm:p-7"><div className="flex justify-between"><div><p className="cfb-micro-label text-cfb-brand">Week 1</p><h2 className="mt-2 text-3xl font-black">Matchup Snapshot</h2></div><span className="rounded-full border border-cfb-brand/40 px-3 py-2 text-xs font-black">PROJECTED</span></div><div className="mt-8 grid grid-cols-[1fr_auto_1fr] items-center"><div><p className="font-bold">Your Team</p><p className="mt-2 text-5xl font-black text-cfb-brand">128.4</p></div><span className="rounded-full border border-white/15 px-3 py-2 font-black">VS</span><div className="text-right"><p className="font-bold">Opponent</p><p className="mt-2 text-5xl font-black text-cfb-pink">121.6</p></div></div><div className="mt-7 grid grid-cols-3 gap-3 border-t border-white/10 pt-5 text-center text-sm font-bold text-cfb-text-secondary"><span>Draft smart</span><span>Set lineup</span><span>Win Saturday</span></div></div>
    </section>
    <section id="features" className="border-y border-white/10 bg-[#0a1930] py-16"><div className="mx-auto max-w-7xl px-4 sm:px-6"><p className="cfb-micro-label text-cfb-brand">Built for Saturdays</p><h2 className="mt-3 text-3xl font-black sm:text-4xl">Everything your league needs</h2><div className="mt-8 grid gap-px bg-white/10 sm:grid-cols-2 lg:grid-cols-3">{features.map(([Icon, title, copy]) => <article key={title} className="bg-[#0a1930] p-6 transition hover:bg-[#102443]"><Icon className="h-6 w-6 text-cfb-brand" /><h3 className="mt-5 text-xl font-black">{title}</h3><p className="mt-2 leading-6 text-cfb-text-secondary">{copy}</p></article>)}</div></div></section>
    <section id="how-it-works" className="mx-auto max-w-7xl px-4 py-16 sm:px-6"><p className="cfb-micro-label text-cfb-brand">How it works</p><h2 className="mt-3 text-3xl font-black">Your college football season starts here</h2><ol className="mt-8 grid gap-6 md:grid-cols-3">{[["01","Create or Join a League"],["02","Draft Your College Football Team"],["03","Compete Every Saturday"]].map(([number,title]) => <li key={number} className="border-l-2 border-cfb-brand pl-5"><p className="font-display text-3xl font-black text-cfb-brand">{number}</p><h3 className="mt-3 text-xl font-black">{title}</h3></li>)}</ol></section>
    <section className="border-t border-white/10 bg-[#102443] px-4 py-16 text-center sm:px-6"><CalendarDays className="mx-auto h-8 w-8 text-cfb-brand" /><h2 className="mt-4 text-3xl font-black">Ready for College Football Fantasy?</h2><div className="mt-7 flex justify-center gap-3"><Button asChild><Link to="/login?flow=beta">Join the Beta</Link></Button><Button asChild variant="outline"><Link to="/login">Sign In</Link></Button></div></section>
  </main>;
}
