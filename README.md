# MkDocs Diataxis classifier

This project contains a Python script that scans your MkDocs documentation files, sends each file's content to an API (e.g. OpenAI or Ollama), and retrieves a classification based on the [Diátaxis framework](https://diataxis.fr/) along with a percentage fit for each documentation type (tutorial, how-to, explanation, and reference). This can be useful when attempting to re-organise technical documentation content across the four Diátaxis quadrants.

## Setup

### 1. Clone the Repository

If you haven't already, clone this repository:

```bash
git clone https://github.com/jasonmadigan/diataxis-classifier.git
cd diataxis-classifier
```

### 2. Create a Virtual Environment

It is recommended to use a Python virtual environment to manage dependencies:

```bash
python3 -m venv venv
```

Activate the virtual environment:

```bash
source venv/bin/activate
```

### 3. Install Dependencies

Install the required packages using `pip`:

```bash
pip install -r requirements.txt
```

Also, install the Ollama Python library:

```bash
pip install ollama
```

### 4. Set Your OpenAI API Key

The script uses the OpenAI API. Set your API key as an environment variable:

```bash
export OPENAI_API_KEY="your_actual_api_key_here"
```

> Alternatively, you can modify the script (`classifier.py`) to include your API key directly, but this is not recommended for production.

### 5. Update MkDocs Navigation (if needed)

Ensure your `mkdocs.yml` file contains a `nav` section with the files you want to analyse. Files should be relative to the folder defined as `docs_dir` in your `mkdocs.yml` (or default to `docs`). For example:

```yaml
nav:
  - Home: index.md
  - About: about.md
  - Guides:
      - Tutorial: guides/tutorial.md
      - How-To: guides/how-to.md
```

## Running the Script

The only required argument is the path to your MkDocs configuration file. The script will automatically:

- Clone (or update) multi-repo repositories into a `tmp` folder (located in the same directory as `classifier.py`).
- Deduce the docs directory from your `mkdocs.yml` (defaulting to `docs` if not specified).
- Process the documentation files listed in your MkDocs navigation.
- Truncate file content if needed.
- Send each file’s content to the selected API using the Diátaxis classification prompt.
- Output the JSON response for each file along with an aggregated final JSON result.

### Example: Use OpenAI (default provider)

By default, the script will use OpenAI and the `gpt-4o` model.

```bash
python3 classifier.py -c ../docs.kuadrant.io/mkdocs.yml 
```


### Example: Use OpenAI & specific model

```bash
python3 classifier.py -c ../docs.kuadrant.io/mkdocs.yml --model o1-mini
```

### Example: Use Ollama as the Provider with a Specific Model

To use Ollama, specify the provider (`--provider ollama`), the model (e.g. `granite-code:34b`), and supply your Ollama server's host URL using the `--ollama-host` option. For example, if your Ollama server is running at `http://192.168.1.2:11434`:

```bash
python3 classifier.py -c ../docs.kuadrant.io/mkdocs.yml --provider ollama --model granite-code:34b --ollama-host http://192.168.1.2:11434
```

### Sample Output

```json
{
    "index.md": {
        "dominant": "xplanation",
        "explanation": 70,
        "tutorial": 20,
        "how_to": 5,
        "reference": 5
    },
    "getting-started-single-cluster.md": {
        "dominant": "tutorial",
        "explanation": 10,
        "tutorial": 70,
        "how_to": 15,
        "reference": 5
    },
    "kuadrant-operator/doc/install/install-openshift.md": {
        "dominant": "how_to",
        "explanation": 0,
        "tutorial": 10,
        "how_to": 80,
        "reference": 10
    },
    "architecture/docs/design/architectural-overview-v1.md": {
        "dominant": "explanation",
        "explanation": 70,
        "tutorial": 0,
        "how_to": 10,
        "reference": 20
    },
    "kuadrant-operator/doc/overviews/dns.md": {
        "dominant": "reference",
        "explanation": 20,
        "tutorial": 15,
        "how_to": 35,
        "reference": 70
    },
    "kuadrant-operator/doc/overviews/tls.md": {
        "dominant": "reference",
        "explanation": 10,
        "tutorial": 10,
        "how_to": 30,
        "reference": 50
    },
    "kuadrant-operator/doc/overviews/auth.md": {
        "dominant": "reference",
        "explanation": 20,
        "tutorial": 20,
        "how_to": 40,
        "reference": 80
    }
}
```
      

## Troubleshooting

- **API Key Error:**  
  Ensure that the `OPENAI_API_KEY` environment variable is correctly set.
  
- **Missing Files:**  
  If a documentation file cannot be found, verify that your `mkdocs.yml` navigation paths are correct and that the files exist in the corresponding folder (default is `docs`) or in the cloned repositories.

- **Request Too Large:**  
  If you encounter errors due to large requests, consider adjusting the maximum number of characters sent using the `--max-chars` parameter (default is 15,000 characters).

- **Ollama Issues:**  
  If using Ollama, ensure that:
  - Your Ollama server is running.
  - The model specified is available on your Ollama server (pull it using `ollama pull <model>` if needed).
  - The `--ollama-host` parameter points to the correct host URL (e.g. `http://192.168.1.2:11434`).

Happy coding and documenting!
