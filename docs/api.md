# YotuDrive API Reference

## Response Envelope

All JSON responses include:

- `ok`: boolean
- `request_id`: correlation ID (also returned as `X-Request-ID` response header)

Error responses include:

- `error.error_code`
- `error.message`
- optional `error.details`
- optional `error.job_id`

## Health

- `GET /api/health`

## Files

- `GET /api/files`
- `DELETE /api/files/<file_id>`
- `POST /api/files/<file_id>/attach`
- `POST /api/upload/manual/register`

## Settings

- `GET /api/settings`
- `PUT /api/settings`

## Verification & Tools

- `POST /api/verify`
- `POST /api/tools/auto-join`
- `POST /api/youtube/playlist/inspect`

## Async Jobs

- `GET /api/jobs/<job_id>`

Returned payload includes `job` object with:

- `id`, `kind`, `status`, `progress`, `message`, `result`, `error`

## Encode / Decode Endpoints

Raw core operations:

- `POST /api/encode/start`
- `POST /api/decode/start`

Full pipeline operations:

- `POST /api/pipeline/encode-video/start`
  - `input_file`, `output_video`
  - optional: `password`, `overrides`, `verify_roundtrip`, `register_in_db`
- `POST /api/pipeline/decode-video/start`
  - `video_path`, `output_file`
  - optional: `password`, `overrides`

## OAuth Upload

- `POST /api/upload/oauth/start`
  - `file_path`, `title`
  - optional: `description`, `privacy_status`, `file_id`

This starts an async job and returns `job_id`.
