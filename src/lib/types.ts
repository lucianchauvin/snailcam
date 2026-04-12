export interface Snapshot {
	filename: string;
	timestamp: string;
	display: string;
}

export interface ControlDef {
	name: string;
	label: string;
	min: number;
	max: number;
	step: number;
	default: number;
}
