# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-06

### Added

- Client for every API endpoint: IP, email and phone checks, the three batch checks, balance and my IP.
- Typed results with the `flagged()` and `flag_reasons()` helpers.
- Typed exceptions for every API error status.
- Opt-in retry of HTTP 429 responses, honouring `Retry-After`.
- Batch helpers that chunk requests by 100 items.
- Bring-your-own `httpx.Client`.

[Unreleased]: https://github.com/dahleedam/fraudnova-python/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/dahleedam/fraudnova-python/releases/tag/v1.0.0
