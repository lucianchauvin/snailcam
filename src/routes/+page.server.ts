export const load = async ({ url }: { url: URL }) => {
	return { origin: url.origin };
};
