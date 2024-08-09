# Changelog

## [1.3.5](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.3.4...hauki-v1.3.5) (2024-08-09)


### Reverts

* Remove earlier fix for HAUKI-656 ([88d4ce4](https://github.com/City-of-Helsinki/hauki/commit/88d4ce4233cab1cb1d2c17087c83c5cbe162c074))

## [1.3.4](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.3.3...hauki-v1.3.4) (2024-07-26)


### Bug Fixes

* Remove null=True from UserOrigin.origin_id ([60fe755](https://github.com/City-of-Helsinki/hauki/commit/60fe75567d15c7f56ac53395a92d4ffe0f4fd0cc))


### Dependencies

* Bump pre-commit tool versions ([d239a20](https://github.com/City-of-Helsinki/hauki/commit/d239a204a9b336c3d3d01b9709ae1f432885f33d))


### Documentation

* **readme:** Add note about .git-blame-ignore-revs ([5e93609](https://github.com/City-of-Helsinki/hauki/commit/5e93609666894f726fea956e006d2d8482c03bc0))

## [1.3.3](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.3.2...hauki-v1.3.3) (2024-05-29)


### Bug Fixes

* **kirjastot:** Force sync finish ([a8707f8](https://github.com/City-of-Helsinki/hauki/commit/a8707f8bbabce826385509b583805a5dc10a9ae4))

## [1.3.2](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.3.1...hauki-v1.3.2) (2024-05-24)


### Dependencies

* Upgrade dependencies ([1b55384](https://github.com/City-of-Helsinki/hauki/commit/1b553848b37026c5f5660722ca72fb256ed119b9))

## [1.3.1](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.3.0...hauki-v1.3.1) (2024-05-14)


### Bug Fixes

* **kirjastot:** Use finnish translations for holidays ([18a96c9](https://github.com/City-of-Helsinki/hauki/commit/18a96c9df1c2ecc4e2d45a60ba530e53522f5c35))

## [1.3.0](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.2.2...hauki-v1.3.0) (2024-05-08)


### Features

* Add resource_data_source filter to date periods ([822de66](https://github.com/City-of-Helsinki/hauki/commit/822de66eb7360684a82d2f4341042cccccc21137))
* Enforce date filters with resource data source ([a73d85e](https://github.com/City-of-Helsinki/hauki/commit/a73d85ea4d4b4f40e890803be55c4a102efe8a16))

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
