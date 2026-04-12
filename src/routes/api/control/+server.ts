import { json } from '@sveltejs/kit';
import { spawn } from 'node:child_process';
import type { RequestHandler } from './$types';

const ALLOWED_CONTROLS = new Set([
	'brightness', 'contrast', 'saturation', 'gain', 'sharpness',
	'backlight_compensation', 'white_balance_temperature',
	'exposure_time_absolute', 'focus_absolute',
	'pan_absolute', 'tilt_absolute', 'zoom_absolute'
]);

export const POST: RequestHandler = async ({ request }) => {
	const data = await request.json().catch(() => null);
	if (!data) return json({ status: 'error', message: 'Invalid JSON' }, { status: 400 });

	const { control, value } = data;

	if (!ALLOWED_CONTROLS.has(control)) {
		return json({ status: 'error', message: 'Invalid control name' }, { status: 400 });
	}

	if (value === undefined || value === null || !/^-?\d+(\.\d+)?$/.test(String(value))) {
		return json({ status: 'error', message: 'Value must be a number' }, { status: 400 });
	}

	const proc = spawn('v4l2-ctl', ['-d', '/dev/video0', '--set-ctrl', `${control}=${value}`]);
	proc.stderr.resume();

	return json({ status: 'success' });
};
