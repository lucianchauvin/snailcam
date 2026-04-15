import { redirect, error } from '@sveltejs/kit';
import { readdir } from 'node:fs/promises';
import type { RequestHandler } from './$types';

const SNAPSHOT_DIR = '/home/snail/snapshots';

export const GET: RequestHandler = async () => {
	let files: string[];
	try {
		files = await readdir(SNAPSHOT_DIR);
	} catch {
		throw error(404, 'No snapshots found');
	}

	const latest = files
		.filter((f) => f.endsWith('.jpg'))
		.sort()
		.at(-1);

	if (!latest) throw error(404, 'No snapshots found');

	throw redirect(302, `/api/snapshots/image/${latest}`);
};
