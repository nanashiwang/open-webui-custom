<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import {
		assignSubscription,
		cancelSubscription,
		createSubscriptionPlan,
		getSubscriptionPlans,
		getSubscriptionUsers,
		updateSubscriptionPlan
	} from '$lib/apis/subscriptions';

	const i18n = getContext('i18n');

	let loading = true;
	let plans: any[] = [];
	let users: any[] = [];
	let total = 0;
	let query = '';
	let page = 1;

	let newPlan: any = {
		name: '',
		description: '',
		price_cents: 0,
		currency: 'USD',
		token_limit: null,
		request_limit: null,
		model_ids: ''
	};

	const number = (value: any) => Number(value ?? 0).toLocaleString();
	const percent = (used: any, limit: any) =>
		limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
	const date = (value: any) => (value ? new Date(value * 1000).toLocaleDateString() : '-');
	const limitText = (value: any) => (value ? number(value) : $i18n.t('Unlimited'));
	const selectValue = (event: Event) => (event.currentTarget as HTMLSelectElement).value;

	const load = async () => {
		loading = true;
		try {
			plans = await getSubscriptionPlans(localStorage.token);
			const result = await getSubscriptionUsers(localStorage.token, query, page);
			users = result?.items ?? [];
			total = result?.total ?? 0;
		} catch (err) {
			toast.error(`${err}`);
		}
		loading = false;
	};

	const createPlan = async () => {
		if (!newPlan.name.trim()) {
			toast.error($i18n.t('Name is required'));
			return;
		}

		await createSubscriptionPlan(localStorage.token, {
			...newPlan,
			price_cents: Number(newPlan.price_cents || 0),
			token_limit: newPlan.token_limit ? Number(newPlan.token_limit) : null,
			request_limit: newPlan.request_limit ? Number(newPlan.request_limit) : null,
			model_ids: newPlan.model_ids
				? newPlan.model_ids
						.split(',')
						.map((id: string) => id.trim())
						.filter(Boolean)
				: null
		}).catch((err) => toast.error(`${err}`));

		newPlan = {
			name: '',
			description: '',
			price_cents: 0,
			currency: 'USD',
			token_limit: null,
			request_limit: null,
			model_ids: ''
		};
		await load();
	};

	const togglePlan = async (plan: any) => {
		await updateSubscriptionPlan(localStorage.token, plan.id, { is_active: !plan.is_active }).catch((err) =>
			toast.error(`${err}`)
		);
		await load();
	};

	const assign = async (userId: string, planId: string) => {
		if (!planId) return;
		await assignSubscription(localStorage.token, userId, planId).catch((err) => toast.error(`${err}`));
		await load();
	};

	const cancel = async (userId: string) => {
		await cancelSubscription(localStorage.token, userId).catch((err) => toast.error(`${err}`));
		await load();
	};

	onMount(load);
</script>

<div class="w-full max-w-6xl mx-auto px-4 py-3 text-sm">
	<div class="flex items-center justify-between gap-3 mb-3">
		<div>
			<div class="text-xl font-medium">{$i18n.t('Subscriptions')}</div>
			<div class="text-xs text-gray-500 mt-0.5">
				{$i18n.t('Manage plans, quotas, and user usage.')}
			</div>
		</div>
		{#if loading}<Spinner className="size-5" />{/if}
	</div>

	<div class="grid lg:grid-cols-3 gap-3 mb-4">
		<div class="lg:col-span-1 rounded-xl border border-gray-100 dark:border-gray-850 p-3">
			<div class="font-medium mb-2">{$i18n.t('New plan')}</div>
			<div class="space-y-2">
				<input class="w-full bg-transparent border rounded-lg px-3 py-2 dark:border-gray-800" bind:value={newPlan.name} placeholder={$i18n.t('Name')} />
				<input class="w-full bg-transparent border rounded-lg px-3 py-2 dark:border-gray-800" bind:value={newPlan.description} placeholder={$i18n.t('Description')} />
				<div class="grid grid-cols-2 gap-2">
					<input class="w-full bg-transparent border rounded-lg px-3 py-2 dark:border-gray-800" type="number" min="0" bind:value={newPlan.token_limit} placeholder={$i18n.t('Token limit')} />
					<input class="w-full bg-transparent border rounded-lg px-3 py-2 dark:border-gray-800" type="number" min="0" bind:value={newPlan.request_limit} placeholder={$i18n.t('Request limit')} />
				</div>
				<input class="w-full bg-transparent border rounded-lg px-3 py-2 dark:border-gray-800" bind:value={newPlan.model_ids} placeholder="model-a, model-b" />
				<button class="w-full rounded-lg bg-black text-white dark:bg-white dark:text-black px-3 py-2" on:click={createPlan}>{$i18n.t('Create')}</button>
			</div>
		</div>

		<div class="lg:col-span-2 rounded-xl border border-gray-100 dark:border-gray-850 p-3 overflow-x-auto">
			<div class="font-medium mb-2">{$i18n.t('Plans')}</div>
			<table class="w-full text-left text-xs">
				<thead class="text-gray-500">
					<tr>
						<th class="py-2">{$i18n.t('Name')}</th>
						<th class="py-2 text-right">{$i18n.t('Tokens')}</th>
						<th class="py-2 text-right">{$i18n.t('Requests')}</th>
						<th class="py-2 text-right">{$i18n.t('Status')}</th>
					</tr>
				</thead>
				<tbody>
					{#each plans as plan}
						<tr class="border-t border-gray-50 dark:border-gray-850">
							<td class="py-2">
								<div class="font-medium">{plan.name}</div>
								<div class="text-gray-500">{plan.description ?? ''}</div>
							</td>
							<td class="py-2 text-right">{limitText(plan.token_limit)}</td>
							<td class="py-2 text-right">{limitText(plan.request_limit)}</td>
							<td class="py-2 text-right">
								<button class="px-2 py-1 rounded-lg border dark:border-gray-800" on:click={() => togglePlan(plan)}>{plan.is_active ? $i18n.t('Active') : $i18n.t('Paused')}</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>

	<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3">
		<div class="flex items-center justify-between gap-2 mb-2">
			<div class="font-medium">{$i18n.t('Users')} <span class="text-gray-500">{total}</span></div>
			<input class="bg-transparent border rounded-lg px-3 py-1.5 dark:border-gray-800" bind:value={query} placeholder={$i18n.t('Search')} on:change={load} />
		</div>

		<div class="overflow-x-auto">
			<table class="w-full text-left text-xs">
				<thead class="text-gray-500">
					<tr>
						<th class="py-2">{$i18n.t('User')}</th>
						<th class="py-2">{$i18n.t('Plan')}</th>
						<th class="py-2 text-right">{$i18n.t('Tokens')}</th>
						<th class="py-2 text-right">{$i18n.t('Requests')}</th>
						<th class="py-2 text-right">{$i18n.t('Period')}</th>
						<th class="py-2 text-right">{$i18n.t('Action')}</th>
					</tr>
				</thead>
				<tbody>
					{#each users as row}
						<tr class="border-t border-gray-50 dark:border-gray-850">
							<td class="py-2 pr-3">
								<div class="font-medium">{row.user.name}</div>
								<div class="text-gray-500">{row.user.email}</div>
							</td>
							<td class="py-2 pr-3">
								<select class="bg-transparent border rounded-lg px-2 py-1 dark:border-gray-800" value={row.plan?.id ?? ''} on:change={(e) => assign(row.user.id, selectValue(e))}>
									<option value="">{$i18n.t('No plan')}</option>
									{#each plans.filter((plan) => plan.is_active) as plan}
										<option value={plan.id}>{plan.name}</option>
									{/each}
								</select>
							</td>
							<td class="py-2 text-right">
								{number(row.usage.total_tokens)} / {limitText(row.plan?.token_limit)}
								{#if row.plan?.token_limit}<div class="text-gray-500">{percent(row.usage.total_tokens, row.plan.token_limit)}%</div>{/if}
							</td>
							<td class="py-2 text-right">
								{number(row.usage.request_count)} / {limitText(row.plan?.request_limit)}
							</td>
							<td class="py-2 text-right text-gray-500">{date(row.period_start)} - {date(row.period_end)}</td>
							<td class="py-2 text-right">
								{#if row.subscription}<button class="px-2 py-1 rounded-lg border dark:border-gray-800" on:click={() => cancel(row.user.id)}>{$i18n.t('Cancel')}</button>{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
</div>
