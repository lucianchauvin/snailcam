import { error } from '@sveltejs/kit';
import { readFile } from 'node:fs/promises';
import { join, basename } from 'node:path';
import type { RequestHandler } from './$types';

const SNAPSHOT_DIR = '/home/snail/snapshots';

export const GET: RequestHandler = async ({ params }) => {
	const safe = basename(params.filename);
	const filepath = join(SNAPSHOT_DIR, safe);

	let data: Buffer;
	try {
		data = await readFile(filepath);
	} catch {
		throw error(404, 'Snapshot not found');
	}

	return new Response(data, {
		headers: {
			'Content-Type': 'image/jpeg',
			'Cache-Control': 'public, max-age=31536000, immutable'
		}
	});
};
