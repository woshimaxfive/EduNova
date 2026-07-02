import { Copy, Monitor, SlidersHorizontal } from "@phosphor-icons/react";
import { type CSSProperties, useMemo, useState } from "react";

import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";

type RecentLearningPosition = "below" | "side";
type NavigationDensity = "quiet" | "compact";

type DesignLabPreset = {
  historyWidth: number;
  composerWidth: number;
  titleSize: number;
  backgroundStrength: number;
  recentLearningPosition: RecentLearningPosition;
  navigationDensity: NavigationDensity;
};

const defaultPreset: DesignLabPreset = {
  historyWidth: 240,
  composerWidth: 800,
  titleSize: 64,
  backgroundStrength: 36,
  recentLearningPosition: "below",
  navigationDensity: "quiet"
};

function formatPreset(preset: DesignLabPreset) {
  return JSON.stringify(preset, null, 2);
}

export function DesignLabPage() {
  const [preset, setPreset] = useState<DesignLabPreset>(defaultPreset);
  const [status, setStatus] = useState("等待调参");
  const exportedPreset = useMemo(() => formatPreset(preset), [preset]);
  const previewStyle = {
    "--design-history-width": `${preset.historyWidth}px`,
    "--design-composer-width": `${preset.composerWidth}px`,
    "--design-title-size": `${preset.titleSize}px`,
    "--design-background-strength": `${preset.backgroundStrength / 100}`
  } as CSSProperties;

  function updatePreset<Key extends keyof DesignLabPreset>(key: Key, value: DesignLabPreset[Key]) {
    setPreset((current) => ({ ...current, [key]: value }));
  }

  async function copyPreset() {
    try {
      await navigator.clipboard?.writeText(exportedPreset);
    } catch {
      // Clipboard permission is optional in the development lab; the textarea remains the source of truth.
    }

    setStatus("配置已生成，可交给 Codex 固化到正式页面。");
  }

  return (
    <LearningSpaceShell>
      <section className="design-lab-page">
        <header className="design-lab-hero">
          <p className="section-kicker">开发调试用</p>
          <h1>Design Lab v0</h1>
          <p>先把主页骨架调到顺眼，再把导出的 JSON 交给 Codex 固化到正式页面。这里不连接后端，也不写入正式学习数据。</p>
        </header>

        <div className="design-lab-workbench">
          <section className="design-lab-controls" role="region" aria-label="主页调参控制台">
            <div className="design-panel-heading">
              <SlidersHorizontal size={20} weight="duotone" aria-hidden="true" />
              <div>
                <p className="section-kicker">Controls</p>
                <h2>手动调主页骨架</h2>
              </div>
            </div>

            <DesignSlider label="历史栏宽度" value={preset.historyWidth} min={180} max={360} step={10} unit="px" onChange={(value) => updatePreset("historyWidth", value)} />
            <DesignSlider label="输入框宽度" value={preset.composerWidth} min={620} max={980} step={20} unit="px" onChange={(value) => updatePreset("composerWidth", value)} />
            <DesignSlider label="标题大小" value={preset.titleSize} min={44} max={82} step={2} unit="px" onChange={(value) => updatePreset("titleSize", value)} />
            <DesignSlider label="背景强度" value={preset.backgroundStrength} min={0} max={90} step={5} unit="%" onChange={(value) => updatePreset("backgroundStrength", value)} />

            <fieldset className="design-option-group">
              <legend>最近学习位置</legend>
              <button
                className={preset.recentLearningPosition === "below" ? "active" : ""}
                type="button"
                aria-pressed={preset.recentLearningPosition === "below"}
                onClick={() => updatePreset("recentLearningPosition", "below")}
              >
                最近学习放到下方
              </button>
              <button
                className={preset.recentLearningPosition === "side" ? "active" : ""}
                type="button"
                aria-pressed={preset.recentLearningPosition === "side"}
                onClick={() => updatePreset("recentLearningPosition", "side")}
              >
                最近学习放到右侧
              </button>
            </fieldset>

            <fieldset className="design-option-group">
              <legend>导航密度</legend>
              <button
                className={preset.navigationDensity === "quiet" ? "active" : ""}
                type="button"
                aria-pressed={preset.navigationDensity === "quiet"}
                onClick={() => updatePreset("navigationDensity", "quiet")}
              >
                舒展
              </button>
              <button
                className={preset.navigationDensity === "compact" ? "active" : ""}
                type="button"
                aria-pressed={preset.navigationDensity === "compact"}
                onClick={() => updatePreset("navigationDensity", "compact")}
              >
                紧凑
              </button>
            </fieldset>
          </section>

          <section className="design-lab-preview" role="region" aria-label="主页预览画布">
            <div className="design-panel-heading">
              <Monitor size={20} weight="duotone" aria-hidden="true" />
              <div>
                <p className="section-kicker">Preview</p>
                <h2>主页骨架实时预览</h2>
              </div>
            </div>

            <div
              className={[
                "design-preview-shell",
                `recent-${preset.recentLearningPosition}`,
                `nav-${preset.navigationDensity}`
              ].join(" ")}
              style={previewStyle}
            >
              <aside className="design-preview-history">
                <strong>历史栏 {preset.historyWidth}px</strong>
                <span>神经网络反向传播怎么复习</span>
                <span>把期末题按知识点分组</span>
              </aside>

              <main className="design-preview-main">
                <nav className="design-preview-nav" aria-label="预览导航">
                  <span>学习空间</span>
                  <span>资料库</span>
                  <span>Studio</span>
                </nav>
                <section className="design-preview-chat">
                  <p className="home-kicker">EduNova</p>
                  <h3>嗨，同学，准备好一起学习了吗？</h3>
                  <div className="design-preview-composer">
                    <span>问我怎么复习，或者说：用这些资料生成一门期末复习课</span>
                  </div>
                </section>
                <section className="design-preview-recent" aria-label="预览最近学习">
                  <strong>最近学习</strong>
                  <span>人工智能导论 · 47%</span>
                  <span>期末冲刺课 · 草稿</span>
                </section>
              </main>
            </div>
          </section>

          <section className="design-lab-output" aria-label="配置输出">
            <div className="design-panel-heading">
              <Copy size={20} weight="duotone" aria-hidden="true" />
              <div>
                <p className="section-kicker">Preset</p>
                <h2>交给 Codex 的配置</h2>
              </div>
            </div>
            <textarea aria-label="Design Lab 配置 JSON" readOnly value={exportedPreset} />
            <div className="design-output-actions">
              <button className="primary-action" type="button" onClick={copyPreset}>
                复制配置
              </button>
              <p role="status">{status}</p>
            </div>
          </section>
        </div>
      </section>
    </LearningSpaceShell>
  );
}

type DesignSliderProps = {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  onChange: (value: number) => void;
};

function DesignSlider({ label, value, min, max, step, unit, onChange }: DesignSliderProps) {
  return (
    <label className="design-slider">
      <span>
        {label}
        <strong>
          {value}
          {unit}
        </strong>
      </span>
      <input type="range" aria-label={label} min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}
