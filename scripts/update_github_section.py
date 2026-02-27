#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.github.com/graphql"
DEFAULT_USER = "gulldan"
START_MARKER = "<!--START_SECTION:github-metrics-->"
END_MARKER = "<!--END_SECTION:github-metrics-->"
README_PATH = Path(__file__).resolve().parent.parent / "README.md"

QUERY = """
query($login: String!, $from: DateTime!, $after: String) {
  user(login: $login) {
    login
    url
    followers {
      totalCount
    }
    repositories(
      ownerAffiliations: OWNER
      isFork: false
      privacy: PUBLIC
      first: 100
      after: $after
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      totalCount
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        stargazerCount
        languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
            }
          }
        }
      }
    }
    contributionsCollection(from: $from) {
      contributionCalendar {
        totalContributions
      }
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
    }
  }
}
"""


def graphql(token: str, variables: dict[str, object]) -> dict[str, object]:
    payload = json.dumps({"query": QUERY, "variables": variables}).encode("utf-8")
    request = Request(API_URL, data=payload, method="POST")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/vnd.github+json")

    try:
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API HTTP {error.code}: {body}") from error
    except URLError as error:
        raise RuntimeError(f"GitHub API connection error: {error}") from error

    if data.get("errors"):
        messages = "; ".join(err.get("message", "Unknown GraphQL error") for err in data["errors"])
        raise RuntimeError(messages)

    return data["data"]


def collect_metrics(token: str, login: str) -> dict[str, object]:
    after: str | None = None
    stars_total = 0
    language_sizes: Counter[str] = Counter()

    profile_url = f"https://github.com/{login}"
    followers = 0
    repos_total = 0
    commits_30d = 0
    prs_30d = 0
    issues_30d = 0
    reviews_30d = 0

    from_date = (
        (datetime.now(timezone.utc) - timedelta(days=30))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    while True:
        response = graphql(token, {"login": login, "from": from_date, "after": after})
        user = response.get("user")
        if not user:
            raise RuntimeError(f"GitHub user not found: {login}")

        profile_url = user["url"]
        followers = user["followers"]["totalCount"]
        repos_total = user["repositories"]["totalCount"]

        contributions = user["contributionsCollection"]
        commits_30d = contributions["contributionCalendar"]["totalContributions"]
        prs_30d = contributions["totalPullRequestContributions"]
        issues_30d = contributions["totalIssueContributions"]
        reviews_30d = contributions["totalPullRequestReviewContributions"]

        repositories = user["repositories"]
        nodes = repositories.get("nodes") or []
        for repo in nodes:
            stars_total += repo.get("stargazerCount", 0) or 0
            language_edges = (repo.get("languages") or {}).get("edges") or []
            for edge in language_edges:
                name = (edge.get("node") or {}).get("name")
                size = edge.get("size") or 0
                if name and size > 0:
                    language_sizes[name] += size

        page = repositories["pageInfo"]
        if page.get("hasNextPage"):
            after = page.get("endCursor")
            if not after:
                break
        else:
            break

    return {
        "login": login,
        "profile_url": profile_url,
        "followers": followers,
        "repos_total": repos_total,
        "stars_total": stars_total,
        "commits_30d": commits_30d,
        "prs_30d": prs_30d,
        "issues_30d": issues_30d,
        "reviews_30d": reviews_30d,
        "language_sizes": language_sizes,
    }


def format_languages(language_sizes: Counter[str], limit: int = 5) -> str:
    total = sum(language_sizes.values())
    if total <= 0:
        return "n/a"

    top = language_sizes.most_common(limit)
    return ", ".join(f"{name} ({size / total * 100:.0f}%)" for name, size in top)


def render_metrics_lines(metrics: dict[str, object]) -> list[str]:
    profile_url = str(metrics["profile_url"])
    login = str(metrics["login"])
    repo_url = f"{profile_url}?tab=repositories"
    stars_url = f"{profile_url}?tab=stars"
    updated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    top_langs = format_languages(metrics["language_sizes"])

    return [
        f"- Profile: [{login}]({profile_url})",
        f"- Repositories (public, owner, non-fork): [{metrics['repos_total']}]({repo_url})",
        f"- Stars (across owned public repos): [{metrics['stars_total']}]({stars_url})",
        f"- Followers: {metrics['followers']}",
        f"- Contributions (last 30 days): {metrics['commits_30d']}",
        (
            "- PRs / Issues / Reviews (last 30 days): "
            f"{metrics['prs_30d']} / {metrics['issues_30d']} / {metrics['reviews_30d']}"
        ),
        f"- Top languages in owned repos: {top_langs}",
        f"- Updated (UTC): {updated_utc}",
    ]


def replace_marked_section(content: str, lines: list[str]) -> str:
    if START_MARKER not in content or END_MARKER not in content:
        raise RuntimeError(
            f"Missing markers in README: {START_MARKER} ... {END_MARKER}"
        )
    start = content.index(START_MARKER) + len(START_MARKER)
    end = content.index(END_MARKER)
    return content[:start] + "\n" + "\n".join(lines) + "\n" + content[end:]


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("G_USER", DEFAULT_USER)

    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 1

    if not README_PATH.exists():
        print(f"README not found: {README_PATH}", file=sys.stderr)
        return 1

    readme = README_PATH.read_text(encoding="utf-8")
    metrics = collect_metrics(token, login)
    lines = render_metrics_lines(metrics)
    updated = replace_marked_section(readme, lines)

    if updated != readme:
        README_PATH.write_text(updated, encoding="utf-8")
        print("README metrics section updated")
    else:
        print("README metrics section is already up to date")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
