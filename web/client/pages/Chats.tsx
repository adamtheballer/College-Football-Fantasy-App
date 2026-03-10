import React, { useState } from "react";
import { MessageSquare, Users, TrendingUp, Search, Send, Sparkles, Hash, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const rooms = [
  { id: "general", name: "Public Discussion", description: "The main lobby for CFB Fantasy talk", users: 124, type: "public", icon: Hash },
  { id: "draft-strategy", name: "Draft Strategy", description: "Pro tips and snake logic analysis", users: 86, type: "pro", icon: TrendingUp },
  { id: "waiver-wire", name: "Waiver Alerts", description: "Get the jump on rising stars", users: 42, type: "alerts", icon: Sparkles },
  { id: "league-commish", name: "Commish Chat", description: "Rule changes and league setup help", users: 12, type: "support", icon: ShieldCheck },
];

const messagesMock = [
  { id: 1, user: "Mike R.", text: "Quinn Ewers is looking solid for 1.01", time: "10:42 AM", avatar: "MR" },
  { id: 2, user: "Sarah J.", text: "Don't sleep on Ashton Jeanty though, he's a monster", time: "10:45 AM", avatar: "SJ" },
  { id: 3, user: "Alex P.", text: "Anyone starting a new league today?", time: "10:48 AM", avatar: "AP" },
];

export default function Chats() {
  const [activeRoom, setActiveRoom] = useState(rooms[0]);
  const [message, setMessage] = useState("");

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-1000">
      <div className="flex flex-col gap-2">
        <h1 className="text-6xl font-black italic uppercase tracking-tighter text-foreground bg-gradient-to-br from-white via-white to-primary/40 bg-clip-text text-transparent">
          Chats
        </h1>
        <p className="text-muted-foreground font-medium uppercase tracking-[0.4em] text-[10px]">Community & Strategy Hub</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[350px_1fr] gap-8 h-[75vh]">
        {/* Sidebar Rooms */}
        <div className="space-y-4 flex flex-col">
          <div className="relative group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
            <Input 
              placeholder="Find a discussion..." 
              className="pl-12 bg-white/5 border-white/5 rounded-2xl h-14 text-xs font-bold tracking-widest uppercase"
            />
          </div>
          
          <div className="flex-1 space-y-2 overflow-y-auto no-scrollbar pr-2">
            {rooms.map((room) => (
              <button
                key={room.id}
                onClick={() => setActiveRoom(room)}
                className={cn(
                  "w-full p-6 rounded-[2rem] border text-left transition-all duration-500 group relative overflow-hidden",
                  activeRoom.id === room.id
                    ? "bg-primary/10 border-primary/40 shadow-[0_10px_30px_rgba(var(--primary),0.1)]"
                    : "bg-white/5 border-white/5 hover:border-white/10"
                )}
              >
                <div className="flex items-center gap-4 relative z-10">
                  <div className={cn(
                    "w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-500",
                    activeRoom.id === room.id ? "bg-primary text-primary-foreground" : "bg-white/5 text-muted-foreground"
                  )}>
                    <room.icon className="w-6 h-6" />
                  </div>
                  <div className="flex-1 space-y-1">
                    <h3 className="text-sm font-black italic uppercase text-foreground">{room.name}</h3>
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="text-[9px] font-black text-muted-foreground uppercase">{room.users} Online</span>
                    </div>
                  </div>
                </div>
                {activeRoom.id === room.id && (
                  <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 blur-2xl rounded-full -mr-12 -mt-12" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Chat Area */}
        <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3rem] overflow-hidden flex flex-col relative group">
          <div className="absolute top-0 right-0 w-96 h-96 bg-primary/5 blur-[120px] pointer-events-none" />
          
          <CardHeader className="p-8 border-b border-white/5 bg-white/5 relative z-10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-2xl bg-primary/20 flex items-center justify-center border border-primary/20">
                  <activeRoom.icon className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-lg font-black italic uppercase text-foreground">{activeRoom.name}</CardTitle>
                  <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-widest">{activeRoom.description}</p>
                </div>
              </div>
              <Users className="w-5 h-5 text-muted-foreground/40" />
            </div>
          </CardHeader>

          <CardContent className="flex-1 overflow-y-auto p-8 space-y-8 no-scrollbar relative z-10">
            {messagesMock.map((msg) => (
              <div key={msg.id} className="flex gap-4 group/msg">
                <div className="w-10 h-10 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-[10px] font-black text-primary group-hover/msg:border-primary/40 transition-colors">
                  {msg.avatar}
                </div>
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-black text-foreground uppercase italic">{msg.user}</span>
                    <span className="text-[9px] font-bold text-muted-foreground/30 uppercase">{msg.time}</span>
                  </div>
                  <div className="p-4 rounded-2xl bg-white/5 border border-white/5 max-w-2xl text-sm font-medium text-muted-foreground/80 leading-relaxed italic">
                    {msg.text}
                  </div>
                </div>
              </div>
            ))}
          </CardContent>

          <div className="p-8 border-t border-white/5 bg-white/5 relative z-10">
            <div className="relative group/input">
              <Input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={`Message #${activeRoom.id}...`}
                className="pr-16 bg-white/5 border-white/10 rounded-[1.5rem] h-16 focus:ring-primary/20 focus:border-primary/40 transition-all text-xs font-bold tracking-widest uppercase"
              />
              <Button className="absolute right-2 top-1/2 -translate-y-1/2 w-12 h-12 rounded-xl bg-primary text-primary-foreground hover:scale-105 transition-all">
                <Send className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
