import { useState } from 'react';
import { ReputationPanel } from '@/app/components/ReputationPanel';
import { BadgePanel } from '@/app/components/BadgePanel';
import { RecentCommentsPanel } from '@/app/components/RecentCommentsPanel';
import { ViolationsPanel } from '@/app/components/ViolationsPanel';
import { ModeratorActionsPanel } from '@/app/components/ModeratorActionsPanel';
import { ImageWithFallback } from '@/app/components/figma/ImageWithFallback';

export default function App() {
  const [userName] = useState('JohnDoe42');

  return (
    <div className="min-h-screen bg-black pb-8">
      <header className="bg-black shadow-lg shadow-cyan-500/20 border-b border-white/20 sticky top-0 z-10 px-4 py-4 lg:px-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-white">User Management</h1>
            <p className="text-gray-300 text-sm mt-1">Managing: {userName}</p>
          </div>
          <img
            src="https://images.unsplash.com/photo-1701463387028-3947648f1337?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxwcm9mZXNzaW9uYWwlMjBhdmF0YXIlMjBwb3J0cmFpdHxlbnwxfHx8fDE3NjgzODk0Nzl8MA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
            alt="User avatar"
            className="w-16 h-16 rounded-full object-cover"
          />
        </div>
      </header>

      <main className="lg:px-4 lg:py-4 lg:space-y-3 lg:max-w-4xl lg:mx-auto">
        <ReputationPanel />
        <BadgePanel />
        <RecentCommentsPanel />
        <ViolationsPanel />
        <ModeratorActionsPanel />
      </main>
    </div>
  );
}