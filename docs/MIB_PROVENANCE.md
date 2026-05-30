# MIB Provenance Guide

This document describes how to obtain, verify, and manage MIB files in NMS Custom.
Following these guidelines ensures that MIBs loaded into the system are authentic,
unmodified, and traceable to a known authoritative source.

---

## Table of Contents

1. [Recommended MIB Sources](#1-recommended-mib-sources)
2. [Verifying MIB Integrity](#2-verifying-mib-integrity)
3. [Optional GPG/PGP Signature Verification](#3-optional-gpgpgp-signature-verification)
4. [Best Practices for Third-Party MIB Packs](#4-best-practices-for-third-party-mib-packs)
5. [Integration with the Upload API](#5-integration-with-the-upload-api)
6. [Checksum Reference Table](#6-checksum-reference-table)

---

## 1. Recommended MIB Sources

### Cisco

| Source | URL | Notes |
|--------|-----|-------|
| Cisco MIB Locator | https://mibs.cloudapps.cisco.com/ITDIT/MIBS/servlet/index | Search by platform, release, or OID |
| Cisco GitHub mirror | https://github.com/cisco/cisco-mibs | Tagged releases; SHA-verified via GitHub checksums |
| IOS/IOS-XE/IOS-XR release bundles | Distributed with software images | Authoritative; accompanies each platform release |
| Cisco DevNet | https://developer.cisco.com/docs/ios-xe/#!supported-mibs | Cross-reference for YANG/SNMP mapping |

**Recommendation:** Always download MIBs from the Cisco MIB Locator or the GitHub
mirror rather than untrusted third-party aggregators. The Locator provides
release-specific MIB sets, which avoids OID collision from older versions.

### IETF / Standards-Track MIBs

| Source | URL | Notes |
|--------|-----|-------|
| IETF RFC Index | https://www.rfc-editor.org/ | RFC-defined MIBs; stable OID assignments |
| IANA MIB registry | https://www.iana.org/assignments/enterprise-numbers/ | Enterprise number/OID root registry |
| net-snmp mibs | Bundled with net-snmp package | RFC MIBs for SNMPv2/SNMPv3 core objects |

### Vendor-Specific (Other)

- **Juniper:** https://apps.juniper.net/mib-explorer/
- **Nokia (Alcatel-Lucent):** Download with SR OS release packages
- **Arista:** https://www.arista.com/en/support/product-documentation (under each EOS release)
- **Generic aggregators (use with caution):** https://oidref.com, https://mib.bz — cross-reference only; always validate against vendor originals before loading.

---

## 2. Verifying MIB Integrity

### SHA-256 Checksums

Every MIB file should have its SHA-256 digest verified before loading. This catches:

- Accidental file corruption during download or transit
- Truncated downloads
- Deliberate tampering

**Generating a checksum:**

```bash
# macOS / Linux
sha256sum CISCO-SMI.my
# or
shasum -a 256 CISCO-SMI.my

# Output format: <hex-digest>  <filename>
# e17c6e3...abc  CISCO-SMI.my
```

**Verifying a known checksum:**

```bash
# Save the expected digest to a .sha256 file
echo "e17c6e3...abc  CISCO-SMI.my" > CISCO-SMI.my.sha256
sha256sum --check CISCO-SMI.my.sha256
# Output: CISCO-SMI.my: OK
```

---

## 3. Optional GPG/PGP Signature Verification

Some vendors sign their release artifacts with a GPG key. When a signature file
(`.sig`, `.asc`, `.gpg`) is available, verify it before loading the MIB.

### Typical Verification Flow

```bash
# 1. Import the vendor's public key (one-time setup)
gpg --keyserver keyserver.ubuntu.com --recv-keys <KEY_ID>
# or from a key file:
gpg --import vendor-public.asc

# 2. Verify the signature
gpg --verify CISCO-SMI.my.asc CISCO-SMI.my
# Expected output:
#   gpg: Good signature from "Cisco Systems, Inc. <security@cisco.com>"

# 3. If OK, note the fingerprint and match it to the vendor's published key
gpg --fingerprint <KEY_ID>
```

### Cisco IOS-XR Release Key

Cisco IOS-XR software images are signed using Cisco's Code Signing keys. Check
https://www.cisco.com/c/en/us/about/trust-center/secure-software.html for the
current signing key fingerprints and validation procedures.

### Notes

- GPG verification is **optional** for the NMS Custom upload workflow. The API
  does not enforce GPG checks; that step is expected to happen out-of-band
  (in your CI/CD pipeline or pre-upload script) before calling the upload endpoint.
- Store verified public keys in a controlled keyring. Do not auto-import keys from
  unknown sources.

---

## 4. Best Practices for Third-Party MIB Packs

When consuming bundled MIB packs (vendor CDs, community archives, internal mirrors):

1. **Trace to origin.** Every MIB file should reference its source URL in the
   `source_url` upload parameter so auditors can locate the original.

2. **One-file-one-checksum.** Maintain a manifest file (e.g., `mibs.sha256`) that
   lists the SHA-256 hash of each file in the pack:

   ```
   e17c...  CISCO-SMI.my
   3a8b...  CISCO-TC.my
   f021...  CISCO-PRODUCTS-MIB.my
   ```

3. **Pin to a release tag.** When pulling from GitHub mirrors, use a pinned tag or
   commit SHA rather than `main`/`HEAD`. This prevents unintended updates from
   silently changing MIBs in production.

4. **Separate community MIBs from vendor MIBs.** Keep RFC/IANA MIBs in a distinct
   import group from vendor-proprietary ones. This makes it easier to update each
   group independently.

5. **Audit before loading.** Run a parser (e.g., `smilint`, `mib2c`) or the built-in
   NMS Custom MIB parser (`GET /api/mibs/{id}/summary`) against new files before
   promoting them to production. The summary endpoint reports the module name,
   identity OID, and notification count.

6. **Remove deprecated MIBs.** Old MIBs with superseded OIDs can cause trap decode
   conflicts. Mark them `status: inactive` via `PATCH /api/mibs/{id}` rather than
   deleting them, so historical audit trails remain intact.

---

## 5. Integration with the Upload API

The NMS Custom MIB upload endpoint (`POST /api/mibs/upload`) supports two
provenance parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `expected_sha256` | query string | 64-hex-character SHA-256 digest. When supplied, the server verifies the file against this digest and rejects uploads that do not match. **Strongly recommended.** |
| `source_url` | query string | Authoritative URL where the MIB was obtained. Stored in the database for audit purposes. |

### Example: Upload with checksum verification

```bash
# 1. Compute the checksum of the file you are about to upload
CHECKSUM=$(sha256sum CISCO-SMI.my | awk '{print $1}')

# 2. Upload with checksum and source URL
curl -X POST "https://nms.example.com/api/mibs/upload" \
  -H "X-Api-Key: <your-api-key>" \
  -F "file=@CISCO-SMI.my" \
  -G \
  --data-urlencode "expected_sha256=${CHECKSUM}" \
  --data-urlencode "source_url=https://github.com/cisco/cisco-mibs/raw/main/v2/CISCO-SMI.my"
```

### Checksum mismatch response

If the digest does not match, the API returns **HTTP 422**:

```json
{
  "detail": "SHA-256 checksum mismatch. Expected: <expected>  Computed: <actual>. Upload rejected. Verify the file was not corrupted in transit."
}
```

### Warning header when no checksum is provided

Uploads without `expected_sha256` succeed but return the response header:

```
X-MIB-Checksum-Warning: No expected_sha256 checksum was provided. Consider supplying the checksum from a trusted source to verify file integrity.
```

Callers are encouraged to treat this header as an alert in their automation
pipelines.

### CI/CD Pipeline Example

```yaml
# .github/workflows/upload-mibs.yml
- name: Upload MIBs with provenance
  run: |
    for mib in mibs/*.my; do
      checksum=$(sha256sum "$mib" | awk '{print $1}')
      curl -sf -X POST "${NMS_URL}/api/mibs/upload" \
        -H "X-Api-Key: ${NMS_API_KEY}" \
        -F "file=@${mib}" \
        -G \
        --data-urlencode "expected_sha256=${checksum}" \
        --data-urlencode "source_url=${MIB_REPO_URL}/$(basename ${mib})"
    done
```

---

## 6. Checksum Reference Table

Maintain a local `docs/mib-checksums.sha256` file alongside each MIB import
batch. Example format:

```
# NMS Custom MIB import manifest
# Source: https://github.com/cisco/cisco-mibs (tag: v1.0.0)
# Date: 2026-05-30

e17c6e3b0a1d...  CISCO-SMI.my
3a8b72f1cc0e...  CISCO-TC.my
f02145ac8872...  CISCO-PRODUCTS-MIB.my
```

Verify the manifest before each deployment:

```bash
sha256sum --check docs/mib-checksums.sha256
```

---

## See Also

- [MIB Upload API Reference](../backend/app/api/mibs.py) — `POST /api/mibs/upload`
- [MIB Summary API](../backend/app/api/mibs.py) — `GET /api/mibs/{id}/summary`
- [Security Review](SECURITY_REVIEW.md)
- [API Key Management](API_KEY_MANAGEMENT.md)
