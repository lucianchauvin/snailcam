import { spawn } from 'node:child_process';
import type { RequestHandler } from './$types';

const FAN_IP    = '192.168.88.237';
const HEATER_IP = '192.168.88.236';
const LIGHT_IP  = '192.168.88.238';

const HUM_FAN_ON      = 90;
const HUM_FAN_OFF     = 82;
const FAN_MAX_MS      = 5 * 60 * 1000;

type Subscriber = (msg: string) => void;

interface DeviceStates {
	fan:    boolean | null;
	heater: boolean | null;
	light:  boolean | null;
}

let lastPayload: string | null = null;
const subscribers = new Set<Subscriber>();
let deviceStates: DeviceStates = { fan: null, heater: null, light: null };
let fanOnAt: number | null = null;

function runCmd(cmd: string, args: string[]): Promise<string> {
	return new Promise((resolve, reject) => {
		const proc = spawn(cmd, args);
		let out = '';
		proc.stdout.on('data', (d: Uint8Array) => { out += d; });
		proc.stderr.resume();
		proc.on('close', (code: number | null) => {
			if (code === 0) resolve(out);
			else reject(new Error(`${cmd} exited ${code}`));
		});
		proc.on('error', reject);
	});
}

async function getKasaState(ip: string): Promise<boolean | null> {
	try {
		const out = await runCmd('kasa', ['--host', ip, 'state']);
		const m = out.match(/Device state:\s+(True|False)/);
		return m ? m[1] === 'True' : null;
	} catch {
		return null;
	}
}

async function setKasa(ip: string, on: boolean): Promise<void> {
	await runCmd('kasa', ['--host', ip, on ? 'on' : 'off']);
}

async function pollDeviceStates() {
	const [fan, heater, light] = await Promise.all([
		getKasaState(FAN_IP),
		getKasaState(HEATER_IP),
		getKasaState(LIGHT_IP),
	]);
	deviceStates = { fan, heater, light };
}

function broadcast(data: object) {
	const msg = `data: ${JSON.stringify(data)}\n\n`;
	lastPayload = msg;
	for (const sub of subscribers) sub(msg);
}

async function pollSensor() {
	const abort = new AbortController();
	const timeout = setTimeout(() => abort.abort(), 4000);
	try {
		const res = await fetch('http://192.168.88.241', { signal: abort.signal }).catch(() => null);
		if (!res?.ok) return;
		const data = await res.json();
		if (typeof data.temperature !== 'number' || isNaN(data.temperature)) return;

		const hum = typeof data.humidity === 'number' ? data.humidity : null;
		if (hum !== null) {
			const fanTimedOut = fanOnAt !== null && Date.now() - fanOnAt >= FAN_MAX_MS;
			if (fanTimedOut && deviceStates.fan === true) {
				fanOnAt = null;
				deviceStates = { ...deviceStates, fan: false };
				setKasa(FAN_IP, false).catch(() => { deviceStates = { ...deviceStates, fan: null }; });
			} else if (hum > HUM_FAN_ON && deviceStates.fan === false) {
				fanOnAt = Date.now();
				deviceStates = { ...deviceStates, fan: true };
				setKasa(FAN_IP, true).catch(() => { deviceStates = { ...deviceStates, fan: null }; });
			} else if (hum < HUM_FAN_OFF && deviceStates.fan === true) {
				fanOnAt = null;
				deviceStates = { ...deviceStates, fan: false };
				setKasa(FAN_IP, false).catch(() => { deviceStates = { ...deviceStates, fan: null }; });
			}
		}

		broadcast({ ...data, devices: deviceStates });
	} finally {
		clearTimeout(timeout);
	}
}

setInterval(pollSensor, 500);
setInterval(pollDeviceStates, 10_000);
pollSensor();
pollDeviceStates();

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
