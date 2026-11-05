<script setup>
import L from 'leaflet'
import 'leaflet.markercluster'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  features: { type: Array, required: true },
  selectedId: { type: String, default: null },
  focus: { type: Object, default: null },
  reporting: { type: Boolean, default: false },
  reportPoint: { type: Object, default: null },
  hoveredId: { type: String, default: null },
  // Alto que tapa el panel en móvil: lo enfocado se centra en la parte visible
  bottomInset: { type: Number, default: 0 },
})
const emit = defineEmits(['bounds', 'select', 'report-point'])

const container = ref(null)
let map
let cluster
let selectedRing
let hoverRing
let resizeObserver
let reportPin
let shownIds = ''
let savedView = null

// Se arma con textContent: la dirección puede venir de un reporte de usuario
function tooltipContent(provider, address) {
  const element = document.createElement('div')
  const title = document.createElement('strong')
  title.textContent = provider
  element.append(title, document.createElement('br'), address)
  return element
}

const pinIcon = (exact) =>
  L.divIcon({
    className: '',
    html: `<div class="pin ${exact ? '' : 'pin--approximate'}"></div>`,
    iconSize: [18, 18],
  })

function clusterIcon(group) {
  const markers = group.getAllChildMarkers()
  // Verde solo si todas son exactas: un grupo mixto no debe parecer preciso
  const allExact = markers.every((marker) => marker.options.exact)
  return L.divIcon({
    className: '',
    html: `<div class="cluster ${allExact ? 'cluster--exact' : ''}" title="${markers.length} vallas: haz clic para verlas">${markers.length}</div>`,
    iconSize: [38, 38],
  })
}

function emitBounds() {
  if (!container.value.clientHeight) return
  const bounds = map.getBounds()
  emit('bounds', {
    min_lat: bounds.getSouth(),
    max_lat: bounds.getNorth(),
    min_lng: bounds.getWest(),
    max_lng: bounds.getEast(),
  })
}

function drawMarkers() {
  // Reconstruir solo si cambian las vallas: así no se cierran los grupos abiertos al mover el mapa
  const ids = props.features.map((feature) => feature.properties.id).join()
  if (ids === shownIds) return
  shownIds = ids
  cluster.clearLayers()
  cluster.addLayers(
    props.features.map((feature) => {
      const { id, provider_name, address, location_precision } = feature.properties
      const [lng, lat] = feature.geometry.coordinates
      const exact = location_precision === 'exacta'
      return L.marker([lat, lng], { icon: pinIcon(exact), alt: provider_name, exact })
        .bindTooltip(tooltipContent(provider_name, address), { direction: 'top', offset: [0, -8] })
        .on('click', () => emit('select', id))
    }),
  )
}

function drawSelection() {
  selectedRing?.remove()
  selectedRing = null
  const feature = props.features.find((item) => item.properties.id === props.selectedId)
  if (!feature) return
  const [lng, lat] = feature.geometry.coordinates
  selectedRing = L.circleMarker([lat, lng], {
    radius: 17,
    color: '#23282d',
    weight: 3,
    fill: false,
    interactive: false,
  }).addTo(map)
}

onMounted(() => {
  map = L.map(container.value, { zoomControl: false }).setView([-2.16, -79.89], 12)
  L.control.zoom({ position: 'topright' }).addTo(map)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© colaboradores de OpenStreetMap',
  }).addTo(map)
  cluster = L.markerClusterGroup({ iconCreateFunction: clusterIcon, showCoverageOnHover: false })
  map.addLayer(cluster)
  map.on('moveend', emitBounds)
  map.on('click', ({ latlng }) => {
    if (props.reporting) emit('report-point', { lat: latlng.lat, lng: latlng.lng })
  })
  // El contenedor puede medir 0 al montar: los límites solo valen cuando ya tiene tamaño
  resizeObserver = new ResizeObserver(() => {
    map.invalidateSize()
    emitBounds()
  })
  resizeObserver.observe(container.value)
  drawMarkers()
})

const fitOptions = () => ({ paddingTopLeft: [20, 20], paddingBottomRight: [20, props.bottomInset + 20] })

function fitZone([south, west, north, east]) {
  savedView = null
  map.fitBounds([[south, west], [north, east]], fitOptions())
}

function fitFeatures(features) {
  if (!features.length) return
  savedView = null
  const points = features.map(({ geometry: { coordinates: [lng, lat] } }) => [lat, lng])
  map.fitBounds(points, { ...fitOptions(), maxZoom: 15 })
}

function saveView() {
  savedView ??= { center: map.getCenter(), zoom: map.getZoom() }
}

function restoreView() {
  if (savedView) map.setView(savedView.center, savedView.zoom)
  savedView = null
}

defineExpose({ fitZone, fitFeatures, saveView, restoreView })

onBeforeUnmount(() => {
  resizeObserver.disconnect()
  map.remove()
})

watch(() => props.features, () => {
  drawMarkers()
  drawSelection()
})
watch(() => props.selectedId, drawSelection)
watch(() => props.reporting, (active) => {
  container.value.classList.toggle('map--reporting', active)
})
watch(() => props.reportPoint, (point) => {
  reportPin?.remove()
  reportPin = null
  if (!point) return
  reportPin = L.marker([point.lat, point.lng], {
    draggable: true,
    title: 'Punto de la valla reportada',
    alt: 'Punto de la valla reportada',
    icon: L.divIcon({ className: '', html: '<div class="report-pin"></div>', iconSize: [26, 26] }),
    zIndexOffset: 1000,
  }).addTo(map)
  reportPin.on('dragend', () => {
    const { lat, lng } = reportPin.getLatLng()
    emit('report-point', { lat, lng })
  })
  if (!map.getBounds().contains([point.lat, point.lng])) map.setView([point.lat, point.lng], 17)
})
watch(() => props.focus, (point) => {
  if (!point) return
  const zoom = Math.max(map.getZoom(), 17)
  const center = map.project([point.lat, point.lng], zoom).add([0, props.bottomInset / 2])
  map.setView(map.unproject(center, zoom), zoom)
})
watch(() => props.hoveredId, (id) => {
  hoverRing?.remove()
  hoverRing = null
  const feature = id && props.features.find((item) => item.properties.id === id)
  if (!feature) return
  const [lng, lat] = feature.geometry.coordinates
  hoverRing = L.circleMarker([lat, lng], { radius: 22, color: '#0b6e4f', weight: 3, fill: true, fillOpacity: 0.14, interactive: false }).addTo(map)
})
</script>

<template>
  <div ref="container" class="map" role="application" aria-label="Mapa de vallas publicitarias"></div>
</template>

<style scoped>
.map { width: 100%; height: 100%; }
.map--reporting { cursor: crosshair; }
</style>
