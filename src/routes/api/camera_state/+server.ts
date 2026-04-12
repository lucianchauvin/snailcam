import { json } from '@sveltejs/kit';
import { spawn } from 'node:child_process';
import type { RequestHandler } from './$types';

function runV4l2Ctl(): Promise<string> {
	return new Promise((resolve, reject) => {
		const proc = spawn('v4l2-ctl', ['--list-ctrls', '-d', '/dev/video0']);
		let stdout = '';
		let stderr = '';
		proc.stdout.on('data', (chunk) => { stdout += chunk; });
		proc.stderr.on('data', (chunk) => { stderr += chunk; });
		proc.on('close', (code) => {
			if (code === 0) resolve(stdout);
			else reject(new Error(`v4l2-ctl exited ${code}: ${stderr}`));
		});
		proc.on('error', reject);
	});
}

export const GET: RequestHandler = async () => {
	try {
		const output = await runV4l2Ctl();
		const values: Record<string, number> = {};

		for (const line of output.split('\n')) {
			const nameMatch  = line.match(/^\s+(\w+)\s+0x[\da-f]+\s+\([^)]+\)/);
			const valueMatch = line.match(/\bvalue=(-?\d+)/);
			if (nameMatch && valueMatch) {
				values[nameMatch[1]] = parseInt(valueMatch[1], 10);
			}
		}

		return json({ values });
	} catch (e: unknown) {
		return json({ error: e instanceof Error ? e.message : 'Failed to read camera state' }, { status: 500 });
	}
};
