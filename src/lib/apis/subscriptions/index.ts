import { WEBUI_API_BASE_URL } from '$lib/constants';

const request = async (url: string, token: string, options: RequestInit = {}) => {
	let error = null;
	const res = await fetch(url, {
		...options,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`,
			...(options.headers ?? {})
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) throw error;
	return res;
};

export const getSubscriptionPlans = async (token: string, includeInactive = true) => {
	const searchParams = new URLSearchParams();
	searchParams.set('include_inactive', `${includeInactive}`);
	return await request(`${WEBUI_API_BASE_URL}/subscriptions/plans?${searchParams.toString()}`, token);
};

export const getAvailableSubscriptionPlans = async (token: string) => {
	return await request(`${WEBUI_API_BASE_URL}/subscriptions/available-plans`, token);
};

export const createSubscriptionPlan = async (token: string, plan: object) => {
	return await request(`${WEBUI_API_BASE_URL}/subscriptions/plans`, token, {
		method: 'POST',
		body: JSON.stringify(plan)
	});
};

export const updateSubscriptionPlan = async (token: string, planId: string, plan: object) => {
	return await request(`${WEBUI_API_BASE_URL}/subscriptions/plans/${planId}`, token, {
		method: 'PATCH',
		body: JSON.stringify(plan)
	});
};

export const getMySubscription = async (token: string) => {
	return await request(`${WEBUI_API_BASE_URL}/subscriptions/me`, token);
};

export const createSubscriptionCheckout = async (
	token: string,
	planId: string,
	paymentType = ''
) => {
	return await request(`${WEBUI_API_BASE_URL}/subscriptions/checkout`, token, {
		method: 'POST',
		body: JSON.stringify({
			plan_id: planId,
			...(paymentType ? { payment_type: paymentType } : {})
		})
	});
};

export const getSubscriptionUsers = async (token: string, query = '', page = 1) => {
	const searchParams = new URLSearchParams();
	searchParams.set('page', `${page}`);
	if (query) searchParams.set('query', query);
	return await request(`${WEBUI_API_BASE_URL}/subscriptions/users?${searchParams.toString()}`, token);
};

export const assignSubscription = async (token: string, userId: string, planId: string) => {
	return await request(`${WEBUI_API_BASE_URL}/subscriptions/users/${userId}`, token, {
		method: 'POST',
		body: JSON.stringify({ plan_id: planId })
	});
};

export const cancelSubscription = async (token: string, userId: string) => {
	return await request(`${WEBUI_API_BASE_URL}/subscriptions/users/${userId}`, token, {
		method: 'DELETE'
	});
};
