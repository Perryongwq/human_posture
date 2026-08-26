<!-- frontend/src/views/PostureV3View.vue -->
<!-- Carousel station tracking. Four detections, live overlay. See goal.md.

     1. gloved operator  MediaPipe PoseLandmarker -> wrist landmarks 15/16.
        BODY pose, never hands: hand-landmark models score 0/91 frames on a white
        glove against this white fixture. The body model marks the wrist *joint*
        and the glove is on the hand below it, so it never has to see the glove.
        Needs the operator's torso in frame -- a body model cannot build a
        skeleton from a bare forearm reaching in from the edge.
     2. ring             backend, classical CV. Hub + radius + 10 tag positions.
     3. letters          backend, qwen3-vl + alphabetical ring fit.
     4. stations         wrist bearing from hub -> wedge -> letter (carousel.js).

     3 runs ONCE at Calibrate (a ~4 min VLM pass) — no model runs after that.
     2 runs LIVE but cheap: every ~300 ms /ring re-detects the ring with hub+radius
     LOCKED from calibration, so only the rotation is searched; carryLetters then
     turns the calibrated letters rigidly by the median tag rotation (liveRing.js).
     The overlay follows the carousel without drift or per-frame OCR. 1 and 4 run
     every frame.

     Direction (put-in vs take-out) is NOT detected -- it needs a grip signal and
     no model produces one on this glove. The +/- buttons are the counted path. -->
<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { MuStat } from '@/components/ui/mu-stat'
import { MuAlert } from '@/components/ui/mu-alert'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { apiClient } from '@/api/client.js'
import { stationOf } from '@/lib/carousel.js'
import { carryLetters } from '@/lib/liveRing.js'

const STATIONS = [...'ABCDEFGHIJ']
const WRISTS = [15, 16]                                        // MediaPipe Pose wrist landmarks
const ARM_BONES = [[11, 13], [13, 15], [12, 14], [14, 16], [11, 12]]
const MIN_MARGIN = 2        // vote gap below which the letter fit is not trusted

const video = ref(null)
const canvas = ref(null)
const error = ref('')
const loading = ref(true)
const cameraOn = ref(false)
const fps = ref(0)
const mode = ref('camera')          // 'camera' | 'images'
const peopleDetected = ref(0)

const cameras = ref([])
const cameraId = ref(localStorage.getItem('posture.camera') || '')

// ── calibration: ring + letters, from the backend, once per stop ────
const CAL_KEY = 'posture.v3.calibration'
const cal = ref(JSON.parse(localStorage.getItem(CAL_KEY) || 'null'))
const calState = ref('')            // '' | 'busy' | 'ok' | 'unsure' | 'failed'
const calInfo = ref('')
const calibrated = computed(() => !!cal.value?.tags?.length)

// ── live detection ──────────────────────────────────────────────────
const activeStation = ref(null)     // letter, from the wrist; sticky through occlusion
const liveHands = ref([])           // [{side, x, y, letter, offDeg}] for the overlay

// ── runtime ring: the VLM reads letters ONCE at calibration; after that only the
// cheap ring rotation is tracked (no model), so the overlay turns with the carousel.
const RING_MS = 300                 // ring re-detection cadence (~0.03 s server-side)
let liveCal = cal.value             // calibrated ring, rotated to follow the carousel — what draw() uses
const ringState = ref('')           // '' | 'live' | 'searching' | 'stale'

// ── counting ────────────────────────────────────────────────────────
// Manual, and staying manual: telling put-in from take-out needs a grip signal
// (open vs closed hand) and no available model produces one on this glove.
const tally = reactive(Object.fromEntries(STATIONS.map(l => [l, { in: 0, out: 0 }])))
const sessionActive = ref(false)
const sessionStart = ref(null)
const saveState = ref('')
const lastEvent = ref('')
const history = ref([])

const totalIn = () => Object.values(tally).reduce((s, t) => s + t.in, 0)
const totalOut = () => Object.values(tally).reduce((s, t) => s + t.out, 0)

function count(dir) {
  if (!sessionActive.value || !activeStation.value) return
  tally[activeStation.value][dir]++
  lastEvent.value = `Station ${activeStation.value}: ${dir === 'in' ? 'put in' : 'taken out'}`
}

function startSession() {
  STATIONS.forEach(l => { tally[l].in = 0; tally[l].out = 0 })
  sessionStart.value = new Date()
  saveState.value = ''
  lastEvent.value = ''
  sessionActive.value = true
}

async function stopSession() {
  sessionActive.value = false
  saveState.value = 'saving'
  try {
    await apiClient.post('/posture/sessions', {
      started_at: sessionStart.value.toISOString(),
      ended_at: new Date().toISOString(),
      place_count: totalIn(),
      left_count: 0,
      // ponytail: reusing v1's fixed schema — right_count doubles as totalOut,
      // the real per-station breakdown lives in settings.tally
      right_count: totalOut(),
      settings: {
        schema: 'v3-station',
        tally: JSON.parse(JSON.stringify(tally)),
        calibration: liveCal,
      },
    })
    saveState.value = 'saved'
    loadHistory()
  } catch {
    saveState.value = 'failed'
  }
}

async function loadHistory() {
  try {
    history.value = (await apiClient.get('/posture/sessions')).data
      .filter(s => s.settings?.schema === 'v3-station')
  } catch { /* non-critical */ }
}

const fmt = iso => new Date(iso).toLocaleString()

// ── camera + pose model ─────────────────────────────────────────────
let landmarker = null
let stream = null
let rafId = 0
let lastSource = null               // <video> or <img> the loop last saw — calibration source

async function listCameras() {
  cameras.value = (await navigator.mediaDevices.enumerateDevices())
    .filter(d => d.kind === 'videoinput')
}

async function onCameraChange() {
  localStorage.setItem('posture.camera', cameraId.value)
  if (cameraOn.value) { stopCamera(); await startCamera() }
}

async function init() {
  try {
    const { FilesetResolver, PoseLandmarker } = await import('@mediapipe/tasks-vision')
    const base = import.meta.env.BASE_URL
    const fileset = await FilesetResolver.forVisionTasks(`${base}mediapipe/wasm`)
    landmarker = await PoseLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: `${base}mediapipe/pose_landmarker_lite.task`, delegate: 'GPU' },
      runningMode: 'VIDEO',
      numPoses: 2,        // operator plus the occasional passer-by; the reach check filters them
      // ponytail: lowered from the 0.5 default — top-down framing crops the body
      // hard. Raise if passers-by start stealing the active station.
      minPoseDetectionConfidence: 0.3,
      minPosePresenceConfidence: 0.3,
      minTrackingConfidence: 0.3,
    })
    loading.value = false
  } catch (e) {
    error.value = `Failed to load body tracking model: ${e.message}`
    loading.value = false
  }
}

async function startCamera() {
  stopTestImages()
  mode.value = 'camera'
  try {
    const size = { width: { ideal: 1920 }, height: { ideal: 1080 } }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { ...(cameraId.value ? { deviceId: { exact: cameraId.value } } : {}), ...size },
        audio: false,
      })
    } catch (e) {
      if (!cameraId.value) throw e
      cameraId.value = ''
      stream = await navigator.mediaDevices.getUserMedia({ video: size, audio: false })
    }
    video.value.srcObject = stream
    await video.value.play()
    // play() can resolve before the frame size is known; a 0x0 canvas feeds
    // MediaPipe a 0x0 ROI and crashes the pose graph. Wait for real dimensions.
    if (!video.value.videoWidth) {
      await new Promise(res => video.value.addEventListener('loadedmetadata', res, { once: true }))
    }
    await listCameras()
    canvas.value.width = video.value.videoWidth
    canvas.value.height = video.value.videoHeight
    cameraOn.value = true
    lastFrameTime = performance.now()
    loop()
  } catch (e) {
    error.value = `Camera access failed: ${e.message}`
  }
}

function stopCamera() {
  cancelAnimationFrame(rafId)
  stream?.getTracks().forEach(t => t.stop())
  cameraOn.value = false
  if (sessionActive.value) stopSession()
}

// ── test images: replay a photo burst through the same pipeline ─────
const testFiles = ref([])
const testIndex = ref(0)
const testPlaying = ref(false)
let testTimer = null
let syntheticNow = 0
// Running tally over the frames stepped through, so a burst says something as a whole
// and not just frame-by-frame. Only updated from showTestFrame — never from the live
// camera loop, which would count 30 "frames" a second.
const testStats = reactive({ seen: 0, withPerson: 0, withStation: 0 })

function onTestFilesChosen(e) {
  const files = [...e.target.files].sort((a, b) => a.name.localeCompare(b.name))
  if (!files.length) return
  stopCamera()
  stopTestImages()
  mode.value = 'images'
  testFiles.value = files.map(f => ({ name: f.name, url: URL.createObjectURL(f) }))
  testIndex.value = 0
  Object.assign(testStats, { seen: 0, withPerson: 0, withStation: 0 })
  showTestFrame(0)
}

function showTestFrame(i) {
  const entry = testFiles.value[i]
  if (!entry || !landmarker) return
  const img = new Image()
  img.onload = () => {
    canvas.value.width = img.naturalWidth
    canvas.value.height = img.naturalHeight
    syntheticNow += 100        // MediaPipe only needs a monotonically increasing timestamp
    peopleDetected.value = processFrame(img, syntheticNow)
    testStats.seen++
    if (peopleDetected.value) testStats.withPerson++
    if (liveHands.value.length) testStats.withStation++
  }
  img.src = entry.url
}

function nextTestFrame() {
  if (testIndex.value >= testFiles.value.length - 1) {
    testPlaying.value = false; clearInterval(testTimer); return
  }
  showTestFrame(++testIndex.value)
}
function prevTestFrame() { if (testIndex.value > 0) showTestFrame(--testIndex.value) }
function toggleTestPlay() {
  testPlaying.value = !testPlaying.value
  if (testPlaying.value) testTimer = setInterval(nextTestFrame, 300)
  else clearInterval(testTimer)
}
function stopTestImages() {
  clearInterval(testTimer)
  testPlaying.value = false
  testFiles.value.forEach(f => URL.revokeObjectURL(f.url))
  testFiles.value = []
  if (sessionActive.value) stopSession()
}

// ── calibrate: one frame -> ring + letters ──────────────────────────
function frameToBase64(source, maxW = Infinity, q = 0.92) {
  const w = source.videoWidth ?? source.naturalWidth
  const h = source.videoHeight ?? source.naturalHeight
  const sc = Math.min(1, maxW / w)
  const c = document.createElement('canvas')
  c.width = Math.round(w * sc); c.height = Math.round(h * sc)
  c.getContext('2d').drawImage(source, 0, 0, c.width, c.height)
  return c.toDataURL('image/jpeg', q).split(',')[1]
}
const aspectOf = source =>
  (source.videoHeight ?? source.naturalHeight) / (source.videoWidth ?? source.naturalWidth)

async function calibrate() {
  if (!lastSource) {
    calState.value = 'failed'
    calInfo.value = 'Start the camera (or load test images) first.'
    return
  }
  calState.value = 'busy'
  calInfo.value = 'Finding the ring and reading the letters — 40 model calls, a few minutes…'
  try {
    const { data } = await apiClient.post('/posture/calibrate', {
      image: frameToBase64(lastSource), stations: STATIONS.length,
    })
    if (data.margin < MIN_MARGIN) {
      calState.value = 'unsure'
      calInfo.value = `Letters too ambiguous to trust (margin ${data.margin}, need ${MIN_MARGIN}). `
        + `Raw reads: ${Object.values(data.reads).map(v => v.join('') || '—').join(' ')}. `
        + 'Re-frame the fixture or improve lighting, then calibrate again.'
      return
    }
    cal.value = { hub: data.hub, radius: data.radius, tags: data.tags, margin: data.margin }
    localStorage.setItem(CAL_KEY, JSON.stringify(cal.value))
    liveCal = cal.value
    activeStation.value = null
    calState.value = 'ok'
    calInfo.value = `Ring + ${data.tags.length} letters found (margin ${data.margin}, ${data.model}): `
      + data.tags.map(t => t.letter).join(' ')
  } catch (e) {
    calState.value = 'failed'
    calInfo.value = `Calibration failed: ${e.response?.data?.detail ?? e.message}. `
      + 'Is Ollama running on the backend host?'
  }
}

function clearCalibration() {
  cal.value = null
  liveCal = null
  ringState.value = ''
  activeStation.value = null
  localStorage.removeItem(CAL_KEY)
  calState.value = ''
  calInfo.value = ''
}

// ── runtime ring: re-detect from the image, carry the letters over ──
let ringTimer = 0, ringBusy = false
async function ringTick() {
  if (liveCal && lastSource && !ringBusy) {
    ringBusy = true
    try {
      const { data } = await apiClient.post('/posture/ring', {
        image: frameToBase64(lastSource, 960, 0.8), stations: STATIONS.length,
        hub: cal.value.hub, radius: cal.value.radius,   // lock geometry: track rotation only
      })
      const carried = carryLetters(liveCal, data, aspectOf(lastSource))
      if (carried) { liveCal = carried; ringState.value = 'live' }
      else ringState.value = 'searching'      // too few tags visible this frame: hold, don't guess
    } catch { ringState.value = 'stale' }
    ringBusy = false
  }
  ringTimer = setTimeout(ringTick, RING_MS)
}

// ── per-frame detection ─────────────────────────────────────────────
let lastVideoTime = -1
let lastFrameTime = 0

function processFrame(source, now) {
  lastSource = source
  const result = landmarker.detectForVideo(source, now)
  const { width: W, height: H } = canvas.value
  const aspect = H / W          // normalized y -> x units, so bearings aren't skewed

  liveHands.value = result.landmarks.flatMap(lm =>
    WRISTS.map((i, k) => {
      const p = lm[i]
      if (!p) return null
      const st = stationOf(p, liveCal, { aspect })
      return st && {
        side: k ? 'R' : 'L', x: p.x, y: p.y,
        letter: st.letter, offDeg: st.offDeg, reach: st.reach,
      }
    }).filter(Boolean))

  // Sticky: a wrist leaving every wedge does NOT clear the station, so the count
  // buttons stay usable while the arm is briefly occluded or out of frame.
  const hit = liveHands.value[0]
  if (hit) activeStation.value = hit.letter

  draw(source, result.landmarks)
  return result.landmarks.length
}

function loop() {
  rafId = requestAnimationFrame(loop)
  const v = video.value
  if (!v || !v.videoWidth || !v.videoHeight) return   // no frame yet: MediaPipe rejects a 0x0 ROI
  if (v.currentTime === lastVideoTime) return
  lastVideoTime = v.currentTime
  const now = performance.now()
  fps.value = Math.round(1000 / (now - lastFrameTime))
  lastFrameTime = now
  peopleDetected.value = processFrame(v, now)
}

// ── annotation ──────────────────────────────────────────────────────
const RING = '#00c8ff', TAG = '#ffd400', TAG_ON = '#22c55e', BONE = '#ff8c00', HAND = '#22c55e'

function outlined(ctx, text, x, y, size, colour) {
  ctx.font = `bold ${size}px sans-serif`
  ctx.lineWidth = size / 4
  ctx.strokeStyle = 'rgba(0,0,0,.85)'
  ctx.strokeText(text, x, y)
  ctx.fillStyle = colour
  ctx.fillText(text, x, y)
}

function draw(source, poses) {
  const ctx = canvas.value.getContext('2d')
  const { width: W, height: H } = canvas.value
  ctx.clearRect(0, 0, W, H)
  if (mode.value === 'images') ctx.drawImage(source, 0, 0, W, H)

  // ring + lettered tags — liveCal, so the overlay turns with the carousel
  if (liveCal) {
    const { hub, radius, tags } = liveCal
    const hx = hub.x * W, hy = hub.y * H
    ctx.strokeStyle = RING
    ctx.lineWidth = 3
    ctx.beginPath()
    ctx.ellipse(hx, hy, radius * W, radius * W, 0, 0, Math.PI * 2)   // circle in x-units
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(hx - 14, hy); ctx.lineTo(hx + 14, hy)
    ctx.moveTo(hx, hy - 14); ctx.lineTo(hx, hy + 14)
    ctx.stroke()
    for (const t of tags) {
      const on = t.letter === activeStation.value
      const x = t.x * W, y = t.y * H
      ctx.strokeStyle = on ? TAG_ON : TAG
      ctx.lineWidth = on ? 5 : 3
      ctx.beginPath(); ctx.arc(x, y, W * 0.022, 0, Math.PI * 2); ctx.stroke()
      outlined(ctx, t.letter, x - W * 0.011, y - W * 0.028, W * 0.032, on ? TAG_ON : TAG)
    }
  }

  // operator skeleton
  ctx.strokeStyle = BONE
  ctx.lineWidth = 5
  for (const lm of poses) {
    for (const [a, b] of ARM_BONES) {
      if (!lm[a] || !lm[b]) continue
      ctx.beginPath()
      ctx.moveTo(lm[a].x * W, lm[a].y * H)
      ctx.lineTo(lm[b].x * W, lm[b].y * H)
      ctx.stroke()
    }
  }

  // wrist -> station
  for (const h of liveHands.value) {
    const x = h.x * W, y = h.y * H
    ctx.strokeStyle = HAND
    ctx.lineWidth = 4
    ctx.beginPath(); ctx.arc(x, y, 20, 0, Math.PI * 2); ctx.stroke()
    outlined(ctx, `${h.side} wrist → ${h.letter}`, x + 26, y - 14, W * 0.022, HAND)
  }
}

onMounted(() => { init(); listCameras(); loadHistory(); ringTick() })
onBeforeUnmount(() => {
  stopCamera(); stopTestImages(); clearTimeout(ringTimer)
})
</script>

<template>
  <div class="murata space-y-6 max-w-5xl mx-auto">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold">Carousel Station Tracking</h1>
      <div class="mu-row gap-2">
        <Badge v-if="cameraOn" variant="ok">{{ fps }} FPS</Badge>
        <Badge :variant="peopleDetected > 0 ? 'ok' : 'neutral'">{{ peopleDetected }} person(s)</Badge>
        <Badge :variant="calibrated ? 'ok' : 'danger'">
          {{ calibrated ? `ring + ${cal.tags.length} letters` : 'not calibrated' }}
        </Badge>
        <Badge v-if="calibrated" :variant="ringState === 'live' ? 'ok' : 'neutral'">
          ring {{ ringState || 'starting' }}
        </Badge>
      </div>
    </div>

    <MuAlert
      variant="info"
      title="Start the camera and press Calibrate once — the ring and the station letters are found automatically. From then on the ring is re-detected from the live image several times a second and the letters are re-read in the background, so they stay on their stations as the carousel turns. Then just work: the station lights up as your wrist reaches into it. Aim the camera so your torso is in shot with the carousel; body tracking cannot lock on to a forearm alone."
    />
    <MuAlert v-if="error" variant="err" :title="error" />
    <MuAlert v-if="loading" variant="info" title="Loading body tracking model…" />

    <div class="relative inline-block w-full">
      <video v-show="mode === 'camera'" ref="video" class="w-full rounded-lg bg-black" playsinline muted></video>
      <canvas
        ref="canvas"
        :class="mode === 'images' ? 'w-full rounded-lg bg-black' : 'absolute inset-0 w-full h-full'"
      ></canvas>
    </div>

    <div class="mu-row flex-wrap gap-2">
      <select
        v-if="cameras.length > 1" v-model="cameraId"
        class="select select-sm select-bordered" @change="onCameraChange"
      >
        <option value="">Default camera</option>
        <option v-for="(c, i) in cameras" :key="c.deviceId" :value="c.deviceId">
          {{ c.label || `Camera ${i + 1}` }}
        </option>
      </select>

      <Button v-if="!cameraOn" variant="primary" :disabled="loading || !!error" @click="startCamera">
        Start Camera
      </Button>
      <Button v-else variant="secondary" @click="stopCamera">Stop Camera</Button>

      <Button variant="secondary" :disabled="calState === 'busy' || loading" @click="calibrate">
        {{ calState === 'busy' ? 'Calibrating…' : 'Calibrate (ring + letters)' }}
      </Button>
      <Button v-if="calibrated" variant="ghost" size="sm" @click="clearCalibration">Clear</Button>

      <Button v-if="!sessionActive" variant="primary" :disabled="!calibrated" @click="startSession">
        Start Session
      </Button>
      <Button v-else variant="danger" @click="stopSession">Stop Session</Button>

      <Badge v-if="saveState === 'saved'" variant="ok">Session saved</Badge>
      <Badge v-if="saveState === 'failed'" variant="danger">Save failed</Badge>

      <label class="text-sm">
        <input type="file" accept="image/*" multiple class="hidden" @change="onTestFilesChosen" />
        <Button variant="ghost" size="sm" as="span" :disabled="loading">Load Test Images…</Button>
      </label>
      <template v-if="mode === 'images'">
        <Button variant="ghost" size="sm" :disabled="testIndex === 0" @click="prevTestFrame">◀</Button>
        <Button variant="ghost" size="sm" @click="toggleTestPlay">{{ testPlaying ? 'Pause' : 'Play' }}</Button>
        <Button variant="ghost" size="sm" :disabled="testIndex >= testFiles.length - 1" @click="nextTestFrame">▶</Button>
        <span class="text-sm text-gray-500">
          {{ testIndex + 1 }}/{{ testFiles.length }} — {{ testFiles[testIndex]?.name }}
        </span>
      </template>
    </div>

    <MuAlert
      v-if="calInfo"
      :variant="{ ok: 'ok', unsure: 'warn', failed: 'err' }[calState] || 'info'"
      :title="calInfo"
    />

    <!-- image-testing readout: the annotated canvas above shows *where*, this shows
         *what*. Without it you cannot tell a missed detection from a wrong one. -->
    <section v-if="mode === 'images'" class="rounded-lg border p-3 space-y-2">
      <div class="flex items-center justify-between flex-wrap gap-2">
        <span class="font-bold text-sm">Test frame {{ testIndex + 1 }}/{{ testFiles.length }}</span>
        <span class="text-xs font-mono text-gray-500">{{ testFiles[testIndex]?.name }}</span>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
        <div><span class="text-gray-500">Ring:</span>
          <span :class="calibrated ? 'text-green-600' : 'text-red-600'">
            {{ calibrated ? `${cal.tags.length} tags` : 'not calibrated' }}
          </span>
        </div>
        <div><span class="text-gray-500">Letters:</span>
          <span class="font-mono">{{ calibrated ? cal.tags.map(t => t.letter).join('') : '—' }}</span>
        </div>
        <div><span class="text-gray-500">People:</span>
          <span :class="peopleDetected ? 'text-green-600' : 'text-red-600'">{{ peopleDetected }}</span>
        </div>
        <div><span class="text-gray-500">Station:</span>
          <span class="font-bold">{{ activeStation ?? '—' }}</span>
        </div>
      </div>

      <Table v-if="liveHands.length">
        <TableHeader>
          <TableRow>
            <TableHead>Wrist</TableHead><TableHead>Station</TableHead>
            <TableHead>Bearing error</TableHead><TableHead>Reach</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="(h, i) in liveHands" :key="i">
            <TableCell class="font-bold">{{ h.side }}</TableCell>
            <TableCell class="font-bold">{{ h.letter }}</TableCell>
            <!-- a wedge is 36 deg wide, so under 18 is an unambiguous assignment -->
            <TableCell :class="h.offDeg < 18 ? '' : 'text-amber-600'">
              {{ h.offDeg.toFixed(1) }}°
            </TableCell>
            <TableCell>{{ h.reach.toFixed(2) }}×</TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <p v-else class="text-sm text-gray-500">
        {{ !calibrated ? 'Calibrate on a frame first — no ring means no station lookup.'
           : peopleDetected ? 'Person found, but no wrist within reach of the fixture.'
           : 'No person detected — is the operator’s torso in this frame?' }}
      </p>

      <p class="text-xs text-gray-500">
        Stepped {{ testStats.seen }} frame(s): {{ testStats.withPerson }} with a person,
        {{ testStats.withStation }} with a wrist at a station.
        <template v-if="calibrated">
          Ring rotation tracked live ({{ ringState || 'starting' }}); letters are from the
          last calibration — recalibrate if they visibly sit off their tags.
        </template>
      </p>
    </section>

    <!-- counting — manual, and staying manual: direction needs a grip signal
         that no model produces on this glove (goal.md) -->
    <div v-if="sessionActive" class="mu-row gap-2 items-center">
      <Button variant="primary" :disabled="!activeStation" @click="count('in')">+ Put In</Button>
      <Button variant="secondary" :disabled="!activeStation" @click="count('out')">+ Take Out</Button>
      <span v-if="!activeStation" class="text-sm text-gray-500">
        Reach into a station to select it
      </span>
    </div>

    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <MuStat :value="activeStation ?? '—'" label="Active station" />
      <MuStat :value="totalIn()" label="Total put in" />
      <MuStat :value="totalOut()" label="Total taken out" />
      <MuStat :value="cal?.margin ?? '—'" label="Letter confidence" />
    </div>
    <p v-if="lastEvent" class="text-sm font-mono text-gray-500">{{ lastEvent }}</p>

    <template v-if="sessionActive">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Station</TableHead><TableHead>Put in</TableHead><TableHead>Taken out</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="letter in STATIONS" :key="letter">
            <TableCell class="font-bold">{{ letter }}</TableCell>
            <TableCell>{{ tally[letter].in }}</TableCell>
            <TableCell>{{ tally[letter].out }}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </template>

    <section v-if="history.length">
      <h2 class="font-bold mb-2">Session History</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Started</TableHead><TableHead>Put in</TableHead>
            <TableHead>Taken out</TableHead><TableHead>By</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="s in history" :key="s.id">
            <TableCell>{{ fmt(s.started_at) }}</TableCell>
            <TableCell class="font-bold">{{ s.place_count }}</TableCell>
            <TableCell>{{ s.right_count }}</TableCell>
            <TableCell>{{ s.payroll }}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </section>
  </div>
</template>
