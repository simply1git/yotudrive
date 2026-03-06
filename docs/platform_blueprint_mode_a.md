# YotuDrive Platform Blueprint (Mode A)

## 1. Executive Summary

YotuDrive will operate as a robust, user-friendly, limited-membership platform (25 users) that provides Google Drive/Photos-like access while storing large payload data on YouTube instead of platform-owned blob storage.

The platform stores account and metadata only (file index, video pointers, policy/config, job state), keeping platform cost low while preserving multi-device sync and account-based usability.

## 2. Product Goals

- Deliver a simple cloud-drive style user experience across desktop, web, and mobile.
- Keep infrastructure costs low by storing only lightweight metadata on platform services.
- Use YouTube as archive storage for large payload data.
- Provide strong security and account recovery while remaining user-friendly.
- Support real users in a controlled beta (allowlisted 25 members).

## 3. Product Scope

### In Scope (Beta)

- Google login authentication with allowlist and membership cap.
- Metadata sync across devices under one account.
- Core pages: Library, Encoder, Decoder, Settings, Transfers.
- Manual and OAuth-assisted YouTube upload registration flows.
- Archive decode and restore with integrity verification.
- Albums for photo/video collections.
- Admin controls for user management and operational visibility.

### Out of Scope (Initial Beta)

- Public self-signup for unlimited users.
- Team collaboration permissions and sharing matrix.
- Platform-hosted binary file storage.
- Real-time collaborative editing.

## 4. User Experience Model

### 4.1 Main User Pages

1. Library
2. Encoder
3. Decoder
4. Transfers
5. Settings

### 4.2 Upload Flow

1. User signs in with Google.
2. User selects file or folder in Encoder.
3. User configures options (encryption, block size, ECC, naming).
4. Platform encodes payload into archive video.
5. User uploads manually to YouTube or platform uploads via OAuth.
6. User confirms and registers video pointer.
7. Metadata is stored and synced to account library.

### 4.3 Restore Flow

1. User picks an item from Library or pastes YouTube link.
2. Platform inspects archive metadata.
3. User confirms details and enters archive password if encrypted.
4. Platform decodes and verifies checksum.
5. Original file/folder is restored to target location.

## 5. Authentication and Access Control

- Primary auth method: Google OAuth.
- Platform is closed beta only.
- Access gate: allowlisted email addresses.
- Hard cap: 25 active members.
- Admin users can add or disable members.

## 6. Data and Storage Strategy

### 6.1 Platform-Stored Data (Small Metadata Only)

- User profile and account status.
- File index and album mappings.
- YouTube video IDs/URLs and archive metadata.
- Job status/progress and sync revisions.
- Security/audit events.

### 6.2 Not Stored by Platform

- Raw file bytes.
- Large payload blobs.

### 6.3 Archive Backend

- YouTube stores the encoded archive videos.
- Platform metadata points to those videos for recovery.

## 7. Security Architecture

## 7.1 Password and Encryption Policy

- Archive passwords must never be stored in plaintext.
- Distinguish account login from archive encryption secrets.
- Server stores hashes and encrypted key wrappers only.

### 7.2 User-Friendly Recovery Model

To balance robust security and usability:

- Create a per-user Data Encryption Key (DEK).
- Store two wrapped copies:
  - DEK wrapped by user-derived key.
  - DEK wrapped by server/KMS recovery key.
- Recovery flow requires:
  - Google re-authentication.
  - MFA step-up verification.
  - recovery audit log entry.

### 7.3 Operational Security Controls

- MFA for recovery-sensitive operations.
- Session revocation and device management.
- Rotation policy for server master keys.
- Security event logging and anomaly alerts.

## 8. Platform Architecture (Mode A)

### 8.1 Core Components

- Web client (library and account operations).
- Desktop app (high-performance encode/decode and local workflows).
- Mobile app (upload, browse, restore initiation).
- Control-plane API (auth, metadata, jobs, sync).
- Worker layer (background jobs).
- Postgres metadata database.

### 8.2 Suggested Hosting Stack

- DB/Auth: Supabase (Postgres + Auth + RLS)
- API: Render or Railway
- Web UI: Vercel or Cloudflare Pages
- Queue/cache (optional): Upstash Redis

Rationale:

- Minimal operational burden.
- Fast MVP deployment.
- Low cost for metadata-only workloads.

## 9. Data Model (MVP)

- users
- user_membership (allowlist/cap state)
- files
- file_versions
- file_locations
- albums
- album_items
- devices
- jobs
- sync_events
- security_events

## 10. API Surface (MVP)

- /auth/google/start
- /auth/google/callback
- /auth/session
- /admin/users (owner only)
- /files
- /files/{id}
- /files/{id}/locations/youtube
- /albums
- /jobs
- /sync/changes
- /decode/inspect
- /decode/start

## 11. Reliability and Robustness Requirements

- Idempotent metadata upsert operations.
- Retry with exponential backoff for YouTube and network operations.
- Structured error envelopes with correlation IDs.
- Job state machine with resumable steps.
- End-to-end checksum validation on restore.

## 12. Mobile App Strategy

- Framework: React Native (Expo) for iOS and Android.
- MVP mobile features:
  - Google login
  - Library browsing
  - upload from gallery/files
  - decode request initiation
  - transfer/job monitoring
- Keep heavy encode/decode logic in backend/desktop paths initially.

## 13. User Operations and Support

- In-app troubleshooting panel with log export.
- Human-readable error messages for:
  - missing password
  - invalid link/private video
  - quota/rate limits
  - checksum mismatch
- Recovery instructions with security guardrails.

## 14. Compliance and Policy Awareness

- Respect YouTube API and platform usage policies.
- Handle API quota and rate-limit responses gracefully.
- Keep a fallback manual upload path when API automation is constrained.

## 15. Delivery Plan

### Phase 1 - Foundation

- Auth, allowlist, user cap, metadata schema, admin endpoints.

### Phase 2 - Core Product

- Library page, Encoder registration flow, Decoder inspect/restore flow.

### Phase 3 - Multi-Device Sync

- Sync events, device sessions, conflict policy, mobile MVP.

### Phase 4 - Hardening

- Recovery model, security audits, observability, failure injection tests.

## 16. Go/No-Go Criteria for Beta Launch

- All auth and access controls validated.
- Multi-device metadata sync works for at least 3 test devices per account.
- End-to-end encode/upload/register/restore flow verified repeatedly.
- Security recovery flow tested and audited.
- Operational runbook and support docs published.

## 17. Final Product Statement

YotuDrive Mode A is a controlled, robust, and user-friendly archive platform where users access their data from anywhere through account-synced metadata while large payload storage remains externalized to YouTube. This design minimizes platform cost, preserves usability, and creates a strong base for future scale.