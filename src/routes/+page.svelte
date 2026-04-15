<script lang="ts">
	import { onMount } from 'svelte';
	import {
		Header, HeaderNav, HeaderNavItem, SkipToContent,
		Button, Slider, Tile, Tag, InlineNotification
	} from 'carbon-components-svelte';
	import ChevronUp from 'carbon-icons-svelte/lib/ChevronUp.svelte';
	import ChevronDown from 'carbon-icons-svelte/lib/ChevronDown.svelte';
	import ChevronLeft from 'carbon-icons-svelte/lib/ChevronLeft.svelte';
	import ChevronRight from 'carbon-icons-svelte/lib/ChevronRight.svelte';
	import LogoInstagram from 'carbon-icons-svelte/lib/LogoInstagram.svelte';
	import {
		CAMERA_CONTROLS,
		PAN_STEP, TILT_STEP,
		PAN_MIN, PAN_MAX,
		TILT_MIN, TILT_MAX,
		ZOOM_MIN, ZOOM_MAX
	} from '$lib/controls.js';

	let { data } = $props();

	let pan = $state(0);
	let tilt = $state(0);
	let zoom = $state(ZOOM_MIN);
	let mouseControlActive = $state(false);
	let initializing = $state(false);
	let temperature = $state<number | null>(null);
	let humidity = $state<number | null>(null);
	let showNotification = $state(true);
	let videoContainer = $state<HTMLDivElement | null>(null);
	let controlValues = $state(
		Object.fromEntries(CAMERA_CONTROLS.map((c) => [c.name, c.default]))
	);

	let lastMouseSend = 0;

	async function sendControl(control: string, value: number) {
		await fetch('/api/control', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ control, value })
		}).catch(() => {});
	}

	function panLeft()  { pan  = Math.max(PAN_MIN,  pan  - PAN_STEP);  sendControl('pan_absolute',  pan);  }
	function panRight() { pan  = Math.min(PAN_MAX,  pan  + PAN_STEP);  sendControl('pan_absolute',  pan);  }
	function tiltUp()   { tilt = Math.min(TILT_MAX, tilt + TILT_STEP); sendControl('tilt_absolute', tilt); }
	function tiltDown() { tilt = Math.max(TILT_MIN, tilt - TILT_STEP); sendControl('tilt_absolute', tilt); }

	function handleMouseMove(e: MouseEvent) {
		if (!mouseControlActive || !videoContainer) return;
		const now = Date.now();
		if (now - lastMouseSend < 50) return;
		lastMouseSend = now;
		const rect = videoContainer.getBoundingClientRect();
		pan  = PAN_MIN  + ((e.clientX - rect.left) / rect.width)     * (PAN_MAX  - PAN_MIN);
		tilt = TILT_MIN + (1 - (e.clientY - rect.top) / rect.height) * (TILT_MAX - TILT_MIN);
		sendControl('pan_absolute',  pan);
		sendControl('tilt_absolute', tilt);
	}

	function handleWheel(e: WheelEvent) {
		if (!mouseControlActive) return;
		e.preventDefault();
		zoom = e.deltaY < 0 ? Math.min(ZOOM_MAX, zoom + 2.5) : Math.max(ZOOM_MIN, zoom - 2.5);
		sendControl('zoom_absolute', zoom);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Shift' && !e.repeat) mouseControlActive = !mouseControlActive;
	}

	async function loadCameraState() {
		try {
			const res = await fetch('/api/camera_state');
			if (!res.ok) return;
			const state = await res.json();
			if (!state.values) return;
			const v = state.values;
			initializing = true;
			if (v.pan_absolute  !== undefined) pan  = v.pan_absolute;
			if (v.tilt_absolute !== undefined) tilt = v.tilt_absolute;
			if (v.zoom_absolute !== undefined) zoom = v.zoom_absolute;
			for (const ctrl of CAMERA_CONTROLS) {
				if (v[ctrl.name] !== undefined) controlValues[ctrl.name] = v[ctrl.name];
			}
		} catch {} finally {
			initializing = false;
		}
	}

	onMount(() => {
		loadCameraState();
		const evtSource = new EventSource('/api/temp');
		evtSource.onmessage = (e) => {
			try {
				const data = JSON.parse(e.data);
				if (typeof data.temperature === 'number' && !isNaN(data.temperature)) {
					temperature = data.temperature;
					humidity = data.humidity;
				}
			} catch {}
		};
		const notifTimeout = setTimeout(() => { showNotification = false; }, 7000);
		return () => { evtSource.close(); clearTimeout(notifTimeout); };
	});
</script>

<svelte:head>
	<title>Snail Cam</title>
	<meta property="og:title" content="Snail Cam — Live Snail Feed" />
	<meta property="og:description" content="Watch my snail live. Also on Instagram @lucians_snails." />
	<meta property="og:image" content="{data.origin}/api/latest-snapshot" />
	<meta property="og:image:type" content="image/jpeg" />
	<meta property="og:type" content="website" />
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content="Snail Cam — Live Snail Feed" />
	<meta name="twitter:description" content="Watch my snail live. Also on Instagram @lucians_snails." />
	<meta name="twitter:image" content="{data.origin}/api/latest-snapshot" />
</svelte:head>
<svelte:window onkeydown={handleKeydown} />

<Header company="Snail" platformName="Cam" href="/">
	<svelte:fragment slot="skip-to-content">
		<SkipToContent />
	</svelte:fragment>
	<HeaderNav>
		<HeaderNavItem href="/snapshots" text="View Snapshots" />
	</HeaderNav>
	<svelte:fragment slot="header-utilities">
		<a
			href="https://www.instagram.com/lucians_snails"
			target="_blank"
			rel="noopener noreferrer"
			class="instagram-btn"
			aria-label="Instagram @lucians_snails"
		>
			<LogoInstagram size={20} />
		</a>
	</svelte:fragment>
</Header>

<div class="page-body">
	<div
		class="video-container"
		role="application"
		aria-label="Camera view — use buttons or hold SHIFT for mouse pan/tilt"
		bind:this={videoContainer}
		onmousemove={handleMouseMove}
		onwheel={handleWheel}
	>
		<div class="stats-overlay">
			<Tile>
				<p class="stat-row">TEMP <span class="stat-val">{temperature !== null ? temperature.toFixed(1) : '--'}°F</span></p>
				<p class="stat-row">HUMID <span class="stat-val">{humidity !== null ? humidity.toFixed(1) : '--'}%</span></p>
			</Tile>
		</div>

		{#if showNotification}
			<div class="notice-overlay">
				<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
				<InlineNotification
					kind="info"
					title="Tip:"
					subtitle="Press SHIFT to toggle mouse control for pan / tilt / zoom"
					on:close={() => { showNotification = false; }}
				/>
			</div>
		{/if}

		{#if mouseControlActive}
			<div class="badge-overlay">
				<Tag type="blue">Mouse Control Active — SHIFT to disable</Tag>
			</div>
		{/if}

		<img id="camera-stream" src="/api/video_feed" alt="Live camera stream" />

		<div class="overlay-controls" aria-hidden="true">
			<div class="ctrl-top">
				<Button hasIconOnly kind="tertiary" icon={ChevronUp}    iconDescription="Tilt Up"    class="dir-btn" on:click={tiltUp}   />
			</div>
			<div class="ctrl-left">
				<Button hasIconOnly kind="tertiary" icon={ChevronLeft}  iconDescription="Pan Left"   class="dir-btn" on:click={panLeft}  />
			</div>
			<div class="ctrl-right">
				<Button hasIconOnly kind="tertiary" icon={ChevronRight} iconDescription="Pan Right"  class="dir-btn" on:click={panRight} />
			</div>
			<div class="ctrl-bottom">
				<Button hasIconOnly kind="tertiary" icon={ChevronDown}  iconDescription="Tilt Down"  class="dir-btn" on:click={tiltDown} />
			</div>
		</div>

		<div class="zoom-overlay">
			<div class="zoom-row">
				<span class="zoom-label">Zoom</span>
				<input
					class="zoom-range"
					type="range"
					min={ZOOM_MIN}
					max={ZOOM_MAX}
					step={1}
					value={zoom}
					oninput={(e) => { zoom = Number((e.target as HTMLInputElement).value); sendControl('zoom_absolute', zoom); }}
				/>
				<span class="zoom-val">{zoom}</span>
			</div>
		</div>
	</div>

	<div class="controls-panel">
		{#each CAMERA_CONTROLS as ctrl (ctrl.name)}
			<div class="ctrl-item">
				<Slider
					labelText={ctrl.label}
					min={ctrl.min}
					max={ctrl.max}
					step={ctrl.step}
					value={controlValues[ctrl.name]}
					on:change={(e) => {
						controlValues[ctrl.name] = e.detail;
						if (!initializing) sendControl(ctrl.name, e.detail);
					}}
				/>
			</div>
		{/each}
	</div>
</div>

<style>
	.instagram-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 3rem;
		height: 3rem;
		color: #ffffff;
		text-decoration: none;
		transition: background-color 0.15s;
	}

	.instagram-btn:hover {
		background-color: rgba(255, 255, 255, 0.15);
	}

	.page-body {
		padding-top: 3rem;
		display: flex;
		flex-direction: column;
	}

	.video-container {
		position: relative;
		width: 100%;
		height: calc(100vh - 3rem);
		display: flex;
		justify-content: center;
		align-items: center;
		overflow: hidden;
		background: #000000;
	}

	#camera-stream {
		display: block;
		max-width: 100%;
		max-height: 100%;
		object-fit: contain;
	}

	.stats-overlay {
		position: absolute;
		top: 16px;
		left: 16px;
		z-index: 200;
		pointer-events: none;
	}

	:global(.stats-overlay .bx--tile) {
		padding: 10px 14px;
		background: rgba(255, 255, 255, 0.92);
		min-width: 0;
	}

	.stat-row {
		margin: 2px 0;
		font-family: 'IBM Plex Mono', monospace;
		font-size: 0.75rem;
		font-weight: 600;
		color: #525252;
		line-height: 1.4;
	}

	.stat-val {
		color: #0f62fe;
	}

	.notice-overlay {
		position: absolute;
		top: 16px;
		left: 50%;
		transform: translateX(-50%);
		z-index: 300;
		white-space: nowrap;
	}

	.badge-overlay {
		position: absolute;
		top: 80px;
		left: 16px;
		z-index: 200;
	}

	.overlay-controls {
		position: absolute;
		inset: 0;
		z-index: 10;
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		grid-template-rows: 1fr 1fr 1fr;
		padding: 20px;
		pointer-events: none;
	}

	.ctrl-top, .ctrl-left, .ctrl-right, .ctrl-bottom {
		pointer-events: auto;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.ctrl-top    { grid-column: 2; grid-row: 1; align-items: flex-start; }
	.ctrl-left   { grid-column: 1; grid-row: 2; justify-content: flex-start; }
	.ctrl-right  { grid-column: 3; grid-row: 2; justify-content: flex-end; }
	.ctrl-bottom { grid-column: 2; grid-row: 3; align-items: flex-end; }

	:global(.dir-btn.bx--btn--tertiary) {
		background: rgba(255, 255, 255, 0.9) !important;
	}

	:global(.dir-btn.bx--btn--tertiary:hover) {
		background: #0f62fe !important;
		color: #ffffff !important;
	}

	.zoom-overlay {
		position: absolute;
		bottom: 20px;
		left: 20px;
		z-index: 20;
		background: rgba(255, 255, 255, 0.92);
		border: 1px solid #e0e0e0;
		padding: 10px 14px;
		width: 260px;
		box-sizing: border-box;
	}

	.zoom-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.zoom-label {
		font-size: 0.75rem;
		color: #525252;
		white-space: nowrap;
	}

	.zoom-range {
		flex: 1;
		min-width: 0;
		-webkit-appearance: none;
		appearance: none;
		height: 2px;
		background: #c6c6c6;
		border-radius: 0;
		outline: none;
		cursor: pointer;
	}

	.zoom-range::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: #0f62fe;
		cursor: pointer;
		border: none;
	}

	.zoom-range::-moz-range-thumb {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: #0f62fe;
		cursor: pointer;
		border: none;
	}

	.zoom-val {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 0.75rem;
		color: #161616;
		white-space: nowrap;
		min-width: 2rem;
		text-align: right;
	}

	.controls-panel {
		border-top: 1px solid #e0e0e0;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 1px;
		background-color: #e0e0e0;
	}

	.ctrl-item {
		background: #ffffff;
		padding: 1rem 1.25rem 0.75rem;
		min-width: 0;
	}

	:global(.ctrl-item .bx--form-item) {
		width: 100%;
	}

	:global(.ctrl-item .bx--slider-container) {
		width: 100%;
		min-width: 0;
	}

	:global(.ctrl-item .bx--slider) {
		min-width: 0;
	}
</style>
