# Orbit Trending Services Bot — starter

An original Telegram order bot inspired by publicly described DEX promotion-bot features. It is not DexMoji code and is not affiliated with DexMoji or any DEX platform.

## Included
- Package menu, Solana/EVM selection, token and project intake
- Your supplied public receiving addresses
- Order database and transaction-hash submission
- Admin notifications and commands: `/orders`, `/approve ID`, `/done ID`, `/reject ID`

## Important
This is an order-taking/admin-fulfilment MVP, not an automated trending engine. It does not create fake visitors, fake volume, reactions, or rankings. You need a real provider/API or must manually arrange the advertised placement. Never promise guaranteed rankings unless you can deliver them and refund when applicable.

Payments are manually verified. Check the transaction on the correct explorer for destination, asset, amount, network and confirmations. EVM address needs an exact network (Ethereum/Base/BSC etc.). For USD-priced packages, tell the customer the accepted asset and exact amount before payment. Sample package prices in `bot.py` are placeholders; edit them before launch.

## Setup
1. In Telegram, open `@BotFather`, send `/newbot`, follow instructions and copy the token.
2. Get your numeric Telegram user ID (for example via `@userinfobot`).
3. Install Python 3.11+.
4. Extract this ZIP and copy `.env.example` to `.env`.
5. Fill `BOT_TOKEN` and `ADMIN_IDS`. Keep `.env private.
6. Edit the `PACKAGES` dictionary in `bot.py` to your actual prices and only services you can deliver.
7. In terminal in this folder:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

Keep it running locally for testing. For 24/7 hosting, deploy as a Python worker on Render, Railway or a VPS, set the same environment variables in the host dashboard, and use persistent storage for `orders.db`.

## Admin commands
`/orders` lists recent orders. `/approve ID` marks payment verified. `/done ID` marks complete. `/reject ID` flags manual review.

Do not publish your bot token or `.env`; never ask users for seed phrases or private keys.
