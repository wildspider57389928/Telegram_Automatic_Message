import requests
from bs4 import BeautifulSoup
import json
import re
from argostranslate import package, translate

# نصب و بارگذاری مدل ترجمه
package.install_from_path("translate-en_fa-1_5.argosmodel")
installed_languages = translate.load_installed_languages()
from_lang = installed_languages[0]  # انگلیسی
to_lang = installed_languages[1]    # فارسی

# RSS The Verge (Atom feed)
rss_feed = "https://www.theverge.com/rss/index.xml"

def get_top_technology_links(n=5):
    links = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(rss_feed, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "xml")
        entries = soup.find_all("entry")
        for entry in entries:
            link_tag = entry.find("link", rel="alternate")
            title_tag = entry.find("title")
            if link_tag and title_tag:
                link = link_tag.get("href")
                title = title_tag.get_text()
                links.append({"title": title, "link": link})
            if len(links) >= n:
                break
    except:
        pass
    return links[:n]

def get_article_content(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        article = soup.find("article")
        if article:
            paragraphs = [p.get_text() for p in article.find_all("p")]
            full_text = " ".join(paragraphs)
            if len(full_text) >= 600:  # فقط متن کوتاه‌تر از ۶۰۰
                return ""
            return full_text
    except:
        return ""
    return ""

def apply_rtl_ltr(text):
    text = "\u200F" + text  # راست‌چین متن فارسی
    def replace_english(match):
        return "\u200E" + match.group(0) + "\u200E"  # کلمات انگلیسی LTR
    text = re.sub(r'[A-Za-z0-9:/._-]+', replace_english, text)  # شامل لینک‌ها
    return text

if __name__ == "__main__":
    top_links = get_top_technology_links(5)
    news_data_en = []
    news_data_fa = []

    for item in top_links:
        content_en = get_article_content(item["link"])
        if content_en:
            news_data_en.append({
                "title": item["title"],
                "link": item["link"],
                "content": content_en
            })
            translated = from_lang.get_translation(to_lang).translate(content_en)
            translated_rtl = apply_rtl_ltr(translated)
            translated_link = apply_rtl_ltr(item["link"])  # لینک هم RTL/LTR
            news_data_fa.append({
                "title": item["title"],
                "link": translated_link,
                "content": translated_rtl
            })

    with open("top_5_tech_news_en.json", "w", encoding="utf-8") as f:
        json.dump(news_data_en, f, ensure_ascii=False, indent=4)

    with open("top_5_tech_news_fa.json", "w", encoding="utf-8") as f:
        json.dump(news_data_fa, f, ensure_ascii=False, indent=4)

    print("۵ خبر اول The Verge ذخیره شد! لینک‌ها و متن فارسی RTL/LTR آماده است.")
