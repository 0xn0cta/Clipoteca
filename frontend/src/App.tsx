import { useState } from 'react'
import {
  Archive,
  ArrowDownToLine,
  ArrowLeft,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Download,
  FolderOpen,
  HardDrive,
  Link2,
  ListVideo,
  Search,
  Settings2,
} from 'lucide-react'
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
        : 'Pega un enlace para preparar un lote.',
    )
  }

  function showFolderNotice() {
    setNotice('El selector de carpeta se conectará con la ventana de escritorio en la siguiente etapa.')
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Navegación principal">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            <Archive size={19} strokeWidth={1.8} />
          </div>
          <div className="brand-copy">
            <span className="brand-name">clipoteca</span>
            <span className="brand-subtitle">CENTRO DE DESCARGA</span>
          </div>
        </div>

        <div className="sidebar-rule" />

        <nav className="primary-nav" aria-label="Secciones">
          <span className="nav-caption">ESPACIO LOCAL</span>
          <button
            className={`nav-item ${view === 'prepare' ? 'is-active' : ''}`}
            type="button"
            onClick={() => setView('prepare')}
            aria-current={view === 'prepare' ? 'page' : undefined}
          >
            <Link2 size={17} aria-hidden="true" />
            <span>Preparar</span>
          </button>
          <button
            className={`nav-item ${view === 'queue' ? 'is-active' : ''}`}
            type="button"
            onClick={() => setView('queue')}
            aria-current={view === 'queue' ? 'page' : undefined}
          >
            <ListVideo size={17} aria-hidden="true" />
            <span>Cola</span>
            <span className="queue-count">0</span>
          </button>
        </nav>

        <div className="sidebar-bottom">
          <button
            className="nav-item settings-nav"
            type="button"
            onClick={() => setNotice('Los ajustes estarán disponibles en una siguiente etapa.')}
          >
            <Settings2 size={17} aria-hidden="true" />
            <span>Ajustes</span>
          </button>
          <div className="engine-state">
            <span className="engine-dot" aria-hidden="true" />
            <span>Motor pendiente de conexión</span>
          </div>
        </div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <div className="topbar-context">
            <span className="context-mark" aria-hidden="true" />
            <span>Biblioteca local</span>
            <span className="context-separator">/</span>
            <span>{view === 'prepare' ? 'Nuevo lote' : 'Cola de descargas'}</span>
          </div>
          <div className="topbar-state">
            <span className="prototype-tag">PROTOTIPO</span>
            <span className="topbar-caption">Windows · versión inicial</span>
          </div>
        </header>

        {view === 'prepare' ? (
          <div className="page-content">
            <section className="page-heading">
              <div>
                <h1>Prepara un lote</h1>
                <p>Pega un enlace, revisa el contenido y define cómo guardarlo.</p>
              </div>
            </section>

            <div className="prototype-note" role="note">
              <span className="note-icon">
                <CircleAlert size={16} aria-hidden="true" />
              </span>
              <p>
                <strong>Vista de demostración.</strong> La playlist es ficticia y no está asociada a
                la URL; no se analiza ni se descarga contenido.
              </p>
              <span className="note-state">MOTOR NO CONECTADO</span>
            </div>

            <div className="workbench">
              <div className="source-column">
                <section className="source-section" aria-labelledby="source-title">
                  <div className="section-heading">
                    <div>
                      <h2 id="source-title">Fuente</h2>
                      <p>Video o playlist de YouTube</p>
                    </div>
                  </div>
                  <div className="url-control">
                    <Link2 size={18} aria-hidden="true" />
                    <label className="visually-hidden" htmlFor="source-url">
                      URL del video o playlist
                    </label>
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
                      <Search size={15} aria-hidden="true" />
                    </button>
                  </div>
                  <div className="source-footnote">
                    <span>Los elementos se revisan antes de iniciar.</span>
                    <span>MP4 · MP3</span>
                  </div>
                </section>

                <section className="manifest-section" aria-labelledby="manifest-title">
                  <div className="manifest-heading">
                    <div className="manifest-title-group">
                      <div className="manifest-title-line">
                        <h2 id="manifest-title">Playlist de ejemplo</h2>
                        <span className="demo-label">DATOS DE MUESTRA</span>
                      </div>
                      <p>4 elementos · sin enlace asociado</p>
                    </div>
                    <span className="sample-unlinked">NO VINCULADA</span>
                  </div>

                  <div className="manifest-toolbar">
                    <label className="select-all-control">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        onChange={toggleAll}
                        aria-label={allSelected ? 'Desmarcar elementos disponibles' : 'Seleccionar elementos disponibles'}
                      />
                      <span className="custom-check" aria-hidden="true">
                        <Check size={12} />
                      </span>
                      <span>{selectedIds.length} seleccionados</span>
                    </label>
                    <button className="text-button" type="button" onClick={toggleAll}>
                      {allSelected ? 'Desmarcar disponibles' : 'Seleccionar disponibles'}
                    </button>
                  </div>

                  <div className="manifest-table-wrap">
                    <table className="manifest-table">
                      <thead>
                        <tr>
                          <th className="check-column" scope="col">
                            <span className="visually-hidden">Seleccionar</span>
                          </th>
                          <th className="number-column" scope="col">#</th>
                          <th scope="col">ELEMENTO</th>
                          <th className="duration-column" scope="col">DURACIÓN</th>
                          <th className="status-column" scope="col">ESTADO</th>
                        </tr>
                      </thead>
                      <tbody>
                        {demoItems.map((item) => {
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
                                    <Check size={12} />
                                  </span>
                                </label>
                              </td>
                              <td className="item-number">{String(item.id).padStart(2, '0')}</td>
                              <td className="title-cell">
                                <span className="item-title">{item.title}</span>
                                <span className="item-kind">VIDEO · MUESTRA</span>
                              </td>
                              <td className="item-duration">
                                <Clock3 size={13} aria-hidden="true" />
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

                  <div className="manifest-footer">
                    <span>
                      <span className="footer-mark" aria-hidden="true" />
                      Se conserva el orden original de la playlist
                    </span>
                    <span>1 elemento se omitirá</span>
                  </div>
                </section>
              </div>

              <aside className="output-rail" aria-labelledby="output-title">
                <div className="output-heading">
                  <div>
                    <h2 id="output-title">Salida</h2>
                    <p>Opciones del lote</p>
                  </div>
                  <span className="output-symbol" aria-hidden="true">
                    <HardDrive size={17} />
                  </span>
                </div>

                <fieldset className="format-field">
                  <legend>Formato</legend>
                  <div className="format-options">
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
                    Calidad
                    <span>Por defecto, la mejor disponible</span>
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
                  <div className="field-label">
                    <span>Destino</span>
                    <span>DESTINO DE MUESTRA</span>
                  </div>
                  <button className="destination-button" type="button" onClick={showFolderNotice}>
                    <FolderOpen size={17} aria-hidden="true" />
                    <span>
                      <strong>Descargas / Clipoteca</strong>
                      <small>No guardado · vista de demostración</small>
                    </span>
                    <ChevronDown size={15} aria-hidden="true" />
                  </button>
                  <p className="folder-note">En una descarga real, cada playlist tendrá su subcarpeta.</p>
                </div>

                <div className="output-rule" />

                <div className="batch-summary">
                  <div className="summary-line">
                    <span>Elementos seleccionados</span>
                    <strong>{selectedIds.length}</strong>
                  </div>
                  <div className="summary-line">
                    <span>Elementos omitidos</span>
                    <strong className="muted-value">1</strong>
                  </div>
                  <div className="summary-line total-line">
                    <span>Organización</span>
                    <strong>Por playlist</strong>
                  </div>
                </div>
              </aside>
            </div>

            <footer className="action-dock">
              <div className="action-status">
                <span className="action-icon">
                  <Download size={16} aria-hidden="true" />
                </span>
                <div>
                  <strong>{selectedIds.length} elementos listos para preparar</strong>
                  <span>El motor de descarga aún no está conectado.</span>
                </div>
              </div>
              <button className="start-button" type="button" disabled>
                Iniciar lote
                <span className="button-count">{selectedIds.length}</span>
                <ArrowDownToLine size={16} aria-hidden="true" />
              </button>
            </footer>

            {notice && (
              <div className="toast" role="status">
                <span>{notice}</span>
                <button type="button" aria-label="Cerrar aviso" onClick={() => setNotice('')}>
                  <span aria-hidden="true">×</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="queue-page">
            <div className="page-heading">
              <div>
                <h1>Cola de descargas</h1>
                <p>El progreso y los resultados de cada elemento aparecerán aquí.</p>
              </div>
            </div>
            <section className="queue-empty">
              <div className="empty-mark">
                <ListVideo size={24} strokeWidth={1.5} aria-hidden="true" />
              </div>
              <h2>La cola está vacía</h2>
              <p>Cuando el motor de descarga esté conectado, podrás seguir cada video y playlist desde aquí.</p>
              <button className="return-button" type="button" onClick={() => setView('prepare')}>
                Volver a preparar
                <ArrowLeft size={15} aria-hidden="true" />
              </button>
            </section>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
