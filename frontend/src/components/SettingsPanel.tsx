import { themes, type ThemeKey } from '../themes'

interface SettingsPanelProps {
  theme: ThemeKey
  onThemeChange: (t: ThemeKey) => void
  workdir: string
  onWorkdirChange: (d: string) => void
  defaultModel: string
  onDefaultModelChange: (m: string) => void
  effort: string
  onEffortChange: (e: any) => void
}

const MODELS = [
  { key: 'claude', name: 'Claude (OAuth)' },
  { key: 'claude-opus', name: 'Claude Opus' },
  { key: 'claude-haiku', name: 'Claude Haiku' },
]

const EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max']

export function SettingsPanel({
  theme, onThemeChange, workdir, onWorkdirChange,
  defaultModel, onDefaultModelChange, effort, onEffortChange,
}: SettingsPanelProps) {
  return (
    <div className="settings-panel">
      <h2 className="panel-title">Personalizacion</h2>

      <div className="settings-section">
        <label className="settings-label">Tema</label>
        <div className="theme-grid">
          {(Object.keys(themes) as ThemeKey[]).map((key) => (
            <button
              key={key}
              className={`theme-card ${theme === key ? 'active' : ''}`}
              onClick={() => onThemeChange(key)}
              style={{
                background: themes[key].vars['--bg-secondary'],
                borderColor: theme === key ? themes[key].vars['--accent1'] : themes[key].vars['--border'],
              }}
            >
              <div className="theme-preview">
                <span style={{ color: themes[key].vars['--accent1'] }}>A</span>
                <span style={{ color: themes[key].vars['--accent2'] }}>B</span>
                <span style={{ color: themes[key].vars['--accent3'] }}>C</span>
                <span style={{ color: themes[key].vars['--accent4'] }}>D</span>
              </div>
              <div className="theme-name" style={{ color: themes[key].vars['--text-primary'] }}>
                {themes[key].name}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="settings-section">
        <label className="settings-label">Directorio de trabajo</label>
        <input
          className="settings-input"
          type="text"
          value={workdir}
          onChange={(e) => onWorkdirChange(e.target.value)}
          placeholder="~/mi-proyecto"
          spellCheck={false}
        />
      </div>

      <div className="settings-section">
        <label className="settings-label">Modelo por defecto para nuevas tabs</label>
        <select
          className="settings-select"
          value={defaultModel}
          onChange={(e) => onDefaultModelChange(e.target.value)}
        >
          {MODELS.map((m) => (
            <option key={m.key} value={m.key}>{m.name}</option>
          ))}
        </select>
      </div>

      <div className="settings-section">
        <label className="settings-label">Nivel de esfuerzo</label>
        <div className="effort-bar">
          {EFFORTS.map((e) => (
            <button
              key={e}
              className={`effort-level ${effort === e ? 'active' : ''}`}
              onClick={() => onEffortChange(e)}
            >
              {e}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
