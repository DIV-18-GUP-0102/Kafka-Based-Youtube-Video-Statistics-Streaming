import json

def save_to_json(data, filename="output.json"):
    """
    Saves the given data to a JSON file.

    Args:
        data (list): The list of dictionaries to save as JSON.
        filename (str, optional): The name of the file to save to. Defaults to "output.json".
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Data successfully saved to {filename}")
    except Exception as e:
        print(f"An error occurred while saving to JSON: {e}")


