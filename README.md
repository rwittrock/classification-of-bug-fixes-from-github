# Engineering Research Project
Use Github fine grained token in .env file to scrape data using data-mining/src/main.py

The resulting data looks something like:
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

To classify fixes use regex/main.py. Results show up in the terminal.