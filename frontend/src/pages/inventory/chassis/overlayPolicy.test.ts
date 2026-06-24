import { describe, expect, it } from 'vitest';
import { hotspotType, shouldRenderOverlay, OVERLAY_POLICY } from './overlayPolicy';

describe('overlayPolicy', () => {
  describe('hotspotType', () => {
    it('extracts the second segment of a well-formed hotspot id', () => {
      expect(hotspotType('hotspot-sfp-3')).toBe('sfp');
      expect(hotspotType('hotspot-bay-801')).toBe('bay');
      expect(hotspotType('hotspot-qsfp28-0')).toBe('qsfp28');
      expect(hotspotType('hotspot-rp-1')).toBe('rp');
    });

    it('falls back to the whole id when the shape is unexpected', () => {
      expect(hotspotType('weird')).toBe('weird');
      expect(hotspotType('not-a-hotspot')).toBe('not-a-hotspot');
    });
  });

  describe('shouldRenderOverlay', () => {
    it('defaults to true when profileId is unknown or undefined', () => {
      expect(shouldRenderOverlay(undefined, 'hotspot-sfp-3')).toBe(true);
      expect(shouldRenderOverlay('unknown-profile', 'hotspot-sfp-3')).toBe(true);
    });

    it('defaults to true when the profile has no entry for that type', () => {
      // OVERLAY_POLICY ships empty by design (see file header) — no shipped
      // profile currently has any entry, so any (profile, type) pair defaults true.
      expect(shouldRenderOverlay('Cisco_ASR_920_20SZ_M_Router', 'hotspot-mgmt-0')).toBe(true);
    });

    it('returns false when the profile + type pair is disabled', () => {
      // Inject a fixture entry to exercise the `false` branch of the lookup
      // logic, then remove it so other tests still see the real (empty) policy.
      OVERLAY_POLICY['__test_profile__'] = { sfp: false };
      try {
        expect(shouldRenderOverlay('__test_profile__', 'hotspot-sfp-3')).toBe(false);
        expect(shouldRenderOverlay('__test_profile__', 'hotspot-uplink-0')).toBe(true);
      } finally {
        delete OVERLAY_POLICY['__test_profile__'];
      }
    });

    it('does not affect other profiles', () => {
      expect(shouldRenderOverlay('ncs540-12z16g', 'hotspot-rp-0')).toBe(true);
      expect(shouldRenderOverlay('ncs55a1', 'hotspot-sfp-3')).toBe(true);
    });
  });

  describe('policy invariants', () => {
    it('all policy entries are explicit booleans', () => {
      for (const profile of Object.keys(OVERLAY_POLICY)) {
        for (const [t, v] of Object.entries(OVERLAY_POLICY[profile])) {
          expect(typeof v, `${profile}.${t} must be a boolean`).toBe('boolean');
        }
      }
    });
  });
});
