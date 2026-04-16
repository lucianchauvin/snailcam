import { callHeat } from '$lib/heat';

// Run a Medium/Long heater cycle every 10 minutes to prevent sensor drift from condensation.
// Starts immediately when the server process boots, not on first request.
callHeat('Medium', 'Long');
setInterval(() => callHeat('Medium', 'Long'), 10 * 60 * 1000);
