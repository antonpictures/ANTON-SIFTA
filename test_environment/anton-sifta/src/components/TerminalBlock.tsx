import React from 'react';
import { cn } from '../lib/utils';
import { motion } from 'motion/react';

interface TerminalBlockProps {
  title?: string;
  code: string;
  language?: string;
  className?: string;
}

export function TerminalBlock({ title, code, language = 'text', className }: TerminalBlockProps) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5 }}
      className={cn("rounded-md overflow-hidden border border-surface-border bg-surface font-mono text-sm", className)} 
    >
      {title && (
        <div className="flex items-center px-4 py-2 border-b border-surface-border bg-black/50 text-muted text-xs uppercase tracking-wider">
          <div className="flex space-x-2 mr-4">
            <div className="w-2.5 h-2.5 rounded-full bg-danger"></div>
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500"></div>
            <div className="w-2.5 h-2.5 rounded-full bg-accent"></div>
          </div>
          {title}
        </div>
      )}
      <div className="p-4 overflow-x-auto">
        <pre className="text-ink/90 whitespace-pre-wrap break-all">
          <code>{code}</code>
        </pre>
      </div>
    </motion.div>
  );
}
