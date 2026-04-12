<script lang="ts">
	import { onMount } from 'svelte';
	import {
		Header, HeaderNav, HeaderNavItem, SkipToContent,
		Button, Tag
	} from 'carbon-components-svelte';
	import SkipBackFilled    from 'carbon-icons-svelte/lib/SkipBackFilled.svelte';
	import SkipForwardFilled from 'carbon-icons-svelte/lib/SkipForwardFilled.svelte';
	import PreviousFilled    from 'carbon-icons-svelte/lib/PreviousFilled.svelte';
	import NextFilled        from 'carbon-icons-svelte/lib/NextFilled.svelte';
	import PlayFilledAlt     from 'carbon-icons-svelte/lib/PlayFilledAlt.svelte';
	import PauseFilled       from 'carbon-icons-svelte/lib/PauseFilled.svelte';
	import type { Snapshot } from '$lib/types.js';

	let snapshots     = $state<Snapshot[]>([]);
	let currentIndex  = $state(0);
	let isPlaying     = $state(false);
	let playDirection = $state<1 | -1>(1);
	let playFps       = $state(3);
	let loading       = $state(true);
	let errorMsg      = $state('');

	let playbackTimeout: ReturnType<typeof setTimeout> | null = null;

	const current   = $derived(snapshots[currentIndex] ?? null);
	const playDelay = $derived(Math.round(1000 / playFps));
	const hasSnaps  = $derived(snapshots.length > 0);

	async function loadSnapshots() {
		try {
			const res  = await fetch('/api/snapshots/list');
			const data = await res.json();
			if (data.error || !data.snapshots?.length) {
				errorMsg = data.error ?? 'No snapshots found';
				loading  = false;
				return;
			}
			snapshots    = data.snapshots;
			currentIndex = snapshots.length - 1;
			loading      = false;
		} catch (e: unknown) {
			errorMsg = e instanceof Error ? e.message : 'Failed to load';
			loading  = false;
		}
	}

	function goTo(index: number) {
		if (index < 0 || index >= snapshots.length) return;
		currentIndex = index;
	}

	function stopPlayback() {
		if (playbackTimeout !== null) clearTimeout(playbackTimeout);
		playbackTimeout = null;
		isPlaying = false;
	}

	function scheduleNext() {
		if (!isPlaying) return;
		playbackTimeout = setTimeout(() => {
			const next = currentIndex + playDirection;
			if (next < 0 || next >= snapshots.length) { stopPlayback(); return; }
			currentIndex = next;
			scheduleNext();
		}, playDelay);
	}

	function startPlayback(direction: 1 | -1) {
		stopPlayback();
		playDirection = direction;
		isPlaying     = true;
		scheduleNext();
	}

	function togglePlay(direction: 1 | -1) {
		if (isPlaying && playDirection === direction) stopPlayback();
		else startPlayback(direction);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowLeft')  { stopPlayback(); goTo(currentIndex - 1); }
		if (e.key === 'ArrowRight') { stopPlayback(); goTo(currentIndex + 1); }
		if (e.key === ' ')          { e.preventDefault(); togglePlay(1); }
	}

	onMount(() => {
		loadSnapshots();
		return () => stopPlayback();
	});
</script>

<svelte:head><title>Snapshot Timeline — Snail Cam</title></svelte:head>
<svelte:window onkeydown={handleKeydown} />

<Header company="Snail" platformName="Cam — Snapshots" href="/">
	<svelte:fragment slot="skip-to-content">
		<SkipToContent />
	</svelte:fragment>
	<HeaderNav>
		<HeaderNavItem href="/" text="← Live Camera" />
	</HeaderNav>
</Header>

<div class="page-body">
	<div class="image-area">
		{#if loading}
			<p class="status-text">Loading snapshots…</p>
		{:else if errorMsg}
			<p class="status-text error">{errorMsg}</p>
		{:else if current}
			<img
				src="/api/snapshots/image/{current.filename}"
				alt={current.display}
				class="snapshot-img"
			/>
		{/if}
	</div>

	<div class="controls-area">
		<div class="timeline-row">
			<Button
				hasIconOnly kind="ghost" size="sm"
				icon={SkipBackFilled} iconDescription="First frame"
				disabled={!hasSnaps}
				on:click={() => { stopPlayback(); goTo(0); }}
			/>
			<input
				class="timeline-range"
				type="range"
				min={0}
				max={Math.max(0, snapshots.length - 1)}
				value={currentIndex}
				disabled={!hasSnaps}
				oninput={(e) => { stopPlayback(); goTo(Number((e.target as HTMLInputElement).value)); }}
			/>
			<Button
				hasIconOnly kind="ghost" size="sm"
				icon={SkipForwardFilled} iconDescription="Last frame"
				disabled={!hasSnaps}
				on:click={() => { stopPlayback(); goTo(snapshots.length - 1); }}
			/>
		</div>

		<div class="playback-row">
			<Button
				hasIconOnly kind="ghost" size="sm"
				icon={PreviousFilled} iconDescription="Step back"
				disabled={!hasSnaps}
				on:click={() => { stopPlayback(); goTo(currentIndex - 1); }}
			/>

			<Button
				kind={isPlaying && playDirection === -1 ? 'primary' : 'secondary'}
				size="sm"
				icon={isPlaying && playDirection === -1 ? PauseFilled : PlayFilledAlt}
				iconDescription={isPlaying && playDirection === -1 ? 'Pause' : 'Reverse play'}
				disabled={!hasSnaps}
				on:click={() => togglePlay(-1)}
			>
				{isPlaying && playDirection === -1 ? 'Pause' : 'Reverse'}
			</Button>

			<Button
				kind="primary"
				size="sm"
				icon={isPlaying && playDirection === 1 ? PauseFilled : PlayFilledAlt}
				iconDescription={isPlaying && playDirection === 1 ? 'Pause' : 'Play'}
				disabled={!hasSnaps}
				on:click={() => togglePlay(1)}
			>
				{isPlaying && playDirection === 1 ? 'Pause' : 'Play'}
			</Button>

			<Button
				hasIconOnly kind="ghost" size="sm"
				icon={NextFilled} iconDescription="Step forward"
				disabled={!hasSnaps}
				on:click={() => { stopPlayback(); goTo(currentIndex + 1); }}
			/>

			<div class="speed-group">
				<span class="speed-label-text">Speed</span>
				<input
					class="speed-range"
					type="range"
					min={1}
					max={30}
					step={1}
					value={playFps}
					oninput={(e) => {
						playFps = Number((e.target as HTMLInputElement).value);
						if (isPlaying) { stopPlayback(); isPlaying = true; scheduleNext(); }
					}}
				/>
				<span class="speed-val">{playFps} fps</span>
			</div>
		</div>

		<div class="info-row">
			<span class="timestamp">{current?.display ?? '--'}</span>
			<Tag type="cool-gray">
				{hasSnaps ? `${currentIndex + 1} / ${snapshots.length}` : '0 / 0'}
			</Tag>
		</div>
	</div>
</div>

<style>
	:global(html, body) {
		height: 100%;
		overflow: hidden;
	}

	.page-body {
		padding-top: 3rem;
		display: flex;
		flex-direction: column;
		height: 100vh;
	}

	.image-area {
		flex: 1;
		display: flex;
		justify-content: center;
		align-items: center;
		background: #000000;
		overflow: hidden;
		min-height: 0;
	}

	.snapshot-img {
		max-width: 100%;
		max-height: 100%;
		object-fit: contain;
	}

	.status-text {
		color: #8d8d8d;
		font-size: 0.875rem;
	}

	.status-text.error {
		color: #da1e28;
	}

	.controls-area {
		background: #ffffff;
		border-top: 1px solid #e0e0e0;
		padding: 12px 16px;
		display: flex;
		flex-direction: column;
		gap: 10px;
		flex-shrink: 0;
	}

	input[type='range'] {
		-webkit-appearance: none;
		appearance: none;
		height: 2px;
		background: #c6c6c6;
		border-radius: 0;
		outline: none;
		cursor: pointer;
	}

	input[type='range']::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: #0f62fe;
		cursor: pointer;
		border: none;
	}

	input[type='range']::-moz-range-thumb {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: #0f62fe;
		cursor: pointer;
		border: none;
	}

	input[type='range']:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.timeline-row {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.timeline-range {
		flex: 1;
		min-width: 0;
	}

	.playback-row {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
	}

	.speed-group {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-left: auto;
	}

	.speed-label-text {
		font-size: 0.75rem;
		color: #525252;
		white-space: nowrap;
	}

	.speed-range {
		width: 120px;
	}

	.speed-val {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 0.75rem;
		color: #161616;
		white-space: nowrap;
		min-width: 3.5rem;
	}

	.info-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.timestamp {
		font-size: 0.875rem;
		font-weight: 400;
		color: #161616;
		font-family: 'IBM Plex Mono', monospace;
	}
</style>
