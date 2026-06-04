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
      // ASR920 has entries for sfp/uplink/psu but not for mgmt.
      expect(shouldRenderOverlay('Cisco_ASR_920_20SZ_M_Router', 'hotspot-mgmt-0')).toBe(true);
    });

    it('returns false when the profile + type pair is disabled', () => {
      expect(shouldRenderOverlay('Cisco_ASR_920_20SZ_M_Router', 'hotspot-sfp-3')).toBe(false);
      expect(shouldRenderOverlay('Cisco_ASR_920_20SZ_M_Router', 'hotspot-uplink-0')).toBe(false);
      expect(shouldRenderOverlay('Cisco_ASR_920_20SZ_M_Router', 'hotspot-psu-0')).toBe(false);
      expect(shouldRenderOverlay('Cisco_NCS540', 'hotspot-bay-801')).toBe(false);
      expect(shouldRenderOverlay('Cisco_NCS560', 'hotspot-linecard-0')).toBe(false);
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
