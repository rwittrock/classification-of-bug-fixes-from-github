import json
import re
import os

# Keywords expected to be found in the commit messages
message_types = {
    'Name Error: Cannot find name': ['NameError', 'UnboundLocalError'],
    'Wrong/Inconsistent Indentation': ['IndentationError', 'TabError'],
    'Errors with types (Wrong type, null etc.)': ['TypeError', 'AttributeError'],
    'Arrays and Maps': ['IndexError', 'LookupError'],
}


def load_json(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: The file at {file_path} was not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: The file at {file_path} is not a valid JSON.")
        return None


def classify_commit(commit):

    match_counts = {message_type: 0 for message_type in message_types}
    commit_no_specials = ''.join(e for e in commit['message'] if e.isalnum())
    for message_type, keywords in message_types.items():
        for keyword in keywords:
            if re.search(re.escape(keyword), commit_no_specials, re.IGNORECASE):
                match_counts[message_type] += 1

        commit['type'] = classify(match_counts)

        # print(match_counts)
    return commit


def classify(match_counts):
    max_val = max(match_counts.values())

    if max_val == 0:
        return 'Not Classified'

    count = list(match_counts.values()).count(max_val)
    if count > 1:
        return 'Not Classified'
    for key, value in match_counts.items():
        if value == max_val:
            return key


def run(path: str):
    data = load_json(path)
    if data is None:
        print("Invalid JSON file")
        return

    commit_classification = []

    if (isinstance(data, dict)):
        # print("Checking commits for file: ", path)
        for commit in data['commits']:
            commit = classify_commit(commit)
            change = commit['changes'][0]
            commit_classification.append(
                {"classification": commit['type'], "change": change})

        open(path + '.classified.json', 'w').write(json.dumps(data, indent=4))

    return commit_classification


def main():
    file_path = input("Enter JSON file path: ")
    print(file_path)
    # file_path = './commits_data/huggingface_transformers_commits.json'

    if not file_path.endswith('.json'):
        os.listdir(file_path)
        for file in os.listdir(file_path):
            if not file.endswith('.classified.json'):
                run(os.path.join(file_path, file))
    else:
        run(file_path)
# main()
