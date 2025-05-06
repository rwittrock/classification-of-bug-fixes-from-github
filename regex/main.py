import json
import os
from classifier import classify_commit

def parse_diff(diff_string, commit_sha, bug_type=None):
    lines_added = []
    lines_deleted = []
    lines_changed = []

    lines = diff_string.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("-") and not line.startswith("---"):
            # Collect all consecutive deleted lines
            deleted_lines = []
            while (
                i < len(lines)
                and lines[i].startswith("-")
                and not lines[i].startswith("---")
            ):
                deleted_lines.append(lines[i][1:])
                i += 1

            # Check for consecutive added lines
            added_lines = []
            while (
                i < len(lines)
                and lines[i].startswith("+")
                and not lines[i].startswith("+++")
            ):
                added_lines.append(lines[i][1:])
                i += 1

            # Match deletions to additions one-to-one
            if added_lines:
                max_pairs = min(len(deleted_lines), len(added_lines))
                for j in range(max_pairs):
                    added_line = added_lines[j]
                    deleted_line = deleted_lines[j]
                    is_outer = (
                        len(added_line) - len(added_line.lstrip())
                        == min(
                            len(line) - len(line.lstrip())
                            for line in added_lines
                            if line.strip()
                        )
                        if added_line.strip()
                        else False
                    )
                    lines_changed.append(
                        {
                            "deleted": deleted_line.strip(),
                            "added": added_line.strip(),
                            "is_outer": is_outer,
                        }
                    )
                # Handle excess lines as additions or deletions
                for j in range(max_pairs, len(deleted_lines)):
                    line = deleted_lines[j]
                    is_outer = (
                        len(line) - len(line.lstrip())
                        == min(
                            len(l) - len(l.lstrip())
                            for l in deleted_lines
                            if l.strip()
                        )
                        if line.strip()
                        else False
                    )
                    lines_deleted.append(
                        {
                            "line": line.strip(),
                            "is_outer": is_outer,
                        }
                    )
                for j in range(max_pairs, len(added_lines)):
                    line = added_lines[j]
                    lines_added.append(
                        {
                            "line": line.strip(),
                            "is_outer": (
                                len(line) - len(line.lstrip())
                                == min(
                                    len(l) - len(l.lstrip())
                                    for l in added_lines
                                    if l.strip()
                                )
                                if line.strip()
                                else False
                            ),
                        }
                    )
            else:
                # Add is_outer here too
                non_empty = [line for line in deleted_lines if line.strip()]
                min_indent = (
                    min(len(line) - len(line.lstrip()) for line in non_empty)
                    if non_empty
                    else 0
                )
                for line in deleted_lines:
                    lines_deleted.append(
                        {
                            "line": line.strip(),
                            "is_outer": (
                                len(line) - len(line.lstrip()) == min_indent
                                if line.strip()
                                else False
                            ),
                        }
                    )

        elif line.startswith("+") and not line.startswith("+++"):
            # Collect added lines not matched with deletions
            added_lines = []
            while (
                i < len(lines)
                and lines[i].startswith("+")
                and not lines[i].startswith("+++")
            ):
                added_lines.append(lines[i][1:])
                i += 1
            non_empty = [line for line in added_lines if line.strip()]
            min_indent = (
                min(len(line) - len(line.lstrip()) for line in non_empty)
                if non_empty
                else 0
            )
            for line in added_lines:
                lines_added.append(
                    {
                        "line": line.strip(),
                        "is_outer": (
                            len(line) - len(line.lstrip()) == min_indent
                            if line.strip()
                            else False
                        ),
                    }
                )
        else:
            i += 1

    return {
        "lines_added": lines_added,
        "lines_deleted": lines_deleted,
        "lines_changed": lines_changed,
        "bug_type": bug_type,
        "commit_sha": commit_sha,
    }


def load_commits_from_json(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data["commits"]


def map_bug_type_to_error(bug_type):
    # Simple heuristic to extract bug type from commit message
    if "Name Error: Cannot find name" in bug_type:
        return "NameError"
    elif "Wrong/Inconsistent Indentation" in bug_type:
        return "IndentationError"
    elif "Errors with types (Wrong type, null etc.)" in bug_type:
        return "TypeError"
    elif "Arrays and Maps" in bug_type:
        return "IndexError"
    else:
        return None


base_feature_flags_skeleton = {
    "Addition of if condition": False,
    "Removal of if condition": False,
    "Change of if condition": False,
    "Addition of else condition": False,
    "Removal of else condition": False,
    "Changed number of method call parameters": False,
    "Changed method call parameters": False,
    "Removal of operation(s)": False,
    "Addition of operation(s)": False,
    "Change loop signature": False,
    "Addition variable assignment": False,
    "Change variable assignment": False,
    "Addition of switch branch": False,
    "Addition of switch": False,
    "Removal of switch branch": False,
    "Removal of switch": False,
    "Addition of try statement": False,
    "Removal of try statement": False,
    "Addition of except block": False,
    "Removal of except block": False,
    "Change of method declaration": False,
    "Addition of loop": False,
    "Removal of loop": False,
    "Changed method call": False,
}


def classify(differences: list):
    base_features = {
        "Addition of if condition": 0,
        "Removal of if condition": 0,
        "Change of if condition": 0,
        "Addition of else condition": 0,
        "Removal of else condition": 0,
        "Changed number of method call parameters": 0,
        "Changed method call parameters": 0,
        "Removal of operation(s)": 0,
        "Addition of operation(s)": 0,
        "Change loop signature": 0,
        "Addition variable assignment": 0,
        "Change variable assignment": 0,
        "Addition of switch branch": 0,
        "Addition of switch": 0,
        "Removal of switch branch": 0,
        "Removal of switch": 0,
        "Addition of try statement": 0,
        "Removal of try statement": 0,
        "Addition of except block": 0,
        "Removal of except block": 0,
        "Change of method declaration": 0,
        "Addition of loop": 0,
        "Removal of loop": 0,
        "Changed method call": 0,
    }

    bug_type_features = {
        "NameError": base_features.copy(),
        "IndentationError": base_features.copy(),
        "TypeError": base_features.copy(),
        "IndexError": base_features.copy(),
    }

    def is_assignment(line):
        return (
            " = " in line
            and not line.lstrip().startswith(("if ", "elif ", "while ", "for "))
            and "==" not in line
            and "!=" not in line
            and "<=" not in line
            and ">=" not in line
        )

    def is_method_call(line):
        # Basic check for parentheses, excluding definitions and keywords
        return (
            "(" in line
            and ")" in line
            and not line.lstrip().startswith(
                (
                    "def ",
                    "class ",
                    "if ",
                    "elif ",
                    "while ",
                    "for ",
                    "try:",
                    "except ",
                    "match ",
                    "case ",
                )
            )
        )

    def count_params(line):
        """Count the number of parameters in a function call, handling nested parentheses correctly."""
        try:
            # Find the position of the first opening parenthesis
            open_pos = line.index("(")

            stack = []
            params = 1  # Start with 1 because parameters are comma-separated
            in_string = False
            string_char = None

            for i in range(open_pos, len(line)):
                char = line[i]

                # Handle string literals to avoid counting commas inside strings
                if char in ['"', "'"]:
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char:
                        in_string = False

                # Only process parentheses and commas when not inside strings
                if not in_string:
                    if char == "(":
                        stack.append(char)
                    elif char == ")":
                        if stack:
                            stack.pop()
                        # When we've closed the outermost parenthesis, we're done
                        if not stack:
                            break
                    elif char == "," and len(stack) == 1:
                        # Only count commas at the top level of the function call
                        params += 1

            # Check if we have parameters or an empty parenthesis
            param_text = line[open_pos + 1 : i].strip()
            return 0 if not param_text else params

        except ValueError:
            return 0  # Handle cases with no parentheses

    no_change_count = 0
    total_diffs_processed = 0

    for diff in differences:
        bug_type = diff.get("bug_type")
        if not bug_type or bug_type not in bug_type_features:
            print(
                f"Warning: Skipping diff with unknown or missing bug_type: {bug_type}"
            )
            continue

        base_feature_flags = base_feature_flags_skeleton.copy()

        for line_data in diff.get("lines_added", []):
            if not line_data.get("is_outer", False):
                continue

            line = line_data["line"].strip()
            if line.startswith("if ") or line.startswith("elif "):
                base_feature_flags["Addition of if condition"] = True
            elif line.startswith("else:"):
                base_feature_flags["Addition of else condition"] = True
            elif line.startswith("try:"):
                base_feature_flags["Addition of try statement"] = True
            elif line.startswith("except "):
                base_feature_flags["Addition of except block"] = True
            elif line.startswith("case "):
                base_feature_flags["Addition of switch branch"] = True
            elif line.startswith("match "):
                base_feature_flags["Addition of switch"] = True
            elif line.startswith(("while ", "for ")):
                base_feature_flags["Addition of loop"] = True
            elif is_assignment(line):
                base_feature_flags["Addition variable assignment"] = True
            elif is_method_call(line):
                base_feature_flags["Addition of operation(s)"] = True

        for line in diff.get("lines_deleted", []):
            line = line_data["line"].strip()
            if line.startswith("if ") or line.startswith("elif "):
                base_feature_flags["Removal of if condition"] = True
            elif line.startswith("else:"):
                base_feature_flags["Removal of else condition"] = True
            elif line.startswith("try:"):
                base_feature_flags["Removal of try statement"] = True
            elif line.startswith("except "):
                base_feature_flags["Removal of except block"] = True
            elif line.startswith("case "):
                base_feature_flags["Removal of switch case"] = True
            elif line.startswith("match "):
                base_feature_flags["Removal of switch"] = True
            elif line.startswith(("while ", "for ")):
                base_feature_flags["Removal of loop"] = True
            elif is_method_call(line):
                base_feature_flags["Removal of operation(s)"] = True

        for change in diff.get("lines_changed", []):
            if not change.get("is_outer", False):
                continue

            added_text = change.get("added", "").strip()
            deleted_text = change.get("deleted", "").strip()

            # Variable assignment
            if is_assignment(added_text) and is_assignment(deleted_text):
                if added_text != deleted_text:
                    base_feature_flags["Change variable assignment"] = True

            # If
            is_added_if = added_text.startswith(("if ", "elif "))
            is_deleted_if = deleted_text.startswith(("if ", "elif "))

            if is_added_if and is_deleted_if:
                if added_text != deleted_text:
                    base_feature_flags["Change of if condition"] = True

            # Loop
            is_added_loop = any(keyword in added_text for keyword in ("while", "for "))
            is_deleted_loop = any(
                keyword in deleted_text for keyword in ("while", "for ")
            )

            if is_added_loop and is_deleted_loop:
                if added_text != deleted_text:
                    # Filter out cases where the lines are very similar or are just comments
                    if not (
                        added_text.startswith("#") and deleted_text.startswith("#")
                    ) and not (
                        added_text.strip().replace(" ", "")
                        == deleted_text.strip().replace(" ", "")
                    ):
                        base_feature_flags["Change loop signature"] = True
                        print(added_text, deleted_text)

            # Method
            is_added_call = is_method_call(added_text)
            is_deleted_call = is_method_call(deleted_text)
            is_added_def = added_text.startswith("def ")
            is_deleted_def = deleted_text.startswith("def ")

            if is_added_call and is_deleted_call:
                # Extract method name from both lines (before the parenthesis)
                added_method = added_text.split("(")[0].strip()
                deleted_method = deleted_text.split("(")[0].strip()

                params_added = count_params(added_text)
                params_deleted = count_params(deleted_text)

                if added_method != deleted_method:
                    base_feature_flags["Changed method call"] = True
                elif params_added != params_deleted:
                    base_feature_flags["Changed number of method call parameters"] = (
                        True
                    )
                else:
                    base_feature_flags["Changed method call parameters"] = True
            elif is_added_def and is_deleted_def:
                base_feature_flags["Change of method declaration"] = True

        any_feature_flagged = False

        for feature in base_feature_flags:
            if base_feature_flags[feature] == True:
                bug_type_features[bug_type][feature] += 1
                any_feature_flagged = True

        if not any_feature_flagged:
            no_change_count += 1

        total_diffs_processed += 1

        print("\n=== Bug Type Features ===")
        print(json.dumps(bug_type_features[bug_type], indent=2))

        # Print the current diff
        print("\n=== Current Diff ===")
        print(json.dumps(diff, indent=2))

        # Print the commit ID
        print("\n=== Commit ID ===")
        print(json.dumps(diff["commit_sha"], indent=2))

    print("\n--- Classification Results ---")
    for bug_type, counts in bug_type_features.items():
        non_zero_features = {k: v for k, v in counts.items() if v > 0}
        if non_zero_features:
            print(f"\nBug Type: {bug_type}")
            for feature, count in non_zero_features.items():
                print(f"  {feature}: {count}")

    return bug_type_features, total_diffs_processed, no_change_count


# Main execution
commits_data_dir = "commits_data"
all_json_files = [f for f in os.listdir(commits_data_dir) if f.endswith(".json")]

if not all_json_files:
    print(f"No JSON files found in {commits_data_dir}")
else:
    print(f"Found {len(all_json_files)} JSON files to process")

    # Initialize consolidated results
    all_differences = []
    repo_stats = {}

    for json_file in all_json_files:
        file_path = os.path.join(commits_data_dir, json_file)
        repo_name = json_file.replace("_commits.json", "")
        # print(f"\nProcessing {repo_name}...")

        try:
            commits = load_commits_from_json(file_path)
            repo_differences = []

            for commit in commits:
                for change in commit["changes"]:
                    patch = change.get("patch")
                    if patch:
                        commit = classify_commit(commit)
                        bug_type = map_bug_type_to_error(commit["type"])

                        # bug_type = extract_bug_type_from_message(
                        #     commit['message'])
                        if bug_type:
                            parsed_diff = parse_diff(patch, commit["sha"], bug_type)
                            # Add repo information to the diff
                            parsed_diff["repo"] = repo_name
                            repo_differences.append(parsed_diff)
                            all_differences.append(parsed_diff)

            repo_stats[repo_name] = {
                "total_diffs": len(repo_differences),
                "by_bug_type": {},
            }

            # Count bug types for this repo
            for diff in repo_differences:
                bug_type = diff.get("bug_type")
                if bug_type:
                    repo_stats[repo_name]["by_bug_type"][bug_type] = (
                        repo_stats[repo_name]["by_bug_type"].get(bug_type, 0) + 1
                    )

            # print(
            #     f"Processed {len(repo_differences)} diffs with identified bug types from {repo_name}")

        except Exception as e:
            print(f"Error processing {json_file}: {str(e)}")

    # Print overall statistics
    print("\n=== Overall Statistics ===")
    print(f"Total repositories processed: {len(repo_stats)}")
    print(f"Total diffs analyzed: {len(all_differences)}")

    # Count total bugs by type
    bug_type_counts = {}
    for diff in all_differences:
        bug_type = diff.get("bug_type")
        if bug_type:
            bug_type_counts[bug_type] = bug_type_counts.get(bug_type, 0) + 1

    print("\nBug types distribution:")
    for bug_type, count in bug_type_counts.items():
        print(f"  {bug_type}: {count}")

# Perform classification on all differences
print("\n=== Classification Results Across All Repositories ===")
classification_results, total_classified, no_changes_detected = classify(all_differences)

print(f"\nTotal commits classified: {total_classified}")
print(f"Commits with no detected feature changes: {no_changes_detected}")

# Count commits with no changes observed
total_commits_analyzed = len(all_differences)

for diff in all_differences:
    bug_type = diff.get("bug_type")
    if bug_type and bug_type in classification_results:
        feature_counts = classification_results[bug_type]
        # Check if any features are non-zero for this diff
        non_zero = any(feature_counts[feature] > 0 for feature in feature_counts)
        if not non_zero:
            commits_with_no_changes += 1
