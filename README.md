# Automation Studio Project Cleaner

![Automation Studio Project Cleaner Demo](docs/AsCleanerDemo.gif)
A small Windows utility for cleaning generated folders from
B&R Automation Studio projects.

## What it does

The tool recursively scans a selected directory for Automation Studio
projects identified by an `.apj` file.

For each detected project, it can delete:

- `Temp`
- `Binaries`
- `Diagnosis`

It does not delete:

- `.apj` files
- `Logical`
- `Physical`
- other project files

The user must confirm the cleanup before anything is deleted.

## Running the application

### Windows executable

Download the latest release from the GitHub Releases page.

### Running from source

Requires Python 3.14 or newer.

```powershell
python src/ASProjectCleaner.py
