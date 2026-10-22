import os, json, time, hmac, hashlib, re, urllib.parse
from pathlib import Path
from collections import defaultdict, deque
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

BASE = Path(__file__).parent
LOG = BASE / "orders.jsonl"

# Зашитые данные для работы бота и отправки заказов
BOT_TOKEN = "8887560505:AA... [вставьте полный токен, если здесь сокращение, но я оставлю то что вы дали]" # замените на полный токен при необходимости, либо используем ваши данные:
BOT_TOKEN = "8887560505" # Вставьте сюда полный токен от BotFather (например: 8887560505:ABCdef...)
ADMIN_CHAT_ID = "8800476098"

# id: (название, цена, размеры) — должно совпадать с каталогом в index.html
CATALOG = {
    1: ("Футболка Basic", 129000, ["S", "M", "L", "XL"]),
    2: ("Футболка Oversize", 159000, ["M", "L", "XL"]),
    3: ("Худи Heavy", 329000, ["S", "M", "L", "XL"]),
    4: ("Худи на молнии", 359000, ["M", "L", "XL"]),
    5: ("Свитшот Crew", 279000, ["S", "M", "L"]),
    6: ("Джинсы Straight", 319000, ["30", "32", "34", "36"]),
    7: ("Карго Utility", 349000, ["30", "32", "34"]),
    8: ("Джоггеры Fleece", 239000, ["S", "M", "L", "XL"]),
    9: ("Куртка Windbreaker", 489000, ["M", "L", "XL"]),
    10: ("Пуховик Short", 699000, ["S", "M", "L"]),
    11: ("Кепка Logo", 89000, ["One"]),
    12: ("Шарф Wool", 119000, ["One"]),
}
PHONE = re.compile(r"^\+\d{11,15}$")
HITS = defaultdict(deque)
app = FastAPI(docs_url=None, redoc_url=None)


def money(n):
    return f"{n:,}".replace(",", " ") + " сум"


def bad(msg, code=400):
    return JSONResponse({"ok": False, "error": msg}, status_code=code)


def limited(ip):
    now, q = time.time(), HITS[ip]
    while q and now - q[0] > 600:
        q.popleft()
    if len(q) >= 5:
        return True
    q.append(now)
    return False


def check_init_data(raw):
    """Проверка подписи Telegram Mini App. Возвращает dict пользователя или None."""
    if not raw or not BOT_TOKEN:
        return None
    try:
        pairs = dict(urllib.parse.parse_qsl(raw, keep_blank_values=True))
        got = pairs.pop("hash", "")
        dcs = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, got):
            return None
        if time.time() - int(pairs.get("auth_date", "0")) > 86400:
            return None
        return json.loads(pairs.get("user", "{}"))
    except Exception:
        return None


@app.get("/")
def index():
    return FileResponse(BASE / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "configured": bool(BOT_TOKEN and ADMIN_CHAT_ID)}


@app.post("/api/order")
async def order(req: Request):
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        return bad("Сервер не настроен", 500)
    if limited(req.client.host if req.client else "?"):
        return bad("Слишком много заказов, попробуйте позже", 429)
    try:
        d = await req.json()
        name = str(d.get("name", "")).strip()[:60]
        phone = str(d.get("phone", "")).strip()
        items = d.get("items")
    except Exception:
        return bad("Неверный запрос")
    if len(name) < 2:
        return bad("Введите имя")
    if not PHONE.match(phone):
        return bad("Неверный номер телефона")
    if not isinstance(items, list) or not 0 < len(items) <= 30:
        return bad("Корзина пуста")
    lines, total = [], 0
    for it in items:
        try:
            pid, z, q = int(it["id"]), str(it["z"]), int(it["q"])
        except Exception:
            return bad("Неверный товар")
        p = CATALOG.get(pid)
        if not p or z not in p[2] or not 1 <= q <= 99:
            return bad("Неверный товар")
        total += p[1] * q
        lines.append(f"• {p[0]}, размер {z} × {q} = {money(p[1] * q)}")
    u = check_init_data(str(d.get("init_data", "")))
    if u:
        acc = "@" + u["username"] if u.get("username") else "ID " + str(u.get("id"))
        acc += " (подтверждён Telegram)"
    else:
        acc = (str(d.get("account", ""))[:60] or "не указан") + " (не подтверждён)"
    oid = (sum(1 for _ in LOG.open(encoding="utf-8")) + 1) if LOG.exists() else 1
    text = (f"🛍 Новый заказ №{oid}\n" + "\n".join(lines) + f"\n\nИтого: {money(total)}\n"
            f"Имя: {name}\nТелефон: {phone}\nTelegram: {acc}")
    with LOG.open("a", encoding="utf-8") as f:  # сначала сохраняем, потом отправляем
        f.write(json.dumps({"id": oid, "t": int(time.time()), "text": text}, ensure_ascii=False) + "\n")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                             json={"chat_id": ADMIN_CHAT_ID, "text": text})
        if r.status_code != 200:
            return bad("Не удалось отправить заказ", 502)
    except httpx.HTTPError:
        return bad("Не удалось отправить заказ", 502)
    return {"ok": True, "id": oid}
