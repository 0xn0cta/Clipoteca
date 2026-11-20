import { useState } from 'react'
import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  FolderOpen,
  Link2,
  ListVideo,
  Settings2,
  X,
} from 'lucide-react'
import logoMark from './assets/clipoteca-mark.svg'
import './App.css'

type View = 'prepare' | 'queue'
type Format = 'video' | 'audio' | 'both'

type DemoItem = {
  id: number
  title: string
  duration: string
  available: boolean
}

const demoItems: DemoItem[] = [
  { id: 1, title: 'Video de muestra · Introducción', duration: '08:24', available: true },
  { id: 2, title: 'Video de muestra · Capítulo 02', duration: '12:08', available: true },
  { id: 3, title: 'Video de muestra · Capítulo 03', duration: '05:41', available: false },
  { id: 4, title: 'Video de muestra · Cierre', duration: '16:30', available: true },
]

function App() {
  const [view, setView] = useState<View>('prepare')
  const [url, setUrl] = useState('')
  const [format, setFormat] = useState<Format>('video')
  const [quality, setQuality] = useState('auto')
  const [selectedIds, setSelectedIds] = useState<number[]>([1, 2, 4])
  const [notice, setNotice] = useState('')

  const selectableItems = demoItems.filter((item) => item.available)
  const allSelected = selectableItems.every((item) => selectedIds.includes(item.id))

  function toggleItem(id: number) {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id],
    )
  }

  function toggleAll() {
    setSelectedIds(allSelected ? [] : selectableItems.map((item) => item.id))
  }

  function analyzeUrl() {
    setNotice(
      url.trim()
        ? 'El análisis real se conectará con yt-dlp en la siguiente etapa.'
        : 'Pega un enlace para preparar una colección.',
    )
  }

  function showFolderNotice() {
    setNotice('El selector de carpeta se conectará con la ventana de escritorio en la siguiente etapa.')
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-inner">
          <button
            className="brand"
            type="button"
            onClick={() => setView('prepare')}
            aria-label="Clipoteca, preparar descarga"
          >
            <img className="brand-mark" src={logoMark} alt="" aria-hidden="true" />
            <span>clipoteca</span>
          </button>

          <nav className="top-nav" aria-label="Navegación principal">
            <button
              className={`top-nav-item ${view === 'prepare' ? 'is-active' : ''}`}
              type="button"
              onClick={() => setView('prepare')}
              aria-current={view === 'prepare' ? 'page' : undefined}
            >
              Preparar
            </button>
            <button
              className={`top-nav-item ${view === 'queue' ? 'is-active' : ''}`}
              type="button"
              onClick={() => setView('queue')}
              aria-current={view === 'queue' ? 'page' : undefined}
            >
              Descargas
              <span className="nav-count">0</span>
            </button>
          </nav>

          <div className="header-actions">
            <span className="engine-status">
              <span className="engine-dot" aria-hidden="true" />
              Motor pendiente
            </span>
            <button
              className="settings-button"
              type="button"
              aria-label="Ajustes"
              onClick={() => setNotice('Los ajustes estarán disponibles en una siguiente etapa.')}
            >
              <Settings2 size={18} strokeWidth={1.7} aria-hidden="true" />
            </button>
          </div>
        </div>
      </header>

      <main className="main-content">
        {view === 'prepare' ? (
          <div className="preparation-view">
            <section className="page-intro">
              <div>
                <h1>Prepara tu descarga.</h1>
                <p>Pega un enlace. Revisa la lista. Guarda solo lo que quieras.</p>
              </div>
              <span className="prototype-badge">Prototipo visual</span>
            </section>

            <section className="source-panel" aria-labelledby="source-title">
              <label className="source-label" id="source-title" htmlFor="source-url">
                Enlace de video o playlist
              </label>
              <div className="source-control">
                <Link2 size={19} strokeWidth={1.7} aria-hidden="true" />
                <input
                  id="source-url"
                  type="url"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="Pega aquí un enlace de YouTube"
                  autoComplete="url"
                />
                <button className="analyze-button" type="button" onClick={analyzeUrl}>
                  Analizar enlace
                  <ArrowRight size={16} strokeWidth={1.8} aria-hidden="true" />
                </button>
              </div>
              <p className="source-hint">Podrás revisar y elegir los elementos antes de iniciar.</p>
            </section>

            <div className="demo-disclosure" role="note">
              <CircleAlert size={16} strokeWidth={1.7} aria-hidden="true" />
              <p>
                <strong>Muestra interactiva.</strong> La playlist es ficticia y no está asociada a la URL.
                No se analiza ni se descarga contenido.
              </p>
            </div>

            <div className="collection-layout">
              <section className="playlist-section" aria-labelledby="playlist-title">
                <header className="playlist-heading">
                  <div>
                    <div className="playlist-title-line">
                      <h2 id="playlist-title">Playlist de ejemplo</h2>
                      <span className="sample-badge">Muestra</span>
                    </div>
                    <p>4 elementos <span aria-hidden="true">·</span> sin enlace asociado</p>
                  </div>
                  <span className="availability-summary">3 disponibles</span>
                </header>

                <div className="selection-toolbar">
                  <label className="select-all-control">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleAll}
                      aria-label={allSelected ? 'Desmarcar elementos disponibles' : 'Seleccionar elementos disponibles'}
                    />
                    <span className="custom-check" aria-hidden="true">
                      <Check size={12} strokeWidth={2.5} />
                    </span>
                    <span>{selectedIds.length} de 4 seleccionados</span>
                  </label>
                  <button className="text-button" type="button" onClick={toggleAll}>
                    {allSelected ? 'Desmarcar' : 'Seleccionar disponibles'}
                  </button>
                </div>

                <div className="media-list-wrap">
                  <table className="media-list">
                    <thead>
                      <tr>
                        <th className="check-column" scope="col">
                          <span className="visually-hidden">Seleccionar</span>
                        </th>
                        <th scope="col">Elemento</th>
                        <th className="duration-column" scope="col">Duración</th>
                        <th className="status-column" scope="col">Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {demoItems.map((item, index) => {
                        const checked = selectedIds.includes(item.id)
                        return (
                          <tr
                            className={`${checked ? 'is-selected' : ''} ${!item.available ? 'is-unavailable' : ''}`}
                            key={item.id}
                          >
                            <td className="check-cell">
                              <label className="row-check">
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  disabled={!item.available}
                                  onChange={() => toggleItem(item.id)}
                                  aria-label={`Seleccionar ${item.title}`}
                                />
                                <span className="custom-check" aria-hidden="true">
                                  <Check size={12} strokeWidth={2.5} />
                                </span>
                              </label>
                            </td>
                            <td className="title-cell">
                              <span className="item-title">{item.title}</span>
                              <span className="item-number">Elemento {String(index + 1).padStart(2, '0')}</span>
                            </td>
                            <td className="item-duration">
                              <Clock3 size={14} strokeWidth={1.7} aria-hidden="true" />
                              {item.duration}
                            </td>
                            <td>
                              <span className={`availability ${item.available ? 'is-available' : 'is-unavailable'}`}>
                                <span className="availability-dot" aria-hidden="true" />
                                {item.available ? 'Disponible' : 'No disponible'}
                              </span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="playlist-footnote">
                  <span>Se conserva el orden original</span>
                  <span>1 elemento no disponible</span>
                </div>
              </section>

              <aside className="preferences-panel" aria-labelledby="preferences-title">
                <div className="preferences-heading">
                  <h2 id="preferences-title">Preferencias</h2>
                  <p>Para esta colección</p>
                </div>

                <fieldset className="format-field">
                  <legend>Formato</legend>
                  <div className="format-options" role="group" aria-label="Formato de salida">
                    {([
                      ['video', 'Video', 'MP4'],
                      ['audio', 'Audio', 'MP3'],
                      ['both', 'Ambos', ''],
                    ] as const).map(([value, label, detail]) => (
                      <button
                        className={`format-option ${format === value ? 'is-active' : ''}`}
                        type="button"
                        aria-pressed={format === value}
                        key={value}
                        onClick={() => setFormat(value)}
                      >
                        <span>{label}</span>
                        {detail && <small>{detail}</small>}
                      </button>
                    ))}
                  </div>
                </fieldset>

                <div className="quality-field">
                  <label htmlFor="quality-select">
                    <span>Calidad</span>
                    <span>Mejor disponible por defecto</span>
                  </label>
                  <div className={`select-shell ${format === 'audio' ? 'is-disabled' : ''}`}>
                    <select
                      id="quality-select"
                      value={quality}
                      onChange={(event) => setQuality(event.target.value)}
                      disabled={format === 'audio'}
                    >
                      <option value="auto">Automática · mejor disponible</option>
                      <option value="1080">Hasta 1080p</option>
                      <option value="720">Hasta 720p</option>
                      <option value="480">Hasta 480p</option>
                    </select>
                    <ChevronDown size={15} aria-hidden="true" />
                  </div>
                </div>

                <div className="destination-field">
                  <div className="destination-label">Carpeta de destino</div>
                  <button
                    className="destination-button"
                    type="button"
                    onClick={showFolderNotice}
                  >
                    <FolderOpen size={17} strokeWidth={1.7} aria-hidden="true" />
                    <span>
                      <strong>Descargas / Clipoteca</strong>
                      <small>Ejemplo · aún no guardado</small>
                    </span>
                    <ChevronDown size={15} aria-hidden="true" />
                  </button>
                </div>

                <div className="collection-rule" />

                <div className="collection-summary">
                  <div>
                    <span>En la playlist</span>
                    <strong>4 elementos</strong>
                  </div>
                  <div>
                    <span>Guardarás</span>
                    <strong>{selectedIds.length} elementos</strong>
                  </div>
                </div>

                <div className="collection-note">
                  <BookOpen size={16} strokeWidth={1.7} aria-hidden="true" />
                  <span>Cada playlist tendrá su propia carpeta.</span>
                </div>
              </aside>
            </div>

            <footer className="download-bar">
              <div className="download-summary">
                <span className="download-icon">
                  <ArrowDownToLine size={17} strokeWidth={1.8} aria-hidden="true" />
                </span>
                <div>
                  <strong>{selectedIds.length} elementos seleccionados</strong>
                  <span>El motor de descarga todavía no está conectado.</span>
                </div>
              </div>
              <button className="download-button" type="button" disabled>
                Preparar descarga
                <span>{selectedIds.length}</span>
              </button>
            </footer>

            {notice && (
              <div className="toast" role="status">
                <span>{notice}</span>
                <button type="button" aria-label="Cerrar aviso" onClick={() => setNotice('')}>
                  <X size={16} aria-hidden="true" />
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="queue-view">
            <div className="queue-heading">
              <h1>Descargas</h1>
              <p>El progreso de cada video y playlist aparecerá aquí.</p>
            </div>
            <section className="queue-empty">
              <span className="empty-icon">
                <ListVideo size={24} strokeWidth={1.5} aria-hidden="true" />
              </span>
              <h2>Aún no hay descargas</h2>
              <p>Cuando conectemos el motor, podrás seguir tus colecciones desde aquí.</p>
              <button className="return-button" type="button" onClick={() => setView('prepare')}>
                Preparar una descarga
                <ArrowRight size={15} aria-hidden="true" />
              </button>
            </section>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
