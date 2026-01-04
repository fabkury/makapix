import * as SliderPrimitive from "@radix-ui/react-slider";

interface SliderProps {
  min: number;
  max: number;
  step?: number;
  value: number[];
  onValueChange: (values: number[]) => void;
  disabled?: boolean;
}

export function Slider({ min, max, step = 1, value, onValueChange, disabled }: SliderProps) {
  return (
    <>
      <SliderPrimitive.Root
        className="slider-root"
        min={min}
        max={max}
        step={step}
        value={value}
        onValueChange={onValueChange}
        disabled={disabled}
      >
        <SliderPrimitive.Track className="slider-track">
          <SliderPrimitive.Range className="slider-range" />
        </SliderPrimitive.Track>
        {value.map((_, index) => (
          <SliderPrimitive.Thumb key={index} className="slider-thumb" />
        ))}
      </SliderPrimitive.Root>

      <style jsx global>{`
        .slider-root {
          position: relative;
          display: flex;
          align-items: center;
          width: 100%;
          height: 20px;
          touch-action: none;
          user-select: none;
        }

        .slider-root[data-disabled] {
          opacity: 0.5;
          pointer-events: none;
        }

        .slider-track {
          position: relative;
          flex-grow: 1;
          height: 8px;
          background: var(--bg-tertiary);
          border-radius: 4px;
          overflow: hidden;
        }

        .slider-range {
          position: absolute;
          height: 100%;
          background: linear-gradient(90deg, var(--accent-cyan), var(--accent-purple));
          border-radius: 4px;
        }

        .slider-thumb {
          display: block;
          width: 18px;
          height: 18px;
          background: var(--text-primary);
          border-radius: 50%;
          border: 2px solid var(--accent-cyan);
          box-shadow: var(--glow-cyan);
          cursor: pointer;
          transition: transform 0.15s ease, box-shadow 0.15s ease;
        }

        .slider-thumb:hover {
          transform: scale(1.1);
          box-shadow: 0 0 16px rgba(0, 212, 255, 0.8);
        }

        .slider-thumb:focus {
          outline: none;
          box-shadow: var(--glow-cyan), 0 0 0 3px rgba(0, 212, 255, 0.3);
        }
      `}</style>
    </>
  );
}
