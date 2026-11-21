import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type RefObject } from 'react'
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Clock3,
  ExternalLink,
  Film,
  FolderOpen,
  Globe,
  HardDrive,
  History,
  Link2,
  ListVideo,
  MonitorPlay,
  Music2,
  PanelLeftClose,
  PanelLeftOpen,
  Pause,
  Play,
  RotateCcw,
  Search,
  Settings2,
  Layers2,
  Timer,
  Trash2,
  X,
} from 'lucide-react'
import { SiYoutube } from 'react-icons/si'
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
  source_url?: string | null
  download_attempt_started_at?: string | null
  title: string
  duration: number | null
  completed_at?: string | null
  download_elapsed_seconds?: number | null
  status: ItemStatus
  progress: number
  downloaded_bytes?: number
  total_bytes?: number | null
  download_phase?: 'preparing' | 'transfer' | 'video' | 'audio' | 'between_tracks' | 'merging' | 'converting' | 'finalizing' | 'retrying' | null
  download_steps?: DownloadStep[] | null
  speed: number | null
  eta: number | null
  error: string | null
  output_path: string | null
  output_paths: string[]
}

type DownloadStep = {
  id: 'video' | 'audio' | 'merge' | 'file' | 'save' | 'mp3_audio' | 'convert'
  status: 'pending' | 'active' | 'done'
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

const accentOptions = [
  ['clipoteca', 'Granate'],
  ['iris', 'Iris'],
  ['blue', 'Azul'],
  ['green', 'Verde'],
  ['amber', 'Ámbar'],
] as const
type ThemeAccent = (typeof accentOptions)[number][0]

type Preferences = {
  destination: string
  theme_mode?: 'system' | 'dark' | 'light' | null
  theme_accent?: ThemeAccent | null
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
  theme_mode: 'system',
  theme_accent: 'clipoteca',
}

const youtubeVideoIdPattern = /^[A-Za-z0-9_-]{11}$/
const startupBannerMinMs = 1800

function getCachedThemeMode(): NonNullable<Preferences['theme_mode']> {
  try {
    const mode = window.localStorage.getItem('clipoteca-theme-mode')
    return mode === 'dark' || mode === 'light' ? mode : 'system'
  } catch {
    return 'system'
  }
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

function formatTimestamp(value: string | null | undefined) {
  if (!value) return 'Fecha no disponible'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Fecha no disponible'
  return new Intl.DateTimeFormat('es-ES', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function formatElapsed(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value) || value <= 0) return 'Sin medición'
  const seconds = Math.floor(value)
  if (seconds < 60) return `${seconds} s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ${seconds % 60} s`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

function elapsedForItem(item: QueueItem) {
  const accumulated = Math.max(0, item.download_elapsed_seconds ?? 0)
  if (item.status !== 'downloading' || !item.download_attempt_started_at) return accumulated
  const startedAt = Date.parse(item.download_attempt_started_at)
  return Number.isFinite(startedAt)
    ? accumulated + Math.max(0, (Date.now() - startedAt) / 1000)
    : accumulated
}

function sourceLabel(sourceUrl: string | null | undefined) {
  if (!sourceUrl) return 'Fuente desconocida'
  try {
    const host = new URL(sourceUrl).hostname.toLowerCase()
    if (host === 'youtu.be' || host === 'youtube.com' || host.endsWith('.youtube.com')) {
      return 'YouTube'
    }
  } catch {
    // Bad or missing stored URLs stay a generic source rather than breaking the row.
  }
  return 'Otra fuente'
}

function SourceMark({ sourceUrl }: { sourceUrl: string | null | undefined }) {
  const label = sourceLabel(sourceUrl)
  return (
    <span className="source-mark" role="img" aria-label={`Fuente: ${label}`} title={label}>
      {label === 'YouTube'
        ? <SiYoutube size={15} aria-hidden="true" />
        : <Globe size={15} strokeWidth={1.8} aria-hidden="true" />}
      <span aria-hidden="true">{label}</span>
    </span>
  )
}

function isDiskSpaceError(error: string | null | undefined) {
  return /espacio|enospc|disk full|no space left|errno\s*28/i.test(error ?? '')
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

function DownloadProgress({ item }: { item: QueueItem }) {
  const phase = item.download_phase ?? (item.progress >= 1 ? 'finalizing' : 'transfer')
  const transferring = phase === 'transfer' || phase === 'video' || phase === 'audio'
  const total = item.total_bytes ?? 0
  const downloaded = item.downloaded_bytes ?? total * item.progress
  const fraction = transferring && total > 0
    ? Math.max(0, Math.min(1, downloaded / total))
    : null
  const percent = fraction === null ? undefined : Math.min(99, Math.floor(fraction * 100))
  const remainingSeconds = item.eta && item.eta > 0
    ? item.eta
    : total > downloaded && item.speed && item.speed > 0 ? (total - downloaded) / item.speed : null
  const remaining = transferring && remainingSeconds && Number.isFinite(remainingSeconds)
    ? formatElapsed(Math.ceil(remainingSeconds))
    : null
  const elapsed = Math.floor(elapsedForItem(item))
  const speed = transferring ? formatSpeed(item.speed) : ''
  const phaseLabel = {
    preparing: 'Preparando descarga',
    transfer: 'Descargando archivo',
    video: 'Descargando pista de vídeo',
    audio: 'Descargando pista de audio',
    between_tracks: 'Preparando el siguiente paso',
    merging: 'Uniendo vídeo y audio',
    converting: 'Convirtiendo audio',
    finalizing: 'Finalizando archivo',
    retrying: 'Reintentando conexión',
  }[phase]
  const stepLabels: Record<DownloadStep['id'], string> = {
    video: 'Vídeo',
    audio: 'Audio',
    merge: 'Unir',
    file: 'Vídeo y audio',
    save: 'Guardar',
    mp3_audio: 'Audio MP3',
    convert: 'Convertir',
  }

  return (
    <div className="download-progress">
      {!!item.download_steps?.length && <ol className="download-steps" aria-label="Pasos de la descarga">
        {item.download_steps.map((step, index) => {
          const status = step.status === 'active' && (phase === 'preparing' || phase === 'retrying')
            ? 'pending' : step.status
          const stateLabel = { pending: 'pendiente', active: 'en curso', done: 'completado' }[status]
          const label = step.id === 'mp3_audio' && item.download_steps?.length === 2 ? 'Audio' : stepLabels[step.id]
          return (
            <li key={step.id} data-state={status} aria-current={status === 'active' ? 'step' : undefined} aria-label={`${label}, ${stateLabel}`}>
              {index > 0 && <ChevronRight className="step-separator" size={12} aria-hidden="true" />}
              <span className="step-mark" aria-hidden="true">
                {status === 'done' && <Check size={10} strokeWidth={2.4} />}
              </span>
              {label}
            </li>
          )
        })}
      </ol>}
      <div className={`progress-line${fraction === null ? ' is-indeterminate' : ''}`}>
        <span role="progressbar" aria-label={`Descarga de ${item.title}`} aria-valuenow={percent} aria-valuetext={percent === undefined ? phaseLabel : `${phaseLabel} · ${percent}%`}>
          <span style={fraction === null ? undefined : { transform: `scaleX(${Math.min(0.99, fraction)})` }} />
        </span>
        <small>{phaseLabel}{percent !== undefined ? ` · ${percent}%` : transferring ? ' · Progreso indeterminado' : ''}</small>
      </div>
      <div className="download-timing">
        <span>Transcurrido <strong>{elapsed ? formatElapsed(elapsed) : '0 s'}</strong></span>
        <span>Restante en esta fase <strong>{remaining ? `≈ ${remaining}` : transferring ? 'Calculando…' : 'Sin estimación'}</strong></span>
        {speed && <span>{speed}</span>}
      </div>
    </div>
  )
}

function dismissDialog(backdrop: HTMLDivElement | null, done: () => void) {
  if (!backdrop || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    done()
    return
  }
  if (backdrop.inert) return
  backdrop.inert = true
  const options: KeyframeAnimationOptions = { duration: 150, easing: 'ease-in', fill: 'forwards' }
  backdrop.firstElementChild?.animate(
    [{ transform: 'translateY(0) scale(1)' }, { transform: 'translateY(6px) scale(0.99)' }],
    options,
  )
  const exit = backdrop.animate([{ opacity: 1 }, { opacity: 0 }], options)
  void exit.finished.then(done, done)
}

function NoticeToast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)

  useEffect(() => {
    if (hovered || focused) return
    const timer = window.setTimeout(onDismiss, 6000)
    return () => window.clearTimeout(timer)
  }, [hovered, focused, onDismiss])

  return (
    <div className="toast" onPointerEnter={() => setHovered(true)} onPointerLeave={() => setHovered(false)}>
      <span role="status">{message}</span>
      <button type="button" aria-label="Cerrar aviso" onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} onClick={onDismiss}>
        <X size={16} aria-hidden="true" />
      </button>
    </div>
  )
}

function App() {
  const [api, setApi] = useState<DesktopApi | undefined>(() => window.pywebview?.api)
  const [view, setView] = useState<View>('prepare')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [url, setUrl] = useState('')
  const [format, setFormat] = useState<Format>('video')
  const [quality, setQuality] = useState('auto')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [previewItem, setPreviewItem] = useState<MediaItem | null>(null)
  const [previewLoadState, setPreviewLoadState] = useState<'idle' | 'loading' | 'loaded' | 'error'>('idle')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [queueState, setQueueState] = useState<QueueState | null>(null)
  const [preferences, setPreferences] = useState<Preferences>(() => ({
    ...defaultPreferences,
    theme_mode: getCachedThemeMode(),
  }))
  const [startupState, setStartupState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [startupAttempt, setStartupAttempt] = useState(0)
  const [historyQuery, setHistoryQuery] = useState('')
  const [notice, setNotice] = useState('')
  const clearNotice = useCallback(() => setNotice(''), [])
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isEnqueueing, setIsEnqueueing] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [previewAccent, setPreviewAccent] = useState<ThemeAccent | null>(null)
  const [closeConfirmOpen, setCloseConfirmOpen] = useState(false)
  const [engineReady, setEngineReady] = useState(false)
  const [ffmpegReady, setFfmpegReady] = useState(false)
  const [trayAvailable, setTrayAvailable] = useState(false)
  const firstRunPrompted = useRef(false)
  const previewPanel = useRef<HTMLElement>(null)
  const previewTrigger = useRef<HTMLButtonElement>(null)
  const settingsTrigger = useRef<HTMLButtonElement>(null)
  const settingsBackdrop = useRef<HTMLDivElement>(null)
  const closeBackdrop = useRef<HTMLDivElement>(null)
  const closeTrigger = useRef<HTMLElement | null>(null)

  const availableItems = useMemo(
    () => analysis?.items.filter((item) => item.available) ?? [],
    [analysis],
  )
  const allSelected = availableItems.length > 0 && availableItems.every((item) => selectedIds.includes(item.id))
  const activeCount = queueState?.counts.active ?? 0
  const currentList = view === 'history' ? queueState?.history ?? [] : queueState?.queue ?? []
  const normalizedHistoryQuery = historyQuery.trim().toLocaleLowerCase('es')
  const visibleList = view === 'history' && normalizedHistoryQuery
    ? currentList.filter((item) =>
      `${item.title} ${item.batch_title}`.toLocaleLowerCase('es').includes(normalizedHistoryQuery),
    )
    : currentList

  useEffect(() => {
    const onApiReady = () => {
      const connected = window.pywebview?.api
      if (connected && connected !== api) {
        setStartupState('loading')
        setApi(connected)
      }
    }
    window.addEventListener('pywebviewready', onApiReady)
    onApiReady()
    return () => window.removeEventListener('pywebviewready', onApiReady)
  }, [api])

  useEffect(() => {
    const mode = preferences.theme_mode ?? 'system'
    const media = window.matchMedia('(prefers-color-scheme: light)')
    const applyTheme = () => {
      const theme = mode === 'system' ? (media.matches ? 'light' : 'dark') : mode
      document.documentElement.dataset.theme = theme
      document.documentElement.dataset.themeMode = mode
      document.documentElement.style.colorScheme = theme
      const themeColor = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
      if (themeColor) themeColor.content = theme === 'light' ? '#F4F0F1' : '#100B0D'
    }

    try {
      window.localStorage.setItem('clipoteca-theme-mode', mode)
    } catch {
      // The preference remains available from the local desktop bridge.
    }
    applyTheme()
    if (mode !== 'system') return
    media.addEventListener('change', applyTheme)
    return () => media.removeEventListener('change', applyTheme)
  }, [preferences.theme_mode])

  useEffect(() => {
    document.documentElement.dataset.accent = previewAccent ?? preferences.theme_accent ?? 'clipoteca'
  }, [previewAccent, preferences.theme_accent])

  useEffect(() => {
    if (!api) {
      const timeout = window.setTimeout(() => setStartupState('ready'), 900)
      return () => window.clearTimeout(timeout)
    }
    let disposed = false
    let paintFrame: number | undefined
    let readyTimer: number | undefined
    let interval: number | undefined
    let queueErrorReported = false
    const refresh = async () => {
      try {
        const state = await api.get_queue_state()
        if (!disposed) {
          queueErrorReported = false
          setQueueState(state)
          setPreferences((current) => ({ ...current, ...state.preferences }))
        }
      } catch {
        if (!disposed && !queueErrorReported) {
          queueErrorReported = true
          setNotice('No se pudo actualizar la cola. Comprueba que Clipoteca siga abierta.')
        }
      }
    }
    // Give the banner a painted frame before counting its visible time.
    const firstPaint = new Promise<number>((resolve) => {
      paintFrame = window.requestAnimationFrame(() => {
        paintFrame = window.requestAnimationFrame(resolve)
      })
    })
    void Promise.all([api.get_queue_state(), api.get_app_status(), firstPaint])
      .then(([state, status, paintedAt]) => {
        if (disposed) return
        setQueueState(state)
        setPreferences((current) => ({ ...current, ...state.preferences }))
        setEngineReady(status.download_engine_ready)
        setFfmpegReady(status.ffmpeg_ready)
        setTrayAvailable(status.tray_available)
        readyTimer = window.setTimeout(() => {
          setStartupState('ready')
          if (!firstRunPrompted.current) {
            firstRunPrompted.current = true
            if (!state.preferences.concurrency_mode) setSettingsOpen(true)
          }
          interval = window.setInterval(() => void refresh(), 1200)
        }, Math.max(0, startupBannerMinMs - (performance.now() - paintedAt)))
      })
      .catch(() => {
        if (!disposed) setStartupState('error')
      })
    const onCloseRequest = () => {
      closeTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
      setCloseConfirmOpen(true)
    }
    window.addEventListener('clipoteca:close-request', onCloseRequest)
    return () => {
      disposed = true
      if (paintFrame !== undefined) window.cancelAnimationFrame(paintFrame)
      window.clearTimeout(readyTimer)
      window.clearInterval(interval)
      window.removeEventListener('clipoteca:close-request', onCloseRequest)
    }
  }, [api, startupAttempt])

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
    setPreviewItem(null)
    setPreviewLoadState('idle')
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

  function openPreview(item: MediaItem, trigger?: HTMLButtonElement) {
    if (!youtubeVideoIdPattern.test(item.source_id)) {
      setNotice('No se pudo reconocer el identificador de este video para abrir la vista previa.')
      return
    }
    setNotice('')
    setPreviewItem(item)
    if (previewItem?.source_id !== item.source_id || previewLoadState === 'error') {
      setPreviewLoadState('loading')
    }
    if (trigger) {
      previewTrigger.current = trigger
      previewPanel.current?.focus({ preventScroll: true })
      previewPanel.current?.scrollIntoView({ block: 'nearest' })
    }
  }

  function closePreview() {
    setPreviewItem(null)
    setPreviewLoadState('idle')
    previewTrigger.current?.focus()
    previewTrigger.current = null
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
      setPreviewItem(null)
      setPreviewLoadState('idle')
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
      setNotice('No se pudo actualizar la cola. Comprueba que Clipoteca siga abierta.')
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
    closeSettings()
    setNotice('Ajustes guardados.')
    await refreshQueue()
  }

  function closeSettings() {
    dismissDialog(settingsBackdrop.current, () => {
      setSettingsOpen(false)
      setPreviewAccent(null)
      settingsTrigger.current?.focus()
    })
  }

  function returnFromCloseDialog() {
    dismissDialog(closeBackdrop.current, () => {
      setCloseConfirmOpen(false)
      closeTrigger.current?.focus()
    })
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
    if (!api || !window.confirm('¿Cancelar todas las descargas activas, pendientes y pausadas? Los archivos incompletos se eliminarán.')) {
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

  if (startupState === 'loading') {
    return (
      <main className="startup-screen">
        <div className="startup-banner" role="status">
          <img src={logoMark} alt="" aria-hidden="true" />
          <div className="startup-copy">
            <strong>Abriendo Clipoteca</strong>
            <span>Preparando tus descargas e historial…</span>
          </div>
          <span className="startup-spinner" aria-hidden="true" />
        </div>
      </main>
    )
  }

  return (
    <div className="app-shell" data-sidebar-collapsed={sidebarCollapsed}>
      {startupState === 'error' && <div className="startup-banner is-error" role="alert">
        <CircleAlert size={20} aria-hidden="true" />
        <div className="startup-copy">
          <strong>No se pudo iniciar la cola</strong>
          <span>Comprueba que la aplicación siga abierta e inténtalo otra vez.</span>
        </div>
        <button type="button" onClick={() => {
            setStartupState('loading')
            setStartupAttempt((attempt) => attempt + 1)
          }}>Reintentar</button>
      </div>}
      <aside id="app-sidebar" className="app-sidebar" aria-label="Navegación lateral">
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

          <nav className="sidebar-nav" aria-label="Navegación principal">
            <button
              className={`sidebar-nav-item ${view === 'prepare' ? 'is-active' : ''}`}
              type="button"
              onClick={() => setView('prepare')}
              aria-label="Preparar"
              aria-current={view === 'prepare' ? 'page' : undefined}
              title="Preparar"
            >
              <span className="sidebar-nav-icon"><ListVideo size={18} strokeWidth={1.8} aria-hidden="true" /></span>
              <span className="sidebar-label">Preparar</span>
            </button>
            <button
              className={`sidebar-nav-item ${view === 'queue' ? 'is-active' : ''}`}
              type="button"
              onClick={() => setView('queue')}
              aria-label={`Cola, ${activeCount} descargas activas`}
              aria-current={view === 'queue' ? 'page' : undefined}
              title={`Cola · ${activeCount} activas`}
            >
              <span className="sidebar-nav-icon"><ArrowDownToLine size={18} strokeWidth={1.8} aria-hidden="true" /></span>
              <span className="sidebar-label">Cola</span>
              <span className="nav-count" aria-hidden="true">{activeCount}</span>
            </button>
            <button
              className={`sidebar-nav-item ${view === 'history' ? 'is-active' : ''}`}
              type="button"
              onClick={() => setView('history')}
              aria-label={`Historial, ${queueState?.counts.completed ?? 0} resultados`}
              aria-current={view === 'history' ? 'page' : undefined}
              title={`Historial · ${queueState?.counts.completed ?? 0} resultados`}
            >
              <span className="sidebar-nav-icon"><History size={18} strokeWidth={1.8} aria-hidden="true" /></span>
              <span className="sidebar-label">Historial</span>
              <span className="nav-count" aria-hidden="true">{queueState?.counts.completed ?? 0}</span>
            </button>
          </nav>

          <div className="header-actions">
            <span
              className={`engine-status ${engineReady ? 'is-ready' : 'is-offline'}`}
              role="status"
              aria-label={engineReady ? 'Motor de descargas conectado' : 'Motor disponible en la aplicación de escritorio'}
              title={engineReady ? 'Motor conectado' : 'Solo escritorio'}
            >
              {engineReady
                ? <Activity className="engine-status-icon" size={15} strokeWidth={2} aria-hidden="true" />
                : <CircleAlert className="engine-status-icon" size={15} strokeWidth={1.8} aria-hidden="true" />}
              <span className="engine-status-text">{engineReady ? 'Motor conectado' : 'Solo escritorio'}</span>
            </span>
            <button ref={settingsTrigger} className="settings-button" type="button" aria-label="Ajustes" onClick={() => setSettingsOpen(true)} title="Ajustes">
              <Settings2 size={18} strokeWidth={1.7} aria-hidden="true" />
              <span className="sidebar-label">Ajustes</span>
            </button>
            <button
              className="settings-button sidebar-toggle"
              type="button"
              aria-label={sidebarCollapsed ? 'Expandir barra lateral' : 'Contraer barra lateral'}
              title={sidebarCollapsed ? 'Expandir barra lateral' : 'Contraer barra lateral'}
              aria-controls="app-sidebar"
              aria-expanded={!sidebarCollapsed}
              onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
            >
              {sidebarCollapsed
                ? <PanelLeftOpen size={18} strokeWidth={1.7} aria-hidden="true" />
                : <PanelLeftClose size={18} strokeWidth={1.7} aria-hidden="true" />}
              <span className="sidebar-label">Contraer barra</span>
            </button>
          </div>
        </div>
      </aside>

      <main className="main-content">
        {view === 'prepare' ? (
          <div className="preparation-view">
            <section className="page-intro">
              <div>
                <h1>Prepara tu descarga.</h1>
                <p>Pega un enlace. Revisa la lista. Guarda solo lo que quieras.</p>
              </div>
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
                      {analysis && <SourceMark sourceUrl={analysis.source_url} />}
                    </div>
                    <p>{analysis ? `${analysis.items.length} elementos · ${analysis.extractor || 'yt-dlp'}` : 'El manifiesto aparecerá aquí después del análisis'}</p>
                  </div>
                  {analysis && <div className="playlist-heading-actions">
                    <span className="availability-summary">{availableItems.length} disponibles</span>
                  </div>}
                </header>

                {analysis ? (
                  <>
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
                            const isPreviewOpen = previewItem?.id === item.id
                            return (
                              <tr className={`${checked ? 'is-selected' : ''} ${!item.available ? 'is-unavailable' : ''}`} key={item.id}>
                                <td className="check-cell"><label className="row-check">
                                  <input type="checkbox" checked={checked} disabled={!item.available} onChange={() => toggleItem(item.id)} aria-label={`Seleccionar ${item.title}`} />
                                  <span className="custom-check" aria-hidden="true"><Check size={12} strokeWidth={2.5} /></span>
                                </label></td>
                                <td className="title-cell">
                                  <button
                                    className="thumbnail-preview"
                                    type="button"
                                    aria-label={`Abrir vista previa de ${item.title} en YouTube`}
                                    aria-current={isPreviewOpen || undefined}
                                    title={`Reproducir ${item.title}`}
                                    disabled={!youtubeVideoIdPattern.test(item.source_id)}
                                    onClick={(event) => openPreview(item, event.currentTarget)}
                                  >
                                    <span className="thumbnail-fallback" aria-hidden="true"><ListVideo size={16} /></span>
                                    {item.thumbnail && <img src={item.thumbnail} alt="" onError={(event) => { event.currentTarget.style.visibility = 'hidden' }} />}
                                    <span className="thumbnail-play" aria-hidden="true">
                                      {isPreviewOpen ? <MonitorPlay size={19} /> : <Play size={14} fill="currentColor" />}
                                    </span>
                                  </button>
                                  <span className="item-copy">
                                    <span className="item-title">{item.title}</span>
                                    <span className="item-number">Elemento {String(item.index).padStart(2, '0')}</span>
                                  </span>
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

              <div className="workspace-side-column">
                <section ref={previewPanel} className="preview-panel" aria-labelledby="preview-panel-title" tabIndex={-1}>
                  <div className="preview-panel-heading">
                    <h2 id="preview-panel-title">Vista previa</h2>
                    {previewItem && <button
                      className="preview-close"
                      type="button"
                      aria-label="Cerrar vista previa"
                      onClick={closePreview}
                    ><X size={16} aria-hidden="true" /></button>}
                  </div>
                  <div className="preview-player">
                    {previewItem && previewLoadState !== 'error' ? (
                      <iframe
                        key={previewItem.source_id}
                        title={`Reproductor de YouTube: ${previewItem.title}`}
                        src={`https://www.youtube-nocookie.com/embed/${encodeURIComponent(previewItem.source_id)}?playsinline=1&rel=0`}
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                        allowFullScreen
                        loading="lazy"
                        referrerPolicy="strict-origin-when-cross-origin"
                        onLoad={() => setPreviewLoadState('loaded')}
                        onError={() => setPreviewLoadState('error')}
                      />
                    ) : previewItem && previewLoadState === 'error' ? (
                      <div className="preview-error" role="alert">
                        <CircleAlert size={19} aria-hidden="true" />
                        <span>No se pudo cargar el reproductor. Comprueba la conexión e inténtalo otra vez.</span>
                        <button type="button" onClick={() => openPreview(previewItem)}>Reintentar</button>
                      </div>
                    ) : (
                      <div className="preview-empty">
                        <span><Play size={19} fill="currentColor" aria-hidden="true" /></span>
                        <p>{analysis ? 'Pulsa la miniatura de un elemento para reproducirlo aquí.' : 'El reproductor aparecerá aquí al analizar un video o una playlist.'}</p>
                      </div>
                    )}
                  </div>
                  <div className="preview-info">
                    <h3>{previewItem?.title ?? 'Aún no hay ningún elemento abierto'}</h3>
                    {previewItem ? (
                      <>
                        <div className="preview-metadata">
                          <span>{formatDuration(previewItem.duration)}</span>
                          <span>YouTube</span>
                        </div>
                        {previewLoadState === 'loading' && <p className="preview-load-status" role="status">Conectando con YouTube…</p>}
                        <p>{previewLoadState === 'error'
                          ? 'Revisa la conexión y vuelve a intentarlo.'
                          : 'Vista previa en el reproductor oficial. No se guarda ningún archivo; algunos videos no permiten reproducción integrada.'}</p>
                      </>
                    ) : (
                      <p>Elige una miniatura de la lista para abrir el reproductor integrado.</p>
                    )}
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
                    {([['video', 'Video', 'MP4', Film], ['audio', 'Audio', 'MP3', Music2], ['both', 'Ambos', 'MP4 + MP3', Layers2]] as const).map(([value, label, detail, Icon]) => (
                      <button className={`format-option ${format === value ? 'is-active' : ''}`} type="button" aria-pressed={format === value} key={value} onClick={() => setFormat(value)}>
                        <span className="format-option-label"><Icon size={14} aria-hidden="true" />{label}</span>
                        <small>{detail}</small>
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
                <div className="history-tools">
                  <label className="history-search">
                    <Search size={15} aria-hidden="true" />
                    <span className="visually-hidden">Buscar por título o playlist</span>
                    <input
                      type="search"
                      aria-label="Buscar en el historial"
                      placeholder="Buscar en el historial"
                      value={historyQuery}
                      onChange={(event) => setHistoryQuery(event.target.value)}
                    />
                    {historyQuery && <button type="button" aria-label="Borrar búsqueda" onClick={() => setHistoryQuery('')}><X size={14} aria-hidden="true" /></button>}
                  </label>
                  <button className="secondary-action" type="button" disabled={!currentList.length} onClick={() => void clearHistory()}><Trash2 size={15} aria-hidden="true" />Limpiar historial</button>
                </div>
              ) : (
                <div className="queue-actions">
                  <button className="secondary-action" type="button" disabled={!queueState?.queue.some((item) => item.status === 'queued' || item.status === 'downloading')} onClick={() => void api?.pause_all()}><Pause size={15} aria-hidden="true" />Pausar todo</button>
                  <button className="secondary-action" type="button" disabled={!queueState?.queue.some((item) => item.status === 'paused')} onClick={() => void api?.resume_all()}><Play size={15} aria-hidden="true" />Reanudar</button>
                  <button className="secondary-action danger-action" type="button" disabled={!queueState?.queue.some((item) => ['queued', 'downloading', 'paused'].includes(item.status))} onClick={() => void cancelAll()}><X size={15} aria-hidden="true" />Cancelar todo</button>
                </div>
              )}
            </div>

            {visibleList.length ? (
              <div className="download-list">
                {visibleList.map((item) => (
                  <article className={`download-row ${view === 'history' ? 'is-history' : ''}`} key={item.id}>
                    <div className="download-row-main">
                      <div className="download-row-copy">
                        <div className="download-title-line">
                          <span className={`status-pill status-${item.status}`}>{statusLabel(item.status)}</span>
                          <h2>{item.title}</h2>
                          <SourceMark sourceUrl={item.source_url} />
                        </div>
                        <p>{item.batch_title}</p>
                        {view === 'history' && <div className="history-metadata">
                          <span><Clock3 size={13} aria-hidden="true" />{formatDuration(item.duration)} de video</span>
                          <span><CalendarDays size={13} aria-hidden="true" />{formatTimestamp(item.completed_at)}</span>
                          <span><Timer size={13} aria-hidden="true" />Descarga: {formatElapsed(item.download_elapsed_seconds)}</span>
                        </div>}
                      </div>
                      <div className="download-row-actions">
                        {view === 'queue' && item.status === 'failed' && <button className="icon-action" type="button" title="Reintentar" aria-label={`Reintentar ${item.title}`} onClick={() => void api?.retry_item(item.id)}><RotateCcw size={16} /></button>}
                        {view === 'queue' && item.status !== 'failed' && <button className="icon-action" type="button" title="Cancelar elemento" aria-label={`Cancelar ${item.title}`} onClick={() => void api?.cancel_item(item.id)}><X size={16} /></button>}
                      </div>
                    </div>
                    {view === 'queue' && item.status === 'downloading' && <DownloadProgress item={item} />}
                    {view === 'queue' && item.status !== 'downloading' && (item.download_elapsed_seconds ?? 0) > 0 && (
                      <div className="queue-elapsed"><Timer size={13} aria-hidden="true" />Tiempo descargando: {formatElapsed(item.download_elapsed_seconds)}</div>
                    )}
                    {item.error && (isDiskSpaceError(item.error) ? (
                      <div className="download-space-warning" role="alert">
                        <HardDrive size={17} aria-hidden="true" />
                        <div>
                          <strong>Espacio insuficiente</strong>
                          <p>{item.error}</p>
                          <span>Libera espacio en la unidad de destino y vuelve a intentar este elemento.</span>
                        </div>
                      </div>
                    ) : <p className={`download-row-message ${item.status === 'failed' ? 'is-error' : ''}`}>{item.error}</p>)}
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
                <h2>{view === 'history'
                  ? currentList.length && historyQuery ? 'No hay coincidencias' : 'Aún no hay lotes finalizados'
                  : 'La cola está vacía'}</h2>
                <p>{view === 'history'
                  ? currentList.length && historyQuery ? 'Prueba con otro título o nombre de playlist.' : 'Los elementos descargados aparecerán aquí.'
                  : 'Analiza un enlace y prepara tu primer lote para verlo aquí.'}</p>
                {view === 'history' && currentList.length > 0 && historyQuery && <button className="return-button" type="button" onClick={() => setHistoryQuery('')}>Limpiar búsqueda<X size={14} aria-hidden="true" /></button>}
                {view === 'queue' && <button className="return-button" type="button" onClick={() => setView('prepare')}>Preparar una descarga<ArrowRight size={15} aria-hidden="true" /></button>}
              </section>
            )}
          </section>
        )}
      </main>

      {notice && <NoticeToast key={notice} message={notice} onDismiss={clearNotice} />}

      {settingsOpen && <SettingsDialog backdropRef={settingsBackdrop} firstRun={!preferences.concurrency_mode} preferences={preferences} onClose={closeSettings} onAccentPreview={setPreviewAccent} onSave={(value) => void savePreferences(value)} />}

      {closeConfirmOpen && <div ref={closeBackdrop} className="modal-backdrop" role="presentation">
        <section className="dialog-panel close-dialog" role="dialog" aria-modal="true" aria-labelledby="close-title">
          <button className="dialog-close" type="button" aria-label="Volver a la app" onClick={returnFromCloseDialog}><X size={18} /></button>
          <span className="dialog-icon"><CircleAlert size={20} /></span>
          <h2 id="close-title">Hay descargas pendientes</h2>
          <p>{trayAvailable ? 'Puedes dejarlas funcionando en segundo plano o pausarlas para continuar más tarde.' : 'Puedes pausar las descargas y continuar más tarde.'}</p>
          <div className="dialog-actions vertical-actions">
            {trayAvailable && <button className="primary-dialog-action" type="button" onClick={() => void closeInBackground()}>Seguir en segundo plano</button>}
            <button className="secondary-dialog-action" type="button" onClick={() => void pauseAndClose()}>Pausar y cerrar</button>
            <button className="text-dialog-action" type="button" onClick={returnFromCloseDialog}>Volver a la app</button>
          </div>
        </section>
      </div>}
    </div>
  )
}

function SettingsDialog({
  backdropRef,
  firstRun,
  preferences,
  onClose,
  onAccentPreview,
  onSave,
}: {
  backdropRef: RefObject<HTMLDivElement | null>
  firstRun: boolean
  preferences: Preferences
  onClose: () => void
  onAccentPreview: (accent: ThemeAccent) => void
  onSave: (value: Partial<Preferences>) => void
}) {
  const [themeMode, setThemeMode] = useState<NonNullable<Preferences['theme_mode']>>(
    preferences.theme_mode ?? 'system',
  )
  const [accent, setAccent] = useState<ThemeAccent>(preferences.theme_accent ?? 'clipoteca')
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
      theme_mode: themeMode,
      theme_accent: accent,
      concurrency_mode: mode,
      ...(mode === 'manual'
        ? { manual_concurrency: selectedCount }
        : { auto_concurrency_cap: selectedCount }),
    })
  }

  return <div ref={backdropRef} className="modal-backdrop" role="presentation">
    <form className="dialog-panel settings-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-title" onSubmit={submit}>
      <button className="dialog-close" type="button" aria-label="Cerrar ajustes" onClick={onClose}><X size={18} /></button>
      <h2 id="settings-title">{firstRun ? 'Configura tu primera cola' : 'Ajustes de descarga'}</h2>
      <p>{firstRun ? 'Elige cuántas descargas pueden ejecutarse a la vez. Podrás cambiarlo después.' : 'La concurrencia automática se adapta al rendimiento hasta el valor que tú elijas.'}</p>
      <label className="dialog-label" htmlFor="theme-mode">Apariencia</label>
      <div className="select-shell">
        <select id="theme-mode" value={themeMode} onChange={(event) => setThemeMode(event.target.value as NonNullable<Preferences['theme_mode']>)}>
          <option value="system">Seguir Windows</option>
          <option value="dark">Oscuro</option>
          <option value="light">Claro</option>
        </select>
        <ChevronDown size={15} aria-hidden="true" />
      </div>
      <fieldset className="accent-field">
        <legend>Color de acento</legend>
        <div className="accent-options">
          {accentOptions.map(([value, label]) => (
            <label key={value} className="accent-option">
              <input
                type="radio"
                name="theme-accent"
                value={value}
                checked={accent === value}
                onChange={() => {
                  setAccent(value)
                  onAccentPreview(value)
                }}
              />
              <span className="accent-swatch" data-accent={value}>
                <span className="accent-dot" aria-hidden="true"><Check size={14} strokeWidth={2.5} /></span>
                <span>{label}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <label className="dialog-label" htmlFor="concurrency-mode">Modo de concurrencia</label>
      <div className="select-shell">
        <select id="concurrency-mode" value={mode} onChange={(event) => setMode(event.target.value as '' | 'auto' | 'manual')}>
          <option value="" disabled>Elige cómo ejecutar la cola</option>
          <option value="auto">Automático</option>
          <option value="manual">Manual</option>
        </select>
        <ChevronDown size={15} aria-hidden="true" />
      </div>
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
