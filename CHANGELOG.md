# Changelog

## [1.2.2](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.2.1...hauki-v1.2.2) (2024-04-25)


### Dependencies

* Pin drf-spectacular to 0.26.5 ([eced391](https://github.com/City-of-Helsinki/hauki/commit/eced391313978496bb9e8863dde4b007a2a97e36))

## [1.2.1](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.2.0...hauki-v1.2.1) (2024-04-22)


### Dependencies

* Upgrade django to 4.2 ([56be006](https://github.com/City-of-Helsinki/hauki/commit/56be006b44f7e0a748d7cb34a1ba993173fc7160))

## [1.2.0](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.1.0...hauki-v1.2.0) (2024-04-05)


### Features

* Add data source filter to date period list ([91b4910](https://github.com/City-of-Helsinki/hauki/commit/91b4910f5590e82b2fc8c29729d41427f761e4e1))


### Bug Fixes

* Add missing migration ([2d4a7d4](https://github.com/City-of-Helsinki/hauki/commit/2d4a7d416c5d7d534fd5dd9c9f1c895535a912ee))


### Documentation

* Fix incorrect type for resource parameter ([7693a8d](https://github.com/City-of-Helsinki/hauki/commit/7693a8dc5c93c5d02e17e53128accfc29cdbfa38))

## [1.1.0](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.0.0...hauki-v1.1.0) (2024-01-15)


### Features

* Apply migrations on start, refactor pipelines OH-36 ([#193](https://github.com/City-of-Helsinki/hauki/issues/193)) ([c152a4c](https://github.com/City-of-Helsinki/hauki/commit/c152a4c5c6a1b5fccc49fb79c1b6cd5bf1ba8bc9))
* Make KirjastotImporter errors more Sentry-friendly ([1177dc3](https://github.com/City-of-Helsinki/hauki/commit/1177dc3968735d5211b769b4c63e9882dc8a1303))
* Rollback only libraries with failures when importing libraries ([06e2cda](https://github.com/City-of-Helsinki/hauki/commit/06e2cdaf889adbecb2991032d761156686c7550e))
* Collect all errors in KirjastotImporter instead of stopping on the first one ([e0b3f54](https://github.com/City-of-Helsinki/hauki/commit/e0b3f54ef4aef8fe4bd121c3cd4968965b9e34de))
* TPRekImporter: Change deprecated asiointi.hel.fi to tpr.hel.fi ([9736d4b](https://github.com/City-of-Helsinki/hauki/commit/9736d4b6337d90f28c48abbfe0ba579ef2cfa47f))
* Add date_period_ids parameter in copy_date_periods ([7305fd0](https://github.com/City-of-Helsinki/hauki/commit/7305fd02c085dfb458f380462121d39dc4d83547))
