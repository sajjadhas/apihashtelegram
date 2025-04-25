from telethon import TelegramClient, events
from bs4 import BeautifulSoup
import requests, random, string, os

# مقداردهی اولیه از متغیرهای محیطی
api_id = int(os.environ['API_ID'])         # مقدار API ID بات (از MyTelegram برای اکانت توسعه‌دهنده)
api_hash = os.environ['API_HASH']         # مقدار API Hash بات (از MyTelegram)
bot_token = os.environ['BOT_TOKEN']       # توکن بات دریافت‌شده از @BotFather

# ایجاد کلاینت تلگراف (بوتوکنی)
bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

# نگه‌داشتن وضعیت گفتگو برای هر کاربر
user_data = {}  # {'chat_id': {'phone': ..., 'random_hash': ...}}

# تابع کمکی برای ساخت نام تصادفی
def random_word(length=None):
    length = length or random.randint(5,9)
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    chat_id = event.chat_id
    user_data.pop(chat_id, None)  # وضعیت قبلی را پاک می‌کنیم
    await event.reply("سلام! شماره تلفن خود را به همراه پیش‌شماره (فرمت بین‌المللی) ارسال کنید تا API ID و Hash شما استخراج شود.")

@bot.on(events.NewMessage)
async def message_handler(event):
    chat_id = event.chat_id
    text = event.raw_text.strip()

    # اگر هنوز شماره دریافت نشده باشد، اولین ورودی را به عنوان شماره بگیرید
    if chat_id not in user_data or 'phone' not in user_data[chat_id]:
        # ثبت شماره تلفن کاربر
        phone = text
        user_data[chat_id] = {'phone': phone}

        # ارسال درخواست کد ورود به my.telegram.org
        s = requests.Session()
        url = 'https://my.telegram.org/auth/send_password'
        data = {'phone': phone}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json",
            "Origin": "https://my.telegram.org",
            "Referer": "https://my.telegram.org/auth?to=apps",
            "X-Requested-With": "XMLHttpRequest"
        }
        res = s.post(url, data=data, headers=headers)
        if res.status_code == 200 and 'random_hash' in res.text:
            rand_hash = res.json().get("random_hash")
            user_data[chat_id]['random_hash'] = rand_hash
            user_data[chat_id]['session'] = s  # ذخیره session برای ادامه
            await event.reply("کد تأیید به تلگرام شما ارسال شد. لطفاً کد دریافتی را ارسال کنید.")
        else:
            await event.reply("خطا در ارسال کد تأیید. لطفاً دوباره تلاش کنید.")
        return

    # اگر شماره قبلاً دریافت شده و منتظر کد هستیم
    if 'random_hash' in user_data[chat_id]:
        phone = user_data[chat_id]['phone']
        rand_hash = user_data[chat_id]['random_hash']
        s = user_data[chat_id]['session']
        code = text  # کد تأیید تلگرامی از کاربر

        # ارسال درخواست ورود به my.telegram.org
        login_url = 'https://my.telegram.org/auth/login'
        login_data = {
            'phone': phone,
            'random_hash': rand_hash,
            'password': code   # در اینجا از فیلد password برای کد استفاده می‌شود
        }
        res = s.post(login_url, data=login_data, headers=headers)
        if res.status_code == 200 and b'true' in res.content:
            # ورود موفق؛ حالا وارد صفحه برنامه‌ها می‌شویم
            apps_url = 'https://my.telegram.org/apps'
            page = s.get(apps_url)
            soup = BeautifulSoup(page.content, 'html.parser')

            # تلاش برای یافتن مقادیر موجود
            spans = soup.find_all('span', {'class': 'form-control input-xlarge uneditable-input'})
            if spans and len(spans) >= 2:
                api_id_val = spans[0].text.strip()
                api_hash_val = spans[1].text.strip()
            else:
                # اگر هیچ اپلیکیشنی وجود ندارد، یک برنامه جدید ایجاد می‌کنیم
                create_hash = soup.find('input', {'name': 'hash'})['value']
                app_data = {
                    'hash': create_hash,
                    'app_title': random_word(),
                    'app_shortname': random_word(),
                    'app_url': 'https://telegram.org',
                    'app_platform': 'other',
                    'app_desc': random_word(15)
                }
                create_url = 'https://my.telegram.org/apps/create'
                s.post(create_url, data=app_data, headers=headers)
                # دوباره صفحه اپلیکیشن‌ها
                page = s.get(apps_url)
                soup = BeautifulSoup(page.content, 'html.parser')
                spans = soup.find_all('span', {'class': 'form-control input-xlarge uneditable-input'})
                api_id_val = spans[0].text.strip()
                api_hash_val = spans[1].text.strip()

            # ارسال نتیجه به کاربر
            await event.reply(f"✅ **API ID:** `{api_id_val}`\n✅ **API Hash:** `{api_hash_val}`")
        else:
            await event.reply("ورود ناموفق بود. اطمینان حاصل کنید کد تأیید را درست وارد کرده باشید.")

        # پاک کردن اطلاعات حساس پس از استفاده
        user_data.pop(chat_id, None)