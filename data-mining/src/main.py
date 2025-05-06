import requests
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
import json
from datetime import datetime
import time  # Import time module
import sys
 # Resize terminal window to 80x40

load_dotenv()


class GithubRepoFetcher:
    def __init__(self):
        self.base_url = "https://api.github.com"
        token = os.getenv('GITHUB_TOKEN')
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {token}"
        }

    def fetch_python_repos(self, min_stars, per_page) -> List[Dict]:
        query_params = {
            "q": f"language:python stars:>={min_stars}",  # Combine query parts
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
            "page": "11"  # TODO: hardcoded for now
        }

        try:
            response = requests.get(
                f"{self.base_url}/search/repositories",
                headers=self.headers,
                params=query_params
            )
            response.raise_for_status()

            repos = response.json()["items"]
            # Filter for repos where Python is the most used language
            return [
                {
                    "name": repo["full_name"],
                    "stars": repo["stargazers_count"],
                    "description": repo["description"],
                    "url": repo["html_url"],
                    "created_at": repo["created_at"]
                }
                for repo in repos
                if repo.get("language") == "Python"  # Use .get for safety
            ]

        except requests.exceptions.RequestException as e:
            print(f"Error fetching repositories: {e}")
            return []
        except KeyError:
            print(
                f"Unexpected response format from GitHub API: {response.text}")
            return []

    def get_commit_details(self, repo_name: str, commit_sha: str) -> Dict:
        url = f"{self.base_url}/repos/{repo_name}/commits/{commit_sha}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()  # Check for HTTP errors
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching commit details for {commit_sha}: {e}")
            return {}  # Return empty dict on error
        except json.JSONDecodeError:
            print(f"Invalid JSON response for commit details {commit_sha}")
            return {}

    def _matches_keywords(self, text: str, keywords: List[str]) -> bool:
        text = text.lower()
        return any(keyword.lower() in text for keyword in keywords)

    def get_filtered_commits(
        self,
        repo_name: str,
        max_commits: int,
        include_keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        start_date: str = "2010-01-01T00:00:00Z",  # Add start_date parameter
        end_date: str = "2025-01-01T00:00:00Z"     # Add end_date parameter
    ) -> List[Dict]:
        commits_url = f"{self.base_url}/repos/{repo_name}/commits"
        params = {
            "per_page": 100,
            "since": start_date,  # Add since parameter for start date
            "until": end_date     # Add until parameter for end date
        }
        include_keywords = include_keywords or []
        exclude_keywords = exclude_keywords or []

        try:
            commits = []
            page = 1
            fetched_count = 0  # Track fetched commits to respect max_commits

            # Implement pagination to get more commits
            while fetched_count < max_commits:
                params["page"] = page
                print(
                    f"Page {page}, \n{params}")
                response = requests.get(
                    commits_url, headers=self.headers, params=params)
                response.raise_for_status()

                page_commits = response.json()
                if not page_commits:
                    print(
                        f"No more commits found for {repo_name} on page {page}.")
                    break  # No more commits

               
                print(
                    f"Processing page {page} ({len(page_commits)} commits) for {repo_name}")

                for commit in page_commits:
                    # Check if commit data is valid
                    if not commit or "commit" not in commit or "message" not in commit["commit"]:
                        print(
                            f"Skipping invalid commit data: {commit.get('sha', 'N/A')}")
                        continue

                    message = commit["commit"]["message"]

                    # Apply keyword filters
                    if self._matches_keywords(message, exclude_keywords):
                        continue
                    if include_keywords and not self._matches_keywords(message, include_keywords):
                        continue

                    details = self.get_commit_details(repo_name, commit["sha"])
                    if not details:  # Skip if details fetching failed
                        continue

                    # Filter for Python files with small changes and non-empty patches
                    python_changes = [
                        file for file in details.get("files", [])
                        # Ensure file structure is as expected
                        if isinstance(file, dict) and "filename" in file
                        and file["filename"].endswith(".py")
                        and (file.get("additions", 0) + file.get("deletions", 0)) <= 7
                        # Only include changes with patches
                        and file.get("patch")
                    ]

                    # --- New Check: Only keep commits with exactly one changed Python file ---
                    if len(python_changes) == 1:
                        # Get the single changed file
                        changed_file = python_changes[0]

                        # Ensure commit author date exists
                        commit_date = commit.get("commit", {}).get(
                            "author", {}).get("date")
                        if not commit_date:
                            print(
                                f"Skipping commit {commit.get('sha')} due to missing date.")
                            continue  # Skip this commit if date is missing

                        commits.append({
                            "sha": commit["sha"],
                            "message": message,
                            "date": commit_date,
                            "changes": [
                                {
                                    "file": changed_file["filename"],
                                    "patch": changed_file["patch"]
                                }
                                # No loop needed here, as we ensured only one file
                            ]
                        })
                        fetched_count += 1  # Increment count of successfully filtered commits

                        # Show progress
                        if fetched_count % 5 == 0:
                            print(
                                f"Found {fetched_count} matching single-file commits for {repo_name} so far...")
                    # --- End New Check ---
                    # If len(python_changes) is not 1, the commit is skipped implicitly

                    if fetched_count >= max_commits:
                        print(
                            f"Reached max_commits limit ({max_commits}) for {repo_name}.")
                        break  # Exit inner loop

                if fetched_count >= max_commits:
                    break  # Exit outer loop

                page += 1

                # Avoid rate limiting
                print("Waiting briefly to avoid rate limiting...")
                time.sleep(2)  # Use time.sleep

            if not commits:
                print(
                    f"No commits matching criteria found in {repo_name} within the date range.")
            else:
                print(
                    f"Found {len(commits)} matching commits for {repo_name}.")

            return commits

        except requests.exceptions.RequestException as e:
            print(f"Error fetching commits for {repo_name}: {e}")
            # Print response text if available for more context
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response text: {e.response.text}")
            return []
        except KeyError as e:
            print(
                f"KeyError encountered processing commits for {repo_name}: {e}")
            return []
        except Exception as e:  # Catch broader exceptions
            print(f"An unexpected error occurred processing {repo_name}: {e}")
            return []

def save_commits_data(repo_name: str, commits_data: List[Dict[str, Any]],
                      base_dir: str = "commits_data"):
    """Save commits data to a JSON file organized by repository"""
    os.makedirs(base_dir, exist_ok=True)
    repo_filename = repo_name.replace('/', '_')
    filepath = os.path.join(base_dir, f"{repo_filename}_commits.json")

    # Simplify the data structure to focus on bug-related information
    simplified_commits = {
        "repo_name": repo_name,
        "commits": [
            {
                "sha": commit["sha"],
                "message": commit["message"],
                "changes": [
                    {
                        "file": change["file"],
                        "patch": change["patch"]
                    }
                    for change in commit["changes"]
                ]
            }
            for commit in commits_data
        ]
    }

    try:
        with open(filepath, 'w') as f:
            json.dump(simplified_commits, f, indent=2)
        print(f"Commit data for {repo_name} saved to {filepath}")
    except IOError as e:
        print(f"Error saving commit data for {repo_name} to {filepath}: {e}")


def read_processed_repos(log_file="repo_progress.log"):
    """Read the list of already processed repositories"""
    try:
        with open(log_file, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()


def log_processed_repo(repo_name, log_file="repo_progress.log"):
    """Append a processed repository to the log file"""
    try:
        with open(log_file, 'a') as f:
            f.write(f"{repo_name}\n")
        print(f"Added {repo_name} to processed repositories log")
    except IOError as e:
        print(f"Warning: Failed to log processed repository {repo_name}: {e}")


def count_total_commits(commits_dir="commits_data"):
    """Count the total number of commits across all saved JSON files"""
    total_commits = 0

    try:
        if not os.path.exists(commits_dir):
            return 0

        for filename in os.listdir(commits_dir):
            if not filename.endswith('.json'):
                continue

            file_path = os.path.join(commits_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'commits' in data:
                        total_commits += len(data['commits'])
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error reading {file_path}: {e}")

        return total_commits
    except Exception as e:
        print(f"Error counting commits: {e}")
        return 0


if __name__ == "__main__":
    fetcher = GithubRepoFetcher()

    # Maximum number of commits to collect across all repositories
    MAX_TOTAL_COMMITS = 2000

    # Count existing commits
    current_total_commits = count_total_commits()
    print(f"Found {current_total_commits} commits already collected")

    # Get already processed repositories
    processed_repos = read_processed_repos()
    print(f"Found {len(processed_repos)} already processed repositories.")

    # Check if we've already reached the maximum
    if current_total_commits >= MAX_TOTAL_COMMITS:
        print(
            f"Already reached maximum commit count ({MAX_TOTAL_COMMITS}), exiting.")
        exit(0)

    # Get repos with more stars to increase chances of finding bug fixes
    print("Fetching repositories...")
    python_repos = fetcher.fetch_python_repos(min_stars=1000, per_page=100)

    if not python_repos:
        print("No repositories found. Check your GitHub token and rate limits.")
        exit(1)

    print(f"Found {len(python_repos)} potential repositories.")

    # Configure commit filtering with specific error keywords
    include_keywords = [
        "NameError", "UnboundLocalError",
        "IndentationError", "TabError",
        "TypeError", "AttributeError",
        "IndexError", "LookupError"
    ]
    exclude_keywords = ["merge", "sync", "typo",
                        "docs", "documentation", "readme", "refactor", "style", "test"]

    # Process each repository
    successful_repos = 0
    processed_repo_count = 0
    max_repos_to_process = 100
    commits_collected_this_run = 0

    for idx, repo in enumerate(python_repos):
        # Check if we've collected enough commits
        if current_total_commits + commits_collected_this_run >= MAX_TOTAL_COMMITS:
            print(
                f"Reached maximum commit count ({MAX_TOTAL_COMMITS}), stopping.")
            break

        if processed_repo_count >= max_repos_to_process:
            print(
                f"Reached processing limit of {max_repos_to_process} repositories.")
            break

        repo_name = repo["name"]

        # Skip already processed repositories
        if repo_name in processed_repos:
            print(f"Skipping already processed repository: {repo_name}")
            continue

        status_string = f"Processing repository {idx+1}/{len(python_repos)}: {repo_name}"
        print(
            status_string)
            
        sys.stdout.write("\x1b]2;" + status_string + "\x07") 

        try:
            # Get commits matching criteria
            commits = fetcher.get_filtered_commits(
                repo_name,
                max_commits=100,
                include_keywords=include_keywords,
                exclude_keywords=exclude_keywords,
                start_date="2010-01-01T00:00:00Z",
                end_date="2020-01-01T00:00:00Z"
            )

            if not commits:
                print(
                    f"No matching commits found for {repo_name}, skipping...")
                log_processed_repo(repo_name)
                processed_repo_count += 1
                continue

            # Calculate remaining commits we can process
            remaining_commit_capacity = MAX_TOTAL_COMMITS - \
                (current_total_commits + commits_collected_this_run)

            # Limit the commits if necessary
            if len(commits) > remaining_commit_capacity:
                print(
                    f"Limiting commits from {repo_name} to {remaining_commit_capacity} to stay under maximum")
                commits = commits[:remaining_commit_capacity]

            enriched_commits = [
                {
                    "sha": commit["sha"],
                    "message": commit["message"],
                    "changes": commit["changes"]
                }
                for commit in commits
            ]

            if enriched_commits:
                save_commits_data(repo_name, enriched_commits)
                commits_collected_this_run += len(enriched_commits)
                successful_repos += 1
                print(
                    f"Total commits collected so far: {current_total_commits + commits_collected_this_run}/{MAX_TOTAL_COMMITS}")

            # Log this repository as processed
            log_processed_repo(repo_name)
            processed_repo_count += 1

        except Exception as e:
            print(
                f"An unexpected error occurred processing repository {repo_name}: {e}")

        # Avoid rate limiting between repositories
        # if idx < len(python_repos) - 1 and processed_repo_count < max_repos_to_process:
            print("Waiting between repositories to avoid rate limiting...")
            time.sleep(1)

    print(
        f"\nSuccessfully processed and saved data for {successful_repos} out of {processed_repo_count} attempted repositories.")
    print(f"Collected {commits_collected_this_run} new commits in this run.")
    print(
        f"Total commits collected: {current_total_commits + commits_collected_this_run}/{MAX_TOTAL_COMMITS}")
