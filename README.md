# Recipe Converter: Anything to a Valid Recipe | Nextcloud Cookbook
## What It Does
This Python script automatically scans a directory for recipe files (images like JPG, PNG, HEIC, or documents like PDF, TXT, HTML, CSV, etc.) and uses Google's Gemini API (totally free, configurable to `gemini-3.8-flash`) to parse titles, ingredients, instructions, yield, times, and metadata into a clean, Nextcloud Cookbook-compliant JSON format (`schema.org/Recipe`).
After generating and saving the JSON file and creating an appropriate folder title, it automatically cleans up processed local files and uploaded temporary assets on the Gemini servers. It works on Windows and Linux (tested on Windows 11 and Debian 13).

## Why This Way?
I tried a few different approaches:

1. **Full local AI:** Didn't work well (I only have an RX 6700 XT, which struggles with larger models).
2. **OCR scanning + local AI conversion:** Performed better, but still made errors.
3. **Google AI Studio using Flash 3.8:** My current setup (totally free).

With this setup, I reached a success rate of around 99% (only making real mistakes with bad handwriting) and barely have to correct anything manually anymore.

## Features
* **Multi-Format Support:** Converts recipe images (`.jpg`, `.jpeg`, `.png`, `.webp`, `.heic`, `.heif`) as well as documents (`.pdf`, `.txt`, `.md`, `.html`, `.csv`, `.rtf`).
* **Nextcloud Cookbook Compliance:** Formats ingredients, step-by-step instructions, preparation times, cooking times, and yields according to Schema.org standards.
* **Rate-Limit Safe:** Includes a built-in delay between batch API requests to respect Google Gemini rate limits (5 RPM).
* **Automatic Cleanup:** Deletes local files upon successful processing and cleans up remote assets on Gemini servers.
* **Cross-Platform:** Runs seamlessly on Linux and Windows.
* **Fully Automatic**

## Requirements & Installation

1. **Python 3.10+** installed on your system. I think this can everybody do for themselfs (if you want to add a tutorial here, feel free to open a pullrequest). (sudo apt update
sudo apt install python3 python3-venv python3-pip -y python3 -m venv recipe_env
source recipe_env/bin/activate for Debain 13 should work fine. For Windows just download the .exe)
2. Install the official Google GenAI SDK:
```bash
pip install google-genai

```


3. Set your Google Gemini API Key in the script or pass it via environment variables.
4. *(Optional)* Change settings in the script (look at the comments for help, such as changing the Gemini version).


## Usage
Run the Python script directly from your terminal or command prompt:

```bash
python recipe_converter.py

```

The script reads files from the designated input folder and outputs structured JSON files under individual recipe folders in your output directory.


## Automation
### Linux (via Cronjob)
To run the converter automatically (e.g., every hour or daily at midnight), set up a cronjob:

1. Open your crontab editor:
```bash
crontab -e

```


2. Add a line to run the script automatically (example: every hour):
```bash
0 * * * * /usr/bin/python3 /path/to/recipe_converter.py >> /path/to/logfile.log 2>&1

```



## Note
Just a personal project I made for fun. Don't expect a lot of new features or anything like this, but you can open pull requests or issues if something isn't working right. If it helps you, you can add a star.

## TODO
* Day ratelimiter
