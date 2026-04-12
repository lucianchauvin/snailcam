import { json } from '@sveltejs/kit';
import { readdir } from 'node:fs/promises';
import type { RequestHandler } from './$types';

const SNAPSHOT_DIR = '/home/snail/snapshots';

export const GET: RequestHandler = async () => {
	let files: string[];
	try {
		files = await readdir(SNAPSHOT_DIR);
	} catch {
		return json({ snapshots: [] });
	}

	const snapshots = files
		.filter((f) => f.endsWith('.jpg'))
		.sort()
		.flatMap((filename) => {
			const m = filename.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\.jpg$/);
			if (!m) return [];
			const [, yr, mo, dy, hr, mn, sc] = m;
			return [{
				filename,
				timestamp: `${yr}-${mo}-${dy}T${hr}:${mn}:${sc}`,
				display:   `${yr}-${mo}-${dy} ${hr}:${mn}:${sc}`
			}];
		});

	return json({ snapshots });
};
