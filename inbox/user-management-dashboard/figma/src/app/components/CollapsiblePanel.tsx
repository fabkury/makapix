import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface CollapsiblePanelProps {
  title: string;
  children: React.ReactNode;
}

export function CollapsiblePanel({ title, children }: CollapsiblePanelProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="bg-black shadow-lg shadow-cyan-500/10 border-t border-b border-white/20 lg:border-x lg:rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-white/5 transition-colors"
      >
        <h2 className="text-white">{title}</h2>
        {isOpen ? (
          <ChevronUp className="w-5 h-5 text-cyan-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-cyan-400" />
        )}
      </button>
      
      {isOpen && (
        <div className="px-4 py-4 border-t border-white/10">
          {children}
        </div>
      )}
    </div>
  );
}