import React from 'react';
import { cn } from '../lib/utils';
import { Terminal, Activity, Battery, Hash } from 'lucide-react';
import { motion } from 'motion/react';

interface AgentCardProps {
  id: string;
  seq: string;
  energy: number;
  style: string;
  ttl: string;
  face: string;
}

export function AgentCard({ id, seq, energy, style, ttl, face }: AgentCardProps) {
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4 }}
      className="border border-surface-border bg-surface/50 p-4 rounded-md flex flex-col gap-3 hover:border-accent/50 transition-colors group"
    >
      <div className="flex justify-between items-start">
        <div className="flex items-center gap-2">
          <span className="font-mono text-accent font-bold text-lg">{face}</span>
          <span className="font-display font-bold tracking-tight text-lg">{id}</span>
        </div>
        <div className="px-2 py-1 bg-accent/10 text-accent text-xs font-mono rounded border border-accent/20">
          SEQ:{seq}
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-2 text-sm font-mono text-muted">
        <div className="flex items-center gap-1.5">
          <Activity size={14} className="text-ink/70" />
          <span>{style}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Terminal size={14} className="text-ink/70" />
          <span>TTL: {ttl}</span>
        </div>
      </div>

      <div className="mt-2 space-y-1.5">
        <div className="flex justify-between text-xs font-mono">
          <span className="flex items-center gap-1"><Battery size={12} /> ENERGY</span>
          <span className={cn(energy > 50 ? "text-accent" : "text-danger")}>{energy}%</span>
        </div>
        <div className="h-1.5 w-full bg-black rounded-full overflow-hidden">
          <div 
            className={cn("h-full rounded-full transition-all duration-1000", energy > 50 ? "bg-accent" : "bg-danger")} 
            style={{ width: `${energy}%` }}
          />
        </div>
      </div>
    </motion.div>
  );
}
