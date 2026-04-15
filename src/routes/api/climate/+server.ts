import { json } from '@sveltejs/kit';
import { createReadStream } from 'node:fs';
import { createInterface } from 'node:readline';
import type { RequestHandler } from './$types';

const CLIMATE_LOG = '/home/snail/snapshots/climate.jsonl';

export interface ClimateEntry {
	ts: number;
	t: string;
	temp: number;
	hum: number | null;
}

export const GET: RequestHandler = async ({ url }) => {
	const hoursParam = url.searchParams.get('hours');
	const cutoff = hoursParam ? Date.now() - Number(hoursParam) * 3_600_000 : 0;

	const entries: ClimateEntry[] = [];

	try {
		const rl = createInterface({
			input: createReadStream(CLIMATE_LOG),
			crlfDelay: Infinity
		});

		for await (const line of rl) {
			if (!line.trim()) continue;
			try {
				const raw = JSON.parse(line) as { t: string; temp: number; hum?: number };
				const m = raw.t.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/);
				if (!m) continue;
				const [, yr, mo, dy, hr, mn, sc] = m;
				const ts = new Date(`${yr}-${mo}-${dy}T${hr}:${mn}:${sc}`).getTime();
				if (ts >= cutoff) {
					entries.push({ ts, t: raw.t, temp: raw.temp, hum: raw.hum ?? null });
				}
			} catch {}
		}
	} catch {
		return json({ entries: [] });
	}

	return json({ entries });
};
