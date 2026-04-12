import type { RequestHandler } from './$types';

type Subscriber = (msg: string) => void;

let lastPayload: string | null = null;
const subscribers = new Set<Subscriber>();

async function pollSensor() {
	const abort = new AbortController();
	const timeout = setTimeout(() => abort.abort(), 4000);
	try {
		const res = await fetch('http://192.168.88.241', { signal: abort.signal }).catch(() => null);
		if (!res?.ok) return;
		const data = await res.json();
		if (typeof data.temperature !== 'number' || isNaN(data.temperature)) return;
		const msg = `data: ${JSON.stringify(data)}\n\n`;
		lastPayload = msg;
		for (const sub of subscribers) sub(msg);
	} finally {
		clearTimeout(timeout);
	}
}

setInterval(pollSensor, 500);
pollSensor();

export const GET: RequestHandler = () => {
	const encoder = new TextEncoder();
	let mySub: Subscriber | null = null;

	const stream = new ReadableStream({
		start(controller) {
			if (lastPayload) {
				try { controller.enqueue(encoder.encode(lastPayload)); } catch {}
			}

			mySub = (msg) => {
				try {
					controller.enqueue(encoder.encode(msg));
				} catch {
					if (mySub) { subscribers.delete(mySub); mySub = null; }
				}
			};

			subscribers.add(mySub);
		},
		cancel() {
			if (mySub) { subscribers.delete(mySub); mySub = null; }
		}
	});

	return new Response(stream, {
		headers: {
			'Content-Type': 'text/event-stream',
			'Cache-Control': 'no-cache',
			'Connection': 'keep-alive'
		}
	});
};
