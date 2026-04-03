# dvdrip

<!--- BADGES: START --->
[![CI](https://github.com/evandowning/dvdrip/actions/workflows/tests.yml/badge.svg)](https://github.com/evandowning/dvdrip/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/dvdrip.svg)](https://pypi.org/project/dvdrip)
[![Packaging status](https://repology.org/badge/tiny-repos/python:dvdrip.svg)](https://repology.org/project/python:dvdrip/versions)
<!--- BADGES: END --->

Rip DVDs quickly and easily from the command line. Encodes to mp4 (h.264 video, AAC audio) with all audio tracks, subtitles, and chapter markers preserved.

## Requirements

- Python 3.13+
- [HandBrakeCLI](https://handbrake.fr/downloads2.php)

## Build

```shell
make build
```

## Usage

### Scan the disc

```shell
uv run dvdrip --scan -i /dev/cdrom
```

### Rip a movie

```shell
uv run dvdrip --main-feature -i /dev/cdrom -o movie
```

Outputs `movie.mp4` file.

### Rip a tv show

```shell
uv run dvdrip -i /dev/cdrom -o show
```

This creates a `show/` directory containing `Title01_01.mp4`, `Title01_02.mp4`, etc.

## Development

```shell
make format lint test
```
