# Pixhash

[![PyPI version](https://img.shields.io/pypi/v/pixhash)](https://pypi.org/project/pixhash/) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Pixhash** is a simple Cyber Threat Intelligence (CTI) tool that extracts all images from a webpage (including those referenced in CSS) and calculate their hashes.

## Disclaimer

**Pixhash** is provided solely for legitimate security research, threat intelligence, and defensive purposes. The author and contributors are not responsible for any damage, legal liability, or other consequences arising from improper or malicious use of this tool.

## Installation

Install from PyPI:

```bash
pip install pixhash
```

Or install directly from Github:
```bash
pip install git+https://github.com/fwalbuloushi/pixhash.git
```

## Usage

After installation, the pixhash command is available:
```bash
pixhash [OPTIONS] URL
```

### Options

| Flag | Description |
| :--- | :--- |
| `-t`, `--timeout TIMEOUT` | Network timeout in seconds (default: 10.0) |
| `--algo {sha256,sha1,md5}` | Hash algorithm to use (default: `sha256`) |
| `--agent {desktop,mobile}` | User-Agent type (default: `desktop`) |
| `--delay DELAY` | Seconds to wait between each HTTP request (default: 0) |
| `-h`, `--help` | Show this help message |

## Examples

Basic usage with default settings:
```
pixhash https://example.com
```

Set a 5-second timeout and use MD5:
```
pixhash https://example.com -t 5 --algo md5
```

Slow down requests by 2 seconds and pretend to be a mobile browser:
```
pixhash --delay 2 --agent mobile https://example.com
```

## How it works

1. Fetches the HTML of the page you specify.

2. Parses all <img>, <source> tags, CSS url(...) references (inline & external), Open Graph images, and icons.

3. Downloads each resource (respecting your timeout and delay).

4. Hashes the raw image bytes using your chosen algorithm.

5. Prints each image’s full URL and its calculated hash.


## License

This project is licensed under the MIT License.

