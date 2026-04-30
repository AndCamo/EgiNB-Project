# Eginb Project

## Installation

This project requires **Python >= 3.13**. 
The repository has been initializated with `uv` package manager, but it also supports the classic `venv` + `pip` workflow.

- Option 1: Classic method (`venv` + `pip`): 


- Option 2: Fast method (using `uv`)

### Option 1: Classic method (`venv` + `pip`)

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```

2. Activate the virtual environment:
   * **Windows:** `.venv\Scripts\activate`
   * **macOS/Linux:** `source .venv/bin/activate`

3. Install the required libraries:
   ```bash
   pip install -r requirements.txt
   ```

### Option 2: Fast method (using `uv`)
If [`uv`](https://docs.astral.sh/uv/) is installed:

1. Sync the environment and install dependencies:
   ```bash
   uv sync
   ```