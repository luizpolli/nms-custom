import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';

const testRun = Date.now();
const privateFilterName = `e2e-private-${testRun}`;
const publicReadonlyName = `e2e-public-readonly-${testRun}`;
const publicCopyName = `${publicReadonlyName}-copy`;

function psql(sql: string) {
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
  psql(`delete from saved_alarm_filters where name like 'e2e-%';`);
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
});

test.afterAll(() => {
  psql(`delete from saved_alarm_filters where name like 'e2e-%';`);
});

test('alarm saved filters privacy, publish action, read-only public copy flow, and severity colors', async ({ page }) => {
  await page.goto('/alarms');
  await expect(page.getByRole('heading', { name: 'Alarms' })).toBeVisible();
  await expect(page.getByText('Failed to load alarms.')).toHaveCount(0);

  await page.getByRole('button', { name: 'Save Filter' }).click();
  await expect(page.getByText('If unchecked, this filter is saved as private.')).toBeVisible();
  await page.getByLabel('Filter name').fill(privateFilterName);
  await expect(page.getByLabel('Public filter')).not.toBeChecked();
  await page.getByRole('button', { name: 'Save', exact: true }).click();

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
