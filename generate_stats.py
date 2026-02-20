#!/usr/bin/env python3
"""
GitHub Profile Stats Generator
Fetches comprehensive statistics including private repositories
and generates beautiful, animated SVG cards for the README.
"""

import os
import json
import sys
from datetime import datetime, timezone
from collections import defaultdict
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# Configuration
GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "CidQu")
# Clean up excluded repos list
EXCLUDE_REPOS_RAW = os.environ.get("EXCLUDE_REPOS", "").split(",")
EXCLUDE_REPOS = {r.strip() for r in EXCLUDE_REPOS_RAW if r.strip()}

# GraphQL API endpoint
GRAPHQL_URL = "https://api.github.com/graphql"

def get_svg_styles():
    """Return common CSS styles injected into every SVG."""
    return """
    <style>
        :root {
            --bg: #ffffff;
            --card-bg: #ffffff;
            --border: #e4e2e2;
            --text-title: #24292f;
            --text-body: #57606a;
            --text-value: #24292f;
            --bar-bg: #ebecf0;
            --accent: #0969da;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg: #0d1117;
                --card-bg: #0d1117;
                --border: #30363d;
                --text-title: #c9d1d9;
                --text-body: #8b949e;
                --text-value: #c9d1d9;
                --bar-bg: #21262d;
                --accent: #58a6ff;
            }
        }
        * { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
        .card { fill: var(--card-bg); stroke: var(--border); stroke-width: 1px; }
        .title { fill: var(--text-title); font-size: 16px; font-weight: 600; }
        .stat-label { fill: var(--text-body); font-size: 12px; font-weight: 500; }
        .stat-value { fill: var(--text-value); font-size: 20px; font-weight: 700; }
        .lang-name { fill: var(--text-body); font-size: 12px; font-weight: 600; }
        .lang-pct { fill: var(--text-value); font-size: 12px; font-weight: 600; text-anchor: end; }
        .anim-target { opacity: 0; animation: slideIn 0.8s ease-out forwards; }
        .delay-1 { animation-delay: 0.1s; }
        .delay-2 { animation-delay: 0.2s; }
        .delay-3 { animation-delay: 0.3s; }
        .delay-4 { animation-delay: 0.4s; }
        .delay-5 { animation-delay: 0.5s; }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
    """

def graphql_query(query, variables=None):
    """Execute a GraphQL query against GitHub API."""
    if not GITHUB_TOKEN:
        print("❌ Error: Valid GH_TOKEN or GITHUB_TOKEN environment variable required.", file=sys.stderr)
        sys.exit(1)
        
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json"
    }
    
    data = {"query": query}
    if variables:
        data["variables"] = variables
    
    req = Request(
        GRAPHQL_URL,
        data=json.dumps(data).encode(),
        headers=headers,
        method="POST"
    )
    
    try:
        with urlopen(req) as response:
            result = json.loads(response.read().decode())
            if "errors" in result:
                print(f"GraphQL Application Error: {json.dumps(result['errors'])}", file=sys.stderr)
            return result
    except HTTPError as e:
        error_body = e.read().decode()
        print(f"GraphQL Network Error ({e.code}): {error_body}", file=sys.stderr)
        sys.exit(1)


def get_user_info():
    """Get basic user information."""
    query = """
    query($username: String!) {
        user(login: $username) {
            name
            login
            bio
            company
            location
            followers { totalCount }
            following { totalCount }
            contributionsCollection {
                contributionCalendar { totalContributions }
            }
        }
    }
    """
    result = graphql_query(query, {"username": GITHUB_USERNAME})
    if "data" not in result or not result["data"].get("user"):
        print(f"❌ User {GITHUB_USERNAME} not found or token lacks permissions.", file=sys.stderr)
        sys.exit(1)
    return result["data"]["user"]


def get_all_repositories():
    """Get all repositories (public and private) with language info."""
    query = """
    query($username: String!, $cursor: String) {
        user(login: $username) {
            repositories(
                first: 100,
                after: $cursor,
                ownerAffiliations: OWNER,
                isFork: false
            ) {
                pageInfo { hasNextPage endCursor }
                nodes {
                    name
                    isPrivate
                    primaryLanguage { name color }
                    languages(first: 10) {
                        edges {
                            node { name color }
                            size
                        }
                    }
                    stargazerCount
                    forkCount
                    diskUsage
                }
            }
        }
    }
    """
    
    all_repos = []
    cursor = None
    
    while True:
        result = graphql_query(query, {"username": GITHUB_USERNAME, "cursor": cursor})
        repos = result["data"]["user"]["repositories"]
        
        for repo in repos["nodes"]:
            if repo["name"] not in EXCLUDE_REPOS:
                all_repos.append(repo)
        
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]
    
    return all_repos


def calculate_language_stats(repos):
    """Calculate language statistics from repositories."""
    lang_bytes = defaultdict(int)
    lang_colors = {}
    lang_repos = defaultdict(set)
    
    for repo in repos:
        repo_langs_obj = repo.get("languages")
        repo_langs = repo_langs_obj.get("edges", []) if repo_langs_obj else []
        
        if not repo_langs and repo.get("primaryLanguage"):
            lang = repo["primaryLanguage"]["name"]
            lang_bytes[lang] += 1
            lang_colors[lang] = repo["primaryLanguage"].get("color") or "#858585"
            lang_repos[lang].add(repo["name"])
        else:
            for edge in repo_langs:
                lang = edge["node"]["name"]
                size = edge["size"]
                lang_bytes[lang] += size
                lang_colors[lang] = edge["node"].get("color") or "#858585"
                lang_repos[lang].add(repo["name"])
    
    total = sum(lang_bytes.values())
    stats = []
    
    for lang, bytes_count in sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True):
        percentage = (bytes_count / total * 100) if total > 0 else 0
        stats.append({
            "name": lang,
            "bytes": bytes_count,
            "percentage": percentage,
            "color": lang_colors[lang],
            "repo_count": len(lang_repos[lang])
        })
    
    return stats


def calculate_repo_stats(repos):
    """Calculate general repository statistics."""
    total_stars = sum(r.get("stargazerCount", 0) for r in repos)
    total_forks = sum(r.get("forkCount", 0) for r in repos)
    private_count = sum(1 for r in repos if r.get("isPrivate"))
    public_count = len(repos) - private_count
    
    return {
        "total_repos": len(repos),
        "public_repos": public_count,
        "private_repos": private_count,
        "total_stars": total_stars,
        "total_forks": total_forks,
    }


def get_commit_activity():
    """Get commit activity from contributions collection."""
    query = """
    query($username: String!) {
        user(login: $username) {
            contributionsCollection {
                contributionCalendar {
                    weeks {
                        contributionDays { contributionCount }
                    }
                }
            }
        }
    }
    """
    result = graphql_query(query, {"username": GITHUB_USERNAME})
    return result["data"]["user"]["contributionsCollection"]


def generate_language_card(lang_stats, width=400, height=255):
    """Generate an animated SVG card for language statistics."""
    top_langs = lang_stats[:6]
    
    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        get_svg_styles(),
        f'<rect class="card" x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="12"/>',
        '<text class="title anim-target delay-1" x="25" y="35">💻 Most Used Languages</text>',
    ]
    
    y_pos = 75
    for i, lang in enumerate(top_langs):
        delay = i + 2
        bar_width = min(280, (lang["percentage"] / 100) * 280)
        color = lang["color"]
        
        svg_parts.extend([
            f'<g class="anim-target delay-{delay}">',
            f'<text class="lang-name" x="25" y="{y_pos}">{lang["name"]}</text>',
            f'<text class="lang-pct" x="375" y="{y_pos}">{lang["percentage"]:.1f}%</text>',
            f'<line x1="25" y1="{y_pos + 12}" x2="375" y2="{y_pos + 12}" stroke="var(--bar-bg)" stroke-width="8" stroke-linecap="round"/>',
            f'<line x1="25" y1="{y_pos + 12}" x2="{25 + bar_width}" y2="{y_pos + 12}" stroke="{color}" stroke-width="8" stroke-linecap="round">',
            f'<animate attributeName="x2" values="25;{25 + bar_width}" dur="0.8s" begin="0.3s" calcMode="spline" keySplines="0.2 0.8 0.2 1" fill="freeze" />',
            f'</line>',
            '</g>'
        ])
        y_pos += 30
    
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def generate_stats_card(repo_stats, user_info, width=400, height=255):
    """Generate an animated SVG card for repository statistics."""
    contributions = user_info.get("contributionsCollection", {})
    total_contribs = contributions.get("contributionCalendar", {}).get("totalContributions", 0)
    
    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        get_svg_styles(),
        f'<rect class="card" x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="12"/>',
        '<text class="title anim-target delay-1" x="25" y="35">📊 GitHub Statistics</text>',
        
        # Row 1
        '<g class="anim-target delay-2">',
        '<text class="stat-label" x="25" y="65">Total Repositories</text>',
        f'<text class="stat-value" x="25" y="89">{repo_stats["total_repos"]}</text>',
        f'<text class="stat-label" x="25" y="107" font-size="10">🔓 {repo_stats["public_repos"]} public · 🔒 {repo_stats["private_repos"]} private</text>',
        '</g>',
        
        '<g class="anim-target delay-3">',
        '<text class="stat-label" x="205" y="65">Total Stars</text>',
        f'<text class="stat-value" x="205" y="89">⭐ {repo_stats["total_stars"]}</text>',
        '</g>',
        
        # Row 2
        '<g class="anim-target delay-3">',
        '<text class="stat-label" x="25" y="150">Contributions (1y)</text>',
        f'<text class="stat-value" x="25" y="174">🔥 {total_contribs:,}</text>',
        '</g>',
        
        '<g class="anim-target delay-4">',
        '<text class="stat-label" x="205" y="150">Total Forks</text>',
        f'<text class="stat-value" x="205" y="174">🍴 {repo_stats["total_forks"]}</text>',
        '</g>',
        
        # Row 3
        '<g class="anim-target delay-4">',
        '<text class="stat-label" x="25" y="215">Followers</text>',
        f'<text class="stat-value" x="25" y="239">👥 {user_info["followers"]["totalCount"]}</text>',
        '</g>',
        
        '<g class="anim-target delay-5">',
        '<text class="stat-label" x="205" y="215">Following</text>',
        f'<text class="stat-value" x="205" y="239">🏃 {user_info["following"]["totalCount"]}</text>',
        '</g>',
        
        '</svg>'
    ]
    return '\n'.join(svg_parts)


def generate_activity_graph(contributions, width=800, height=140):
    """Generate a rounded bar chart for contribution activity over the last 6 months."""
    weeks = contributions.get("contributionCalendar", {}).get("weeks", [])[-26:]
    max_contribs = max([sum(d.get("contributionCount", 0) for d in w.get("contributionDays", [])) for w in weeks] + [1])
    
    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        get_svg_styles(),
        f'<rect class="card" x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="12"/>',
        '<text class="title anim-target delay-1" x="25" y="32">📈 Contribution Activity (Last 6 Months)</text>',
        '<g transform="translate(25, 60)">',
        '<g class="anim-target delay-2">',
    ]
    
    max_bar_height = 55
    bar_width = (width - 50) / len(weeks) if weeks else 10
    
    for i, week in enumerate(weeks):
        week_contribs = sum(d.get("contributionCount", 0) for d in week.get("contributionDays", []))
        bar_height = (week_contribs / max_contribs) * max_bar_height if max_contribs > 0 else 0
        
        opacity = 0.2 + (0.8 * (week_contribs / max_contribs))
        if week_contribs == 0:
            opacity = 0.05
            
        x = i * bar_width
        y = max_bar_height - bar_height
        
        # Base subtle stub for zero/empty
        svg_parts.extend([
            f'<rect x="{x}" y="{max_bar_height - 3}" width="{bar_width * 0.7}" height="3" fill="var(--bar-bg)" rx="1.5"/>',
        ])
        
        if week_contribs > 0:
            svg_parts.extend([
                f'<rect x="{x}" y="{y}" width="{bar_width * 0.7}" height="{bar_height}" fill="var(--accent)" opacity="{opacity}" rx="2">',
                f'<animate attributeName="y" values="{max_bar_height};{y}" dur="0.8s" begin="0.1s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1"/>',
                f'<animate attributeName="height" values="0;{bar_height}" dur="0.8s" begin="0.1s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1"/>',
                '</rect>'
            ])
            
    svg_parts.extend([
        '</g>',
        '</g>',
        '</svg>'
    ])
    return '\n'.join(svg_parts)


def generate_private_indicator(width=400, height=80):
    """Generate a small card indicating private repos are included."""
    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        get_svg_styles(),
        f'<rect class="card" x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="12"/>',
        '<g class="anim-target delay-1">',
        '<text x="25" y="35" fill="var(--text-title)" font-family="sans-serif" font-size="14" font-weight="600">🔒 Private Repositories Included</text>',
        '<text x="25" y="55" fill="var(--text-body)" font-family="sans-serif" font-size="12">These stats represent absolutely all my work.</text>',
        '</g>',
        '</svg>'
    ]
    return '\n'.join(svg_parts)


def main():
    """Main function to generate all stats."""
    print("🚀 Fetching GitHub statistics...")
    
    # Ensure assets directory exists
    os.makedirs("assets", exist_ok=True)
    
    print(f"📊 Fetching user info for {GITHUB_USERNAME}...")
    user_info = get_user_info()
    
    print("📦 Fetching all repositories (including private)...")
    repos = get_all_repositories()
    
    print("🌈 Calculating language statistics...")
    lang_stats = calculate_language_stats(repos)
    
    print("📈 Calculating repository statistics...")
    repo_stats = calculate_repo_stats(repos)
    
    print("🔥 Fetching contribution activity...")
    contributions = get_commit_activity()
    
    # Generate SVG cards
    print("🎨 Generating SVG cards...")
    
    lang_svg = generate_language_card(lang_stats)
    stats_svg = generate_stats_card(repo_stats, user_info)
    activity_svg = generate_activity_graph(contributions)
    private_svg = generate_private_indicator()
    
    # Save SVG files
    with open("assets/languages.svg", "w", encoding="utf-8") as f:
        f.write(lang_svg)
    
    with open("assets/stats.svg", "w", encoding="utf-8") as f:
        f.write(stats_svg)
    
    with open("assets/activity.svg", "w", encoding="utf-8") as f:
        f.write(activity_svg)
    
    with open("assets/private-indicator.svg", "w", encoding="utf-8") as f:
        f.write(private_svg)
    
    print("✅ Stats generated successfully!")
    print(f"   📁 Saved to assets/ directory")
    print(f"   📦 Total Repositories: {repo_stats['total_repos']}")
    print(f"   🔓 Public: {repo_stats['public_repos']}")
    print(f"   🔒 Private: {repo_stats['private_repos']}")
    print(f"   ⭐ Total Stars: {repo_stats['total_stars']}")
    print(f"   🌈 Top Language: {lang_stats[0]['name'] if lang_stats else 'N/A'}")


if __name__ == "__main__":
    main()
