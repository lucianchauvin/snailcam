const SENSOR_URL = 'http://192.168.88.241';

export const INTERNAL_SECRET = crypto.randomUUID();

export type HeatLevel = 'Highest' | 'Medium' | 'Lowest';
export type HeatDuration = 'Long' | 'Short';

export async function callHeat(level: HeatLevel = 'Medium', duration: HeatDuration = 'Long') {
	const abort = new AbortController();
	const timeout = setTimeout(() => abort.abort(), 8000);
	try {
		const res = await fetch(`${SENSOR_URL}/heat`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ heat: level, duration }),
			signal: abort.signal
		}).catch(() => null);

		if (!res?.ok) return null;
		return await res.json().catch(() => null);
	} finally {
		clearTimeout(timeout);
	}
}
