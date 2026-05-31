import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';

const testRun = Date.now();
const privateFilterName = `e2e-private-${testRun}`;
const publicReadonlyName = `e2e-public-readonly-${testRun}`;
const publicCopyName = `${publicReadonlyName}-copy`;
const alarmSourceTag = `e2e-alarm-${testRun}`;

function psql(sql: string) {
  // E2E_PSQL_CMD lets CI override the psql invocation (we use a direct psql
  // binary against the published port instead of `docker compose exec`).
  const override = process.env.E2E_PSQL_CMD;
  if (override) {
    // Split on whitespace, append -c <sql> -v ON_ERROR_STOP=1
    const parts = override.split(/\s+/).filter(Boolean);
    const [bin, ...args] = parts;
    execFileSync(bin, [...args, '-v', 'ON_ERROR_STOP=1', '-c', sql], { stdio: 'pipe' });
    return;
  }
  execFileSync(
    'docker',
    ['compose', 'exec', '-T', 'postgres', 'psql', '-U', 'nms', '-d', 'nms', '-v', 'ON_ERROR_STOP=1', '-c', sql],
    { cwd: '..', stdio: 'pipe' },
  );
}

function quoted(value: string) {
  return value.replaceAll("'", "''");
}

test.beforeAll(() => {
  // Clean any leftovers from a prior aborted run.
  psql(`delete from saved_alarm_filters where name like 'e2e-%';`);
  psql(`delete from alarms where source_host like 'e2e-%';`);

  // Seed one public read-only filter owned by another user, so the test can
  // exercise the "copy public read-only filter" flow.
  psql(`
    insert into saved_alarm_filters (id, name, owner, is_public, filters, created_at, updated_at)
    values (
      gen_random_uuid(),
      '${quoted(publicReadonlyName)}',
      'other-user',
      true,
      '{"severity":"major","state":"active","limit":100,"offset":0}'::json,
      now(),
      now()
    );
  `);

  // Seed one critical and one major alarm so the page renders severity
  // badges. Without these the AlarmsPage would be empty and the badge
  // colour assertions at the end of the test would never have content to
  // measure. correlation_key just needs to be unique per row.
  psql(`
    insert into alarms (
      id, source_host, severity, category, event_type, message,
      correlation_key, source_type, state, first_seen, last_seen,
      occurrence_count, created_at
    ) values
    (
      gen_random_uuid(),
      '${alarmSourceTag}-crit',
      'critical',
      'device',
      'e2e.device.down',
      'E2E seed: critical alarm',
      '${alarmSourceTag}-crit-key',
      'trap',
      'active',
      now(),
      now(),
      1,
      now()
    ),
    (
      gen_random_uuid(),
      '${alarmSourceTag}-maj',
      'major',
      'link',
      'e2e.link.degraded',
      'E2E seed: major alarm',
      '${alarmSourceTag}-maj-key',
      'trap',
      'active',
      now(),
      now(),
      1,
      now()
    );
  `);
});

test.afterAll(() => {
  psql(`delete from saved_alarm_filters where name like 'e2e-%';`);
  psql(`delete from alarms where source_host like 'e2e-%';`);
});

test('alarm saved filters privacy, publish action, read-only public copy flow, and severity colors', async ({ page }) => {
  // Pre-dismiss the route-onboarding modal (RouteGuideFloat) so it doesn't
  // intercept clicks on the page chrome. The component persists its
  // dismissal in localStorage under 'nms-route-guide-alarms', so we just
  // set that key before the SPA boots.
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem('nms-route-guide-alarms', 'true');
    } catch {
      // ignore (private mode / storage disabled)
    }
  });

  // Surface browser-side failures in CI logs so flaky-debug runs don't
  // require re-downloading traces every time.
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`[browser:${msg.type()}] ${msg.text()}`);
    }
  });
  page.on('requestfailed', (req) => {
    console.log(`[net:failed] ${req.method()} ${req.url()} - ${req.failure()?.errorText ?? 'unknown'}`);
  });
  page.on('response', (resp) => {
    const url = resp.url();
    if (url.includes('/api/alarms/filters') && resp.status() >= 400) {
      console.log(`[net:err] ${resp.request().method()} ${url} -> ${resp.status()}`);
    }
  });

  await page.goto('/alarms');
  await expect(page.getByRole('heading', { name: 'Alarms' })).toBeVisible();
  await expect(page.getByText('Failed to load alarms.')).toHaveCount(0);

  await page.getByRole('button', { name: 'Save Filter' }).click();
  await expect(page.getByText('If unchecked, this filter is saved as private.')).toBeVisible();
  await page.getByLabel('Filter name').fill(privateFilterName);
  await expect(page.getByLabel('Public filter')).not.toBeChecked();
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  // Wait for the Save dialog to close so the next Load Filter click isn't
  // intercepted by the modal overlay (visible in CI where the POST is
  // slower than local).
  await expect(page.getByRole('heading', { name: 'Save alarm filter' })).toHaveCount(0);

  await page.getByRole('button', { name: 'Load Filter' }).click();
  const privateButton = page.getByRole('button', { name: new RegExp(`${privateFilterName} Private · local-dev`) });
  await expect(privateButton).toBeVisible();
  await privateButton.locator('..').getByTitle('Make public').click();
  await expect(page.locator('div').filter({ hasText: privateFilterName }).filter({ hasText: 'Public · local-dev' }).first()).toBeVisible();

  const readonlyPublicButton = page.getByRole('button', { name: new RegExp(`${publicReadonlyName} Public · other-user`) });
  await expect(readonlyPublicButton).toBeVisible();
  await readonlyPublicButton.click();

  await page.getByRole('button', { name: 'Save Filter' }).click();
  await expect(page.getByText(`Loaded public filter: ${publicReadonlyName}.`)).toBeVisible();
  await page.getByLabel('Filter name').fill(publicReadonlyName);
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toBeDisabled();
  await page.getByLabel('Filter name').fill(publicCopyName);
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  // Same dialog-close wait as the private-save path above.
  await expect(page.getByRole('heading', { name: 'Save alarm filter' })).toHaveCount(0);

  await page.getByRole('button', { name: 'Load Filter' }).click();
  await expect(page.locator('div').filter({ hasText: publicCopyName }).filter({ hasText: 'Private · local-dev' }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Load Filter' }).click();
  await page.getByRole('button', { name: 'Clear filters' }).click();

  const criticalBadge = page.locator('span').filter({ hasText: /^critical$/ }).first();
  const majorBadge = page.locator('span').filter({ hasText: /^major$/ }).first();
  await expect(criticalBadge).toBeVisible();
  await expect(majorBadge).toBeVisible();

  const criticalColor = await criticalBadge.evaluate((node) => getComputedStyle(node).color);
  const majorColor = await majorBadge.evaluate((node) => getComputedStyle(node).color);
  expect(criticalColor).not.toBe(majorColor);
});
