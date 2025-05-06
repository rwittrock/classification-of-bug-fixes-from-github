# Engineering Research Project

## GitHub Token Setup

Use a **GitHub fine-grained token** stored in a `.env` file to authenticate and scrape repository data.

## Data Collection

Run the data scraper:
python data-mining/src/main.py

### Output Format

The resulting data will look like:

```json
{
  "repo_name": "3b1b/manim",
  "commits": [
    {
      "sha": "2d552e0aa4878b24cbe2e1c4d23ee7caa32e7e33",
      "message": "Fix Ellipse construct...",
      "changes": [
        {
          "file": "manimlib/mobject/geometry.py",
          "patch": "@@ -316,8 +316,8 @@ class Ellipse(Circle):\n \n..."
        }
      ]
    }
  ]
}
```

To classify commit messages and code changes, run:
python regex/main.py
