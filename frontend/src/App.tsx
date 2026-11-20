import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Eye,
  ExternalLink,
  FolderOpen,
  Link2,
  ListVideo,
  Pause,
  Play,
  RotateCcw,
  Settings2,
  Trash2,
  X,
} from 'lucide-react'
import logoMark from './assets/clipoteca-mark.svg'
import './App.css'

type View = 'prepare' | 'queue' | 'history'
type Format = 'video' | 'audio' | 'both'
type ItemStatus = 'queued' | 'downloading' | 'paused' | 'failed' | 'completed' | 'cancelled'

type MediaItem = {
  id: string
  source_id: string
  source_url: string | null
  title: string
  duration: number | null
  available: boolean
  index: number
  thumbnail: string | null
}

type Analysis = {
  analysis_id: string
  title: string
  source_url: string
  is_playlist: boolean
  extractor: string
  items: MediaItem[]
}

type QueueItem = {
  id: string
  batch_id: string
  batch_title: string
  title: string
  duration: number | null
  status: ItemStatus
  progress: number
  speed: number | null
  eta: number | null
  error: string | null
  output_path: string | null
  output_paths: string[]
}

type PreviewResult = {
  title: string
  item_title: string
  thumbnail: string | null
  duration: number | null
  kind: 'audio' | 'video'
  url: string | null
  mime_type: string
  playable: boolean
}

type Preferences = {
  destination: string
  concurrency_mode?: 'auto' | 'manual' | null
  manual_concurrency?: number | null
  auto_concurrency_cap?: number | null
}

type QueueState = {
  queue: QueueItem[]
  history: QueueItem[]
  counts: { active: number; completed: number }
  preferences: Preferences
}

type ApiResult<T = Record<string, unknown>> = { ok: boolean; error?: string } & T

type DesktopApi = {
  get_app_status: () => Promise<{ desktop: boolean; download_engine_ready: boolean; ffmpeg_ready: boolean; message: string; tray_available: boolean }>
  analyze_url: (url: string) => Promise<ApiResult<Analysis>>
  get_preview: (analysisId: string, itemId: string, outputFormat: Format, quality: string) => Promise<ApiResult<Omit<PreviewResult, 'item_title'>>>
  enqueue_batch: (
    analysisId: string,
    selectedIds: string[],
    outputFormat: Format,
    quality: string,
  ) => Promise<ApiResult<{ queued: number; batch_id: string }>>
  get_queue_state: () => Promise<QueueState>
  get_preferences: () => Promise<Preferences>
  set_preferences: (values: Partial<Preferences>) => Promise<ApiResult<{ preferences: Preferences }>>
  choose_destination: () => Promise<ApiResult<{ destination: string; cancelled?: boolean }>>
  pause_all: () => Promise<unknown>
  resume_all: () => Promise<unknown>
  cancel_item: (itemId: string) => Promise<unknown>
  cancel_all: () => Promise<unknown>
  retry_item: (itemId: string) => Promise<ApiResult>
  clear_history: () => Promise<{ ok: boolean; removed: number }>
  open_history_file: (itemId: string, index: number) => Promise<ApiResult>
  continue_in_background: () => Promise<unknown>
  pause_and_close: () => Promise<unknown>
}

declare global {
  interface Window {
    pywebview?: { api: DesktopApi }
  }
}

const defaultPreferences: Preferences = {
  destination: 'Descargas\\Clipoteca',
}

function formatDuration(value: number | null) {
  if (value === null || !Number.isFinite(value)) return '—'
  const seconds = Math.max(0, Math.floor(value))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainder = seconds % 60
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
    : `${minutes}:${String(remainder).padStart(2, '0')}`
}

function formatSpeed(value: number | null) {
  if (!value || value <= 0) return ''
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} MB/s`
  return `${Math.round(value / 1000)} KB/s`
}

function statusLabel(status: ItemStatus) {
  const labels: Record<ItemStatus, string> = {
    queued: 'En cola',
    downloading: 'Descargando',
    paused: 'Pausada',
    failed: 'Fallida · reintentable',
    completed: 'Finalizada',
    cancelled: 'Cancelada',
  }
  return labels[status]
}

function App() {
  const [api, setApi] = useState<DesktopApi | undefined>(() => window.pywebview?.api)
  const [view, setView] = useState<View>('prepare')
  const [url, setUrl] = useState('')
  const [format, setFormat] = useState<Format>('video')
  const [quality, setQuality] = useState('auto')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [preview, setPreview] = useState<PreviewResult | null>(null)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [queueState, setQueueState] = useState<QueueState | null>(null)
  const [preferences, setPreferences] = useState<Preferences>(defaultPreferences)
  const [notice, setNotice] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [isEnqueueing, setIsEnqueueing] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [closeConfirmOpen, setCloseConfirmOpen] = useState(false)
  const [engineReady, setEngineReady] = useState(false)
  const [ffmpegReady, setFfmpegReady] = useState(false)
  const [trayAvailable, setTrayAvailable] = useState(false)
  const firstRunPrompted = useRef(false)

  const availableItems = useMemo(
    () => analysis?.items.filter((item) => item.available) ?? [],
    [analysis],
  )
  const allSelected = availableItems.length > 0 && availableItems.every((item) => selectedIds.includes(item.id))
  const activeCount = queueState?.counts.active ?? 0
  const currentList = view === 'history' ? queueState?.history ?? [] : queueState?.queue ?? []

  useEffect(() => {
    const onApiReady = () => setApi(window.pywebview?.api)
    window.addEventListener('pywebviewready', onApiReady)
    onApiReady()
    return () => window.removeEventListener('pywebviewready', onApiReady)
  }, [])

  useEffect(() => {
    if (!api) return
    let disposed = false
    const refresh = async () => {
      try {
        const state = await api.get_queue_state()
        if (!disposed) {
          setQueueState(state)
          setPreferences((current) => ({ ...current, ...state.preferences }))
          if (!firstRunPrompted.current) {
            firstRunPrompted.current = true
            if (!state.preferences.concurrency_mode) setSettingsOpen(true)
          }
        }
      } catch {
        if (!disposed) setNotice('No se pudo actualizar la cola. Comprueba que Clipoteca siga abierta.')
      }
    }
    void api.get_app_status().then((status) => {
      if (!disposed) {
        setEngineReady(status.download_engine_ready)
        setFfmpegReady(status.ffmpeg_ready)
        setTrayAvailable(status.tray_available)
      }
    })
    void refresh()
    const interval = window.setInterval(() => void refresh(), 1200)
    const onCloseRequest = () => setCloseConfirmOpen(true)
    window.addEventListener('clipoteca:close-request', onCloseRequest)
    return () => {
      disposed = true
      window.clearInterval(interval)
      window.removeEventListener('clipoteca:close-request', onCloseRequest)
    }
  }, [api])

  async function analyzeUrl() {
    if (!api) {
      setNotice('El análisis y las descargas están disponibles al abrir Clipoteca para escritorio.')
      return
    }
    if (!url.trim()) {
      setNotice('Pega un enlace para analizarlo.')
      return
    }
    setIsAnalyzing(true)
    setNotice('')
    setAnalysis(null)
    setPreview(null)
    setSelectedIds([])
    try {
      const result = await api.analyze_url(url)
      if (!result.ok) {
        setNotice(result.error ?? 'No se pudo analizar el enlace.')
        return
      }
      setAnalysis(result)
      setSelectedIds(result.items.filter((item) => item.available).map((item) => item.id))
      if (result.items.length === 1 && !result.is_playlist) {
        setNotice('Enlace analizado. Revisa las opciones y prepara la descarga.')
      }
    } catch {
      setNotice('No se pudo conectar con el motor de análisis.')
    } finally {
      setIsAnalyzing(false)
    }
  }

  function toggleItem(id: string) {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id],
    )
  }

  function toggleAll() {
    setSelectedIds(allSelected ? [] : availableItems.map((item) => item.id))
  }

  async function previewSelection() {
    if (!api || !analysis) {
      setNotice('La vista previa está disponible al abrir Clipoteca para escritorio.')
      return
    }
    const item = analysis.items.find((candidate) => selectedIds.includes(candidate.id))
    if (!item) return
    setIsPreviewing(true)
    setNotice('')
    try {
      const result = await api.get_preview(analysis.analysis_id, item.id, format, quality)
      if (!result.ok) {
        setNotice(result.error ?? 'No se pudo preparar la vista previa.')
        return
      }
      setPreview({ ...result, item_title: item.title })
    } catch {
      setNotice('No se pudo preparar la vista previa del elemento.')
    } finally {
      setIsPreviewing(false)
    }
  }

  async function startBatch() {
    if (!api || !analysis || selectedIds.length === 0) return
    if (!preferences.concurrency_mode) {
      setSettingsOpen(true)
      setNotice('Antes de descargar, elige cómo ejecutar la cola.')
      return
    }
    setIsEnqueueing(true)
    setNotice('')
    try {
      const result = await api.enqueue_batch(
        analysis.analysis_id,
        selectedIds,
        format,
        quality,
      )
      if (!result.ok) {
        setNotice(result.error ?? 'No se pudo añadir el lote a la cola.')
        return
      }
      setNotice(`${result.queued} elementos añadidos a la cola.`)
      setAnalysis(null)
      setSelectedIds([])
      setUrl('')
      setView('queue')
      await refreshQueue()
    } catch {
      setNotice('No se pudo iniciar el lote.')
    } finally {
      setIsEnqueueing(false)
    }
  }

  async function refreshQueue() {
    if (!api) return
    try {
      const state = await api.get_queue_state()
      setQueueState(state)
      setPreferences((current) => ({ ...current, ...state.preferences }))
    } catch {
      // The regular poll reports transient bridge errors.
    }
  }

  async function chooseDestination() {
    if (!api) return
    const result = await api.choose_destination()
    if (result.ok && result.destination) {
      setPreferences((current) => ({ ...current, destination: result.destination! }))
      await refreshQueue()
    } else if (result.error) {
      setNotice(result.error)
    }
  }

  async function savePreferences(next: Partial<Preferences>) {
    if (!api) return
    const result = await api.set_preferences(next)
    if (!result.ok) {
      setNotice(result.error ?? 'No se pudieron guardar los ajustes.')
      return
    }
    setPreferences({ ...defaultPreferences, ...result.preferences })
    setSettingsOpen(false)
    setNotice('Ajustes guardados.')
    await refreshQueue()
  }

  async function clearHistory() {
    if (!api || !window.confirm('Se borrarán los registros del historial, pero no los archivos descargados. ¿Continuar?')) {
      return
    }
    const result = await api.clear_history()
    setNotice(`${result.removed} registros eliminados. Los archivos descargados no se han tocado.`)
    await refreshQueue()
  }

  async function openHistoryFile(itemId: string, index: number) {
    if (!api) return
    const result = await api.open_history_file(itemId, index)
    if (!result.ok) setNotice(result.error ?? 'No se pudo abrir el archivo.')
  }

  async function cancelAll() {
    if (!api || !window.confirm('¿Cancelar todas las descargas activas y pendientes? Los archivos incompletos se eliminarán.')) {
      return
    }
    await api.cancel_all()
    setNotice('Se han enviado las cancelaciones.')
    await refreshQueue()
  }

  async function closeInBackground() {
    if (!api) return
    await api.continue_in_background()
    setCloseConfirmOpen(false)
  }

  async function pauseAndClose() {
    if (!api) return
    await api.pause_and_close()
    setCloseConfirmOpen(false)
  }

  const destinationName = preferences.destination || 'Descargas\\Clipoteca'

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
            <button className={`top-nav-item ${view === 'prepare' ? 'is-active' : ''}`} type="button" onClick={() => setView('prepare')} aria-current={view === 'prepare' ? 'page' : undefined}>
              Preparar
            </button>
            <button className={`top-nav-item ${view === 'queue' ? 'is-active' : ''}`} type="button" onClick={() => setView('queue')} aria-current={view === 'queue' ? 'page' : undefined}>
              Cola <span className="nav-count">{activeCount}</span>
            </button>
            <button className={`top-nav-item ${view === 'history' ? 'is-active' : ''}`} type="button" onClick={() => setView('history')} aria-current={view === 'history' ? 'page' : undefined}>
              Historial <span className="nav-count">{queueState?.counts.completed ?? 0}</span>
            </button>
          </nav>

          <div className="header-actions">
            <span className="engine-status">
              <span className={`engine-dot ${engineReady ? 'is-ready' : ''}`} aria-hidden="true" />
              {engineReady ? 'Motor conectado' : 'Solo escritorio'}
            </span>
            <button className="settings-button" type="button" aria-label="Ajustes" onClick={() => setSettingsOpen(true)}>
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
              <span className="prototype-badge">{engineReady ? 'Motor conectado' : 'Vista de escritorio'}</span>
            </section>

            <section className="source-panel" aria-labelledby="source-title">
              <label className="source-label" id="source-title" htmlFor="source-url">Enlace de video o playlist</label>
              <form className="source-control" onSubmit={(event) => { event.preventDefault(); void analyzeUrl() }}>
                <Link2 size={19} strokeWidth={1.7} aria-hidden="true" />
                <input
                  id="source-url"
                  type="url"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="Pega un enlace compatible con yt-dlp"
                  autoComplete="url"
                />
                <button className="analyze-button" type="submit" disabled={isAnalyzing}>
                  {isAnalyzing ? 'Analizando…' : 'Analizar enlace'}
                  <ArrowRight size={16} strokeWidth={1.8} aria-hidden="true" />
                </button>
              </form>
              <p className="source-hint">Los elementos se revisan antes de iniciar la descarga.</p>
            </section>

            <div className="demo-disclosure" role="note">
              <CircleAlert size={16} strokeWidth={1.7} aria-hidden="true" />
              <p><strong>Acceso directo.</strong> No se importan cookies ni credenciales. El análisis y la descarga requieren un enlace accesible sin iniciar sesión.</p>
            </div>

            <div className="collection-layout">
              <section className="playlist-section" aria-labelledby="playlist-title">
                <header className="playlist-heading">
                  <div>
                    <div className="playlist-title-line">
                      <h2 id="playlist-title">{analysis?.title ?? 'Contenido por analizar'}</h2>
                      {analysis && <span className="sample-badge">{analysis.is_playlist ? 'Playlist' : 'Video'}</span>}
                    </div>
                    <p>{analysis ? `${analysis.items.length} elementos · ${analysis.extractor || 'yt-dlp'}` : 'El manifiesto aparecerá aquí después del análisis'}</p>
                  </div>
                  {analysis && <div className="playlist-heading-actions">
                    <span className="availability-summary">{availableItems.length} disponibles</span>
                    <button className="preview-button" type="button" disabled={!selectedIds.length || isPreviewing} onClick={() => void previewSelection()}>
                      <Eye size={15} aria-hidden="true" />{isPreviewing ? 'Preparando…' : 'Previsualizar'}
                    </button>
                  </div>}
                </header>

                {analysis ? (
                  <>
                    {preview && <section className="preview-card" aria-label="Vista previa del elemento seleccionado">
                      <div className={`preview-media ${preview.kind === 'audio' ? 'is-audio' : ''}`}>
                        {preview.kind === 'video' && preview.playable && preview.url ? (
                          <video controls playsInline preload="metadata" poster={preview.thumbnail ?? undefined} onError={() => setNotice('La fuente no permitió reproducir la vista previa en esta ventana.')}>
                            <source src={preview.url} type={preview.mime_type || undefined} />
                          </video>
                        ) : preview.thumbnail ? (
                          <img src={preview.thumbnail} alt={`Previsualización de ${preview.item_title}`} />
                        ) : (
                          <span className="preview-placeholder"><ListVideo size={24} aria-hidden="true" /></span>
                        )}
                      </div>
                      <div className="preview-copy">
                        <span className="preview-kicker">VISTA PREVIA · {preview.kind === 'audio' ? 'AUDIO' : 'VÍDEO'}</span>
                        <h3>{preview.item_title}</h3>
                        <p>{preview.playable ? 'Se reproduce desde la fuente; no se guarda en disco.' : 'El sitio no ofrece un flujo reproducible aquí. La miniatura y los metadatos sí sirven como referencia.'}</p>
                        {preview.kind === 'audio' && preview.playable && preview.url && <audio controls preload="metadata" onError={() => setNotice('La fuente no permitió reproducir la vista previa de audio.')}>
                          <source src={preview.url} type={preview.mime_type || undefined} />
                        </audio>}
                      </div>
                      <button className="preview-close" type="button" aria-label="Cerrar vista previa" onClick={() => setPreview(null)}><X size={16} /></button>
                    </section>}

                    <div className="selection-toolbar">
                      <label className="select-all-control">
                        <input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label={allSelected ? 'Desmarcar elementos disponibles' : 'Seleccionar elementos disponibles'} />
                        <span className="custom-check" aria-hidden="true"><Check size={12} strokeWidth={2.5} /></span>
                        <span>{selectedIds.length} de {analysis.items.length} seleccionados</span>
                      </label>
                      <button className="text-button" type="button" onClick={toggleAll}>
                        {allSelected ? 'Desmarcar disponibles' : 'Seleccionar disponibles'}
                      </button>
                    </div>

                    <div className="media-list-wrap">
                      <table className="media-list">
                        <thead><tr>
                          <th className="check-column" scope="col"><span className="visually-hidden">Seleccionar</span></th>
                          <th scope="col">Elemento</th>
                          <th className="duration-column" scope="col">Duración</th>
                          <th className="status-column" scope="col">Estado</th>
                        </tr></thead>
                        <tbody>
                          {analysis.items.map((item) => {
                            const checked = selectedIds.includes(item.id)
                            return (
                              <tr className={`${checked ? 'is-selected' : ''} ${!item.available ? 'is-unavailable' : ''}`} key={item.id}>
                                <td className="check-cell"><label className="row-check">
                                  <input type="checkbox" checked={checked} disabled={!item.available} onChange={() => toggleItem(item.id)} aria-label={`Seleccionar ${item.title}`} />
                                  <span className="custom-check" aria-hidden="true"><Check size={12} strokeWidth={2.5} /></span>
                                </label></td>
                                <td className="title-cell">
                                  <span className="item-title">{item.title}</span>
                                  <span className="item-number">Elemento {String(item.index).padStart(2, '0')}</span>
                                </td>
                                <td className="item-duration"><Clock3 size={14} strokeWidth={1.7} aria-hidden="true" />{formatDuration(item.duration)}</td>
                                <td><span className={`availability ${item.available ? 'is-available' : 'is-unavailable'}`}>
                                  <span className="availability-dot" aria-hidden="true" />{item.available ? 'Disponible' : 'No disponible'}
                                </span></td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                    <div className="playlist-footnote">
                      <span>Se conserva el orden original</span>
                      <span>{analysis.items.length - availableItems.length} no disponibles</span>
                    </div>
                  </>
                ) : (
                  <div className="analysis-empty">
                    <span className="empty-icon"><ListVideo size={23} strokeWidth={1.5} aria-hidden="true" /></span>
                    <p>Analiza una URL para revisar los elementos disponibles antes de guardarlos.</p>
                  </div>
                )}
              </section>

              <aside className="preferences-panel" aria-labelledby="preferences-title">
                <div className="preferences-heading">
                  <h2 id="preferences-title">Preferencias</h2>
                  <p>Para esta colección</p>
                </div>

                <fieldset className="format-field">
                  <legend>Formato</legend>
                  <div className="format-options" role="group" aria-label="Formato de salida">
                    {([['video', 'Video', 'MP4'], ['audio', 'Audio', 'MP3'], ['both', 'Ambos', '']] as const).map(([value, label, detail]) => (
                      <button className={`format-option ${format === value ? 'is-active' : ''}`} type="button" aria-pressed={format === value} key={value} onClick={() => { setFormat(value); setPreview(null) }}>
                        <span>{label}</span>{detail && <small>{detail}</small>}
                      </button>
                    ))}
                  </div>
                </fieldset>

                <div className="quality-field">
                  <label htmlFor="quality-select"><span>Calidad</span><span>Mejor disponible por defecto</span></label>
                  <div className={`select-shell ${format === 'audio' ? 'is-disabled' : ''}`}>
                    <select id="quality-select" value={quality} onChange={(event) => setQuality(event.target.value)} disabled={format === 'audio'}>
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
                  <button className="destination-button" type="button" onClick={() => void chooseDestination()}>
                    <FolderOpen size={17} strokeWidth={1.7} aria-hidden="true" />
                    <span><strong>{destinationName}</strong><small>Se recuerda para próximos lotes</small></span>
                    <ChevronDown size={15} aria-hidden="true" />
                  </button>
                </div>

                <div className="collection-rule" />
                <div className="collection-summary">
                  <div><span>En la lista</span><strong>{analysis?.items.length ?? 0} elementos</strong></div>
                  <div><span>Guardarás</span><strong>{selectedIds.length} elementos</strong></div>
                </div>
                <div className="collection-note"><BookOpen size={16} strokeWidth={1.7} aria-hidden="true" /><span>Las playlists se guardan en su propia carpeta.</span></div>
              </aside>
            </div>

            {engineReady && !ffmpegReady && <p className="ffmpeg-warning" role="note">FFmpeg no está instalado o no está en PATH. Se necesita para MP3 y para combinar algunas pistas de vídeo.</p>}

            <footer className="download-bar">
              <div className="download-summary">
                <span className="download-icon"><ArrowDownToLine size={17} strokeWidth={1.8} aria-hidden="true" /></span>
                <div><strong>{selectedIds.length} elementos seleccionados</strong><span>{engineReady ? 'Descargas locales con yt-dlp.' : 'Abre Clipoteca para escritorio para descargar.'}</span></div>
              </div>
              <button className="download-button" type="button" disabled={!engineReady || !analysis || selectedIds.length === 0 || !preferences.concurrency_mode || isEnqueueing} onClick={() => void startBatch()}>
                {isEnqueueing ? 'Añadiendo…' : 'Preparar descarga'}<span>{selectedIds.length}</span>
              </button>
            </footer>
          </div>
        ) : (
          <section className="queue-view">
            <div className="queue-heading queue-heading-row">
              <div>
                <h1>{view === 'history' ? 'Historial' : 'Cola de descargas'}</h1>
                <p>{view === 'history' ? 'Resultados de lotes finalizados. Limpiar el historial no borra los archivos.' : 'Estado y recuperación por elemento.'}</p>
              </div>
              {view === 'history' ? (
                <button className="secondary-action" type="button" disabled={!currentList.length} onClick={() => void clearHistory()}><Trash2 size={15} aria-hidden="true" />Limpiar historial</button>
              ) : (
                <div className="queue-actions">
                  <button className="secondary-action" type="button" disabled={!queueState?.queue.some((item) => item.status === 'queued' || item.status === 'downloading')} onClick={() => void api?.pause_all()}><Pause size={15} aria-hidden="true" />Pausar todo</button>
                  <button className="secondary-action" type="button" disabled={!queueState?.queue.some((item) => item.status === 'paused')} onClick={() => void api?.resume_all()}><Play size={15} aria-hidden="true" />Reanudar</button>
                  <button className="secondary-action danger-action" type="button" disabled={!queueState?.queue.some((item) => ['queued', 'downloading', 'paused', 'failed'].includes(item.status))} onClick={() => void cancelAll()}><X size={15} aria-hidden="true" />Cancelar todo</button>
                </div>
              )}
            </div>

            {currentList.length ? (
              <div className="download-list">
                {currentList.map((item) => (
                  <article className="download-row" key={item.id}>
                    <div className="download-row-main">
                      <div className="download-row-copy">
                        <span className={`status-pill status-${item.status}`}>{statusLabel(item.status)}</span>
                        <h2>{item.title}</h2>
                        <p>{item.batch_title}</p>
                      </div>
                      <div className="download-row-actions">
                        {view === 'queue' && item.status === 'failed' && <button className="icon-action" type="button" title="Reintentar" aria-label={`Reintentar ${item.title}`} onClick={() => void api?.retry_item(item.id)}><RotateCcw size={16} /></button>}
                        {view === 'queue' && item.status !== 'failed' && <button className="icon-action" type="button" title="Cancelar elemento" aria-label={`Cancelar ${item.title}`} onClick={() => void api?.cancel_item(item.id)}><X size={16} /></button>}
                      </div>
                    </div>
                    {view === 'queue' && item.status === 'downloading' && (
                      <div className="progress-line" aria-label={`${Math.round(item.progress * 100)}% descargado`}>
                        <span><span style={{ width: `${Math.max(0, Math.min(100, item.progress * 100))}%` }} /></span>
                        <small>{Math.round(item.progress * 100)}%{formatSpeed(item.speed) ? ` · ${formatSpeed(item.speed)}` : ''}</small>
                      </div>
                    )}
                    {item.error && <p className={`download-row-message ${item.status === 'failed' ? 'is-error' : ''}`}>{item.error}</p>}
                    {view === 'history' && item.output_paths?.length > 0 && <div className="history-file-actions">
                      {item.output_paths.map((path, index) => {
                        const extension = path.split('.').pop()?.toUpperCase() || 'ARCHIVO'
                        return <button className="open-file-button" type="button" key={`${item.id}-${index}`} title={path} onClick={() => void openHistoryFile(item.id, index)}>
                          <ExternalLink size={14} aria-hidden="true" />{item.output_paths.length > 1 ? `Abrir ${extension}` : 'Abrir archivo'}
                        </button>
                      })}
                    </div>}
                  </article>
                ))}
              </div>
            ) : (
              <section className="queue-empty">
                <span className="empty-icon"><ListVideo size={24} strokeWidth={1.5} aria-hidden="true" /></span>
                <h2>{view === 'history' ? 'Aún no hay lotes finalizados' : 'La cola está vacía'}</h2>
                <p>{view === 'history' ? 'Los elementos descargados aparecerán aquí.' : 'Analiza un enlace y prepara tu primer lote para verlo aquí.'}</p>
                {view === 'queue' && <button className="return-button" type="button" onClick={() => setView('prepare')}>Preparar una descarga<ArrowRight size={15} aria-hidden="true" /></button>}
              </section>
            )}
          </section>
        )}
      </main>

      {notice && <div className="toast" role="status"><span>{notice}</span><button type="button" aria-label="Cerrar aviso" onClick={() => setNotice('')}><X size={16} aria-hidden="true" /></button></div>}

      {settingsOpen && <SettingsDialog firstRun={!preferences.concurrency_mode} preferences={preferences} onClose={() => setSettingsOpen(false)} onSave={(value) => void savePreferences(value)} />}

      {closeConfirmOpen && <div className="modal-backdrop" role="presentation">
        <section className="dialog-panel close-dialog" role="dialog" aria-modal="true" aria-labelledby="close-title">
          <button className="dialog-close" type="button" aria-label="Volver a la app" onClick={() => setCloseConfirmOpen(false)}><X size={18} /></button>
          <span className="dialog-icon"><CircleAlert size={20} /></span>
          <h2 id="close-title">Hay descargas pendientes</h2>
          <p>{trayAvailable ? 'Puedes dejarlas funcionando en segundo plano o pausarlas para continuar más tarde.' : 'Puedes pausar las descargas y continuar más tarde.'}</p>
          <div className="dialog-actions vertical-actions">
            {trayAvailable && <button className="primary-dialog-action" type="button" onClick={() => void closeInBackground()}>Seguir en segundo plano</button>}
            <button className="secondary-dialog-action" type="button" onClick={() => void pauseAndClose()}>Pausar y cerrar</button>
            <button className="text-dialog-action" type="button" onClick={() => setCloseConfirmOpen(false)}>Volver a la app</button>
          </div>
        </section>
      </div>}
    </div>
  )
}

function SettingsDialog({
  firstRun,
  preferences,
  onClose,
  onSave,
}: {
  firstRun: boolean
  preferences: Preferences
  onClose: () => void
  onSave: (value: Partial<Preferences>) => void
}) {
  const [mode, setMode] = useState<'' | 'auto' | 'manual'>(preferences.concurrency_mode ?? '')
  const [manual, setManual] = useState(
    preferences.manual_concurrency == null ? '' : String(preferences.manual_concurrency),
  )
  const [cap, setCap] = useState(
    preferences.auto_concurrency_cap == null ? '' : String(preferences.auto_concurrency_cap),
  )
  const selectedValue = mode === 'auto' ? cap : manual
  const selectedCount = Number.parseInt(selectedValue, 10)
  const canSave = mode !== '' && Number.isInteger(selectedCount) && selectedCount > 0

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSave || !mode) return
    onSave({
      concurrency_mode: mode,
      ...(mode === 'manual'
        ? { manual_concurrency: selectedCount }
        : { auto_concurrency_cap: selectedCount }),
    })
  }

  return <div className="modal-backdrop" role="presentation">
    <form className="dialog-panel settings-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-title" onSubmit={submit}>
      <button className="dialog-close" type="button" aria-label="Cerrar ajustes" onClick={onClose}><X size={18} /></button>
      <h2 id="settings-title">{firstRun ? 'Configura tu primera cola' : 'Ajustes de descarga'}</h2>
      <p>{firstRun ? 'Elige cuántas descargas pueden ejecutarse a la vez. Podrás cambiarlo después.' : 'La concurrencia automática se adapta al rendimiento hasta el valor que tú elijas.'}</p>
      <label className="dialog-label" htmlFor="concurrency-mode">Modo de concurrencia</label>
      <select id="concurrency-mode" value={mode} onChange={(event) => setMode(event.target.value as '' | 'auto' | 'manual')}>
        <option value="" disabled>Elige cómo ejecutar la cola</option>
        <option value="auto">Automático</option>
        <option value="manual">Manual</option>
      </select>
      {mode === 'auto' ? (
        <label className="dialog-label" htmlFor="auto-cap">
          Máximo elegido por ti
          <input id="auto-cap" type="number" min="1" step="1" value={cap} onChange={(event) => setCap(event.target.value)} required />
        </label>
      ) : mode === 'manual' ? (
        <label className="dialog-label" htmlFor="manual-count">
          Descargas simultáneas
          <input id="manual-count" type="number" min="1" step="1" value={manual} onChange={(event) => setManual(event.target.value)} required />
        </label>
      ) : (
        <p className="dialog-footnote">Selecciona un modo para configurar la cola.</p>
      )}
      {selectedCount >= 5 && <p className="dialog-footnote">Un valor alto puede consumir más recursos o provocar límites temporales del sitio. Clipoteca no lo bloqueará.</p>}
      <p className="dialog-footnote">Clipoteca no fija un máximo; el modo automático usa el techo que tú configures.</p>
      <div className="dialog-actions"><button className="secondary-dialog-action" type="button" onClick={onClose}>Cancelar</button><button className="primary-dialog-action" type="submit" disabled={!canSave}>Guardar ajustes</button></div>
    </form>
  </div>
}

export default App
