#!/usr/bin/env python3
from __future__ import annotations

import email.utils
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup


SH_TZ = timezone(timedelta(hours=8))
USER_AGENT = "ai-morning-brief-bot/1.0"
HEADERS = {"User-Agent": USER_AGENT}
TIMEOUT = 20


@dataclass
class NewsItem:
    company: str
    date: str
    title: str
    link: str
    source: str


@dataclass
class GithubItem:
    repo: str
    description: str
    url: str
    reason: str


def fetch_text(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def fetch_json(url: str) -> dict:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def google_news_rss(query: str) -> list[NewsItem]:
    url = (
        "https://news.google.com/rss/search?"
        f"q={requests.utils.quote(query)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    )
    xml_text = fetch_text(url)
    root = ET.fromstring(xml_text)
    items: list[NewsItem] = []

    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        parsed = email.utils.parsedate_to_datetime(pub_date)
        local_date = parsed.astimezone(SH_TZ).strftime("%Y-%m-%d")

        if " - " in title:
            headline, source = title.rsplit(" - ", 1)
        else:
            headline, source = title, "Google News"

        items.append(
            NewsItem(
                company="",
                date=local_date,
                title=headline.strip(),
                link=link,
                source=source.strip(),
            )
        )

    return items


def pick_company_news() -> list[NewsItem]:
    primary_queries = [
        ("Anthropic / Claude", '"Anthropic" OR Claude AI when:3d'),
        ("OpenAI", '"OpenAI" when:3d'),
        ("Google / Gemini / DeepMind", 'Google Gemini OR DeepMind AI when:3d'),
        ("DeepSeek", '"DeepSeek" when:3d'),
        ("Kimi / Moonshot", '"Moonshot AI" OR Kimi AI when:3d'),
    ]
    backup_queries = [
        ("阿里 / 通义", 'Alibaba Qwen OR 通义千问 when:3d'),
        ("字节 / 豆包", 'ByteDance Doubao OR 豆包 AI when:3d'),
        ("百度 / 文心", 'Baidu ERNIE OR 文心一言 when:3d'),
        ("智谱", 'Zhipu AI OR 智谱 AI when:3d'),
    ]

    picked: list[NewsItem] = []
    seen_links: set[str] = set()

    for company, query in primary_queries:
        for item in google_news_rss(query):
            if item.link in seen_links:
                continue
            item.company = company
            picked.append(item)
            seen_links.add(item.link)
            break

    for company, query in backup_queries:
        if len(picked) >= 7:
            break
        for item in google_news_rss(query):
            if item.link in seen_links:
                continue
            item.company = company
            picked.append(item)
            seen_links.add(item.link)
            break

    return picked[:7]


def parse_trending_repo(anchor: str) -> str:
    return "/".join(part.strip() for part in anchor.split("/") if part.strip())


def pick_github_projects() -> list[GithubItem]:
    trending_html = fetch_text("https://github.com/trending?since=daily")
    soup = BeautifulSoup(trending_html, "html.parser")
    articles = soup.select("article.Box-row")

    agent_keywords = ("agent", "agents", "browser", "workflow", "automation", "llm", "mcp")
    agent_items: list[GithubItem] = []

    for article in articles:
        title_tag = article.select_one("h2 a")
        desc_tag = article.select_one("p")
        if not title_tag:
            continue
        repo = parse_trending_repo(title_tag.get("href", ""))
        description = " ".join(desc_tag.get_text(" ", strip=True).split()) if desc_tag else "GitHub 热门项目"
        haystack = f"{repo} {description}".lower()
        if not any(keyword in haystack for keyword in agent_keywords):
            continue
        agent_items.append(
            GithubItem(
                repo=repo,
                description=description,
                url=f"https://github.com/{repo}",
                reason="进入 GitHub Trending，说明最近关注度和讨论度都在上升。",
            )
        )
        if len(agent_items) == 2:
            break

    company_watch = [
        ("openai/codex", "OpenAI 官方终端 coding agent，适合持续盯住 agent 入口。"),
        ("google-gemini/gemini-cli", "Google 官方终端 agent 工具，代表 Gemini 的开发者入口。"),
    ]
    company_items: list[GithubItem] = []

    for repo, reason in company_watch:
        meta = fetch_json(f"https://api.github.com/repos/{repo}")
        description = meta.get("description") or "AI 公司官方项目"
        pushed_at = meta.get("pushed_at", "")
        pushed_date = pushed_at[:10] if pushed_at else ""
        reason_text = reason
        if pushed_date:
            reason_text = f"{reason} 最近一次公开更新日期是 {pushed_date}。"
        company_items.append(
            GithubItem(
                repo=repo,
                description=description,
                url=f"https://github.com/{repo}",
                reason=reason_text,
            )
        )

    return (agent_items[:2] + company_items[:2])[:4]


def pick_yanfeng_news() -> NewsItem:
    html = fetch_text("https://www.yanfeng.com/cn/company-news")
    soup = BeautifulSoup(html, "html.parser")

    for anchor in soup.select("a[href*='/cn/']"):
        text = " ".join(anchor.get_text(" ", strip=True).split())
        href = anchor.get("href", "").strip()
        if not text or len(text) < 8:
            continue
        article_url = href if href.startswith("http") else f"https://www.yanfeng.com{href}"
        article_html = fetch_text(article_url)
        article_soup = BeautifulSoup(article_html, "html.parser")
        article_text = article_soup.get_text("\n", strip=True)
        date = None
        for token in article_text.split():
            if len(token) == 10 and token[4] == "-" and token[7] == "-":
                date = token
                break
        if not date:
            continue
        return NewsItem(
            company="延锋",
            date=date,
            title=text,
            link=article_url,
            source="延锋官网",
        )

    raise RuntimeError("Unable to locate latest Yanfeng official news")


def shorten(text: str, limit: int = 72) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def format_news_line(item: NewsItem) -> str:
    return f"- {item.date} {item.company}：{shorten(item.title, 60)}（{item.source}）"


def format_github_line(item: GithubItem) -> str:
    return f"- {item.repo}：{shorten(item.description, 36)}；{shorten(item.reason, 44)}"


def build_brief() -> str:
    today = datetime.now(SH_TZ).strftime("%Y-%m-%d")
    company_news = pick_company_news()
    github_items = pick_github_projects()
    yanfeng = pick_yanfeng_news()

    lines = [f"AI晨报 | {today}", "", "今日要闻"]
    lines.extend(format_news_line(item) for item in company_news)
    lines.extend(
        [
            "",
            "GitHub 热门",
        ]
    )
    lines.extend(format_github_line(item) for item in github_items)
    lines.extend(
        [
            "",
            "延锋动态",
            f"- {yanfeng.date} 延锋：{shorten(yanfeng.title, 56)}（{yanfeng.source}）",
            "",
            "一句话判断",
            "- 这轮 AI 竞争的核心已经从模型参数转向 agent 落地、企业入口和真实工作流接管。",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def send_feishu(text: str) -> None:
    webhook = os.environ["FEISHU_WEBHOOK_URL"]
    payload = {"msg_type": "text", "content": {"text": text}}
    response = requests.post(webhook, json=payload, timeout=TIMEOUT)
    response.raise_for_status()


def send_telegram(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_HOME_CHANNEL"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    response = requests.post(url, data=payload, timeout=TIMEOUT)
    response.raise_for_status()


def main(argv: Iterable[str]) -> int:
    dry_run = "--dry-run" in set(argv)
    brief = build_brief()
    output_path = Path("artifacts") / "ai_morning_brief.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(brief, encoding="utf-8")

    if not dry_run:
        send_feishu(brief)
        send_telegram(brief)

    sys.stdout.write(brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
