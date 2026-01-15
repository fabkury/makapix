import { useState, useEffect } from 'react';
import { CollapsiblePanel } from '@/app/components/CollapsiblePanel';
import { ChevronUp, ChevronDown } from 'lucide-react';

export function ReputationPanel() {
  const [reputation, setReputation] = useState(10);
  const [reason, setReason] = useState('');
  
  // Apply gamma bias (gamma = 1.5) to convert slider position to reputation value
  const sliderToReputation = (sliderValue: number): number => {
    // Slider range: 0 to 100
    // Reputation range: -1000 to 1000
    const normalized = sliderValue / 100; // 0 to 1
    const gamma = 1.5;
    
    if (sliderValue === 50) return 0;
    
    if (sliderValue > 50) {
      // Positive side: 0 to 1000
      const posNormalized = (sliderValue - 50) / 50; // 0 to 1
      const biased = Math.pow(posNormalized, gamma);
      return Math.round(biased * 1000);
    } else {
      // Negative side: -1000 to 0
      const negNormalized = (50 - sliderValue) / 50; // 0 to 1
      const biased = Math.pow(negNormalized, gamma);
      return -Math.round(biased * 1000);
    }
  };
  
  // Convert reputation value back to slider position
  const reputationToSlider = (rep: number): number => {
    if (rep === 0) return 50;
    
    const gamma = 1.5;
    
    if (rep > 0) {
      const normalized = rep / 1000; // 0 to 1
      const unbiased = Math.pow(normalized, 1 / gamma);
      return 50 + unbiased * 50;
    } else {
      const normalized = Math.abs(rep) / 1000; // 0 to 1
      const unbiased = Math.pow(normalized, 1 / gamma);
      return 50 - unbiased * 50;
    }
  };
  
  const [sliderValue, setSliderValue] = useState(reputationToSlider(10));
  
  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    setSliderValue(value);
    setReputation(sliderToReputation(value));
  };
  
  const handleIncrement = () => {
    const newReputation = Math.min(1000, reputation + 1);
    setReputation(newReputation);
    setSliderValue(reputationToSlider(newReputation));
  };
  
  const handleDecrement = () => {
    const newReputation = Math.max(-1000, reputation - 1);
    setReputation(newReputation);
    setSliderValue(reputationToSlider(newReputation));
  };
  
  const handleGrant = () => {
    if (reason.length >= 8) {
      setReputation(10);
      setSliderValue(reputationToSlider(10));
      setReason('');
    }
  };
  
  const isDisabled = reason.length < 8;
  
  return (
    <CollapsiblePanel title="Reputation">
      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm text-gray-300">
              Reputation points: <span className={reputation >= 0 ? 'text-cyan-400' : 'text-pink-400'}>{reputation > 0 ? '+' : ''}{reputation}</span>
            </label>
            <div className="flex gap-3 pr-2">
              <button
                onClick={handleDecrement}
                disabled={reputation <= -1000}
                className="p-1 rounded hover:bg-white/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                title="Decrease by 1"
              >
                <ChevronDown className="w-5 h-5 text-pink-400" />
              </button>
              <button
                onClick={handleIncrement}
                disabled={reputation >= 1000}
                className="p-1 rounded hover:bg-white/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                title="Increase by 1"
              >
                <ChevronUp className="w-5 h-5 text-cyan-400" />
              </button>
            </div>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="0.1"
            value={sliderValue}
            onChange={handleSliderChange}
            className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-cyan-400"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>-1000</span>
            <span>0</span>
            <span>+1000</span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm text-gray-300 mb-2">
            Reason {reason.length < 8 && <span className="text-gray-500">(min 8 characters)</span>}
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Enter reason for reputation change..."
            className="w-full px-3 py-2 bg-white/5 border border-white/20 rounded-lg focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 outline-none resize-none text-white placeholder:text-gray-500"
            rows={3}
          />
          <div className="text-xs text-gray-400 mt-1">{reason.length} / 8 characters</div>
        </div>
        
        <button
          onClick={handleGrant}
          disabled={isDisabled}
          className={`w-full py-2.5 rounded-lg font-medium transition-colors ${
            isDisabled
              ? 'bg-white/5 text-gray-600 cursor-not-allowed'
              : reputation >= 0
              ? 'bg-cyan-500 text-black hover:bg-cyan-400 active:bg-cyan-600'
              : 'bg-pink-500 text-black hover:bg-pink-400 active:bg-pink-600'
          }`}
        >
          {reputation >= 0 ? 'Grant' : 'Remove'}
        </button>
      </div>
    </CollapsiblePanel>
  );
}