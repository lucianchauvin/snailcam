import { json, type RequestEvent } from '@sveltejs/kit';
import { callHeat, INTERNAL_SECRET, type HeatLevel, type HeatDuration } from '$lib/heat';

export const POST = async ({ request }: RequestEvent) => {
	const auth = request.headers.get('x-internal-secret');
	if (auth !== INTERNAL_SECRET) {
		return json({ error: 'Forbidden' }, { status: 403 });
	}

	const body = await request.json().catch(() => ({}));
	const level: HeatLevel = ['Highest', 'Medium', 'Lowest'].includes(body.heat)
		? body.heat
		: 'Medium';
	const duration: HeatDuration = body.duration === 'Long' ? 'Long' : 'Short';

	const result = await callHeat(level, duration);
	if (!result) return json({ error: 'Heater command failed' }, { status: 502 });
	return json(result);
};
