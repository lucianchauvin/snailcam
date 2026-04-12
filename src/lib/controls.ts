import type { ControlDef } from './types.js';

export const CAMERA_CONTROLS: ControlDef[] = [
	{ name: 'brightness', label: 'Brightness', min: 0, max: 255, step: 1, default: 128 },
	{ name: 'contrast', label: 'Contrast', min: 0, max: 255, step: 1, default: 128 },
	{ name: 'saturation', label: 'Saturation', min: 0, max: 255, step: 1, default: 128 },
	{ name: 'gain', label: 'Gain', min: 0, max: 255, step: 1, default: 0 },
	{ name: 'sharpness', label: 'Sharpness', min: 0, max: 255, step: 1, default: 128 },
	{ name: 'backlight_compensation', label: 'Backlight Comp', min: 0, max: 1, step: 1, default: 0 },
	{ name: 'white_balance_temperature', label: 'White Balance', min: 2000, max: 7500, step: 10, default: 4000 },
	{ name: 'exposure_time_absolute', label: 'Exposure Time', min: 3, max: 2047, step: 1, default: 250 },
	{ name: 'focus_absolute', label: 'Focus', min: 0, max: 255, step: 5, default: 30 }
];

export const PAN_STEP = 3600;
export const TILT_STEP = 3600;
export const PAN_MIN = -36000;
export const PAN_MAX = 36000;
export const TILT_MIN = -36000;
export const TILT_MAX = 36000;
export const ZOOM_MIN = 100;
export const ZOOM_MAX = 500;
