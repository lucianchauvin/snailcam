<script lang="ts">
	import { onMount } from 'svelte';
	import {
		Header, HeaderNav, HeaderNavItem, SkipToContent,
		ContentSwitcher, Switch
	} from 'carbon-components-svelte';

	interface ClimateEntry {
		ts: number;
		t: string;
		temp: number;
		hum: number | null;
	}

	// ── Live readings ────────────────────────────────────────────────────────
	let liveTemp = $state<number | null>(null);
	let liveHum  = $state<number | null>(null);

	// ── Historical data ──────────────────────────────────────────────────────
	let entries  = $state<ClimateEntry[]>([]);
	let loading  = $state(true);
	let errorMsg = $state('');

	const RANGES     = ['1h', '6h', '24h', '7d', '30d', 'all'] as const;
	const RANGE_HOURS: Record<string, number | null> = { '1h': 1, '6h': 6, '24h': 24, '7d': 168, '30d': 720, 'all': null };
	let rangeIdx = $state(0);
	const range  = $derived(RANGES[rangeIdx]);

	async function loadData(r: string) {
		loading  = true;
		errorMsg = '';
		try {
			const hours = RANGE_HOURS[r];
			const res  = await fetch(hours ? `/api/climate?hours=${hours}` : '/api/climate');
			const data = await res.json();
			entries  = data.entries ?? [];
		} catch {
			errorMsg = 'Failed to load climate data.';
		} finally {
			loading = false;
		}
	}

	$effect(() => { void loadData(range); });

	// ── Chart constants ──────────────────────────────────────────────────────
	const W   = 1000;
	const H   = 340;
	const PAD = { top: 28, right: 68, bottom: 52, left: 68 };
	const CW  = W - PAD.left - PAD.right;   // 864
	const CH  = H - PAD.top  - PAD.bottom;  // 260

	// ── Derived chart values ─────────────────────────────────────────────────
	const hasData = $derived(entries.length > 0);
	const xMin    = $derived(hasData ? entries[0].ts                       : Date.now() - 86_400_000);
	const xMax    = $derived(hasData ? entries[entries.length - 1].ts      : Date.now());
	const xSpan   = $derived(Math.max(xMax - xMin, 1));

	const tempVals = $derived(entries.map(e => e.temp));
	const humVals  = $derived(entries.filter(e => e.hum !== null).map(e => e.hum as number));
	const hasHum   = $derived(humVals.length > 0);

	// Nice-ish axis bounds – add a little padding on each side
	const tMin = $derived(hasData ? Math.floor(Math.min(...tempVals)) - 2 : 60);
	const tMax = $derived(hasData ? Math.ceil (Math.max(...tempVals)) + 2 : 90);
	const hMin = $derived(hasHum  ? Math.floor(Math.min(...humVals))  - 3 : 30);
	const hMax = $derived(hasHum  ? Math.ceil (Math.max(...humVals))  + 3 : 100);

	// ── Scale helpers (read reactive values, called inside $derived) ─────────
	function xs(ts: number)   { return PAD.left + ((ts - xMin)  / xSpan)              * CW; }
	function ts_(t:  number)  { return PAD.top  + (1 - (t - tMin) / Math.max(tMax - tMin, 1)) * CH; }
	function hs(h:  number)   { return PAD.top  + (1 - (h - hMin) / Math.max(hMax - hMin, 1)) * CH; }

	const tempLine = $derived(entries.map(e  => `${xs(e.ts).toFixed(1)},${ts_(e.temp).toFixed(1)}`).join(' '));
	const humLine  = $derived(entries.filter(e => e.hum !== null)
	                                 .map(e  => `${xs(e.ts).toFixed(1)},${hs(e.hum!).toFixed(1)}`).join(' '));

	// ── Y-axis ticks (5 evenly-spaced) ───────────────────────────────────────
	const yTicks = $derived(
		Array.from({ length: 5 }, (_, i) => tMin + (i / 4) * (tMax - tMin))
	);
	const hTicks = $derived(
		Array.from({ length: 5 }, (_, i) => hMin + (i / 4) * (hMax - hMin))
	);

	// ── X-axis ticks ─────────────────────────────────────────────────────────
	const xTicks = $derived.by(() => {
		if (!hasData) return [] as number[];
		const hours = RANGE_HOURS[range] ?? ((xMax - xMin) / 3_600_000);
		const interval =
			hours > 24 * 20  ? 7  * 86_400_000 :
			hours > 24 * 4   ?     86_400_000  :
			hours > 24       ? 12 * 3_600_000  :
			hours > 6        ?  3 * 3_600_000  :
			hours > 1        ?      3_600_000  :
			                   15 * 60_000;
		const first = Math.ceil(xMin / interval) * interval;
		const ticks: number[] = [];
		for (let t = first; t <= xMax; t += interval) ticks.push(t);
		return ticks;
	});

	function fmtXTick(ts: number) {
		const hours = RANGE_HOURS[range];
		const d = new Date(ts);
		if (!hours || hours > 24 * 4)
			return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
		if (hours <= 1)
			return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
		return d.toLocaleTimeString('en-US', { hour: 'numeric', hour12: true });
	}

	// ── Hover / tooltip ──────────────────────────────────────────────────────
	let svgEl     = $state<SVGSVGElement | null>(null);
	let hoverEntry = $state<ClimateEntry | null>(null);

	function onMouseMove(e: MouseEvent) {
		if (!svgEl || !hasData) { hoverEntry = null; return; }
		const rect = svgEl.getBoundingClientRect();
		const svgX = (e.clientX - rect.left) * (W / rect.width);
		if (svgX < PAD.left || svgX > W - PAD.right) { hoverEntry = null; return; }
		const ts = xMin + ((svgX - PAD.left) / CW) * xSpan;
		hoverEntry = entries.reduce((best, e) =>
			Math.abs(e.ts - ts) < Math.abs(best.ts - ts) ? e : best
		);
	}
	function onMouseLeave() { hoverEntry = null; }

	const hoverLX    = $derived(hoverEntry ? xs(hoverEntry.ts) : null);
	const tooltipX   = $derived(hoverLX !== null ? (hoverLX > W / 2 ? hoverLX - 162 : hoverLX + 10) : 0);
	const tooltipY   = $derived(PAD.top + 6);

	function fmtTime(ts: number) {
		return new Date(ts).toLocaleString('en-US', {
			month: 'short', day: 'numeric',
			hour: 'numeric', minute: '2-digit', hour12: true
		});
	}

	// ── SSE live data ────────────────────────────────────────────────────────
	onMount(() => {
		const src = new EventSource('/api/temp');
		src.onmessage = (e) => {
			try {
				const d = JSON.parse(e.data);
				if (typeof d.temperature === 'number') liveTemp = d.temperature;
				if (typeof d.humidity    === 'number') liveHum  = d.humidity;
			} catch {}
		};
		return () => src.close();
	});
</script>

<svelte:head><title>Stats — Snail Cam</title></svelte:head>

<Header company="Snail" platformName="Cam — Stats" href="/">
	<svelte:fragment slot="skip-to-content"><SkipToContent /></svelte:fragment>
	<HeaderNav>
		<HeaderNavItem href="/"          text="Live Camera"  />
		<HeaderNavItem href="/snapshots" text="Snapshots"    />
	</HeaderNav>
</Header>

<div class="page-body">

	<!-- Live readings bar -->
	<div class="live-bar">
		<div class="live-item">
			<span class="live-label">TEMPERATURE</span>
			<span class="live-val temp-color">
				{liveTemp !== null ? liveTemp.toFixed(1) : '--'}°F
			</span>
		</div>
		<div class="live-divider"></div>
		<div class="live-item">
			<span class="live-label">HUMIDITY</span>
			<span class="live-val hum-color">
				{liveHum !== null ? liveHum.toFixed(1) : '--'}%
			</span>
		</div>
		<div class="live-dot" title="Live"></div>
	</div>

	<!-- Chart card -->
	<div class="chart-card">
		<div class="chart-header">
			<h2 class="chart-title">Climate History</h2>
			<ContentSwitcher size="sm" bind:selectedIndex={rangeIdx}>
				<Switch text="1h"  />
				<Switch text="6h"  />
				<Switch text="24h" />
				<Switch text="7d"  />
				<Switch text="30d" />
				<Switch text="All" />
			</ContentSwitcher>
		</div>

		<div class="chart-wrap">
			{#if loading}
				<div class="chart-state">Loading…</div>
			{:else if errorMsg}
				<div class="chart-state error">{errorMsg}</div>
			{:else if !hasData}
				<div class="chart-state">No climate data recorded yet.</div>
			{:else}
				<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
				<svg
					bind:this={svgEl}
					viewBox="0 0 {W} {H}"
					preserveAspectRatio="xMidYMid meet"
					class="chart-svg"
					role="img"
					aria-label="Climate history chart"
					onmousemove={onMouseMove}
					onmouseleave={onMouseLeave}
				>
					<!-- Grid lines -->
					{#each yTicks as tick}
						{@const y = ts_(tick)}
						<line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y}
							stroke="#e0e0e0" stroke-width="1" />
					{/each}

					<!-- X-axis ticks -->
					{#each xTicks as tick}
						{@const x = xs(tick)}
						<line x1={x} y1={PAD.top} x2={x} y2={H - PAD.bottom + 5}
							stroke="#e0e0e0" stroke-width="1" />
						<text x={x} y={H - PAD.bottom + 18} class="axis-label x-label">{fmtXTick(tick)}</text>
					{/each}

					<!-- Left Y-axis — temperature -->
					<line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={H - PAD.bottom}
						stroke="#c6c6c6" stroke-width="1" />
					{#each yTicks as tick}
						<text x={PAD.left - 6} y={ts_(tick) + 4} class="axis-label y-label-left">
							{tick % 1 === 0 ? tick : tick.toFixed(1)}°
						</text>
					{/each}
					<text
						x={16} y={PAD.top + CH / 2}
						class="axis-title axis-title-left"
						transform="rotate(-90, 16, {PAD.top + CH / 2})"
					>Temp (°F)</text>

					<!-- Right Y-axis — humidity -->
					{#if hasHum}
						<line x1={W - PAD.right} y1={PAD.top} x2={W - PAD.right} y2={H - PAD.bottom}
							stroke="#c6c6c6" stroke-width="1" />
						{#each hTicks as tick}
							<text x={W - PAD.right + 6} y={hs(tick) + 4} class="axis-label y-label-right">
								{tick % 1 === 0 ? tick : tick.toFixed(0)}%
							</text>
						{/each}
						<text
							x={W - 16} y={PAD.top + CH / 2}
							class="axis-title axis-title-right"
							transform="rotate(90, {W - 16}, {PAD.top + CH / 2})"
						>Humidity (%)</text>
					{/if}

					<!-- X-axis baseline -->
					<line x1={PAD.left} y1={H - PAD.bottom} x2={W - PAD.right} y2={H - PAD.bottom}
						stroke="#c6c6c6" stroke-width="1" />

					<!-- Humidity polyline -->
					{#if hasHum && humLine}
						<polyline
							points={humLine}
							fill="none"
							stroke="#08bdba"
							stroke-width="2"
							stroke-linejoin="round"
							stroke-linecap="round"
						/>
					{/if}

					<!-- Temperature polyline -->
					{#if tempLine}
						<polyline
							points={tempLine}
							fill="none"
							stroke="#4589ff"
							stroke-width="2"
							stroke-linejoin="round"
							stroke-linecap="round"
						/>
					{/if}

					<!-- Hover elements -->
					{#if hoverEntry && hoverLX !== null}
						<!-- Vertical rule -->
						<line
							x1={hoverLX} y1={PAD.top}
							x2={hoverLX} y2={H - PAD.bottom}
							stroke="#525252" stroke-width="1" stroke-dasharray="3 3"
						/>

						<!-- Dots -->
						<circle cx={hoverLX} cy={ts_(hoverEntry.temp)} r="4"
							fill="#4589ff" stroke="#ffffff" stroke-width="1.5" />
						{#if hoverEntry.hum !== null}
							<circle cx={hoverLX} cy={hs(hoverEntry.hum)} r="4"
								fill="#08bdba" stroke="#ffffff" stroke-width="1.5" />
						{/if}

						<!-- Tooltip box -->
						<g transform="translate({tooltipX}, {tooltipY})">
							<rect
								x="0" y="0"
								width="152" height={hoverEntry.hum !== null ? 74 : 56}
								fill="white" stroke="#e0e0e0" stroke-width="1" rx="1"
							/>
							<text x="10" y="17" class="tt-time">{fmtTime(hoverEntry.ts)}</text>
							<line x1="0" y1="24" x2="152" y2="24" stroke="#e0e0e0" stroke-width="1" />
							<circle cx="18" cy="38" r="4" fill="#4589ff" />
							<text x="28" y="42" class="tt-val">
								{hoverEntry.temp.toFixed(1)}°F
							</text>
							{#if hoverEntry.hum !== null}
								<circle cx="18" cy="58" r="4" fill="#08bdba" />
								<text x="28" y="62" class="tt-val">
									{hoverEntry.hum.toFixed(1)}%
								</text>
							{/if}
						</g>
					{/if}

					<!-- Invisible mouse capture area -->
					<rect
						x={PAD.left} y={PAD.top}
						width={CW} height={CH}
						fill="transparent"
					/>
				</svg>
			{/if}
		</div>

		<!-- Legend -->
		{#if hasData}
			<div class="legend">
				<div class="legend-item">
					<span class="legend-swatch temp-swatch"></span>
					<span class="legend-label">Temperature</span>
				</div>
				{#if hasHum}
					<div class="legend-item">
						<span class="legend-swatch hum-swatch"></span>
						<span class="legend-label">Humidity</span>
					</div>
				{/if}
				<span class="legend-count">{entries.length} readings</span>
			</div>
		{/if}
	</div>
</div>

<style>
	.page-body {
		padding-top: 3rem;
		min-height: calc(100vh - 3rem);
		background: #f4f4f4;
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	/* ── Live bar ──────────────────────────────────────────────────────── */
	.live-bar {
		display: flex;
		align-items: center;
		background: #161616;
		padding: 16px 24px;
		gap: 24px;
		position: relative;
	}

	.live-item {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.live-label {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 0.625rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		color: #8d8d8d;
	}

	.live-val {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 1.75rem;
		font-weight: 300;
		line-height: 1;
	}

	.temp-color { color: #4589ff; }
	.hum-color  { color: #08bdba; }

	.live-divider {
		width: 1px;
		height: 40px;
		background: #393939;
	}

	.live-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #42be65;
		margin-left: auto;
		animation: pulse 2s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50%       { opacity: 0.3; }
	}

	/* ── Chart card ────────────────────────────────────────────────────── */
	.chart-card {
		background: #ffffff;
		margin: 24px;
		border: 1px solid #e0e0e0;
		flex: 1;
	}

	.chart-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px;
		border-bottom: 1px solid #e0e0e0;
		flex-wrap: wrap;
		gap: 12px;
	}

	.chart-title {
		font-size: 1rem;
		font-weight: 600;
		color: #161616;
		margin: 0;
	}

	.chart-wrap {
		padding: 8px 4px 4px;
		min-height: 280px;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.chart-svg {
		width: 100%;
		height: auto;
		display: block;
		cursor: crosshair;
		overflow: visible;
	}

	.chart-state {
		color: #8d8d8d;
		font-size: 0.875rem;
		padding: 48px;
	}

	.chart-state.error { color: #da1e28; }

	/* ── SVG text styles ───────────────────────────────────────────────── */
	:global(.axis-label) {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 11px;
		fill: #6f6f6f;
	}

	:global(.x-label) {
		text-anchor: middle;
	}

	:global(.y-label-left) {
		text-anchor: end;
	}

	:global(.y-label-right) {
		text-anchor: start;
	}

	:global(.axis-title) {
		font-family: 'IBM Plex Sans', sans-serif;
		font-size: 11px;
		fill: #8d8d8d;
		text-anchor: middle;
	}

	:global(.tt-time) {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 10px;
		fill: #525252;
	}

	:global(.tt-val) {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 12px;
		fill: #161616;
	}

	/* ── Legend ────────────────────────────────────────────────────────── */
	.legend {
		display: flex;
		align-items: center;
		gap: 20px;
		padding: 10px 20px 16px;
		border-top: 1px solid #f4f4f4;
	}

	.legend-item {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.legend-swatch {
		display: inline-block;
		width: 20px;
		height: 2px;
		border-radius: 1px;
	}

	.temp-swatch { background: #4589ff; }
	.hum-swatch  { background: #08bdba; }

	.legend-label {
		font-size: 0.75rem;
		color: #525252;
	}

	.legend-count {
		margin-left: auto;
		font-family: 'IBM Plex Mono', monospace;
		font-size: 0.75rem;
		color: #8d8d8d;
	}
</style>
