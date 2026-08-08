from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# 内存数据库，按 Chat ID 隔离存储数据
db = {}

def get_chat_data(chat_id: int):
    """获取或初始化群组账目数据"""
    if chat_id not in db:
        db[chat_id] = {
            "in_records": [],   # 入款记录
            "out_records": [],  # 出款记录
            "fee_rate": 0.0,    # 费率 (%)
            "exchange_rate": 1.0 # 汇率
        }
    return db[chat_id]

def generate_bill_text(chat_title: str, data: dict) -> str:
    """生成账单文本"""
    in_records = data["in_records"]
    out_records = data["out_records"]
    fee_rate = data["fee_rate"]
    rate = data["exchange_rate"]

    in_text = f"**{chat_title}**  `管理员`\n"
    in_text += f"入款（{len(in_records)}笔）：\n"
    total_in = 0.0
    if not in_records:
        in_text += "无\n"
    else:
        for r in in_records:
            total_in += r["amount"]
            usdt = r["amount"] / rate if rate != 0 else 0
            in_text += f"{r['time']} {r['amount']:g} / {rate:g} = {usdt:.2f}U\n"

    out_text = f"\n出款（{len(out_records)}笔）：\n"
    total_out = 0.0
    if not out_records:
        out_text += "无\n"
    else:
        for r in out_records:
            total_out += r["amount"]
            usdt = r["amount"] / rate if rate != 0 else 0
            out_text += f"{r['time']} {r['amount']:g} ({usdt:.2f}USDT)\n"

    should_pay_rmb = total_in * (1 - fee_rate / 100.0)
    should_pay_usdt = should_pay_rmb / rate if rate != 0 else 0

    has_paid_rmb = total_out
    has_paid_usdt = has_paid_rmb / rate if rate != 0 else 0

    unpaid_rmb = should_pay_rmb - has_paid_rmb
    unpaid_usdt = unpaid_rmb / rate if rate != 0 else 0

    fee_display = f"{fee_rate:g}%" if fee_rate > 0 else "0"

    text = (
        f"{in_text}"
        f"{out_text}\n"
        f"费率：{fee_display}\n"
        f"汇率：{rate:g}\n"
        f"总入款金额：{total_in:g}\n\n"
        f"应下发：{should_pay_rmb:g} | {should_pay_usdt:.2f} (USDT)\n"
        f"已下发：{has_paid_rmb:g} | {has_paid_usdt:.2f} (USDT)\n"
        f"未下发：{unpaid_rmb:g} | {unpaid_usdt:.2f} (USDT)"
    )
    return text

def get_keyboard():
    keyboard = [[InlineKeyboardButton("历史账单 ↗", callback_data="history_bill")]]
    return InlineKeyboardMarkup(keyboard)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 **账单机器人已就绪**\n\n"
        "📌 **常用记账指令**：\n"
        "• 入款：发送 `+1000`\n"
        "• 出款：发送 `-1000`\n"
        "• 设置汇率：发送 `/rate 7.2`\n"
        "• 设置费率：发送 `/fee 1.5`\n"
        "• 清空账单：发送 `/reset`\n"
        "• 查看账单：发送 `/bill`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = get_chat_data(chat_id)
    try:
        new_rate = float(context.args[0])
        data["exchange_rate"] = new_rate
        await update.message.reply_text(f"✅ 汇率已更新为：{new_rate}")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ 格式错误！请输入：`/rate 7.2`", parse_mode="Markdown")

async def set_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = get_chat_data(chat_id)
    try:
        new_fee = float(context.args[0])
        data["fee_rate"] = new_fee
        await update.message.reply_text(f"✅ 费率已更新为：{new_fee}%")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ 格式错误！请输入：`/fee 1`", parse_mode="Markdown")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db[chat_id] = {
        "in_records": [],
        "out_records": [],
        "fee_rate": 0.0,
        "exchange_rate": 1.0
    }
    await update.message.reply_text("🔄 账单已全部清空重置！")

async def show_bill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    data = get_chat_data(chat.id)
    chat_title = chat.title if chat.title else "MIniTH 888"
    text = generate_bill_text(chat_title, data)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_keyboard())

async def handle_quick_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat = update.effective_chat
    data = get_chat_data(chat.id)
    now_time = datetime.now().strftime("%H:%M:%S")

    if text.startswith("+"):
        try:
            amount = float(text[1:])
            data["in_records"].append({"time": now_time, "amount": amount})
        except ValueError:
            return
    elif text.startswith("-"):
        try:
            amount = float(text[1:])
            data["out_records"].append({"time": now_time, "amount": amount})
        except ValueError:
            return
    else:
        return

    chat_title = chat.title if chat.title else "MIniTH 888"
    bill_text = generate_bill_text(chat_title, data)
    await update.message.reply_text(bill_text, parse_mode="Markdown", reply_markup=get_keyboard())

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

if __name__ == "__main__":
    import os
    TOKEN = os.environ.get("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("rate", set_rate))
    app.add_handler(CommandHandler("fee", set_fee))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CommandHandler("bill", show_bill))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_quick_record))

    print("🤖 机器人已启动...")
    app.run_polling()
