import os
import sqlite3
import logging
from datetime import datetime, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Add BOT_TOKEN and ADMIN_IDS to your hosting environment variables.
# ADMIN_IDS should be comma-separated Telegram numeric user IDs.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}

# Payment addresses supplied by the bot owner.
EVM_WALLET = "0x04d300280C278C67cB56Bec676d406C6c46635DC"
SOL_WALLET = "E2pdG1FofHeBf8jdmJtZgqQdSJZuzsX58pqLkWPY7Z8t"

DB_PATH = os.getenv("DATABASE_PATH", "orders.db")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Prices are intentionally not invented. Set confirmed prices here before
# accepting payments, or leave as "Request quote".
SERVICES = {
    "trending": {
        "title": "Trending Services",
        "items": [
            ("gecko", "GeckoTerminal promotion"),
            ("dexscreener", "DEX Screener promotion"),
            ("dextools", "DEXTools promotion"),
            ("padre", "Padre promotion"),
            ("custom", "Custom campaign"),
        ],
    },
    "reactions": {
        "title": "DEX Reactions",
        "items": [
            ("dex_reactions", "DEX reactions — request quote"),
        ],
    },
    "volume": {
        "title": "Volume Bots",
        "items": [
            ("volume_bot", "Volume bot service — request quote"),
        ],
    },
    "bundler": {
        "title": "Bundler Bot",
        "items": [
            ("bundler_bot", "Bundler bot service — request quote"),
        ],
    },
}

SERVICE_NAMES = {
    key: item[1]
    for group in SERVICES.values()
    for item in group["items"]
    for key in [item[0]]
}


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                service_key TEXT NOT NULL,
                service_name TEXT NOT NULL,
                payment_network TEXT,
                tx_hash TEXT,
                status TEXT NOT NULL DEFAULT 'awaiting_quote',
                created_at TEXT NOT NULL
            )
            """
        )


def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Trending Services", callback_data="menu:trending")],
        [InlineKeyboardButton("💬 DEX Reactions", callback_data="menu:reactions")],
        [InlineKeyboardButton("📈 Volume Bots", callback_data="menu:volume")],
        [InlineKeyboardButton("🚀 Bundler Bot", callback_data="menu:bundler")],
        [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
        [InlineKeyboardButton("❓ How it works", callback_data="how")],
    ])


def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Main menu", callback_data="home")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name if user else "there"
    await update.message.reply_text(
        f"Welcome, {name}!\n\n"
        "Choose a service below to view available options and request a quote.",
        reply_markup=main_keyboard(),
    )


async def show_service_menu(query, group_key):
    group = SERVICES[group_key]
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"service:{key}")]
        for key, label in group["items"]
    ]
    buttons.append([InlineKeyboardButton("⬅️ Main menu", callback_data="home")])
    await query.edit_message_text(
        f"**{group['title']}**\n\nSelect a service to continue.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "home":
        await query.edit_message_text(
            "Choose a service below:",
            reply_markup=main_keyboard(),
        )
        return

    if data.startswith("menu:"):
        await show_service_menu(query, data.split(":", 1)[1])
        return

    if data.startswith("service:"):
        service_key = data.split(":", 1)[1]
        service_name = SERVICE_NAMES.get(service_key)
        if not service_name:
            await query.edit_message_text("That service could not be found.", reply_markup=back_keyboard())
            return

        context.user_data["pending_service"] = service_key
        await query.edit_message_text(
            f"**{service_name}**\n\n"
            "Price: Please request a quote from the admin before sending payment.\n\n"
            "Tap the button below to request this service.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Request this service", callback_data=f"request:{service_key}")],
                [InlineKeyboardButton("⬅️ Back", callback_data="home")],
            ]),
        )
        return

    if data.startswith("request:"):
        service_key = data.split(":", 1)[1]
        service_name = SERVICE_NAMES.get(service_key)
        if not service_name:
            await query.edit_message_text("That service could not be found.", reply_markup=back_keyboard())
            return

        user = query.from_user
        with db() as connection:
            cursor = connection.execute(
                """
                INSERT INTO orders
                (user_id, username, service_key, service_name, status, created_at)
                VALUES (?, ?, ?, ?, 'awaiting_quote', ?)
                """,
                (
                    user.id,
                    user.username or "",
                    service_key,
                    service_name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            order_id = cursor.lastrowid

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"New quote request #{order_id}\n"
                    f"Service: {service_name}\n"
                    f"User: {user.full_name} (@{user.username or 'no_username'})\n"
                    f"User ID: {user.id}\n\n"
                    f"Reply with /quote {order_id} AMOUNT NETWORK",
                )
            except Exception:
                logger.exception("Could not notify admin %s", admin_id)

        await query.edit_message_text(
            f"Your request #{order_id} has been sent to the admin.\n"
            "Please wait for the confirmed price and payment instructions. "
            "Do not send payment until the amount and network are confirmed.",
            reply_markup=back_keyboard(),
        )
        return

    if data == "how":
        await query.edit_message_text(
            "How it works\n\n"
            "1. Choose a service.\n"
            "2. Request a quote.\n"
            "3. Wait for the admin to confirm the price and network.\n"
            "4. Pay only to the wallet and network confirmed by the admin.\n"
            "5. Submit your transaction hash when requested.\n"
            "6. The admin reviews your order and updates its status.\n\n"
            "Never pay an unconfirmed amount.",
            reply_markup=back_keyboard(),
        )
        return

    if data == "my_orders":
        user_id = query.from_user.id
        with db() as connection:
            rows = connection.execute(
                "SELECT id, service_name, status, created_at FROM orders "
                "WHERE user_id = ? ORDER BY id DESC LIMIT 10",
                (user_id,),
            ).fetchall()

        if not rows:
            await query.edit_message_text("You have no orders yet.", reply_markup=back_keyboard())
            return

        lines = ["Your latest orders:"]
        for row in rows:
            lines.append(f"#{row['id']} — {row['service_name']} — {row['status']}")
        await query.edit_message_text("\n".join(lines), reply_markup=back_keyboard())
        return

    if data.startswith("tx:"):
        try:
            order_id = int(data.split(":", 1)[1])
        except ValueError:
            return
        context.user_data["tx_order_id"] = order_id
        await query.edit_message_text(
            f"Send the transaction hash for order #{order_id} in your next message.",
            reply_markup=back_keyboard(),
        )


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    order_id = context.user_data.get("tx_order_id")
    if not order_id:
        await update.message.reply_text(
            "Use the menu to choose a service or view your orders.",
            reply_markup=main_keyboard(),
        )
        return

    user = update.effective_user
    with db() as connection:
        order = connection.execute(
            "SELECT id FROM orders WHERE id = ? AND user_id = ?",
            (order_id, user.id),
        ).fetchone()
        if not order:
            context.user_data.pop("tx_order_id", None)
            await update.message.reply_text("I couldn't find that order.")
            return

        connection.execute(
            "UPDATE orders SET tx_hash = ?, status = 'payment_submitted' WHERE id = ?",
            (text, order_id),
        )

    context.user_data.pop("tx_order_id", None)
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"Transaction submitted for order #{order_id}\n"
                f"User ID: {user.id}\nHash: {text}\n\n"
                f"Review it, then use /approve {order_id} or /reject {order_id}.",
            )
        except Exception:
            logger.exception("Could not notify admin %s", admin_id)

    await update.message.reply_text(
        f"Transaction hash received for order #{order_id}. "
        "The admin will review it.",
        reply_markup=main_keyboard(),
    )


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /quote ORDER_ID AMOUNT NETWORK")
        return
    try:
        order_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Order ID must be a number.")
        return

    amount = context.args[1]
    network = " ".join(context.args[2:])
    with db() as connection:
        row = connection.execute(
            "SELECT user_id, service_name FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        if not row:
            await update.message.reply_text("Order not found.")
            return
        connection.execute(
            "UPDATE orders SET status = 'quoted', payment_network = ? WHERE id = ?",
            (network, order_id),
        )

    network_upper = network.upper()
    if "SOL" in network_upper or "SOLANA" in network_upper:
        wallet_text = f"Solana wallet: {SOL_WALLET}"
    elif any(tag in network_upper for tag in ("EVM", "ETH", "BSC", "BASE")):
        wallet_text = f"EVM wallet: {EVM_WALLET}"
    else:
        wallet_text = (
            f"EVM wallet: {EVM_WALLET}\\n"
            f"Solana wallet: {SOL_WALLET}\\n"
            "Ask the admin which address applies before paying."
        )

    await context.bot.send_message(
        row["user_id"],
        f"Quote for order #{order_id} ({row['service_name']}):\\n"
        f"Amount: {amount}\\nNetwork: {network}\\n\\n"
        f"{wallet_text}\\n\\n"
        "Only pay after checking the network and wallet. "
        "After paying, tap the button below to submit your transaction hash.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Submit transaction hash", callback_data=f"tx:{order_id}")]
        ]),
    )
    await update.message.reply_text(f"Quote sent for order #{order_id}.")


async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /approve ORDER_ID")
        return
    order_id = int(context.args[0])
    with db() as connection:
        row = connection.execute(
            "SELECT user_id FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if not row:
            await update.message.reply_text("Order not found.")
            return
        connection.execute(
            "UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,)
        )
    await context.bot.send_message(row["user_id"], f"Your order #{order_id} has been approved.")
    await update.message.reply_text(f"Order #{order_id} approved.")


async def reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /reject ORDER_ID")
        return
    order_id = int(context.args[0])
    with db() as connection:
        row = connection.execute(
            "SELECT user_id FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if not row:
            await update.message.reply_text("Order not found.")
            return
        connection.execute(
            "UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,)
        )
    await context.bot.send_message(row["user_id"], f"Your order #{order_id} was rejected. Contact the admin.")
    await update.message.reply_text(f"Order #{order_id} rejected.")


async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    with db() as connection:
        rows = connection.execute(
            "SELECT id, user_id, service_name, status FROM orders ORDER BY id DESC LIMIT 20"
        ).fetchall()
    if not rows:
        await update.message.reply_text("No orders yet.")
        return
    lines = ["Latest orders:"]
    for row in rows:
        lines.append(
            f"#{row['id']} | user {row['user_id']} | "
            f"{row['service_name']} | {row['status']}"
        )
    await update.message.reply_text("\n".join(lines))


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Set BOT_TOKEN in your hosting environment variables.")
    if not ADMIN_IDS:
        raise RuntimeError("Set ADMIN_IDS in your hosting environment variables.")
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("orders", orders_command))
    application.add_handler(CommandHandler("quote", quote_command))
    application.add_handler(CommandHandler("approve", approve_command))
    application.add_handler(CommandHandler("reject", reject_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text))
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
