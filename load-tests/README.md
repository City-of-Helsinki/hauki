# Hauki load testing

Scripts for load testing Hauki API.

## Prerequisities

* [k6](https://k6.io/docs/getting-started/installation) installed

## How to run the tests

This script works as a wrapper for the k6 command and ensures that the proper authentication token is provided in the requests. Thus you can pass all the same parameters as you would do when using k6 directly.

```bash
    ./run.sh -v 1 -i 1 <SCRIPT>
```

## How to run Hauki scenarios

```bash
./run.sh hauki-scenarios.js
```

## HTML report
The script is using [k6-reporter](https://github.com/benc-uk/k6-reporter) for outputting html test report. The results `summary.html` is created under this folder.

You can also open it automatically after the test like this.
```bash
./run.sh hauki-scenarios.js && open summary.html
```
