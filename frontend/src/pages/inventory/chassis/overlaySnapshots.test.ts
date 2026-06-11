import { readFileSync, readdirSync, existsSync, type Dirent } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { hotspotType, shouldRenderOverlay } from './overlayPolicy';

/**
 * Freezes the effective overlay behaviour for every shipped chassis profile.
 *
 * For each `public/chassis-assets/<dir>/normalized.json` this snapshots, per
 * view and hotspot type: how many hotspots exist, how many carry an `asset`
 * overlay, and whether the overlay policy renders or suppresses them.
 *
 * If a snapshot diff shows up, one of three things changed:
 *   1. OVERLAY_POLICY in overlayPolicy.ts (intentional visual decision)
 *   2. a profile's normalized.json hotspots/assets (data regeneration)
 *   3. a profileId rename (policy keys silently stop matching!)
 * Review the diff against docs/chassis-view-overlay-policy.md before
 * accepting it with `vitest -u`.
 */

const ASSETS_DIR = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../public/chassis-assets',
);

type Hotspot = { id: string; asset?: unknown };
type View = { id: string; hotspots: Hotspot[] };
type NormalizedProfile = { profileId?: string; views: View[] };

function profileDirs(): string[] {
  return readdirSync(ASSETS_DIR, { withFileTypes: true })
    .filter((entry: Dirent) => entry.isDirectory())
    .map((entry: Dirent) => entry.name)
    .filter((name: string) => existsSync(join(ASSETS_DIR, name, 'normalized.json')))
    .sort();
}

type TypeSummary = {
  hotspots: number;
  withAsset: number;
  overlay: 'rendered' | 'suppressed';
};

function summarizeView(profileId: string | undefined, view: View): Record<string, TypeSummary> {
  const byType: Record<string, TypeSummary> = {};
  for (const hotspot of view.hotspots) {
    const type = hotspotType(hotspot.id);
    const entry = (byType[type] ??= { hotspots: 0, withAsset: 0, overlay: 'rendered' });
    entry.hotspots += 1;
    if (hotspot.asset) entry.withAsset += 1;
    entry.overlay = shouldRenderOverlay(profileId, hotspot.id) ? 'rendered' : 'suppressed';
  }
  return byType;
}

describe('chassis overlay snapshots', () => {
  const dirs = profileDirs();

  it('covers every shipped profile directory', () => {
    expect(dirs.length).toBeGreaterThan(0);
    expect(dirs).toMatchSnapshot();
  });

  it.each(dirs)('%s overlay summary is stable', (dir) => {
    const raw = readFileSync(join(ASSETS_DIR, dir, 'normalized.json'), 'utf-8');
    const profile = JSON.parse(raw) as NormalizedProfile;

    const summary = {
      profileId: profile.profileId ?? null,
      views: Object.fromEntries(
        profile.views.map((view) => [view.id, summarizeView(profile.profileId, view)]),
      ),
    };

    expect(summary).toMatchSnapshot();
  });

  it('every hotspot type within a profile has a consistent overlay decision', () => {
    // The policy operates on (profileId, type) pairs, so two hotspots of the
    // same type in the same profile can never disagree. This guards against
    // future per-hotspot exceptions sneaking in without a policy redesign.
    for (const dir of dirs) {
      const raw = readFileSync(join(ASSETS_DIR, dir, 'normalized.json'), 'utf-8');
      const profile = JSON.parse(raw) as NormalizedProfile;
      for (const view of profile.views) {
        const seen = new Map<string, boolean>();
        for (const hotspot of view.hotspots) {
          const type = hotspotType(hotspot.id);
          const rendered = shouldRenderOverlay(profile.profileId, hotspot.id);
          const previous = seen.get(type);
          expect(
            previous === undefined || previous === rendered,
            `${dir}/${view.id}: type "${type}" has inconsistent overlay decisions`,
          ).toBe(true);
          seen.set(type, rendered);
        }
      }
    }
  });
});
