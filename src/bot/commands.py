import sqlite3
import logging
import datetime
import re
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext, ContextTypes
from config.config import BOT_TOKEN, ADMIN_IDS, DATABASE_PATH
from db.database import create_connection
from config.config import ADMIN_IDS, CHANNEL_ID
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def escape_markdown_v2(text):
    """Escape all reserved MarkdownV2 characters properly."""
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    telegram_user_id = user.id
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    username = user.username or ""

    # Check if user already exists in the database.
    conn = create_connection(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE telegram_user_id = ?", (telegram_user_id,))
    user_exists = cursor.fetchone()
    conn.close()
    # — If it’s an admin, send them a quick command cheat‑sheet and bail out —
    if telegram_user_id in ADMIN_IDS:
        admin_help = (
            "👮‍♂️ *Admin Commands*\n\n"
            "/aprobar \\<user\\_id\\> \\- Aprueba un pago y extiende la suscripción\n"
            "/denegar \\<user\\_id\\> \\- Rechaza un pago y elimina al usuario\n"
            "/renovar \\- Notifica a admins que quieres renovar tu suscripción\n"
            "/tiempoRestante \\- Comprueba días restantes de tu suscripción\n"
            "/expiring \\<days\\> \\- Lista usuarios con suscripciones próximas a vencer\n"
        )
        await update.message.reply_text(admin_help, parse_mode="MarkdownV2")
        return
    
    
    if user_exists:
        # The user is already registered: send a different message.
        renewal_info_msg = (
            "Ya estás registrado en nuestro sistema.\n\n"
            "Si deseas /renovar tu suscripción o saber cuánto tiempo te queda, "
            "puedes contactarte con el administrador o enviar el comando /tiempoRestante para verificarlo.\n\n"
            "¡Gracias por formar parte de nuestro grupo!"
        )
        await update.message.reply_text(renewal_info_msg)
    else:
        # New user: send welcome message and notify admins.
        welcome_msg = (
            "Bienvenido al Bot de 1% aquí podrás /renovar tu suscripción para mantenerte en el grupo. "
            "También podrás verificar el tiempo que te resta con el comando /tiempoRestante.\n\n"
            "Si estás aquí es porque ya debes haber realizado el pago para la suscripción y en este momento "
            "solo debes esperar que un Admin confirme que tu pago ha sido aprobado.\n\n"
            "Una vez aprobado te enviaré un mensaje por este chat para que te unas al grupo de señales 🚀"
        )
        await update.message.reply_text(welcome_msg)

        admin_msg = (
            "⚠️ *Admin*, tienes una nueva verificación de pago que realizar\\.\n\n"
            f"• *ID:* `{escape_markdown_v2(str(telegram_user_id))}`\n"
            f"• *Username:* @{escape_markdown_v2(username)}\n"
            f"• *Nombre y Apellido:* {escape_markdown_v2(first_name)} {escape_markdown_v2(last_name)}\n\n"
            "El usuario está intentando unirse al grupo\\.\n\n"
            f"Si no tienes un pago de parte de esta persona, contacta o envía el comando "
            f"`/denegar {telegram_user_id}`\n\n"
            f"Para aprobar al usuario y permitirle acceso usa `/aprobar {telegram_user_id}`\n"
        )

        for admin_id in ADMIN_IDS:
            await context.bot.send_message(chat_id=admin_id, text=admin_msg, parse_mode="MarkdownV2")

async def renovar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /renovar command.
    1. Send renewal message to user.
    2. Notify all admins about the renewal request.
    """
    user = update.message.from_user
    telegram_user_id = user.id
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    username = user.username or ""

    if telegram_user_id in ADMIN_IDS:
        admin_help = (
            "👮‍♂️ *Admin Commands*\n\n"
            "/aprobar <user_id> — Aprueba un pago y extiende la suscripción\n"
            "/denegar <user_id> — Rechaza un pago y elimina al usuario\n"
            "/renovar — Notifica a admins que quieres renovar la suscripción\n"
            "/tiempoRestante — Comprueba días restantes de tu suscripción\n"
            "/expiring <days> — Lista usuarios con suscripciones próximas a vencer\n"
        )
        await update.message.reply_text(admin_help, parse_mode="MarkdownV2")
        return
    
    
    renewal_msg = (
        "Estás intentando renovar tu suscripción.\n\n"
        "Si ya realizaste el pago, por favor espera a que un Admin confirme que tu pago ha sido aprobado.\n\n"
        "Una vez aprobado te enviaré un mensaje por este chat para que sepas que tu renovación está activa 🚀"
    )
    await update.message.reply_text(renewal_msg)

    admin_msg = (
        f"⚠️ *Admin*, tienes una nueva verificación de *renovación* de pago\\.\n\n"
        f"• *ID:* `{escape_markdown_v2(str(telegram_user_id))}`\n"
        f"• *Username:* @{escape_markdown_v2(username)}\n"
        f"• *Nombre y Apellido:* {escape_markdown_v2(first_name)} {escape_markdown_v2(last_name)}\n\n"
        "El usuario está intentando renovar su acceso\\.\n\n"
        f"Si no tienes un pago de parte de esta persona, contacta o envía el comando "
        f"`/denegar {telegram_user_id}`\n\n"
        f"Para aprobar la renovación usa `/aprobar {telegram_user_id}`\n"
    )

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=admin_msg,
            parse_mode="MarkdownV2"
        )

async def aprobar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /aprobar <telegram_user_id>
    Admin command to confirm the user (new or renewal).
      - If the user doesn't exist, create it with 30 days from now.
      - If the user exists and is still within paid_until (not expired), add 30 days.
      - If expired, reset or extend based on how long ago it expired.
    """
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ No tienes permisos para aprobar pagos.")
        return

    try:
        user_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Uso incorrecto. Usa: /aprobar <telegram_user_id>")
        return

    conn = create_connection(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, paid_until FROM users WHERE telegram_user_id = ?", (user_id,))
    row = cursor.fetchone()

    today = datetime.now().date()
    today_str = today.strftime('%Y-%m-%d')
    new_paid_until_str = None

    if not row:
        # User doesn't exist: create new record with 30 days access.
        join_date_str = today_str
        paid_until_date = today + timedelta(days=30)
        new_paid_until_str = paid_until_date.strftime('%Y-%m-%d')

        cursor.execute("""
            INSERT INTO users 
                (telegram_user_id, username, first_name, last_name, join_date, paid_until, last_payment_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, "", "", "", join_date_str, new_paid_until_str, today_str))
        conn.commit()
    else:
        db_id, paid_until_str = row
        old_paid_until = datetime.strptime(paid_until_str, '%Y-%m-%d').date()

        if old_paid_until >= today:
            # Still active: extend from current paid_until.
            new_paid_until = old_paid_until + timedelta(days=30)
        else:
            days_expired = (today - old_paid_until).days
            if days_expired > 30:
                # Expired more than 30 days ago: reset from today.
                new_paid_until = today + timedelta(days=30)
            else:
                # Expired within 30 days: extend from the old paid_until.
                new_paid_until = old_paid_until + timedelta(days=30)

        new_paid_until_str = new_paid_until.strftime('%Y-%m-%d')

        cursor.execute("""
            UPDATE users
            SET paid_until = ?, last_payment_date = ?
            WHERE id = ?
        """, (new_paid_until_str, today_str, db_id))
        cursor.execute("""
            INSERT INTO payments (user_id, payment_date, paid_until)
            VALUES (?, ?, ?)
        """, (db_id, today_str, new_paid_until_str))
        conn.commit()

    await update.message.reply_text(
        f"✅ Pago aprobado. El usuario {user_id} tiene acceso hasta {new_paid_until_str}."
    )

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ ¡Tu pago ha sido confirmado! Tienes acceso hasta {new_paid_until_str}. \n\n Por favor utiliza este link para unirte al grupo: 🔗 https://t.me/+Qei0MTdpyggzYTNh"
        )
    except Exception as e:
        logger.error(f"No se pudo enviar mensaje al usuario {user_id}: {e}")

    conn.close()

async def denegar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /denegar <telegram_user_id>
    Admin command to reject a payment attempt.
      - Notifies the user of rejection.
      - Optionally removes the user from the database.
    """
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ No tienes permisos para denegar pagos.")
        return

    try:
        user_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Uso incorrecto. Usa: /denegar <telegram_user_id>")
        return

    conn = create_connection(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE telegram_user_id = ?", (user_id,))
    user_row = cursor.fetchone()

    if user_row:
        cursor.execute("DELETE FROM users WHERE telegram_user_id = ?", (user_id,))
        conn.commit()
        await update.message.reply_text(f"🚫 Usuario {user_id} ha sido denegado.")
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🚫 Tu pago no fue confirmado. Contacta con un administrador."
            )
        except Exception as e:
            logger.error(f"No se pudo enviar mensaje al usuario {user_id}: {e}")
    else:
        await update.message.reply_text(f"⚠️ No se encontró al usuario con ID {user_id} en la base de datos.")

    conn.close()

async def tiempo_restante(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tiempoRestante - Check how many days left before payment is due."""
    user = update.message.from_user
    telegram_user_id = user.id

    conn = create_connection(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT paid_until FROM users WHERE telegram_user_id = ?", (telegram_user_id,))
    user_row = cursor.fetchone()

    if user_row:
        paid_until = datetime.strptime(user_row[0], '%Y-%m-%d').date()
        days_left = (paid_until - datetime.now().date()).days

        if days_left > 0:
            await update.message.reply_text(f"🕒 Te quedan {days_left} días antes de que venza tu acceso.")
        else:
            await update.message.reply_text("🚫 Tu acceso ha expirado. Contacta con un administrador para renovarlo.")
            # Make sure to use the proper chat id from update.message.chat.id
            # “Kick” = ban then unban so they can re‑join later
            await context.bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=telegram_user_id)
            await context.bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=telegram_user_id)
            cursor.execute("DELETE FROM users WHERE telegram_user_id = ?", (telegram_user_id,))
            conn.commit()
    else:
        await update.message.reply_text("⚠️ No estás registrado en el sistema.")

    conn.close()

async def expiring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ No tienes permiso para usar este comando.")
        return

    # Get days argument
    try:
        days = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Uso: /expiring <días>")
        return

    threshold_date = (datetime.now() + timedelta(days=days)).date()

    conn = create_connection(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT username, first_name, last_name, paid_until
        FROM users
        WHERE paid_until IS NOT NULL
    """)
    users = cursor.fetchall()
    conn.close()

    expiring_users = []
    for username, first_name, last_name, paid_until_str in users:
        try:
            paid_until = datetime.strptime(paid_until_str, "%Y-%m-%d").date()
            if paid_until <= threshold_date:
                full_name = f"{first_name or ''} {last_name or ''}".strip()
                expiring_users.append((username or 'N/A', full_name, paid_until.strftime("%Y-%m-%d")))
        except ValueError:
            continue  # Skip invalid dates

    if not expiring_users:
        await update.message.reply_text(f"Ningún usuario con suscripción próxima a vencer en {days} días.")
        return

    msg_lines = [f"📅 *Suscripciones por vencer:* {len(expiring_users)} usuarios\n"]
    for uname, name, date in expiring_users:
        line = f"• @{escape_markdown_v2(uname)} \\| {escape_markdown_v2(name)} \\| `{date}`"
        msg_lines.append(line)

    result = "\n".join(msg_lines)
    chunk = ""
    for line in msg_lines:
        if len(chunk) + len(line) + 1 > 4000:  # Keeping a bit of buffer
            await update.message.reply_text(chunk, parse_mode="MarkdownV2")
            chunk = ""
        chunk += line + "\n"

    if chunk:
        await update.message.reply_text(chunk, parse_mode="MarkdownV2")
    
def get_handlers():
    """Return all bot command handlers for integration in main.py"""
    return [
        CommandHandler("start", start),
        CommandHandler("renovar", renovar),
        CommandHandler("aprobar", aprobar),
        CommandHandler("denegar", denegar),
        CommandHandler("tiempoRestante", tiempo_restante),
        CommandHandler("expiring", expiring)
    ]