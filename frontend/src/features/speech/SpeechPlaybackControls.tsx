import { Pause, Play, Stop } from "@phosphor-icons/react";

type SpeechPlaybackControlsProps = {
  active: boolean;
  paused: boolean;
  rate: number;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  onRateChange: (rate: number) => void;
};

export function SpeechPlaybackControls({ active, paused, rate, onPause, onResume, onStop, onRateChange }: SpeechPlaybackControlsProps) {
  if (!active) return null;

  return (
    <div className="speech-playback-controls" role="group" aria-label="回答朗读控制">
      <button type="button" onClick={paused ? onResume : onPause}>
        {paused ? <Play size={15} weight="fill" aria-hidden="true" /> : <Pause size={15} weight="fill" aria-hidden="true" />}
        <span>{paused ? "继续" : "暂停"}</span>
      </button>
      <button type="button" onClick={onStop}>
        <Stop size={15} weight="fill" aria-hidden="true" />
        <span>停止</span>
      </button>
      <label>
        <span>语速</span>
        <select value={rate} onChange={(event) => onRateChange(Number(event.target.value))}>
          <option value={0.8}>0.8×</option>
          <option value={1}>1.0×</option>
          <option value={1.2}>1.2×</option>
          <option value={1.5}>1.5×</option>
        </select>
      </label>
    </div>
  );
}
