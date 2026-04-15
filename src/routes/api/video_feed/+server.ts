import { spawn } from 'node:child_process';
import type { RequestHandler } from './$types';

const BOUNDARY = 'frame';
const SOI = Buffer.from([0xff, 0xd8]);
const EOI = Buffer.from([0xff, 0xd9]);

type Subscriber = (frame: Buffer) => void;

let ffmpegProc: ReturnType<typeof spawn> | null = null;
const subscribers = new Set<Subscriber>();
let buf = Buffer.alloc(0);

function ensureFFmpeg() {
	if (ffmpegProc) return;

	ffmpegProc = spawn('ffmpeg', [
		// Input: tell ffmpeg it's a V4L2 device, request native MJPEG so we
		// can stream the frames directly without re-encoding (c:v copy below).
		// If your camera doesn't support MJPEG output, swap -input_format mjpeg
		// for -input_format yuyv422 and change -c:v copy to -c:v mjpeg -q:v 5.
		'-f', 'v4l2',
		'-input_format', 'mjpeg',
		'-framerate', '60',
		'-video_size', '1920x1080',
		'-i', '/dev/video0',
		// Output: pass JPEG frames straight through — no decode/re-encode cycle.
		'-an', '-c:v', 'copy',
		'-flush_packets', '1',
		'-f', 'image2pipe', 'pipe:1'
	]);

	ffmpegProc.stderr?.resume();

	ffmpegProc.stdout?.on('data', (chunk: Buffer) => {
		buf = Buffer.concat([buf, chunk]);

		while (true) {
			const start = buf.indexOf(SOI);
			if (start === -1) break;
			const end = buf.indexOf(EOI, start + 2);
			if (end === -1) break;
			const frame = Buffer.from(buf.subarray(start, end + 2));
			buf = buf.subarray(end + 2);
			for (const sub of subscribers) sub(frame);
		}
	});

	ffmpegProc.on('close', () => {
		ffmpegProc = null;
		buf = Buffer.alloc(0);
		if (subscribers.size > 0) ensureFFmpeg();
	});

	ffmpegProc.on('error', () => {
		ffmpegProc = null;
		buf = Buffer.alloc(0);
	});
}

function removeSubscriber(sub: Subscriber) {
	subscribers.delete(sub);
	if (subscribers.size === 0 && ffmpegProc) {
		ffmpegProc.kill('SIGTERM');
		ffmpegProc = null;
		buf = Buffer.alloc(0);
	}
}

export const GET: RequestHandler = () => {
	const encoder = new TextEncoder();
	let cancelled = false;
	let mySub: Subscriber | null = null;

	const stream = new ReadableStream({
		start(controller) {
			mySub = (frame) => {
				if (cancelled) return;
				const header =
					`--${BOUNDARY}\r\n` +
					`Content-Type: image/jpeg\r\n` +
					`Content-Length: ${frame.length}\r\n\r\n`;
				try {
					controller.enqueue(encoder.encode(header));
					controller.enqueue(new Uint8Array(frame));
					controller.enqueue(encoder.encode('\r\n'));
				} catch {
					cancelled = true;
					removeSubscriber(mySub!);
					mySub = null;
				}
			};

			subscribers.add(mySub);
			ensureFFmpeg();
		},
		cancel() {
			cancelled = true;
			if (mySub) {
				removeSubscriber(mySub);
				mySub = null;
			}
		}
	});

	return new Response(stream, {
		headers: {
			'Content-Type': `multipart/x-mixed-replace; boundary=${BOUNDARY}`,
			'Cache-Control': 'no-cache, no-store, must-revalidate',
			'Connection': 'keep-alive'
		}
	});
};
