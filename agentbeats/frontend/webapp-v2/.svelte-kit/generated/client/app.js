export { matchers } from './matchers.js';

export const nodes = [
	() => import('./nodes/0'),
	() => import('./nodes/1'),
	() => import('./nodes/2'),
	() => import('./nodes/3'),
	() => import('./nodes/4'),
	() => import('./nodes/5'),
	() => import('./nodes/6'),
	() => import('./nodes/7'),
	() => import('./nodes/8'),
	() => import('./nodes/9'),
	() => import('./nodes/10'),
	() => import('./nodes/11'),
	() => import('./nodes/12'),
	() => import('./nodes/13'),
	() => import('./nodes/14'),
	() => import('./nodes/15'),
	() => import('./nodes/16'),
	() => import('./nodes/17'),
	() => import('./nodes/18'),
	() => import('./nodes/19'),
	() => import('./nodes/20'),
	() => import('./nodes/21'),
	() => import('./nodes/22'),
	() => import('./nodes/23'),
	() => import('./nodes/24')
];

export const server_loads = [];

export const dictionary = {
		"/": [6],
		"/(game)/agents": [7,[2,3]],
		"/(game)/agents/directory": [9,[2,3]],
		"/(game)/agents/my-agents": [10,[2,3]],
		"/(game)/agents/register": [~11,[2,3]],
		"/(game)/agents/[agent_id]": [8,[2,3]],
		"/auth/callback": [18],
		"/(game)/battles": [12,[2,4]],
		"/(game)/battles/ongoing": [14,[2,4]],
		"/(game)/battles/past": [15,[2,4]],
		"/(game)/battles/stage-battle": [16,[2,4]],
		"/(game)/battles/[battle_id]": [13,[2,4]],
		"/(game)/dashboard": [17,[2]],
		"/docs": [19,[5]],
		"/docs/api/api-reference": [20,[5]],
		"/docs/cli/cli-reference": [21,[5]],
		"/docs/getting-started/making-new-docs": [22,[5]],
		"/docs/getting-started/quick-start": [23,[5]],
		"/login": [24]
	};

export const hooks = {
	handleError: (({ error }) => { console.error(error) }),
	
	reroute: (() => {}),
	transport: {}
};

export const decoders = Object.fromEntries(Object.entries(hooks.transport).map(([k, v]) => [k, v.decode]));

export const hash = false;

export const decode = (type, value) => decoders[type](value);

export { default as root } from '../root.js';