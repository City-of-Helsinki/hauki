# Changelog

## [1.3.8](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.3.7...hauki-v1.3.8) (2024-10-31)


### Bug Fixes

* **importer:** Remove re.U as count argument ([ce498a1](https://github.com/City-of-Helsinki/hauki/commit/ce498a11c453cc9664c5feeeacc5872ef8921a72))


### Dependencies

* Bump authlib from 1.3.0 to 1.3.1 ([c2d299f](https://github.com/City-of-Helsinki/hauki/commit/c2d299fb1549476663dfd252e45c1a7b455f3785))
* Bump cryptography from 42.0.7 to 43.0.1 ([fc693f7](https://github.com/City-of-Helsinki/hauki/commit/fc693f768bd46843db74301723be310123f53e59))
* Bump django from 4.2.13 to 4.2.16 ([3c502f2](https://github.com/City-of-Helsinki/hauki/commit/3c502f26b1c364c537c9b2d36f4a2aa9024f4d5c))
* Bump djangorestframework from 3.15.1 to 3.15.2 ([7fc4b44](https://github.com/City-of-Helsinki/hauki/commit/7fc4b441930b40a897039c63263bdcbc1c58db82))
* Bump sentry-sdk from 2.2.1 to 2.16.0 ([adeeaf2](https://github.com/City-of-Helsinki/hauki/commit/adeeaf2c8a4ba53ea08e7a18dad8ca9983886d9d))
* Bump zipp from 3.18.2 to 3.19.1 ([652f458](https://github.com/City-of-Helsinki/hauki/commit/652f458343a95d11278a6ee645fcd2d88ab7a3ac))

## [1.3.7](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.3.6...hauki-v1.3.7) (2024-09-16)


### Bug Fixes

* Sort imported time spans before comparing to DB values ([f400aaf](https://github.com/City-of-Helsinki/hauki/commit/f400aaf51bae6bbc9b2e3d1e8e5ddc9eeeec9ccd))
* Speed up DatePeriodsAsTextForTprek ([16234ca](https://github.com/City-of-Helsinki/hauki/commit/16234cae2aa3b8906e379cb1eb135f6d191977cf))
* Speed up OpeningHours ([bd8591a](https://github.com/City-of-Helsinki/hauki/commit/bd8591a0e121c37d0ff393ddc8deb286191f9237))


### Performance Improvements

* Remove unnecessary qs distinct call ([c3fa71b](https://github.com/City-of-Helsinki/hauki/commit/c3fa71bb9d36d7aba42f9c7d1986a74b6a52f7bf))
* Remove unnecessary qs distinct call ([d8d9e77](https://github.com/City-of-Helsinki/hauki/commit/d8d9e77cfc8066fe1379e930f41f4643036d1aac))

## [1.3.6](https://github.com/City-of-Helsinki/hauki/compare/hauki-v1.3.5...hauki-v1.3.6) (2024-08-22)


### Bug Fixes

* Add constraint for UserOrigin's user and data_source fields ([fc61972](https://github.com/City-of-Helsinki/hauki/commit/fc61972883b03dd7e68d9fdbd7764557c0838a4d))

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
