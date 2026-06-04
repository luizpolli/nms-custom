/**
 * Chassis overlay render policy.
 *
 * Some EPNM base chassis SVGs are *full artwork*: they already paint every
 * SFP, QSFP, PSU, fan tray and RP at the right pixels.  Drawing our hotspot
 * `asset` SVG on top of those produces visual doubling (offset duplicates,
 * ghost connectors).  Other base SVGs are frame-only and *need* the overlay
 * to show any port at all.
 *
 * This file is the single source of truth for "should we render an overlay
 * for hotspot type X on profile Y?".  It is **presentation config**, not
 * inventory data — that's why it lives in the frontend and not in the
 * chassis JSON.  The JSON keeps its `asset` blocks intact so that:
 *
 *   - clicking a hotspot still resolves to the right `typeId` / PID
 *   - the inspector panel still shows the right module image
 *   - alarm mapping by `slotKey` is unaffected
 *
 * Adding a new entry here is a *visual* decision.  Procedure:
 *   1. Open the chassis in the UI.
 *   2. If you see duplicated ports/PSUs/fans on top of the base SVG, note
 *      which hotspot type is duplicated (sfp, qsfp28, psu, fan, ...).
 *   3. Add `{ '<profileId>': { '<type>': false } }` below.
 *   4. NEVER fix this by deleting `asset` from normalized.json — that is
 *      a data mutation and we lose the typeId metadata.
 *
 * The hotspot "type" is the second segment of `hotspot.id`
 * (e.g. `hotspot-sfp-3` -> "sfp", `hotspot-bay-801` -> "bay").
 */

export type OverlayPolicy = Record<string, Record<string, boolean>>;

/**
 * Profile -> hotspot-type -> shouldRenderOverlay.
 *
 * Default for missing entries: `true` (render the overlay).
 * Explicit `false` disables the overlay for that (profile, type) pair.
 */
export const OVERLAY_POLICY: OverlayPolicy = {
  // ASR920 base SVG is full artwork (704 paths) — it already paints all 24
  // SFP bays, the 4 RJ45/SFP uplinks, the PSU slots and the fan tray.  The
  // overlay was duplicating every connector.  Verified visually 2026-06-04.
  asr920: {
    sfp: false,
    uplink: false,
    psu: false,
  },
};

/**
 * Extract the hotspot type prefix from a hotspot id.
 * Examples: "hotspot-sfp-3" -> "sfp", "hotspot-bay-801" -> "bay".
 * Falls back to the whole id when it doesn't match the expected shape.
 */
export function hotspotType(hotspotId: string): string {
  const parts = hotspotId.split('-');
  if (parts.length >= 2 && parts[0] === 'hotspot') {
    return parts[1];
  }
  return hotspotId;
}

/**
 * Should the overlay <SlotAsset> be rendered for this hotspot on this profile?
 */
export function shouldRenderOverlay(profileId: string | undefined, hotspotId: string): boolean {
  if (!profileId) return true;
  const profilePolicy = OVERLAY_POLICY[profileId];
  if (!profilePolicy) return true;
  const t = hotspotType(hotspotId);
  if (Object.prototype.hasOwnProperty.call(profilePolicy, t)) {
    return profilePolicy[t];
  }
  return true;
}
