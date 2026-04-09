# dvdrip

<!--- BADGES: START --->
[![CI](https://github.com/evandowning/dvdrip/actions/workflows/tests.yml/badge.svg)](https://github.com/evandowning/dvdrip/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/dvdrip.svg)](https://pypi.org/project/dvdrip)
[![Packaging status](https://repology.org/badge/tiny-repos/python:dvdrip.svg)](https://repology.org/project/python:dvdrip/versions)
<!--- BADGES: END --->

Rip DVDs quickly and easily from the command line. Encodes to mp4 (h.265 video, AAC audio) with all audio tracks, subtitles, and chapter markers preserved.

## Requirements

* [uv](https://docs.astral.sh/uv/)
* [HandBrakeCLI](https://handbrake.fr/downloads2.php)

## Build

```shell
make build
```

## Usage

```shell
uv run dvdrip -i /dev/cdrom -o output
```

## Development

```shell
make format lint test
```
