# Pixhash

[![PyPI version](https://img.shields.io/pypi/v/pixhash)](https://pypi.org/project/pixhash/) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Pixhash** is a simple Cyber Threat Intelligence (CTI) tool that extracts all images from a webpage (including those referenced in CSS), calculate their hashes, and optionally download them.

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

| Flag | Description | Default |
| :--- | :--- | :--- |
| `-t`, `--timeout <sec>` | Network timeout in seconds | `10` |
| `--algo {sha256,sha1,md5}` | Hash algorithm to use | `sha256` |
| `-U`, `--user-agent <string>` | Custom User-Agent header for all HTTP requests | `Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0` |
| `--delay <sec>` | Seconds to wait between each HTTP request | `0` |
| `--download` | Download each image to disk and hash it *(requires -o/--output-dir)* | *disabled* |
| `-o`, `--output-dir <path>` | Directory to save images (when using --download) and/or write the timestamped log file (pixhash_YYYYMMDD_HHMMSS.txt) | `none` |

## Examples

#### 1) Basic usage with default settings. Just hash & print the results (no downloads, no log):
```
pixhash https://example.com
```

#### 2) Hash & write a log file (no images downloaded):
```
pixhash https://example.com -o ./hash-logs
```

#### 3) Download each image, hash it, AND write log:
```
pixhash https://example.com --download -o ./downloaded-images
```

#### 4) Custom User-Agent:
```
pixhash https://example.com -U "CustomUA/1.2" --download -o ./my-images
```

#### 5) Customizing everything (Spaghetti):
```
pixhash https://example.com -U "CustomUA/1.2" -t 4 --algo md5 --delay 3 --download -o ./Org-1
```

> [!IMPORTANT]
> If your URL’s query string uses the `&` separator, wrap it in single quotes so your shell doesn’t treat `&` as the background operator.  
>
> ```bash
> pixhash 'https://example.com/page?foo=1&bar=2' --delay 5
> ```

## Sample Log File

When you run with `-o ./logs`, you will get a file named like `pixhash_20250519_153012.txt` containing:
```
Pixhash Run Log
================
Target URL:    https://example.com
Date:          2025-05-19
Time:          15:30:12
Algorithm:     sha256
User-Agent:    Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0
Output Dir:    ./logs

Results
-------
https://example.com/img/logo.png >> d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2
https://example.com/css/bg.jpg     >> a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1
https://example.com/svg/icon.svg   >> b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3

Hash results and log file saved into:
./logs
```

## License

This project is licensed under the MIT License.

