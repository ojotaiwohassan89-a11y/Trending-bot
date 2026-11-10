import os, sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN=os.getenv("BOT_TOKEN","")
ADMINS={int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()}
EVM=os.getenv("EVM_WALLET","0x04d300280C278C67cB56Bec676d406C6c46635DC")
SOL=os.getenv("SOL_WALLET","E2pdG1FofHeBf8jdmJtZgqQdSJZuzsX58pqLkWPY7Z8t")
DB=os.getenv("DATABASE_PATH","orders.db")
PACKAGES={
 "gecko24":{"name":"GeckoTerminal promotion · 24h","price":"150"},
 "dex12":{"name":"DEX Screener promotion · 12h","price":"250"},
 "tools12":{"name":"DEXTools promotion · 12h","price":"200"},
 "padre24":{"name":"Padre promotion · 24h (Solana)","price":"150"},
 "custom":{"name":"Custom campaign · quote required","price":"0"}
}
def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 c.execute("""CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY,user_id INTEGER,username TEXT,pkg TEXT,chain TEXT,token TEXT,project TEXT,tx TEXT,status TEXT,created TEXT)""")
 c.commit(); return c
def home():
 return InlineKeyboardMarkup([[InlineKeyboardButton("📈 Trending packages",callback_data="packages")],
 [InlineKeyboardButton("🧾 My orders",callback_data="orders"),InlineKeyboardButton("ℹ️ How it works",callback_data="how")]])
async def start(u:Update,c:ContextTypes.DEFAULT_TYPE):
 c.user_data.clear()
 await u.message.reply_text("Welcome to Orbit Trending Services. Choose a campaign below. Orders are manually reviewed; no ranking, volume or price outcome is guaranteed.",reply_markup=home())
async def cb(u:Update,c:ContextTypes.DEFAULT_TYPE):
 q=u.callback_query; await q.answer(); d=q.data
 if d=="home": await q.edit_message_text("Main menu:",reply_markup=home())
 elif d=="packages":
  rows=[[InlineKeyboardButton(f"{p['name']} — {'$'+p['price'] if p['price']!='0' else 'quote'}",callback_data="pkg:"+k)] for k,p in PACKAGES.items()]
  rows.append([InlineKeyboardButton("⬅️ Back",callback_data="home")])
  await q.edit_message_text("Choose a package (edit sample prices before launch):",reply_markup=InlineKeyboardMarkup(rows))
 elif d.startswith("pkg:"):
  c.user_data["pkg"]=d.split(":")[1]
  await q.edit_message_text("Choose token network:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Solana",callback_data="chain:Solana"),InlineKeyboardButton("EVM",callback_data="chain:EVM")]]))
 elif d.startswith("chain:"):
  c.user_data["chain"]=d.split(":")[1]; c.user_data["step"]="token"
  await q.edit_message_text("Send the token contract / mint address.")
 elif d=="how":
  await q.edit_message_text("1. Choose package. 2. Submit token details. 3. Bot shows the receiving wallet. 4. Submit transaction hash. 5. Admin checks payment and confirms a real provider/placement before fulfillment. Payment alone does not create trending.",reply_markup=home())
 elif d=="orders":
  db=conn(); rs=db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10",(q.from_user.id,)).fetchall(); db.close()
  msg="No orders yet." if not rs else "\n\n".join([f"#{r['id']} · {PACKAGES[r['pkg']]['name']}\n{r['chain']} · {r['token']}\nStatus: {r['status']}" for r in rs])
  await q.edit_message_text(msg,reply_markup=home())
 elif d.startswith("paid:"):
  oid=int(d.split(":")[1]); c.user_data["tx_order"]=oid
  await q.edit_message_text("Send the transaction hash. Never send a seed phrase or private key.")
async def msg(u:Update,c:ContextTypes.DEFAULT_TYPE):
 t=(u.message.text or "").strip(); user=u.effective_user
 if "tx_order" in c.user_data:
  oid=c.user_data.pop("tx_order"); db=conn()
  db.execute("UPDATE orders SET tx=?,status='payment_submitted' WHERE id=? AND user_id=?",(t,oid,user.id)); db.commit(); db.close()
  await u.message.reply_text(f"TX submitted for order #{oid}. Admin will verify it.")
  for a in ADMINS:
   try: await c.bot.send_message(a,f"Payment submitted · order #{oid}\nUser {user.id} @{user.username or ''}\nTX: {t}\nUse /orders to review.")
   except: pass
  return
 step=c.user_data.get("step")
 if step=="token":
  if not 20<=len(t)<=120: await u.message.reply_text("That address length looks unusual. Send the token address again."); return
  c.user_data["token"]=t; c.user_data["step"]="project"; await u.message.reply_text("Send project name (or - to skip)."); return
 if step=="project":
  pkg=c.user_data["pkg"]; chain=c.user_data["chain"]; token=c.user_data["token"]; project="" if t=="-" else t[:80]
  db=conn(); cur=db.execute("INSERT INTO orders(user_id,username,pkg,chain,token,project,status,created) VALUES(?,?,?,?,?,?,?,?)",(user.id,user.username,pkg,chain,token,project,"awaiting_payment",datetime.now(timezone.utc).isoformat()))
  oid=cur.lastrowid; db.commit(); db.close(); c.user_data.clear()
  wallet=SOL if chain=="Solana" else EVM; price=PACKAGES[pkg]["price"]
  note="Send only on Solana mainnet." if chain=="Solana" else "Confirm the exact EVM network with support before sending."
  await u.message.reply_text(f"Order #{oid}\nPackage: {PACKAGES[pkg]['name']}\nPrice: {'$'+price+' USD' if price!='0' else 'Quote required — do not pay yet'}\nProject: {project or '-'}\nToken: {token}\n{note}\n\nReceiving wallet:\n{wallet}\n\nFor USD prices, get the exact crypto amount and accepted asset from support before paying. Then submit your TX hash.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("I've paid · submit TX",callback_data=f"paid:{oid}")],[InlineKeyboardButton("Main menu",callback_data="home")]]))
async def orders(u:Update,c:ContextTypes.DEFAULT_TYPE):
 if u.effective_user.id not in ADMINS: return await u.message.reply_text("Not authorized.")
 db=conn(); rs=db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 25").fetchall(); db.close()
 if not rs: return await u.message.reply_text("No orders.")
 for r in rs:
  await u.message.reply_text(f"#{r['id']} · {r['status']}\nUser: {r['user_id']} @{r['username'] or ''}\n{PACKAGES[r['pkg']]['name']}\n{r['chain']} · {r['token']}\nTX: {r['tx'] or 'not submitted'}\nCommands: /approve {r['id']} · /done {r['id']} · /reject {r['id']}")
async def status(u,c,s,txt):
 if u.effective_user.id not in ADMINS: return await u.message.reply_text("Not authorized.")
 if not c.args or not c.args[0].isdigit(): return await u.message.reply_text("Supply order ID.")
 db=conn(); r=db.execute("SELECT user_id FROM orders WHERE id=?",(int(c.args[0]),)).fetchone()
 if r: db.execute("UPDATE orders SET status=? WHERE id=?",(s,int(c.args[0]))); db.commit()
 db.close()
 if not r: return await u.message.reply_text("Order not found.")
 await c.bot.send_message(r["user_id"],f"Order #{c.args[0]}: {txt}"); await u.message.reply_text("Updated.")
async def approve(u,c): await status(u,c,"payment_verified","Payment verified; campaign awaiting fulfillment.")
async def done(u,c): await status(u,c,"completed","Campaign marked completed.")
async def reject(u,c): await status(u,c,"manual_review","Order needs manual review; contact support.")
def main():
 if not TOKEN: raise SystemExit("Set BOT_TOKEN in .env")
 conn().close()
 app=Application.builder().token(TOKEN).build()
 app.add_handler(CommandHandler("start",start)); app.add_handler(CommandHandler("orders",orders))
 app.add_handler(CommandHandler("approve",approve)); app.add_handler(CommandHandler("done",done)); app.add_handler(CommandHandler("reject",reject))
 app.add_handler(CallbackQueryHandler(cb)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,msg))
 app.run_polling()
if __name__=="__main__": main()
