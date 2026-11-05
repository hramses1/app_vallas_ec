<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import BackButton from './BackButton.vue'
import BillboardSign from './BillboardSign.vue'
import { prettyName } from './format.js'
import Icon from './Icon.vue'
import MapView from './MapView.vue'
import ReportForm from './ReportForm.vue'

const TYPES = { estatica: 'Estática', digital: 'Digital', puente: 'Puente peatonal', mupi: 'Mupi', movil: 'Móvil' }
const UNITS = { dia: 'día', hora: 'hora', mes: 'mes' }
const LIST_SIZE = 100
const MOBILE_WIDTH = 800
const SHEET_TOP_GAP = 56
const SHEET_HANDLE = 30
const SHEET_PEEK = 204
// Recuadros aproximados: sur, oeste, norte, este
const ZONES = {
  Guayaquil: [-2.3, -80.02, -2.03, -79.86],
  Samborondón: [-2.14, -79.89, -2.05, -79.83],
  Durán: [-2.22, -79.85, -2.16, -79.78],
  'Todo el país': [-5.0, -81.1, 1.5, -75.2],
}
const COUNTRY = ZONES['Todo el país']

const filters = reactive({ q: '', provider: '', types: [], minPrice: '', maxPrice: '', exactOnly: false })
const bounds = ref(null)
const features = ref([])
const unlocated = ref([])
const providers = ref([])
const selected = ref(null)
const focus = ref(null)
const hovered = ref(null)
const tab = ref('map')
const reporting = ref(false)
const reportPoint = ref(null)
const loading = ref(false)
const loadedOnce = ref(false)
const error = ref('')
const mapView = ref(null)
const panel = ref(null)
const scroller = ref(null)

const viewport = reactive({ width: window.innerWidth, height: window.innerHeight })
const sheet = ref('peek')
const dragVisible = ref(null)

let pendingMap = null
let pendingList = null
let timer = null
let dragStart = null

const isMobile = computed(() => viewport.width <= MOBILE_WIDTH)
const sheetSizes = computed(() => ({
  peek: SHEET_PEEK,
  half: Math.round(viewport.height * 0.52),
  full: viewport.height - SHEET_TOP_GAP,
}))
const sheetVisible = computed(() => dragVisible.value ?? sheetSizes.value[sheet.value])
const panelStyle = computed(() =>
  isMobile.value
    ? {
        '--sheet-height': `${viewport.height - SHEET_TOP_GAP}px`,
        '--sheet-offset': `${viewport.height - SHEET_TOP_GAP - sheetVisible.value}px`,
        '--sheet-visible': `${sheetVisible.value - SHEET_HANDLE}px`,
      }
    : {},
)
const bottomInset = computed(() => (isMobile.value ? sheetSizes.value[sheet.value] : 0))

const isExact = (feature) => feature.properties.location_precision === 'exacta'
// Buscar por texto o empresa no depende de lo que se ve en el mapa
const searching = computed(() => Boolean(filters.q.trim() || filters.provider))
const exactCount = computed(() => features.value.filter(isExact).length)
// Exactas primero: son las que se pueden visitar sin buscar
const listed = computed(() =>
  [...features.value].sort((a, b) => Number(isExact(b)) - Number(isExact(a))).slice(0, LIST_SIZE),
)
const rows = computed(() => (tab.value === 'map' ? listed.value : unlocated.value.slice(0, LIST_SIZE)))
const advancedCount = computed(
  () =>
    (filters.provider ? 1 : 0) +
    (filters.types.length ? 1 : 0) +
    (filters.minPrice !== '' || filters.maxPrice !== '' ? 1 : 0) +
    (filters.exactOnly ? 1 : 0),
)
const hasFilters = computed(() => Boolean(filters.q.trim()) || advancedCount.value > 0)
const showSkeleton = computed(() => tab.value === 'map' && !loadedOnce.value && !error.value)

function buildQuery(base) {
  const params = new URLSearchParams(base)
  if (filters.q.trim()) params.set('q', filters.q.trim())
  if (filters.provider) params.set('provider', filters.provider)
  filters.types.forEach((type) => params.append('type', type))
  if (filters.minPrice !== '') params.set('min_price', filters.minPrice)
  if (filters.maxPrice !== '') params.set('max_price', filters.maxPrice)
  if (filters.exactOnly) params.set('precision', 'exacta')
  return params
}

async function loadMap(fit = false) {
  if (!bounds.value) return
  pendingMap?.abort()
  const controller = new AbortController()
  pendingMap = controller
  loading.value = true
  try {
    const base = searching.value ? { limit: 5000 } : bounds.value
    const response = await fetch(`/api/billboards?${buildQuery(base)}`, { signal: controller.signal })
    if (!response.ok) throw new Error(String(response.status))
    features.value = (await response.json()).features
    error.value = ''
    loadedOnce.value = true
    if (fit && searching.value) mapView.value?.fitFeatures(features.value)
  } catch (failure) {
    if (failure.name === 'AbortError') return
    error.value = 'No se pudieron cargar las vallas. Revisa tu conexión e inténtalo de nuevo.'
  }
  loading.value = false
}

// Las vallas sin punto no cambian al mover el mapa: solo se piden cuando cambian los filtros
async function loadUnlocated() {
  pendingList?.abort()
  if (filters.exactOnly) {
    unlocated.value = []
    return
  }
  const controller = new AbortController()
  pendingList = controller
  try {
    const response = await fetch(`/api/billboards?${buildQuery({ located: false, limit: 5000 })}`, {
      signal: controller.signal,
    })
    if (response.ok) unlocated.value = (await response.json()).features
  } catch (failure) {
    if (failure.name !== 'AbortError') unlocated.value = []
  }
}

function onBounds(next) {
  bounds.value = next
  if (searching.value) return
  clearTimeout(timer)
  timer = setTimeout(() => loadMap(), 250)
}

function onFiltersChanged() {
  clearTimeout(timer)
  timer = setTimeout(() => {
    loadMap(true)
    loadUnlocated()
  }, 250)
}

function clearFilters() {
  Object.assign(filters, { q: '', provider: '', types: [], minPrice: '', maxPrice: '', exactOnly: false })
}

function goToZone(zone) {
  mapView.value?.fitZone(ZONES[zone])
}

function startReport() {
  selected.value = null
  reportPoint.value = null
  reporting.value = true
  sheet.value = 'half'
  showTop()
}

function locateReport(point) {
  reportPoint.value = point
  focus.value = point
}

function stopReport() {
  reporting.value = false
  reportPoint.value = null
}

function showTop() {
  scroller.value?.scrollTo(0, 0)
}

// Desde la lista se acerca el mapa; al volver, regresa a donde estaba
function pick(feature) {
  hovered.value = null
  selected.value = feature
  sheet.value = 'half'
  showTop()
  if (!feature.geometry) return
  mapView.value?.saveView()
  const [lng, lat] = feature.geometry.coordinates
  focus.value = { lat, lng }
}

function selectFromMap(id) {
  selected.value = features.value.find((feature) => feature.properties.id === id) ?? null
  sheet.value = 'half'
  showTop()
}

function closeCard() {
  selected.value = null
  mapView.value?.restoreView()
}

function onEscape(event) {
  if (event.key !== 'Escape') return
  if (reporting.value) stopReport()
  else if (selected.value) closeCard()
}

function onResize() {
  viewport.width = window.innerWidth
  viewport.height = window.innerHeight
}

// Panel inferior en móvil: se arrastra entre tres alturas, o se alterna con un toque
function startDrag(event) {
  dragStart = { y: event.clientY, visible: sheetSizes.value[sheet.value], moved: false }
  event.currentTarget.setPointerCapture(event.pointerId)
}

function moveDrag(event) {
  if (!dragStart) return
  const delta = dragStart.y - event.clientY
  if (Math.abs(delta) > 4) dragStart.moved = true
  if (dragStart.moved) {
    dragVisible.value = Math.min(sheetSizes.value.full, Math.max(SHEET_HANDLE + 40, dragStart.visible + delta))
  }
}

function endDrag() {
  if (!dragStart) return
  if (dragStart.moved) {
    const nearest = Object.entries(sheetSizes.value).sort(
      (a, b) => Math.abs(a[1] - dragVisible.value) - Math.abs(b[1] - dragVisible.value),
    )[0][0]
    sheet.value = nearest
  } else {
    cycleSheet()
  }
  dragVisible.value = null
  dragStart = null
}

function cycleSheet() {
  sheet.value = { peek: 'half', half: 'full', full: 'peek' }[sheet.value]
}

watch(filters, onFiltersChanged)

onMounted(async () => {
  window.addEventListener('keydown', onEscape)
  window.addEventListener('resize', onResize)
  loadUnlocated()
  try {
    providers.value = await (await fetch('/api/providers')).json()
  } catch {
    // El filtro de empresa queda vacío; el mapa avisa si la API no responde
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onEscape)
  window.removeEventListener('resize', onResize)
})

const priceAmount = ({ price_usd }) => (price_usd === null ? null : `$${price_usd.toLocaleString('es-EC')}`)
const priceUnit = ({ price_unit }) => `por ${UNITS[price_unit] ?? price_unit}`
const size = ({ width_m, height_m }) =>
  width_m && height_m ? `${String(width_m).replace('.', ',')} × ${String(height_m).replace('.', ',')} m` : ''

function precisionText(billboard) {
  if (!billboard.location_precision) {
    return 'Todavía no tiene punto en el mapa. Usa la dirección y confirma el sitio con la empresa.'
  }
  if (billboard.source === 'reporte' && billboard.location_precision !== 'exacta') {
    return 'Punto marcado por un usuario y revisado. Aún sin confirmar en el sitio.'
  }
  if (billboard.location_precision !== 'exacta') {
    return 'El punto marca la vía o el lugar citado, no la valla. Puede estar lejos: confirma el sitio con la empresa.'
  }
  return billboard.verified_at
    ? 'Ubicación exacta confirmada por revisión.'
    : billboard.source === 'cne_2023'
      ? 'Coordenadas registradas por la empresa en el CNE en 2023. Aún sin confirmar en el sitio.'
      : 'Coordenadas de la fuente. Aún sin confirmar en el sitio.'
}

function directionsUrl(feature) {
  const { location_precision, address } = feature.properties
  const [lng, lat] = feature.geometry?.coordinates ?? []
  const destination = location_precision === 'exacta' ? `${lat},${lng}` : `${prettyName(address)}, Ecuador`
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`
}

const precisionLabel = ({ location_precision }) =>
  ({ exacta: 'Ubicación exacta', aproximada: 'Ubicación aproximada' })[location_precision] ?? 'Sin ubicar en el mapa'

function rowDetails(billboard) {
  const precision = precisionLabel(billboard)
  const dimensions = size(billboard)
  return dimensions ? `${dimensions}, ${precision.toLowerCase()}` : precision
}

const hasContact = ({ contact_phone, contact_email, provider_website }) =>
  Boolean(contact_phone || contact_email || provider_website)
const companySearchUrl = ({ provider_name }) =>
  `https://www.google.com/search?q=${encodeURIComponent(`${provider_name} vallas publicitarias Ecuador contacto`)}`
const telHref = (phone) => `tel:${phone.split(/ext/i)[0].replace(/[^\d+]/g, '')}`
</script>

<template>
  <div class="layout">
    <main class="map-area">
      <MapView
        ref="mapView"
        :features="features"
        :selected-id="selected?.properties.id ?? null"
        :hovered-id="hovered"
        :focus="focus"
        :reporting="reporting"
        :report-point="reportPoint"
        :bottom-inset="bottomInset"
        @report-point="reportPoint = $event"
        @bounds="onBounds"
        @select="selectFromMap"
      />
      <p v-if="reporting && !reportPoint" class="map-hint" role="status">Toca el mapa donde está la valla</p>
      <button v-if="!reporting" class="report-pill" type="button" @click="startReport">
        <Icon name="plus" :size="16" /> ¿Viste una valla que falta?
      </button>
      <div class="legend" aria-label="Qué significa cada marca del mapa">
        <span><i class="pin"></i> Ubicación exacta</span>
        <span><i class="pin pin--approximate"></i> Aproximada</span>
        <span><i class="cluster cluster--mini">3</i> Varias: haz clic para verlas</span>
      </div>
    </main>

    <aside ref="panel" class="panel" :class="{ 'panel--dragging': dragVisible !== null }" :style="panelStyle">
      <button
        class="handle"
        type="button"
        aria-label="Cambiar el tamaño del panel"
        @pointerdown="startDrag"
        @pointermove="moveDrag"
        @pointerup="endDrag"
        @pointercancel="endDrag"
        @keydown.enter.prevent="cycleSheet"
        @keydown.space.prevent="cycleSheet"
      ></button>

      <div ref="scroller" class="panel-scroll">
        <ReportForm
          v-if="reporting"
          :point="reportPoint"
          :types="TYPES"
          @close="stopReport"
          @locate="locateReport"
          @again="reportPoint = null"
        />

        <section v-else-if="selected" :key="selected.properties.id" class="card" aria-label="Ficha de la valla">
          <BackButton @click="closeCard" />

          <BillboardSign
            v-if="selected.properties.width_m && selected.properties.height_m"
            :key="selected.properties.id"
            :width="selected.properties.width_m"
            :height="selected.properties.height_m"
            :type="selected.properties.type"
          />

          <div class="card-head">
            <h2>{{ prettyName(selected.properties.provider_name) }}</h2>
            <p class="address">{{ prettyName(selected.properties.address) }}</p>
            <p class="card-price">
              <template v-if="priceAmount(selected.properties)">
                <strong>{{ priceAmount(selected.properties) }}</strong> {{ priceUnit(selected.properties) }}
              </template>
              <strong v-else>Precio por confirmar</strong>
            </p>
            <p class="muted">{{ [TYPES[selected.properties.type], size(selected.properties)].filter(Boolean).join(', ') }}</p>
          </div>

          <div class="actions">
            <a
              v-if="selected.properties.contact_phone"
              class="action action--primary"
              :href="telHref(selected.properties.contact_phone)"
            ><Icon name="phone" /> Llamar al {{ selected.properties.contact_phone }}</a>
            <a
              v-if="selected.properties.contact_email"
              class="action"
              :href="`mailto:${selected.properties.contact_email}`"
            ><Icon name="mail" /> Escribir a {{ selected.properties.contact_email }}</a>
            <a
              v-if="selected.properties.provider_website"
              class="action"
              :href="selected.properties.provider_website"
              target="_blank"
              rel="noopener"
            ><Icon name="globe" /> Abrir el sitio web de la empresa</a>
            <template v-if="!hasContact(selected.properties)">
              <p class="muted">Todavía no tenemos el contacto de esta empresa.</p>
              <a class="action" :href="companySearchUrl(selected.properties)" target="_blank" rel="noopener">
                <Icon name="search" /> Buscar a la empresa en Google
              </a>
            </template>
            <a class="action" :href="directionsUrl(selected)" target="_blank" rel="noopener">
              <Icon name="route" />
              {{ selected.properties.location_precision === 'exacta' ? 'Cómo llegar' : 'Buscar la dirección en Google Maps' }}
            </a>
          </div>

          <div class="precision" :class="{ 'precision--exact': selected.properties.location_precision === 'exacta' }">
            <strong>{{ precisionLabel(selected.properties) }}</strong>
            <p>{{ precisionText(selected.properties) }}</p>
            <p v-if="selected.properties.location_precision === 'exacta'" class="coords">
              {{ selected.geometry.coordinates[1] }}, {{ selected.geometry.coordinates[0] }}
            </p>
          </div>

          <p v-if="selected.properties.provider_address" class="muted">
            Oficina de la empresa: {{ selected.properties.provider_address }}
          </p>
          <p class="muted">{{ selected.properties.notes }}. Confirma el precio actual con la empresa.</p>
        </section>

        <template v-else>
          <header class="brand">
            <h1>Mapa de vallas</h1>
            <p>Encuentra, ubica y contacta vallas publicitarias.</p>
          </header>

          <div class="search">
            <label for="search">Buscar</label>
            <span class="search-field">
              <Icon name="search" />
              <input
                id="search"
                v-model="filters.q"
                type="search"
                placeholder="Avenida, sector o empresa"
                autocomplete="off"
                @focus="sheet = 'full'"
              />
            </span>
          </div>

          <nav class="zones" aria-label="Ir a una zona del mapa">
            <button v-for="(_, zone) in ZONES" :key="zone" type="button" @click="goToZone(zone)">{{ zone }}</button>
          </nav>

          <details class="filters">
            <summary>
              <Icon name="filter" /> Más filtros<span v-if="advancedCount" class="badge">{{ advancedCount }}</span>
              <Icon class="filters-chevron" name="chevron" :size="16" />
            </summary>
            <form class="filter-fields" @submit.prevent>
              <label>
                Empresa
                <select v-model="filters.provider">
                  <option value="">Todas</option>
                  <option v-for="item in providers" :key="item.provider_name" :value="item.provider_name">
                    {{ prettyName(item.provider_name) }} ({{ item.billboards }})
                  </option>
                </select>
              </label>
              <fieldset class="chips">
                <legend>Tipo</legend>
                <label v-for="(label, value) in TYPES" :key="value" class="chip">
                  <input v-model="filters.types" type="checkbox" :value="value" />
                  <span>{{ label }}</span>
                </label>
              </fieldset>
              <fieldset class="prices">
                <legend>Tarifa por día, en dólares</legend>
                <label>Desde <input v-model="filters.minPrice" type="number" min="0" inputmode="numeric" /></label>
                <label>Hasta <input v-model="filters.maxPrice" type="number" min="0" inputmode="numeric" /></label>
              </fieldset>
              <label class="check">
                <input v-model="filters.exactOnly" type="checkbox" /> Solo con ubicación exacta
              </label>
            </form>
          </details>
          <button v-if="hasFilters" class="link" type="button" @click="clearFilters">Quitar filtros</button>

          <div v-if="error" class="notice" role="alert">
            <p>{{ error }}</p>
            <button class="link" type="button" @click="loadMap()">Reintentar</button>
          </div>
          <template v-else>
            <div class="tabs" role="group" aria-label="Qué vallas ver">
              <button type="button" :aria-pressed="tab === 'map'" @click="tab = 'map'">
                En el mapa ({{ features.length }})
              </button>
              <button type="button" :aria-pressed="tab === 'unlocated'" @click="tab = 'unlocated'">
                Sin ubicar ({{ unlocated.length }})
              </button>
            </div>

            <p v-if="tab === 'map'" class="summary" role="status">
              <strong>{{ features.length }}</strong>
              {{ searching ? 'vallas encontradas en el mapa' : 'vallas en esta zona del mapa' }},
              {{ exactCount }} con ubicación exacta<span v-if="loading" class="muted">. Actualizando...</span>
            </p>
            <p v-else class="summary">Vallas de todo el país que conocemos, pero aún sin un punto en el mapa.</p>

            <ul v-if="showSkeleton" class="skeleton" aria-hidden="true">
              <li v-for="n in 5" :key="n"><i></i><span><b></b><b></b><b></b></span></li>
            </ul>

            <div v-else-if="tab === 'map' && !features.length && !loading" class="notice">
              <p>{{ searching ? 'No encontramos vallas en el mapa con esa búsqueda.' : 'No hay vallas aquí con estos filtros.' }}</p>
              <button v-if="!searching" class="link" type="button" @click="mapView.fitZone(COUNTRY)">Ver todo el país</button>
              <button v-if="unlocated.length" class="link" type="button" @click="tab = 'unlocated'">
                Ver {{ unlocated.length }} sin ubicar
              </button>
            </div>

            <ul class="results">
              <li v-for="feature in rows" :key="feature.properties.id">
                <button
                  type="button"
                  @click="pick(feature)"
                  @mouseenter="hovered = feature.geometry ? feature.properties.id : null"
                  @mouseleave="hovered = null"
                  @focus="hovered = feature.geometry ? feature.properties.id : null"
                  @blur="hovered = null"
                >
                  <i v-if="feature.geometry" class="pin" :class="{ 'pin--approximate': !isExact(feature) }"></i>
                  <span class="row-main">
                    <strong>{{ prettyName(feature.properties.provider_name) }}</strong>
                    <span class="result-address">{{ prettyName(feature.properties.address) }}</span>
                    <span class="muted">{{ rowDetails(feature.properties) }}</span>
                  </span>
                  <span class="row-price">
                    <template v-if="priceAmount(feature.properties)">
                      <strong>{{ priceAmount(feature.properties) }}</strong>
                      <span class="muted">{{ priceUnit(feature.properties) }}</span>
                    </template>
                    <span v-else class="muted">Por confirmar</span>
                  </span>
                </button>
              </li>
            </ul>
            <p v-if="(tab === 'map' ? features : unlocated).length > LIST_SIZE" class="muted list-note">
              Se muestran {{ LIST_SIZE }}. {{ tab === 'map' ? 'Acerca el mapa o busca' : 'Busca' }} por avenida o empresa para ver el resto.
            </p>
          </template>

          <button class="report-cta" type="button" @click="startReport">
            <span class="report-icon"><Icon name="plus" /></span>
            <span>
              <strong>¿Viste una valla y no está aquí?</strong>
              <small>Repórtala para ponerla en el mapa. Tu ayuda es esencial.</small>
            </span>
          </button>
        </template>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-columns: 412px 1fr; height: 100dvh; }
.panel { grid-row: 1; grid-column: 1; min-height: 0; border-right: 1px solid var(--line); background: var(--surface); }
.panel-scroll { display: flex; flex-direction: column; gap: 12px; height: 100%; padding: 16px 16px 0; overflow-y: auto; }
.map-area { position: relative; grid-row: 1; grid-column: 2; min-height: 0; }
.handle { display: none; }

.brand {
  flex: none;
  padding: 11px 14px;
  background: var(--sign-green);
  color: var(--surface);
  border-radius: var(--radius-panel);
  box-shadow: inset 0 0 0 2px var(--sign-green), inset 0 0 0 3.5px rgb(255 255 255 / 85%);
}
.brand h1 { font-size: 21px; font-weight: 800; line-height: 1.15; }
.brand p { margin-top: 2px; font-size: 13px; line-height: 1.3; }

.search label { display: block; margin-bottom: 4px; font-size: 13px; font-weight: 600; }
.search-field { position: relative; display: block; }
.search-field > svg { position: absolute; top: 12px; left: 12px; color: var(--muted); pointer-events: none; }
.search-field input { padding-left: 38px; font-size: 16px; }

.zones { display: flex; flex: none; gap: 6px; overflow-x: auto; scrollbar-width: none; margin-inline: -2px; padding: 2px; }
.zones button {
  flex: none;
  min-height: 34px;
  padding: 5px 12px;
  background: var(--surface-soft);
  border: 0;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
  transition: background-color 150ms ease, transform 160ms var(--ease-out);
}
.zones button:hover { background: var(--line); }
.zones button:active { transform: scale(0.96); }

.filters summary { display: flex; align-items: center; gap: 6px; min-height: 32px; font-size: 14px; font-weight: 600; cursor: pointer; list-style: none; }
.filters summary::-webkit-details-marker { display: none; }
.filters-chevron { margin-left: 2px; color: var(--muted); transition: transform 200ms var(--ease-out); }
.filters[open] .filters-chevron { transform: rotate(180deg); }
.badge {
  display: inline-grid;
  place-items: center;
  min-width: 20px;
  height: 20px;
  background: var(--sign-green);
  border-radius: 10px;
  color: var(--surface);
  font-size: 12px;
  line-height: 1;
}
.filter-fields { display: grid; gap: 12px; margin-top: 8px; padding: 12px; background: var(--surface-soft); border-radius: var(--radius-panel); }
.filter-fields label { display: grid; gap: 4px; font-size: 13px; font-weight: 600; }
fieldset { display: flex; flex-wrap: wrap; gap: 6px; margin: 0; padding: 0; border: 0; }
legend { padding: 0; margin-bottom: 5px; font-size: 13px; font-weight: 600; }
.filter-fields .chip { position: relative; display: block; font-weight: 500; }
.chip input { position: absolute; inset: 0; margin: 0; opacity: 0; cursor: pointer; }
.chip span {
  display: block;
  padding: 6px 11px;
  background: var(--surface);
  border-radius: 999px;
  box-shadow: inset 0 0 0 1px #a9b5af;
  font-size: 13px;
  transition: background-color 150ms ease, color 150ms ease;
}
.chip input:checked + span { background: var(--sign-green); box-shadow: none; color: var(--surface); }
.chip input:focus-visible + span { outline: 3px solid var(--lane-yellow); outline-offset: 2px; }
.prices { flex-wrap: nowrap; gap: 8px; }
.prices label { flex: 1; min-width: 0; }
.filter-fields .check { display: flex; align-items: center; gap: 8px; font-weight: 500; font-size: 14px; }
.check input { width: 18px; height: 18px; accent-color: var(--sign-green); }

.tabs { display: grid; flex: none; grid-template-columns: 1fr 1fr; gap: 2px; padding: 3px; background: var(--surface-soft); border-radius: 10px; }
.tabs button {
  min-height: 38px;
  padding: 6px 4px;
  background: none;
  border: 0;
  border-radius: 7px;
  color: var(--muted);
  font-size: 14px;
  font-weight: 600;
  transition: background-color 150ms ease, color 150ms ease;
}
.tabs button:hover { color: var(--asphalt); }
.tabs button[aria-pressed='true'] { background: var(--surface); box-shadow: 0 1px 3px rgb(20 45 35 / 18%); color: var(--asphalt); }

.pin { flex: none; }
.summary { font-size: 14px; }
.muted { color: var(--muted); font-size: 13px; }
.notice { display: grid; gap: 6px; justify-items: start; padding: 12px; background: var(--surface-soft); border-radius: var(--radius-panel); }

.results { margin: 0 -8px; padding: 0; list-style: none; }
.results li + li { border-top: 1px solid var(--line); }
.results button {
  display: flex;
  gap: 10px;
  width: 100%;
  padding: 11px 8px;
  background: none;
  border: 0;
  border-radius: var(--radius-control);
  text-align: left;
  transition: background-color 120ms ease;
}
.results button:hover, .results button:focus-visible { background: var(--surface-soft); }
.results button:active { background: var(--line); }
.row-main { display: grid; flex: 1; gap: 1px; min-width: 0; }
.row-main strong { font-size: 14px; font-weight: 600; line-height: 1.3; }
.result-address { font-size: 13px; line-height: 1.35; overflow-wrap: anywhere; }
.row-price { display: grid; flex: none; align-content: start; justify-items: end; max-width: 84px; text-align: right; }
.row-price strong { font-size: 15px; font-weight: 800; }
.row-price .muted { font-size: 12px; line-height: 1.25; }
.results .pin { margin-top: 1px; }
.list-note { padding-bottom: 8px; }

.skeleton { display: grid; gap: 16px; margin: 4px 0; padding: 0; list-style: none; }
.skeleton li { display: flex; gap: 10px; }
.skeleton i { flex: none; width: 18px; height: 18px; background: var(--line); border-radius: 50%; }
.skeleton span { display: grid; flex: 1; gap: 6px; }
.skeleton b { display: block; height: 11px; background: var(--surface-soft); border-radius: 4px; animation: pulse 1.2s ease-in-out infinite alternate; }
.skeleton b:first-child { width: 58%; background: var(--line); }
.skeleton b:last-child { width: 40%; }
@keyframes pulse { to { opacity: 0.45; } }

.report-cta {
  position: sticky;
  bottom: 0;
  z-index: 2;
  display: flex;
  flex: none;
  align-items: center;
  gap: 12px;
  margin: auto -16px 0;
  padding: 11px 16px;
  background: var(--lane-yellow);
  border: 0;
  color: var(--asphalt);
  text-align: left;
  transition: background-color 150ms ease;
}
.report-cta:hover { background: var(--lane-yellow-hover); }
.report-cta > span:last-child { display: grid; }
.report-cta strong { font-size: 15px; font-weight: 800; }
.report-cta small { font-size: 13px; line-height: 1.3; }
.report-icon { display: grid; place-items: center; flex: none; width: 32px; height: 32px; background: var(--asphalt); border-radius: 50%; color: var(--lane-yellow); }

.report-pill {
  display: none;
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: var(--layer-map-ui);
  align-items: center;
  gap: 6px;
  min-height: 40px;
  padding: 8px 14px 8px 10px;
  background: var(--lane-yellow);
  border: 0;
  border-radius: 999px;
  box-shadow: var(--shadow-float);
  font-size: 14px;
  font-weight: 800;
}

.card { display: grid; gap: 12px; padding-bottom: 16px; animation: enter 200ms var(--ease-out); }
@keyframes enter { from { opacity: 0; transform: translateY(6px); } }
.card-head { display: grid; gap: 3px; }
.card h2 { font-size: 21px; font-weight: 800; line-height: 1.2; }
.address { font-size: 15px; overflow-wrap: anywhere; }
.card-price { margin-top: 5px; color: var(--muted); font-size: 15px; }
.card-price strong { color: var(--asphalt); font-size: 24px; font-weight: 800; letter-spacing: -0.02em; }

.link {
  align-self: flex-start;
  justify-self: start;
  padding: 2px 0;
  background: none;
  border: 0;
  color: var(--sign-green-dark);
  text-align: left;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.actions { display: grid; gap: 6px; }
.action {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 44px;
  padding: 9px 14px;
  background: var(--surface-soft);
  border-radius: var(--radius-control);
  color: var(--asphalt);
  font-weight: 600;
  text-align: center;
  text-decoration: none;
  overflow-wrap: anywhere;
  transition: background-color 150ms ease, transform 160ms var(--ease-out);
}
.action:hover { background: var(--line); }
.action:active { transform: scale(0.98); }
.action--primary { min-height: 48px; background: var(--sign-green); color: var(--surface); }
.action--primary:hover { background: var(--sign-green-dark); }

.precision { padding: 11px 13px; background: var(--lane-yellow-soft); border-radius: var(--radius-panel); font-size: 14px; }
.precision--exact { background: var(--sign-green-soft); }
.coords { margin-top: 4px; font-weight: 600; }

.map-hint {
  position: absolute;
  top: 12px;
  left: 50%;
  z-index: var(--layer-map-ui);
  transform: translateX(-50%);
  padding: 9px 15px;
  background: var(--asphalt);
  border-radius: var(--radius-control);
  box-shadow: var(--shadow-float);
  color: var(--surface);
  font-weight: 600;
  white-space: nowrap;
  pointer-events: none;
}

.legend {
  position: absolute;
  bottom: 24px;
  left: 12px;
  z-index: var(--layer-map-ui);
  display: grid;
  gap: 6px;
  padding: 9px 13px;
  background: var(--surface);
  border-radius: var(--radius-panel);
  box-shadow: var(--shadow-float);
  font-size: 13px;
  pointer-events: none;
}
.legend span { display: flex; align-items: center; gap: 8px; }
.cluster--mini { flex: none; width: 18px; height: 18px; border-width: 1px; font-size: 10px; font-style: normal; box-shadow: none; }

@media (max-width: 800px) {
  .layout { display: block; height: 100dvh; overflow: hidden; }
  .map-area { height: 100%; }
  .legend { display: none; }
  .report-pill { display: inline-flex; }
  .report-cta { display: none; }
  .brand { display: none; }
  /* En móvil, contactar queda antes que el anuncio de ejemplo */
  .card > * { order: 2; }
  .card > .back-bar, .card > .card-head { order: 0; }
  .card > .actions { order: 1; }
  .card > .sign { order: 2; }
  .card > .precision, .card > p { order: 3; }

  .panel {
    position: fixed;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: var(--layer-panel);
    height: var(--sheet-height);
    transform: translateY(var(--sheet-offset));
    border: 0;
    border-radius: 16px 16px 0 0;
    box-shadow: var(--shadow-sheet);
    transition: transform 320ms var(--ease-drawer);
    will-change: transform;
  }
  .panel--dragging { transition: none; }
  .handle {
    display: block;
    position: relative;
    width: 100%;
    height: 30px;
    background: none;
    border: 0;
    touch-action: none;
    cursor: grab;
  }
  .handle::before {
    content: '';
    position: absolute;
    top: 11px;
    left: 50%;
    width: 44px;
    height: 5px;
    margin-left: -22px;
    background: #a9b5af;
    border-radius: 3px;
  }
  .panel-scroll { height: auto; max-height: var(--sheet-visible); padding-top: 0; padding-bottom: 16px; }
}
</style>
