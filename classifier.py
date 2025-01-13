#!/usr/bin/env python3
import os
import re
import json
import time
import argparse
import yaml
import openai
import subprocess
from ollama import Client

# OpenAI Settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-api-key")
if OPENAI_API_KEY == "your-openai-api-key":
    raise ValueError("Please set your OpenAI API key in the OPENAI_API_KEY environment variable or directly in the script.")
openai.api_key = OPENAI_API_KEY

CUSTOM_PROMPT = (
    "The following documentation content is provided from a MkDocs file. "
    "Please analyze the content and classify it into the Diátaxis documentation framework quadrants:\n"
    "    - Explanation\n"
    "    - Tutorial\n"
    "    - How-To\n"
    "    - Reference\n\n"
    "For each quadrant, provide a percentage fit as an integer between 0 and 100 (without the '%' sign) "
    "that indicates how much the content aligns with that quadrant. Also, indicate the most dominant quadrant. "
    "Return the output in JSON format with keys 'dominant', 'explanation', 'tutorial', 'how_to', and 'reference'."
    "In the returned output in JSON, ensure the values of 'dominant' is only one of the following, case-sensitive values: 'explanation', 'tutorial', 'how_to', and 'reference'.\n\n"
    "Here is the documentation content:\n\n"
    "{content}\n\n"
    "Ensure your response is a valid JSON object."
)

class CustomLoader(yaml.SafeLoader):
    pass

def ignore_unknown(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    else:
        return None

CustomLoader.add_multi_constructor("tag:yaml.org,2002:python/name:", ignore_unknown)
CustomLoader.add_multi_constructor("!", ignore_unknown)

# multi-repo plugin support
def clone_multi_repos(mkdocs_config_path, target_dir):
    """
    Parse the mkdocs.yml file for the multi-repo plugin configuration,
    then clone (or update) each repository from the 'nav_repos' section.
    Repositories are cloned into target_dir/<repo_name>.
    """
    if not os.path.exists(mkdocs_config_path):
        raise FileNotFoundError(f"Could not find {mkdocs_config_path}")
    
    with open(mkdocs_config_path, "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=CustomLoader)
    
    plugins = config.get("plugins", [])
    multi_repo_config = None
    for item in plugins:
        if isinstance(item, dict) and "multirepo" in item:
            multi_repo_config = item["multirepo"]
            break
    
    if not multi_repo_config:
        print("No multi-repo configuration found in mkdocs.yml.")
        return
    
    nav_repos = multi_repo_config.get("nav_repos", [])
    if not nav_repos:
        print("No nav_repos entries found in the multi-repo config.")
        return

    os.makedirs(target_dir, exist_ok=True)
    for repo in nav_repos:
        name = repo.get("name")
        import_url = repo.get("import_url")
        if not name or not import_url:
            print(f"Skipping invalid repo entry: {repo}")
            continue
        destination = os.path.join(target_dir, name)
        if os.path.exists(destination):
            print(f"Repository '{name}' already exists. Updating...")
            try:
                subprocess.run(["git", "-C", destination, "pull"], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error updating {name}: {e}")
        else:
            base_url = import_url.split("?")[0]
            print(f"Cloning repository '{name}' from {base_url} ...")
            try:
                subprocess.run(["git", "clone", base_url, destination], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error cloning {name}: {e}")

def load_mkdocs_nav(mkdocs_config_path):
    """
    Load the file paths specified in the 'nav' section of the MkDocs configuration.
    Ignores any URLs.
    """
    if not os.path.exists(mkdocs_config_path):
        raise FileNotFoundError(f"Could not find {mkdocs_config_path}")
    with open(mkdocs_config_path, "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=CustomLoader)
    nav_files = []
    nav = config.get("nav", [])
    
    def extract_files(item):
        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, list):
                    for v in value:
                        extract_files(v)
                elif isinstance(value, str):
                    if value.startswith("http://") or value.startswith("https://"):
                        return
                    nav_files.append(re.split(r"#", value)[0])
        elif isinstance(item, list):
            for v in item:
                extract_files(v)
    
    extract_files(nav)
    return nav_files

def read_file_content(file_path, config_path, clone_dir):
    """
    Deduces the docs directory from the MkDocs config file.
    If 'docs_dir' is not specified in the config, defaults to 'docs'.
    Searches for the file in:
      1. base_dir/docs_dir/
      2. base_dir/
      3. The cloned repositories in clone_dir
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=CustomLoader)
    docs_dir = config.get("docs_dir", "docs")
    base = os.path.dirname(config_path)
    
    candidate = os.path.join(base, docs_dir, file_path)
    if os.path.exists(candidate):
        with open(candidate, "r", encoding="utf-8") as f:
            return f.read()
    candidate = os.path.join(base, file_path)
    if os.path.exists(candidate):
        with open(candidate, "r", encoding="utf-8") as f:
            return f.read()
    candidate = os.path.join(clone_dir, file_path)
    if os.path.exists(candidate):
        with open(candidate, "r", encoding="utf-8") as f:
            return f.read()
    raise FileNotFoundError(f"File '{file_path}' not found in expected locations.")

def truncate_content(content, max_chars):
    return content[:max_chars] if len(content) > max_chars else content

def send_to_openai(prompt, model):
    retries = 0
    retry_delay = 2
    max_retries = 5
    while retries < max_retries:
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            error_str = str(e)
            if "Rate limit reached" in error_str:
                m = re.search(r"Please try again in ([\d.]+)s", error_str)
                wait_time = float(m.group(1)) if m else retry_delay
                print(f"Rate limit encountered (OpenAI), sleeping for {wait_time} seconds...")
                time.sleep(wait_time)
                retries += 1
            else:
                print(f"Error contacting OpenAI API: {e}")
                return None
    print("Max retries reached for OpenAI; moving on.")
    return None

def send_to_ollama(prompt, model, ollama_host):
    try:
        client = Client(host=ollama_host)
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert documentation analyst."},
                {"role": "user", "content": prompt},
            ],
            stream=False
        )
        return response.message.content
    except Exception as e:
        print(f"Error contacting Ollama API: {e}")
        return None

def send_request(prompt, provider, model, ollama_host):
    if provider.lower() == "ollama":
        return send_to_ollama(prompt, model, ollama_host)
    else:
        return send_to_openai(prompt, model)

def parse_json_response(response_text):
    try:
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start == -1 or end == -1:
            raise ValueError("No valid JSON object found.")
        json_text = response_text[start:end]
        return json.loads(json_text)
    except Exception as e:
        return {"error": f"Error parsing JSON: {e}", "raw_response": response_text}

def main():
    parser = argparse.ArgumentParser(
        description="Scan MkDocs docs and classify using an API (Diátaxis framework)"
    )
    parser.add_argument("--config", "-c", default="mkdocs.yml", help="Path to the MkDocs configuration file")
    parser.add_argument("--provider", "-p", default="openai", choices=["openai", "ollama"], help="API provider to use (default: openai)")
    parser.add_argument("--model", "-M", default="gpt-4o", help="Model to use")
    parser.add_argument("--ollama-host", default="http://localhost:11434", help="Host for the Ollama server (default: http://localhost:11434)")
    parser.add_argument("--max-chars", "-l", type=int, default=15000, help="Max number of characters to include from each file's content")
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    # Always clone repos into a 'tmp' folder in the same directory as this script.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    clone_dir = os.path.join(script_dir, "tmp")
    print(f"Cloning/updating multi-repo repositories into {clone_dir} ...")
    clone_multi_repos(config_path, clone_dir)
    
    try:
        nav_files = load_mkdocs_nav(config_path)
        if not nav_files:
            print("No files found in the navigation section.")
            return
        print(f"Found {len(nav_files)} file(s) in the navigation.")

        results = {}
        for file in nav_files:
            try:
                content = read_file_content(file, config_path, clone_dir)
                content = truncate_content(content, args.max_chars)
                prompt = CUSTOM_PROMPT.format(content=content)
                print(f"\nProcessing file: {file}")
                raw_response = send_request(prompt, args.provider, args.model, args.ollama_host)
                if raw_response:
                    parsed = parse_json_response(raw_response)
                    print("Response:")
                    print(json.dumps(parsed, indent=4))
                    results[file] = parsed
                else:
                    print("No response received for this file.")
                    results[file] = None
            except Exception as e:
                err_msg = f"Error processing file {file}: {e}"
                print(err_msg)
                results[file] = err_msg
            time.sleep(1)
        
        print("\nFinal aggregated results:")
        print(json.dumps(results, indent=4))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
