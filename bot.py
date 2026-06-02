from deep_translator import GoogleTranslator
import feedparser
from bs4 import BeautifulSoup
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from flask import Flask, request
import requests
import os
from google import genai

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://telegram-automatic-message.onrender.com/"
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

BALE_TOKEN = os.getenv("BALE_TOKEN")
BALE_CHAT_ID = os.getenv("BALE_CHAT_ID")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

RSS_URL = "https://www.engadget.com/rss.xml"

translator = GoogleTranslator(source="en", target="fa")
client = genai.Client(api_key=GEMINI_API_KEY)

IMAGES_DIR = "images"
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

user_news_cache = {}
preview_cache = {}

def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text().strip()

def remove_copyright(text):
    markers = ["This article originally appeared on Engadget", "Read more at Engadget"]
    for marker in markers:
        if marker in text:
            text = text.split(marker)[0].strip()
    return text

def download_image(url, filename):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open(filename, "wb") as f:
                f.write(r.content)
            return True
    except:
        pass
    return False

def analyze_news_with_gemini(description):
    prompt = f"""
    تو یک خبرنگار حرفه‌ای هستی. متن طولانی خبری زیر را به یک خبر کوتاه و مفید در ۳ تا ۴ پاراگراف تبدیل کن.

قوانین:
پاراگراف اول: شامل چه کسی، چه اتفاقی، کجا، کی (Who, What, Where, When) همراه با مهمترین عدد یا آمار.

پاراگراف دوم: جزئیات تکمیلی و چرایی اصلی رویداد (Why).

پاراگراف سوم (و در صورت نیاز چهارم): پیامد فوری، واکنش مسئول یا تأثیر خبر.

سبک: خشک، بی‌طرف، روان و ساده. حذف نقل قول مستقیم و توضیحات اضافی.به جای گذاشتن اطلاعات اضافی، اصلاعات اصلی را نگه دار و در ضمن فرد باید فرد فقط خواندن این تحلیل بتواند کل متن خبر را بفهمد. هیچ قسمتی از متن را بولد یا پررنگ نکن. طول کل حداکثر ۱۰۰ کلمه.
متن خبر:
{description}
"""
    try:
        response = client.models.generate_content(model="gemini-3.1-flash-lite",contents=prompt)
        return response.text.strip()
    except Exception as e:
        return f"خطا در تحلیل خبر:{e}"

def get_latest_news(limit=10):
    feed = feedparser.parse(RSS_URL)
    news_list = []
    for entry in feed.entries:
        title = entry.title if "title" in entry else "No Title"
        description = clean_html(entry.summary if "summary" in entry else "")
        description = remove_copyright(description)
        if len(description) > 4000:
            continue
        description = description[:3900]
        pub_date = entry.get("published", "Unknown")

        image_url = None
        if "media_content" in entry:
            for media in entry.media_content:
                if media.get("medium") == "image" and "url" in media:
                    image_url = media["url"]
                    break

        news_list.append({"title": title,"description": description,"image": image_url,"pub_date": pub_date,"link": entry.link})
        if len(news_list) >= limit:
            break
    return news_list
    
def send_to_bale(text, image_path=None):
    try:
        if image_path and os.path.exists(image_path):
            url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendPhoto"
            with open(image_path, "rb") as photo:
                r = requests.post(url, data={"chat_id": BALE_CHAT_ID}, files={"photo": photo})
                print("Bale photo:", r.text)
        url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": BALE_CHAT_ID, "text": text})
        print("Bale message:", r.text)
    except Exception as e:
        print("Bale error:", e)
        
footer_text = """
\n📌 برای دنبال کردن آخرین اخبار و مطالب دنیای تکنولوژی و هوش مصنوعی، کانال‌های ما را مشاهده کنید:

💬 تلگرام:
https://t.me/MBB_Software_Group
https://t.me/hooshmalinovin

📱 بله:
https://ble.ir/MBB_Software_Group
"""

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "send news")
def send_news_list_combined(message):
    news_list = get_latest_news()
    if not news_list:
        bot.send_message(message.chat.id, "خبری یافت نشد ❌")
        return
    
    user_news_cache[message.chat.id] = {
        "news_list": news_list,
        "temp_data": {}
    }
    
    for idx, news in enumerate(news_list):
        preview = news["description"][:200] + "..."
        text = f"📢 {news['title']}\n🗓 {news['pub_date']}\n\n{preview}"
        
        keyboard = InlineKeyboardMarkup(row_width=3)
        btn_telegram = InlineKeyboardButton("📤 ارسال به تلگرام", callback_data=f"tg_{idx}")
        btn_bale = InlineKeyboardButton("📱 ارسال به بله", callback_data=f"bl_{idx}")
        btn_both = InlineKeyboardButton("🔄 ارسال به هر دو", callback_data=f"both_{idx}")
        keyboard.add(btn_telegram, btn_bale, btn_both)
        
        bot.send_message(message.chat.id, text, reply_markup=keyboard)

def get_target_name(target):
    if target == "tg":
        return "تلگرام"
    elif target == "bl":
        return "بله"
    elif target == "both":
        return "هر دو پلتفرم"
    return "نامشخص"

@bot.callback_query_handler(func=lambda call: call.data.startswith(("tg_", "bl_", "both_")))
def handle_destination_selection(call: CallbackQuery):
    try:
        parts = call.data.split("_")
        target = parts[0]
        idx = int(parts[1])
        
        chat_data = user_news_cache.get(call.message.chat.id)
        if not chat_data:
            bot.answer_callback_query(call.id, "خبر یافت نشد ❌", show_alert=True)
            return
        
        news_list = chat_data["news_list"]
        if idx >= len(news_list):
            bot.answer_callback_query(call.id, "خبر یافت نشد ❌", show_alert=True)
            return
        
        news = news_list[idx]
        cache_key = hash(news["description"][:200])
        
        # اعلام وضعیت در حال پردازش
        bot.answer_callback_query(call.id, "🤖 در حال تحلیل خبر با هوش مصنوعی...", show_alert=False)
        
        # اگر قبلاً تحلیل نشده، الان انجام بده
        if cache_key not in preview_cache:
            title_fa = translator.translate(news["title"])
            analysis_text = analyze_news_with_gemini(news["description"])
            
            preview_cache[cache_key] = {
                "title_fa": title_fa,
                "analysis": analysis_text,
                "caption": f"📢 {title_fa}",
                "full_text": f"📢 {title_fa}\n\n{analysis_text}{footer_text}",
                "image_url": news["image"]
            }
        
        cached = preview_cache[cache_key]
        
        preview_text = f"""📋 **پیش‌نمایش خبر برای ارسال به {get_target_name(target)}:**

{cached['analysis'][:400]}...

---
✅ آیا برای ارسال تأیید می‌کنید؟"""
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        confirm_btn = InlineKeyboardButton("✅ تأیید و ارسال", callback_data=f"confirm_{target}_{idx}")
        cancel_btn = InlineKeyboardButton("❌ لغو", callback_data="cancel_send")
        keyboard.add(confirm_btn, cancel_btn)
        
        # پیام قبلی رو پاک کن
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # ذخیره اطلاعات در temp_data
        chat_data["temp_data"]["selected_target"] = target
        chat_data["temp_data"]["selected_idx"] = idx
        
        # ارسال پیش‌نمایش با عکس (اگه داشته باشه)
        if cached.get('image_url') and cached['image_url']:
            image_path = os.path.join(IMAGES_DIR, f"preview_{idx}.jpg")
            download_image(cached['image_url'], image_path)
            if os.path.exists(image_path):
                with open(image_path, "rb") as photo:
                    bot.send_photo(
                        chat_id=call.message.chat.id,
                        photo=photo,
                        caption=preview_text,
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                chat_data["temp_data"]["preview_image"] = image_path
            else:
                bot.send_message(
                    call.message.chat.id,
                    preview_text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
        else:
            bot.send_message(
                call.message.chat.id,
                preview_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"Error in handle_destination_selection: {e}")
        bot.answer_callback_query(call.id, "خطایی رخ داد ❌", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_send")
def cancel_send_handler(call: CallbackQuery):
    try:
        # حذف تصویر پیش‌نمایش اگر وجود دارد
        chat_data = user_news_cache.get(call.message.chat.id)
        if chat_data:
            preview_image = chat_data["temp_data"].get("preview_image")
            if preview_image and os.path.exists(preview_image):
                os.remove(preview_image)
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    bot.answer_callback_query(call.id, "❌ ارسال لغو شد", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_"))
def send_confirmed_news(call: CallbackQuery):
    try:
        parts = call.data.split("_")
        target = parts[1]
        idx = int(parts[2])
        
        chat_id = call.message.chat.id
        chat_data = user_news_cache.get(chat_id)
        
        if not chat_data or idx >= len(chat_data["news_list"]):
            bot.answer_callback_query(call.id, "خبر یافت نشد ❌", show_alert=True)
            return
        
        news_list = chat_data["news_list"]
        news = news_list[idx]
        cache_key = hash(news["description"][:200])
        cached = preview_cache.get(cache_key)
        
        if not cached:
            bot.answer_callback_query(call.id, "خطا در پردازش خبر ❌", show_alert=True)
            return
        
        # ارسال به مقصد مورد نظر
        image_path = None
        if cached['image_url']:
            image_path = os.path.join(IMAGES_DIR, f"final_{idx}.jpg")
            download_image(cached['image_url'], image_path)
        
        success_tg = False
        success_bl = False
        
        if target == "tg" or target == "both":
            try:
                if image_path and os.path.exists(image_path):
                    with open(image_path, "rb") as photo:
                        bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=cached['caption'])
                else:
                    bot.send_message(chat_id=CHANNEL_ID, text=cached['caption'])
                
                bot.send_message(chat_id=CHANNEL_ID, text=cached['analysis'] + footer_text)
                success_tg = True
            except Exception as e:
                print(f"Telegram error: {e}")
        
        if target == "bl" or target == "both":
            try:
                send_to_bale(cached['full_text'], image_path)
                success_bl = True
            except Exception as e:
                print(f"Bale error: {e}")
        
        # پاک کردن فایل‌های موقت
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        
        preview_image = chat_data["temp_data"].get("preview_image")
        if preview_image and os.path.exists(preview_image):
            os.remove(preview_image)
        
        # پاک کردن پیام پیش‌نمایش
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        
        # نمایش نتیجه نهایی
        if target == "tg":
            if success_tg:
                bot.answer_callback_query(call.id, "✅ به تلگرام ارسال شد!", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "❌ خطا در ارسال به تلگرام", show_alert=True)
        elif target == "bl":
            if success_bl:
                bot.answer_callback_query(call.id, "✅ به بله ارسال شد!", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "❌ خطا در ارسال به بله", show_alert=True)
        else:
            if success_tg and success_bl:
                bot.answer_callback_query(call.id, "✅ به هر دو پلتفرم ارسال شد!", show_alert=True)
            elif success_tg:
                bot.answer_callback_query(call.id, "⚠️ فقط تلگرام ارسال شد (بله خطا)", show_alert=True)
            elif success_bl:
                bot.answer_callback_query(call.id, "⚠️ فقط بله ارسال شد (تلگرام خطا)", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "❌ ارسال به هر دو失败 شد", show_alert=True)
        
    except Exception as e:
        print(f"Error in send_confirmed_news: {e}")
        bot.answer_callback_query(call.id, f"❌ خطا: {str(e)[:50]}", show_alert=True)
# ================== بخش جدید: پردازش خبر دنیای اقتصاد با Gemini ==================
# این بخش کاملاً جداگانه و بدون تداخل با کد اصلی کار می‌کند
# ================== بخش جدید: پردازش خبر دنیای اقتصاد با انتخاب کاربر ==================
# این بخش کاملاً جداگانه و بدون تداخل با کد اصلی کار می‌کند
# ================== بخش جدید: پردازش خبر دنیای اقتصاد با انتخاب کاربر ==================
# این بخش کاملاً جداگانه و بدون تداخل با کد اصلی کار می‌کند

DONYAYE_EQTESAD_RSS = "https://donya-e-eqtesad.com/fa/feeds/?p=Y2F0ZWdvcmllcz0yNA%2C%2C"

# کش موقت برای ذخیره اخبار هر کاربر
user_donya_news_cache = {}

def get_donya_news_list(limit=10):
    """دریافت لیست اخبار از RSS (فقط عنوان و خلاصه RSS)"""
    feed = feedparser.parse(DONYAYE_EQTESAD_RSS)
    news_list = []
    
    for idx, entry in enumerate(feed.entries):
        if idx >= limit:
            break
            
        title = entry.title
        # استفاده از توضیحات خود RSS (بدون درخواست اضافی)
        rss_description = entry.description if "description" in entry else ""
        if rss_description:
            # حذف تگ‌های HTML از توضیحات RSS
            soup = BeautifulSoup(rss_description, "html.parser")
            rss_description = soup.get_text(strip=True)[:200] + "..."
        
        news_list.append({
            "idx": idx,
            "title": title,
            "preview": rss_description,
            "link": entry.link
        })
    
    return news_list

def get_donya_full_text(link):
    """دریافت متن کامل خبر از لینک (برای تحلیل با Gemini)"""
    try:
        response = requests.get(link, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # استخراج lead justify
        lead_element = soup.find(class_="lead justify")
        lead_text = ""
        if lead_element:
            lead_text = lead_element.get_text(strip=True)
            import re
            lead_text = re.sub(r'^مترجم:\s*', '', lead_text)
        
        # استخراج متن اصلی از echo-detail
        echo_detail = soup.find(id="echo-detail")
        if not echo_detail:
            article_body = soup.find(class_="article-body")
            if article_body:
                echo_detail = article_body.find(id="echo-detail")
        
        if not echo_detail:
            return None, "امکان استخراج متن کامل خبر وجود ندارد ❌"
        
        # حذف عکس‌ها
        for primary_file in echo_detail.find_all(class_="primary-files"):
            primary_file.decompose()
        
        # حذف آخرین پاراگراف تکراری
        paragraphs = echo_detail.find_all('p')
        if paragraphs:
            last_p = paragraphs[-1]
            last_text = last_p.get_text(strip=True)
            if any(word in last_text for word in ["مفید", "کپی", "پسندیده", "منبع"]):
                last_p.decompose()
        
        # استخراج متن تمیز
        full_text = echo_detail.get_text(strip=True)
        import re
        full_text = re.sub(r'منبع:\s*[^\n]+', '', full_text)
        full_text = re.sub(r'این مطلب برایم مفید است\s*\d*', '', full_text)
        full_text = re.sub(r'\d*نفر این مطلب را پسندیده اند', '', full_text)
        full_text = re.sub(r'کپی شد', '', full_text)
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        
        # ترکیب lead و متن اصلی
        if lead_text:
            combined = lead_text + " " + full_text
        else:
            combined = full_text
        
        return combined, None
        
    except Exception as e:
        return None, f"خطا: {str(e)[:100]}"

def analyze_with_gemini_podcast(text):
    """تحلیل متن خبر با Gemini و خروجی کوتاه و مفید"""
    
    prompt = f"""
    تو یک تحلیلگر خبری حرفه‌ای هستی. متن خبر زیر را به یک تحلیل کوتاه، مفید و روان تبدیل کن.

    قوانین مهم:
    - حداکثر 2500 کاراکتر
    - فقط مهم‌ترین نکات خبر را پوشش بده
    - سبک: روان، ساده و بی‌طرف
    - بدون نقل قول مستقیم
    - بدون توضیحات اضافی
    - پاراگراف اول: اصل خبر (چه، کجا، کی)
    - پاراگراف دوم: جزئیات تکمیلی و چرایی
    - پاراگراف سوم (اختیاری): پیامد یا تاثیر خبر
    
    متن خبر:
    {text[:8000]}
    """
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"خطا در تحلیل خبر: {e}"

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "send podcast")
def handle_send_podcast(message):
    """نمایش لیست اخبار برای انتخاب کاربر"""
    
    bot.reply_to(message, "📡 در حال دریافت لیست آخرین اخبار از دنیای اقتصاد...")
    
    # دریافت لیست اخبار
    news_list = get_donya_news_list(limit=8)
    
    if not news_list:
        bot.send_message(message.chat.id, "❌ هیچ خبری یافت نشد. لطفاً چند دقیقه دیگر تلاش کنید.")
        return
    
    # ذخیره در کش کاربر
    user_donya_news_cache[message.chat.id] = news_list
    
    # ساخت پیام با دکمه‌ها
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for news in news_list:
        # عنوان کوتاه شده برای دکمه
        short_title = news['title'][:40] + "..." if len(news['title']) > 40 else news['title']
        callback_data = f"donya_select_{news['idx']}"
        keyboard.add(InlineKeyboardButton(f"📰 {short_title}", callback_data=callback_data))
    
    # دکمه لغو
    keyboard.add(InlineKeyboardButton("❌ لغو", callback_data="donya_cancel"))
    
    # ساخت پیام پیش‌نمایش
    preview_text = "📬 **لیست آخرین اخبار دنیای اقتصاد:**\n\n"
    for news in news_list:
        preview_text += f"🔹 **{news['title']}**\n"
        if news['preview']:
            preview_text += f"   {news['preview']}\n"
        preview_text += "\n"
    
    preview_text += "👇 لطفاً یکی از اخبار بالا را انتخاب کنید."
    
    bot.send_message(
        message.chat.id,
        preview_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("donya_select_"))
def handle_donya_news_selection(call):
    """پردازش خبر انتخاب شده توسط کاربر"""
    
    try:
        # استخراج ایندکس خبر
        idx = int(call.data.split("_")[2])
        
        # دریافت لیست خبر از کش
        news_list = user_donya_news_cache.get(call.message.chat.id)
        
        if not news_list or idx >= len(news_list):
            bot.answer_callback_query(call.id, "❌ خطا: خبر یافت نشد", show_alert=True)
            return
        
        selected_news = news_list[idx]
        news_link = selected_news['link']
        news_title = selected_news['title']
        
        # اعلام به کاربر
        bot.answer_callback_query(call.id, f"✅ خبر '{news_title[:50]}...' انتخاب شد. در حال پردازش...")
        
        # حذف پیام قبلی (لیست اخبار)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # پیام وضعیت
        status_msg = bot.send_message(
            call.message.chat.id,
            f"📰 **خبر انتخاب شده:** {news_title}\n\n🔄 در حال دریافت متن کامل خبر..."
        )
        
        # دریافت متن کامل خبر
        full_text, error = get_donya_full_text(news_link)
        
        if error or not full_text:
            bot.edit_message_text(
                f"❌ {error or 'مشکلی در دریافت خبر پیش آمد'}\n\nلطفاً دوباره با ارسال 'send podcast' تلاش کنید.",
                call.message.chat.id,
                status_msg.message_id
            )
            return
        
        # تحلیل با Gemini
        bot.edit_message_text(
            f"📰 **خبر انتخاب شده:** {news_title}\n\n🧠 در حال تحلیل خبر با هوش مصنوعی Gemini...",
            call.message.chat.id,
            status_msg.message_id
        )
        
        analysis = analyze_with_gemini_podcast(full_text)
        
        # ========== تغییر اصلی اینجاست ==========
        # ساخت متن نهایی با عنوان در ابتدا (بدون لینک منبع)
        final_text = f"📰 **{news_title}**\n\n{analysis}"
        
        # برش به حداکثر طول مجاز تلگرام (4096 کاراکتر)
        MAX_LEN = 4096
        if len(final_text) > MAX_LEN:
            final_text = final_text[:MAX_LEN-50] + "..."
        
        # ارسال به کانال
        bot.edit_message_text(
            f"📰 **خبر انتخاب شده:** {news_title}\n\n📤 در حال ارسال به کانال...",
            call.message.chat.id,
            status_msg.message_id
        )
        
        try:
            bot.send_message(
                chat_id=CHANNEL_ID,
                text=final_text,
                parse_mode="Markdown"
            )
            bot.edit_message_text(
                f"✅ **خبر با موفقیت در کانال ارسال شد!**\n\n📰 عنوان: {news_title}",
                call.message.chat.id,
                status_msg.message_id
            )
        except Exception as e:
            bot.edit_message_text(
                f"❌ خطا در ارسال به کانال: {str(e)[:200]}",
                call.message.chat.id,
                status_msg.message_id
            )
            
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ خطا: {str(e)[:50]}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "donya_cancel")
def handle_donya_cancel(call):
    """لغو انتخاب خبر"""
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "❌ عملیات لغو شد", show_alert=True)
        bot.send_message(call.message.chat.id, "عملیات انتخاب خبر لغو شد. برای شروع مجدد 'send podcast' را ارسال کنید.")
    except:
        bot.answer_callback_query(call.id, "لغو شد", show_alert=True)
-------------------------------------------------------------------
# ================== بخش جدید: send podcast voice (گفتگوی صوتی) ==================
import wave
import tempfile
import os
from google.genai import types

# کش جداگانه برای اخبار voice
user_donya_voice_cache = {}

def save_wav(filename: str, pcm_data: bytes) -> None:
    """ذخیره دیتای خام PCM به عنوان فایل WAV"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)          # mono
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(24000)      # 24kHz
        wf.writeframes(pcm_data)

def generate_dialogue_from_news(news_summary: str) -> str:
    """تولید دیالوگ بین علی و سارا بر اساس خلاصه خبر"""
    prompt = f"""
    Write a short, natural dialogue between two friends named 'Ali' and 'Sara' 
    discussing the following news summary. Keep it engaging and informative.

    News summary:
    {news_summary}

    Format exactly like this:
    Ali: [text]
    Sara: [text]
    """
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are a professional dialogue writer. "
                    "The dialogue must be short (max 10 exchanges). "
                    "Do not add any extra text before or after the dialogue."
                )
            )
        )
        dialogue = response.text.strip()
        # اعتبارسنجی ساده
        if "Ali:" not in dialogue or "Sara:" not in dialogue:
            raise ValueError("Model did not generate proper dialogue format")
        return dialogue
    except Exception as e:
        raise Exception(f"Dialogue generation failed: {e}")

def text_to_speech_multi_speaker(dialogue_text: str, output_filename: str) -> str:
    """تبدیل دیالوگ چندنفره به فایل صوتی با دو صدای متفاوت"""
    # پیکربندی دو گوینده: علی (صدای Kore) و سارا (صدای Puck)
    multi_speaker_config = types.MultiSpeakerVoiceConfig(
        speaker_voice_configs=[
            types.SpeakerVoiceConfig(
                speaker="Ali",
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
            types.SpeakerVoiceConfig(
                speaker="Sara",
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                )
            ),
        ]
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-tts-preview",
        contents=dialogue_text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                multi_speaker_voice_config=multi_speaker_config
            ),
        ),
    )

    if (response.candidates and response.candidates[0].content
        and response.candidates[0].content.parts
        and response.candidates[0].content.parts[0].inline_data):
        audio_data = response.candidates[0].content.parts[0].inline_data.data
        save_wav(output_filename, audio_data)
        return output_filename
    else:
        raise Exception("No audio data received from TTS model")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "send podcast voice")
def handle_send_podcast_voice(message):
    """نمایش لیست اخبار برای انتخاب و ساخت گفتگوی صوتی"""
    bot.reply_to(message, "🎙️ در حال دریافت لیست آخرین اخبار از دنیای اقتصاد...")

    news_list = get_donya_news_list(limit=8)   # تابع قبلی (در کد اصلی وجود دارد)
    if not news_list:
        bot.send_message(message.chat.id, "❌ هیچ خبری یافت نشد. لطفاً چند دقیقه دیگر تلاش کنید.")
        return

    # ذخیره در کش مخصوص voice
    user_donya_voice_cache[message.chat.id] = news_list

    keyboard = InlineKeyboardMarkup(row_width=1)
    for news in news_list:
        short_title = news['title'][:40] + "..." if len(news['title']) > 40 else news['title']
        keyboard.add(InlineKeyboardButton(f"🎧 {short_title}", callback_data=f"donya_voice_select_{news['idx']}"))
    keyboard.add(InlineKeyboardButton("❌ لغو", callback_data="donya_voice_cancel"))

    preview_text = "📬 **لیست آخرین اخبار (تبدیل به گفتگوی صوتی):**\n\n"
    for news in news_list:
        preview_text += f"🔹 **{news['title']}**\n"
        if news['preview']:
            preview_text += f"   {news['preview']}\n"
        preview_text += "\n"
    preview_text += "👇 لطفاً یکی از اخبار را انتخاب کنید."

    bot.send_message(message.chat.id, preview_text, reply_markup=keyboard, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("donya_voice_select_"))
def handle_donya_voice_selection(call):
    """پردازش خبر انتخاب شده: دریافت متن، تحلیل، ساخت دیالوگ و ارسال فایل صوتی"""
    try:
        idx = int(call.data.split("_")[3])
        chat_id = call.message.chat.id

        news_list = user_donya_voice_cache.get(chat_id)
        if not news_list or idx >= len(news_list):
            bot.answer_callback_query(call.id, "❌ خطا: خبر یافت نشد", show_alert=True)
            return

        selected_news = news_list[idx]
        news_title = selected_news['title']
        news_link = selected_news['link']

        bot.answer_callback_query(call.id, f"✅ خبر '{news_title[:50]}...' انتخاب شد. در حال پردازش...")

        # حذف پیام لیست
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass

        status_msg = bot.send_message(chat_id, f"📰 **خبر:** {news_title}\n\n🔄 دریافت متن کامل...")

        # دریافت متن کامل خبر
        full_text, error = get_donya_full_text(news_link)  # تابع قبلی
        if error or not full_text:
            bot.edit_message_text(f"❌ {error or 'مشکل در دریافت خبر'}", chat_id, status_msg.message_id)
            return

        # تحلیل خبر با Gemini (خلاصه‌سازی)
        bot.edit_message_text(f"📰 **خبر:** {news_title}\n\n🧠 تحلیل خبر با هوش مصنوعی...", chat_id, status_msg.message_id)
        analysis = analyze_with_gemini_podcast(full_text)   # تابع قبلی

        # تولید دیالوگ بر اساس تحلیل
        bot.edit_message_text(f"📰 **خبر:** {news_title}\n\n💬 ساخت گفتگوی دو نفره...", chat_id, status_msg.message_id)
        dialogue = generate_dialogue_from_news(analysis)

        # تبدیل دیالوگ به صدا
        bot.edit_message_text(f"📰 **خبر:** {news_title}\n\n🎤 تبدیل به گفتگوی صوتی (حدود ۱۵ ثانیه)...", chat_id, status_msg.message_id)

        # ذخیره در فایل موقت
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            audio_path = tmp.name
        text_to_speech_multi_speaker(dialogue, audio_path)

        # ارسال فایل صوتی به کانال به همراه عنوان خبر به عنوان کپشن
        caption = f"🎙️ گفتگوی صوتی: {news_title}"
        with open(audio_path, "rb") as voice_file:
            bot.send_voice(chat_id=CHANNEL_ID, voice=voice_file, caption=caption)

        # پاکسازی فایل موقت و پیام وضعیت
        os.unlink(audio_path)
        bot.edit_message_text(f"✅ **گفتگوی صوتی با موفقیت در کانال ارسال شد!**\n\n📰 عنوان: {news_title}", chat_id, status_msg.message_id)

    except Exception as e:
        error_msg = f"❌ خطا: {str(e)[:200]}"
        bot.edit_message_text(error_msg, call.message.chat.id, status_msg.message_id)
        bot.answer_callback_query(call.id, error_msg[:50], show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "donya_voice_cancel")
def handle_donya_voice_cancel(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "❌ عملیات لغو شد", show_alert=True)
        bot.send_message(call.message.chat.id, "عملیات ساخت گفتگوی صوتی لغو شد. برای شروع مجدد 'send podcast voice' را ارسال کنید.")
    except:
        bot.answer_callback_query(call.id, "لغو شد", show_alert=True)




@app.route("/", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "ok"

if __name__ == "__main__":
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
