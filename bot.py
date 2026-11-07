import os
import re
import threading
import time
import telebot
from telebot import types
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from mailcx import MailCX

# Initialize Database
db.init_db()

# Read BOT_TOKEN from environment or .env file
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("BOT_TOKEN="):
                    BOT_TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

if not BOT_TOKEN:
    BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
mail_client = MailCX()

# Button labels for ReplyKeyboard
BTN_CREATE_MAIL = "📧 Create Mail"
BTN_CURRENT_INBOX = "📥 Current Inbox"
BTN_LOGIN_MAIL = "🔐 Login Mail"
BTN_SAVED_MAIL = "💾 Saved Mail"
BTN_SETTING = "⚙️ Setting"

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = KeyboardButton(BTN_CREATE_MAIL, style="success")   # Green
    btn2 = KeyboardButton(BTN_CURRENT_INBOX, style="primary")  # Primary/White
    btn3 = KeyboardButton(BTN_LOGIN_MAIL, style="primary")     # Primary/White
    btn4 = KeyboardButton(BTN_SAVED_MAIL, style="primary")     # Primary/White
    btn5 = KeyboardButton(BTN_SETTING, style="danger")         # Red
    keyboard.row(btn1, btn2)
    keyboard.row(btn3, btn4)
    keyboard.row(btn5)
    return keyboard

def clean_html(raw_html):
    """HTML tag and CSS/JS stripper for clean text previews."""
    if not raw_html:
        return ""
    clean = re.sub(r'<(style|script)[^>]*>.*?</\1>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = clean.replace('&nbsp;', ' ').replace('&#064;', '@').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return ' '.join(clean.split())

# Extract OTP code if found in text or subject
def extract_otp(text):
    if not text:
        return None
    labeled_patterns = [
        r'(?:verification\s*code|security\s*code|confirmation\s*code|activation\s*code|otp|passcode|secret\s*code|pin\s*code|pin|code)[\s:=#\-]+([0-9]{4,8})\b',
        r'(?:verification\s*code|security\s*code|confirmation\s*code|otp|passcode|code)[\s:=#\-]+([0-9]{3}[\-\s][0-9]{3})\b',
        r'\b([0-9]{3}[\-][0-9]{3})\b',
        r'is\s+([0-9]{4,8})\b',
        r'\b([0-9]{6})\b',
        r'\b([0-9]{4,5})\b',
        r'\b([0-9]{7,8})\b'
    ]
    for p in labeled_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).replace('-', '').replace(' ', '')
    return None

def detect_service(sender, subject):
    combined = f"{sender} {subject}".lower()
    services = [
        ("Google", ["google", "gmail"]),
        ("Telegram", ["telegram"]),
        ("WhatsApp", ["whatsapp"]),
        ("Facebook", ["facebook", "meta"]),
        ("Instagram", ["instagram"]),
        ("TikTok", ["tiktok", "bytedance"]),
        ("Discord", ["discord"]),
        ("Twitter / X", ["twitter", "x.com"]),
        ("Microsoft", ["microsoft", "live.com", "outlook", "msn"]),
        ("Apple", ["apple", "icloud"]),
        ("Amazon", ["amazon", "aws"]),
        ("Steam", ["steam", "valvesoftware"]),
        ("OpenAI / ChatGPT", ["openai", "chatgpt"]),
        ("GitHub", ["github"]),
        ("Netflix", ["netflix"]),
        ("Spotify", ["spotify"]),
        ("Roblox", ["roblox"]),
        ("Snapchat", ["snapchat"]),
        ("LinkedIn", ["linkedin"]),
        ("Pinterest", ["pinterest"])
    ]
    for name, keywords in services:
        if any(k in combined for k in keywords):
            return name
            
    match = re.search(r'@([a-zA-Z0-9.-]+)', sender)
    if match:
        dom = match.group(1).split('.')[0].capitalize()
        return dom
    return "Online Service"

# ==================== COMMAND HANDLERS ====================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    db.create_or_update_user(user_id)
    
    welcome_text = (
        "👋 <b>Welcome to Mail.cx Temp Mail Bot!</b>\n\n"
        "Here you can generate instant disposable temporary email addresses, "
        "receive verification codes (OTP), and view inboxes in real-time.\n\n"
        "👇 <b>Select an option below:</b>"
    )
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=get_main_keyboard()
    )

# ==================== 1. CREATE MAIL ====================

def handle_create_mail(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    domain = user['preferred_domain'] if user and user['preferred_domain'] else 'uqu.me'
    
    new_email = mail_client.generate_email(domain=domain)
    # Set as active email
    db.create_or_update_user(user_id, current_email=new_email)
    # Automatically save to SQLite database so it is NEVER lost on bot restart!
    db.save_email(user_id, new_email)
    
    markup = InlineKeyboardMarkup()
    btn_copy = InlineKeyboardButton("📋 Copy Email", copy_text=types.CopyTextButton(new_email), style="success")
    btn_check = InlineKeyboardButton("📥 Check Inbox", callback_data=f"inbox_{new_email}", style="primary")
    btn_saved_list = InlineKeyboardButton("📁 Saved Mails", callback_data="open_saved_list", style="primary")
    btn_new = InlineKeyboardButton("🔄 New Mail", callback_data="new_mail", style="success")
    markup.row(btn_copy, btn_check)
    markup.row(btn_saved_list, btn_new)
    
    msg = (
        "✨ <b>Your Temporary Email Address:</b>\n\n"
        f"<code>{new_email}</code>\n\n"
        "<i>(Click the email to copy automatically)</i>\n\n"
        "⏳ <b>Status:</b> Ready & Active 🟢\n"
        "💾 <b>Saved:</b> Permanently saved to your database (will not be lost even on restart)."
    )
    bot.send_message(message.chat.id, msg, reply_markup=markup)

# ==================== 2. CURRENT INBOX ====================

def handle_current_inbox(message, email=None):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    current_email = email or (user['current_email'] if user else None)
    
    if not current_email:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📧 Create New Mail", callback_data="new_mail"))
        bot.send_message(
            message.chat.id,
            "⚠️ <b>No active email found!</b>\nPlease create a new email or activate one from <b>Saved Mail</b>.",
            reply_markup=markup
        )
        return
    
    # Ensure this email is set as current if passed explicitly
    if email and user and user['current_email'] != email:
        db.create_or_update_user(user_id, current_email=email)

    status_msg = bot.send_message(message.chat.id, f"🔍 Checking inbox for <code>{current_email}</code>...")
    
    # Check Mail.cx inbox
    emails = mail_client.check_inbox(current_email, timeout=4)
    
    markup = InlineKeyboardMarkup()
    btn_refresh = InlineKeyboardButton("🔄 Refresh Inbox", callback_data=f"refresh_{current_email}", style="primary")
    btn_save = InlineKeyboardButton("💾 Save to List", callback_data=f"save_{current_email}", style="primary")
    markup.row(btn_refresh, btn_save)
    
    if not emails:
        text = (
            f"📬 <b>Active Email:</b> <code>{current_email}</code>\n"
            f"🟢 <b>Status:</b> Listening for emails & OTP codes...\n\n"
            "📭 <b>Inbox is empty.</b>\n"
            "Waiting for incoming emails... Send your email or sign up on a website, then click <b>Refresh Inbox</b>."
        )
        try:
            bot.edit_message_text(text, chat_id=message.chat.id, message_id=status_msg.message_id, reply_markup=markup)
        except Exception:
            bot.send_message(message.chat.id, text, reply_markup=markup)
        return

    # If emails found
    text = f"📬 <b>Inbox for:</b> <code>{current_email}</code>\n"
    text += f"🟢 <b>Status:</b> ACTIVE (Auto-Listening ON)\n"
    text += f"Total messages received: <b>{len(emails)}</b>\n\n"
    
    for idx, em in enumerate(emails[:10], start=1):
        sender = em.get('from_name') or em.get('from_email') or em.get('from') or 'Unknown'
        subject = em.get('subject', 'No Subject')
        e_id = em.get('id', '')
        service = detect_service(sender, subject)
        
        # Check if subject or preview contains OTP
        preview_text = clean_html(em.get('preview_text', ''))
        otp_found = extract_otp(subject) or extract_otp(preview_text)
        
        # If not in preview, check detail
        if not otp_found and e_id:
            detail = mail_client.get_email_detail(e_id)
            if detail:
                body = detail.get('text_body') or clean_html(detail.get('html_body', ''))
                otp_found = extract_otp(body)

        otp_text = f"\n   🔑 <b>OTP: <code>{otp_found}</code></b>" if otp_found else ""
        
        text += f"<b>{idx}. 🏷️ {service}</b>\n"
        text += f"   <b>From:</b> {sender}\n"
        text += f"   <b>Subject:</b> {subject}{otp_text}\n\n"

        row_btns = []
        if otp_found:
            row_btns.append(InlineKeyboardButton(f"📋 Copy OTP: {otp_found}", copy_text=types.CopyTextButton(otp_found), style="success"))
        row_btns.append(InlineKeyboardButton(f"📖 Read Full Email #{idx}", callback_data=f"read_{e_id}", style="primary"))
        markup.row(*row_btns)
        
    try:
        bot.edit_message_text(text, chat_id=message.chat.id, message_id=status_msg.message_id, reply_markup=markup)
    except Exception:
        bot.send_message(message.chat.id, text, reply_markup=markup)

# ==================== 3. LOGIN MAIL ====================

def handle_login_mail(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    pref_dom = user['preferred_domain'] if user and user['preferred_domain'] else 'uqu.me'

    text = (
        "🔐 <b>Login to Existing Mail.cx Address:</b>\n\n"
        "Send your email address or username below:\n\n"
        "<i>Examples:</i>\n"
        f"• <code>0hk6zu@{pref_dom}</code> (Full email address)\n"
        f"• <code>0hk6zu</code> (Username only — will use @{pref_dom})\n\n"
        "💡 <i>You can login to any address created from <b>mail.cx web browser</b> or another bot!</i>\n"
        "<i>(Type /cancel to abort)</i>"
    )
    sent_msg = bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(sent_msg, process_login_mail)

def process_login_mail(message):
    user_id = message.from_user.id
    raw_text = message.text.strip() if message.text else ""
    
    # If user tapped one of the menu buttons instead of typing:
    if raw_text in [BTN_CREATE_MAIL, BTN_CURRENT_INBOX, BTN_LOGIN_MAIL, BTN_SAVED_MAIL, BTN_SETTING]:
        handle_menu_selection(message)
        return

    # Check for cancel
    if raw_text.lower() in ["/cancel", "cancel"]:
        bot.send_message(message.chat.id, "❌ Login cancelled.", reply_markup=get_main_keyboard())
        return

    user = db.get_user(user_id)
    pref_dom = user['preferred_domain'] if user and user['preferred_domain'] else 'uqu.me'
    valid_domains = mail_client.get_domains()  # ['uqu.me', 'ddker.com', '9k3r.com']

    # Auto clean input (URLs, mailto, quotes, spaces)
    clean_text = raw_text.strip().lower()
    if "/" in clean_text:
        clean_text = clean_text.split("/")[-1]
    clean_text = re.sub(r'^(?:https?://|mailto:|[<"\'\s]+)', '', clean_text)
    clean_text = re.sub(r'[>"\'\s;,\.]+$', '', clean_text)

    # Extract username and domain
    match = re.search(r'([a-z0-9._-]+)@([a-z0-9.-]+)', clean_text)
    if match:
        username = match.group(1).strip("._-")
        domain_part = match.group(2)
        # If user provided a valid Mail.cx domain, use it; otherwise auto-remove domain and fallback to pref_dom!
        if domain_part in valid_domains:
            domain = domain_part
        else:
            domain = pref_dom
    else:
        # Username only: extract alphanumeric/dots/hyphens
        username = re.sub(r'[^a-z0-9._-]', '', clean_text).strip("._-")
        domain = pref_dom
    
    # Basic validation for username
    if len(username) < 2:
        bot.send_message(
            message.chat.id,
            "⚠️ <b>Invalid Username!</b>\n"
            "Username must have at least 2 characters.\n"
            "Please click <b>🔐 Login Mail</b> and try again.",
            reply_markup=get_main_keyboard()
        )
        return

    full_email = f"{username}@{domain}"
    
    # Save as active email & permanently save in user's saved list
    db.create_or_update_user(user_id, current_email=full_email)
    db.save_email(user_id, full_email)
    
    bot.send_message(
        message.chat.id,
        f"✅ <b>Successfully Logged In!</b>\n\n"
        f"👤 <b>Username:</b> <code>{username}</code>\n"
        f"📬 <b>Active Email:</b> <code>{full_email}</code>\n\n"
        "Connecting to inbox and checking for incoming OTP codes...",
        reply_markup=get_main_keyboard()
    )
    
    # Immediately check and show inbox for this email
    handle_current_inbox(message, email=full_email)

# ==================== 4. SAVED MAIL ====================

def handle_saved_mail(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    current_active = user['current_email'] if user and user['current_email'] else None
    
    # Ensure current email is saved to database if not already
    if current_active:
        db.save_email(user_id, current_active)

    saved = db.get_saved_emails(user_id)
    
    if not saved:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("➕ Create & Save New Mail", callback_data="new_mail"))
        bot.send_message(
            message.chat.id,
            "📂 <b>You have no saved emails yet.</b>\n\n"
            "Whenever you create a temporary email, it will automatically be saved here permanently.",
            reply_markup=markup
        )
        return

    markup = InlineKeyboardMarkup()
    text = "📁 <b>Your Saved Temporary Emails:</b>\n"
    text += "<i>(Permanently stored in database - safe across bot restarts)</i>\n\n"
    text += "👉 <i>Click on any email button below to set it as <b>ACTIVE</b> and view its OTP codes/inbox!</i>\n\n"
    
    for idx, item in enumerate(saved, start=1):
        email_addr = item['email']
        is_active = (email_addr == current_active)
        status_icon = "🟢 [ACTIVE]" if is_active else "⚪"
        text += f"{idx}. {status_icon} <code>{email_addr}</code>\n"
        
        btn_label = f"🟢 {email_addr} (Active)" if is_active else f"⚡ Activate {email_addr}"
        btn_activate = InlineKeyboardButton(btn_label, callback_data=f"activate_{email_addr}", style="success" if is_active else "primary")
        btn_del = InlineKeyboardButton("❌", callback_data=f"delsaved_{email_addr}", style="danger")
        markup.row(btn_activate, btn_del)
        
    bot.send_message(message.chat.id, text, reply_markup=markup)

# ==================== 4. SETTING ====================

def handle_setting(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    current_dom = user['preferred_domain'] if user and user['preferred_domain'] else 'uqu.me'
    active_mail = user['current_email'] if user and user['current_email'] else 'None'
    saved = db.get_saved_emails(user_id)
    
    domains = mail_client.get_domains()
    
    markup = InlineKeyboardMarkup()
    # Domain selection buttons
    row_doms = []
    for d in domains:
        btn_text = f"✅ @{d}" if d == current_dom else f"@{d}"
        row_doms.append(InlineKeyboardButton(btn_text, callback_data=f"setdom_{d}"))
    markup.row(*row_doms)
        
    btn_clear = InlineKeyboardButton("🗑️ Clear Active Mail", callback_data="clear_current", style="danger")
    btn_clear_all = InlineKeyboardButton("⚠️ Delete All Saved Mails", callback_data="clear_all_saved", style="danger")
    markup.row(btn_clear)
    markup.row(btn_clear_all)

    text = (
        "⚙️ <b>Mail.cx Settings & Status:</b>\n\n"
        f"• <b>Active Email:</b> <code>{active_mail}</code>\n"
        f"• <b>Default Domain:</b> <code>@{current_dom}</code>\n"
        f"• <b>Total Saved Mails:</b> <b>{len(saved)}</b>\n\n"
        "🌐 <b>Change Default Domain:</b>\n"
        "<i>Select which domain to use when generating new emails:</i>\n\n"
        "🧹 <b>Management:</b>\n"
        "• <b>Clear Active Mail:</b> Disconnects currently active email.\n"
        "• <b>Delete All Saved Mails:</b> Removes all emails from your saved list."
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

# ==================== REPLY KEYBOARD TEXT DISPATCHER ====================

@bot.message_handler(func=lambda msg: True)
def handle_menu_selection(message):
    text = message.text.strip()
    
    if BTN_CREATE_MAIL in text or "create mail" in text.lower():
        handle_create_mail(message)
    elif BTN_CURRENT_INBOX in text or "current inbox" in text.lower() or "inbox" in text.lower():
        handle_current_inbox(message)
    elif BTN_LOGIN_MAIL in text or "login mail" in text.lower() or "login" in text.lower():
        handle_login_mail(message)
    elif BTN_SAVED_MAIL in text or "saved mail" in text.lower():
        handle_saved_mail(message)
    elif BTN_SETTING in text or "setting" in text.lower():
        handle_setting(message)
    else:
        bot.send_message(
            message.chat.id,
            "Please use the buttons below to navigate 👇",
            reply_markup=get_main_keyboard()
        )

# ==================== INLINE CALLBACK HANDLERS ====================

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    data = call.data
    user_id = call.from_user.id
    
    if data == "new_mail":
        bot.answer_callback_query(call.id, "Generating new email...")
        handle_create_mail(call.message)

    elif data == "open_saved_list":
        bot.answer_callback_query(call.id)
        handle_saved_mail(call.message)

    elif data.startswith("inbox_") or data.startswith("refresh_"):
        email = data.split("_", 1)[1]
        bot.answer_callback_query(call.id, "Refreshing inbox...")
        handle_current_inbox(call.message, email=email)

    elif data.startswith("save_"):
        email = data.split("_", 1)[1]
        saved = db.save_email(user_id, email)
        if saved:
            bot.answer_callback_query(call.id, f"Saved: {email}!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "Already in your saved list!", show_alert=True)

    elif data.startswith("activate_") or data.startswith("use_"):
        email = data.split("_", 1)[1]
        db.create_or_update_user(user_id, current_email=email)
        bot.answer_callback_query(call.id, f"✅ Activated: {email}!", show_alert=False)
        handle_current_inbox(call.message, email=email)

    elif data.startswith("delsaved_"):
        email = data.split("_", 1)[1]
        db.delete_saved_email(user_id, email)
        bot.answer_callback_query(call.id, f"Removed {email} from saved list!")
        handle_saved_mail(call.message)

    elif data == "clear_all_saved":
        db.delete_all_saved_emails(user_id)
        bot.answer_callback_query(call.id, "All saved emails deleted!", show_alert=True)
        handle_setting(call.message)

    elif data.startswith("setdom_"):
        domain = data.split("_", 1)[1]
        db.create_or_update_user(user_id, preferred_domain=domain)
        bot.answer_callback_query(call.id, f"Default domain set to @{domain}!")
        handle_setting(call.message)

    elif data == "clear_current":
        user = db.get_user(user_id)
        if user and user['current_email']:
            mail_client.delete_inbox(user['current_email'])
            db.create_or_update_user(user_id, current_email="")
            bot.answer_callback_query(call.id, "Current email cleared!", show_alert=True)
            handle_setting(call.message)
        else:
            bot.answer_callback_query(call.id, "No active email to clear.")

    elif data.startswith("read_"):
        email_id = data.split("_", 1)[1]
        bot.answer_callback_query(call.id, "Loading email content...")
        detail = mail_client.get_email_detail(email_id)
        if not detail:
            bot.send_message(call.message.chat.id, "⚠️ Failed to load email content or it was expired.")
            return

        sender = detail.get("from_name") or detail.get("from_email") or detail.get("from", "Unknown")
        subject = detail.get("subject", "No Subject")
        date = detail.get("date") or detail.get("created_at", "")
        body_text = detail.get("text_body") or detail.get("text") or clean_html(detail.get("html_body") or detail.get("html", "")) or "No text content"
        
        # Check for OTP in subject first, then body text
        otp = extract_otp(subject) or extract_otp(body_text)
        otp_msg = f"\n\n🔑 <b>Detected Verification Code:</b> <code>{otp}</code>\n" if otp else ""

        preview = body_text[:3000]
        full_text = (
            f"📨 <b>From:</b> {sender}\n"
            f"📌 <b>Subject:</b> {subject}\n"
            f"🕒 <b>Date:</b> {date}{otp_msg}\n"
            f"----------------------------------------\n"
            f"<pre>{preview}</pre>"
        )

        read_markup = InlineKeyboardMarkup()
        if otp:
            # Native Telegram 1-click copy button (copies to clipboard without sending new message)
            read_markup.add(InlineKeyboardButton(f"📋 Copy OTP: {otp}", copy_text=types.CopyTextButton(otp), style="success"))
            
        user = db.get_user(user_id)
        active_addr = user['current_email'] if user and user['current_email'] else ""
        btn_back = InlineKeyboardButton("🔙 Back to Inbox", callback_data=f"refresh_{active_addr}", style="primary")
        read_markup.add(btn_back)

        bot.send_message(call.message.chat.id, full_text, reply_markup=read_markup)

# ==================== REAL-TIME AUTO NOTIFIER WORKER ====================

def auto_listener_worker():
    """
    Background worker that continuously polls active inboxes
    and auto-pushes incoming emails and OTPs to Telegram in real-time!
    """
    time.sleep(2)  # initial delay
    while True:
        try:
            active_users = db.get_active_users()
            for row in active_users:
                user_id = row['user_id']
                email_addr = row['current_email']
                if not email_addr:
                    continue
                
                # Check Mail.cx inbox
                emails = mail_client.check_inbox(email_addr, timeout=3)
                if not emails:
                    continue
                
                for em in emails:
                    email_id = em.get('id')
                    if not email_id or db.is_email_notified(email_id):
                        continue
                    
                    # Mark as notified immediately to prevent double notifications
                    db.mark_email_notified(email_id, user_id, email_addr)
                    
                    # Fetch full email details
                    detail = mail_client.get_email_detail(email_id) or em
                    sender = detail.get('from_name') or detail.get('from_email') or detail.get('from') or em.get('from_name') or em.get('from_email') or 'Unknown'
                    subject = detail.get('subject') or em.get('subject', 'No Subject')
                    body_text = detail.get('text_body') or detail.get('text') or clean_html(detail.get('html_body') or detail.get('html', '')) or clean_html(em.get('preview_text', ''))
                    
                    # Extract OTP and detect service
                    otp = extract_otp(subject) or extract_otp(body_text)
                    service = detect_service(sender, subject)
                    
                    otp_card = (
                        f"\n🔑 <b>Verification Code:</b> <code>{otp}</code>\n"
                        f"<i>(Tap the button below to copy code in 1-click)</i>\n"
                    ) if otp else ""

                    clean_body = body_text.strip()
                    preview = (clean_body[:500] + '...') if len(clean_body) > 500 else clean_body
                    if not preview:
                        preview = "No text content."

                    msg_text = (
                        "🔔 <b>NEW EMAIL / OTP RECEIVED!</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        f"🏷️ <b>Service:</b> <b>{service}</b>\n"
                        f"📬 <b>To:</b> <code>{email_addr}</code>\n"
                        f"👤 <b>From:</b> {sender}\n"
                        f"📌 <b>Subject:</b> {subject}\n"
                        f"{otp_card}"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        f"📄 <b>Preview:</b>\n"
                        f"<pre>{preview}</pre>"
                    )
                    
                    markup = InlineKeyboardMarkup()
                    if otp:
                        # 1-click copy button (styled success green)
                        markup.add(InlineKeyboardButton(f"📋 Copy OTP: {otp}", copy_text=types.CopyTextButton(otp), style="success"))
                    markup.add(InlineKeyboardButton("📖 Read Full Email", callback_data=f"read_{email_id}", style="primary"))
                    
                    try:
                        bot.send_message(user_id, msg_text, reply_markup=markup)
                    except Exception as send_err:
                        print(f"Error sending auto-notification to {user_id}: {send_err}")
                        
            time.sleep(3)
        except Exception as e:
            time.sleep(5)

# ==================== RENDER HEALTH CHECK SERVER ====================

def run_health_server():
    """
    Lightweight HTTP server to satisfy Render's Web Service port binding
    and health checks without requiring external frameworks.
    """
    import http.server
    port = int(os.getenv("PORT", 8080))

    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Mail.cx Telegram Bot is running 24/7 on Render!")

        def log_message(self, format, *args):
            pass  # Silence routine health check logs

    try:
        server = http.server.HTTPServer(("0.0.0.0", port), HealthHandler)
        print(f"🌐 Health server listening on 0.0.0.0:{port} (Render Ready)")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ Health server warning: {e}")

# ==================== MAIN ENTRY POINT ====================

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Mail.cx Telegram Bot is starting...")
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("⚠️ NOTE: Please set your BOT_TOKEN in .env or bot.py!")
    print("=" * 50)

    # Start Health Check server on Render or when PORT is provided
    if os.getenv("PORT") or os.getenv("RENDER"):
        health_thread = threading.Thread(target=run_health_server, daemon=True)
        health_thread.start()

    # Start Real-time Auto-Notifier background thread
    listener = threading.Thread(target=auto_listener_worker, daemon=True)
    listener.start()
    print("🔔 Real-time auto-incoming message listener started!")

    try:
        bot.infinity_polling(skip_pending=True)
    except KeyboardInterrupt:
        print("Bot stopped by user.")
    except Exception as e:
        print(f"Error occurred: {e}")
