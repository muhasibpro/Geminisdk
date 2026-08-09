#!/usr/bin/env python3
"""
Google TV Web Remote Server
Supports Android TV Remote Protocol v2 (TLS pairing with PIN code).
"""

import asyncio
import json
import logging
import os
import socket
import sys
from aiohttp import web
import ifaddr
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser

from androidtvremote2 import (
    AndroidTVRemote,
    CannotConnect,
    ConnectionClosed,
    InvalidAuth,
    certificate_generator,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gtv_remote")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERTS_DIR = os.path.join(BASE_DIR, "certs")
STATIC_DIR = os.path.join(BASE_DIR, "static")
CONFIG_FILE = os.path.join(BASE_DIR, "devices.json")

os.makedirs(CERTS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

CERT_PATH = os.path.join(CERTS_DIR, "cert.pem")
KEY_PATH = os.path.join(CERTS_DIR, "key.pem")

# Global State
active_remote = None  # Current AndroidTVRemote instance
current_ip = None
connection_status = "disconnected"  # disconnected, pairing, connected, error
last_error = None
device_info = {}

# Saved devices configuration
def load_saved_devices():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    return {"last_ip": "", "saved_devices": []}

def save_devices_config(data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving config: {e}")

# Ensure SSL Certificates exist
def ensure_certificates():
    if not os.path.exists(CERT_PATH) or not os.path.exists(KEY_PATH):
        logger.info("Generating new client TLS certificate and key...")
        cert_data, key_data = certificate_generator.generate_selfsigned_cert("Google TV Web Remote")
        mode = "wb" if isinstance(cert_data, bytes) else "w"
        with open(CERT_PATH, mode) as f:
            f.write(cert_data)
        with open(KEY_PATH, mode) as f:
            f.write(key_data)
        logger.info("TLS certificate generated successfully.")

# Get local network subnets for scanning
def get_local_subnets():
    subnets = []
    try:
        adapters = ifaddr.get_adapters()
        for adapter in adapters:
            for ip in adapter.ips:
                if isinstance(ip.ip, str) and not ip.ip.startswith("127.") and "." in ip.ip:
                    parts = ip.ip.split(".")
                    if len(parts) == 4:
                        subnets.append(".".join(parts[:3]))
    except Exception as e:
        logger.error(f"Subnet error: {e}")
    return list(set(subnets))

# Async port scanner for Google TV protocol ports (6467 / 6466)
async def scan_network_for_tvs():
    found_tvs = []
    subnets = get_local_subnets()
    if not subnets:
        subnets = ["192.168.1", "192.168.0", "10.0.0"]

    async def check_ip(ip):
        try:
            fut = asyncio.open_connection(ip, 6467)
            reader, writer = await asyncio.wait_for(fut, timeout=0.25)
            writer.close()
            await writer.wait_closed()
            return {"ip": ip, "name": f"Google TV ({ip})", "port": 6467}
        except Exception:
            try:
                fut = asyncio.open_connection(ip, 6466)
                reader, writer = await asyncio.wait_for(fut, timeout=0.25)
                writer.close()
                await writer.wait_closed()
                return {"ip": ip, "name": f"Google TV ({ip})", "port": 6466}
            except Exception:
                return None

    tasks = []
    for subnet in subnets:
        for i in range(1, 255):
            tasks.append(check_ip(f"{subnet}.{i}"))

    results = await asyncio.gather(*tasks)
    found_tvs = [r for r in results if r is not None]
    return found_tvs

# --- HTTP API Handlers ---

async def handle_index(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))

async def handle_get_status(request):
    global active_remote, current_ip, connection_status, last_error, device_info
    is_on = None
    curr_app = None
    vol = None
    if active_remote and connection_status == "connected":
        try:
            is_on = active_remote.is_on
            curr_app = active_remote.current_app
            vol = active_remote.volume_info
        except Exception:
            pass

    return web.json_response({
        "status": connection_status,
        "ip": current_ip,
        "error": last_error,
        "is_on": is_on,
        "current_app": curr_app,
        "volume": vol,
        "saved_config": load_saved_devices()
    })

async def handle_discover(request):
    logger.info("Discovering Google TVs on local network...")
    devices = await scan_network_for_tvs()
    return web.json_response({"devices": devices})

async def handle_pair_start(request):
    global active_remote, current_ip, connection_status, last_error
    ensure_certificates()
    try:
        body = await request.json()
        ip = body.get("ip", "").strip()
        if not ip:
            return web.json_response({"success": False, "error": "IP manzil kiritilmadi"}, status=400)

        current_ip = ip
        connection_status = "pairing"
        last_error = None

        if active_remote:
            try:
                active_remote.disconnect()
            except Exception:
                pass
            active_remote = None

        logger.info(f"Initiating Google TV remote connection/pairing with {ip}...")
        remote = AndroidTVRemote(
            "Google TV Web Remote",
            CERT_PATH,
            KEY_PATH,
            ip,
            api_port=6466,
            pair_port=6467,
            enable_ime=True
        )
        active_remote = remote

        # Try connecting first (if already paired)
        try:
            await remote.async_connect()
            connection_status = "connected"
            config = load_saved_devices()
            config["last_ip"] = ip
            if ip not in [d.get("ip") for d in config.get("saved_devices", [])]:
                config.get("saved_devices", []).append({"ip": ip, "name": f"Google TV ({ip})"})
            save_devices_config(config)

            return web.json_response({
                "success": True,
                "paired": True,
                "status": "connected",
                "message": "Televizorga muvaffaqiyatli ulandi!"
            })
        except (InvalidAuth, CannotConnect, ConnectionClosed) as auth_err:
            logger.info(f"Pairing required for {ip}. Starting pairing process...")
            # Request pairing pin code on TV screen
            await remote.async_start_pairing()
            return web.json_response({
                "success": True,
                "paired": False,
                "status": "pairing",
                "message": "Televizor ekranida 6 xonali PIN kod paydo bo'ldi. Kodni kiriting!"
            })

    except Exception as e:
        logger.error(f"Pairing start error: {e}", exc_info=True)
        connection_status = "error"
        last_error = str(e)
        return web.json_response({"success": False, "error": f"Ulanishda xatolik: {str(e)}"}, status=500)

async def handle_pair_finish(request):
    global active_remote, current_ip, connection_status, last_error
    try:
        body = await request.json()
        pin = body.get("pin", "").strip()
        if not pin:
            return web.json_response({"success": False, "error": "PIN kod kiritilmadi"}, status=400)

        if not active_remote:
            return web.json_response({"success": False, "error": "Avval ulanishni boshlang"}, status=400)

        logger.info(f"Finishing pairing with PIN: {pin}")
        await active_remote.async_finish_pairing(pin)
        logger.info("Pairing code accepted! Connecting to remote service...")
        
        # Connect after pairing
        await active_remote.async_connect()
        connection_status = "connected"
        last_error = None

        config = load_saved_devices()
        config["last_ip"] = current_ip
        if current_ip not in [d.get("ip") for d in config.get("saved_devices", [])]:
            config.get("saved_devices", []).append({"ip": current_ip, "name": f"Google TV ({current_ip})"})
        save_devices_config(config)

        return web.json_response({
            "success": True,
            "status": "connected",
            "message": "PIN kod tasdiqlandi! Televizor boshqaruvga tayyor."
        })

    except Exception as e:
        logger.error(f"Pairing finish error: {e}", exc_info=True)
        connection_status = "error"
        last_error = str(e)
        return web.json_response({"success": False, "error": f"PIN kodi xato yoki vaqti o'tdi: {str(e)}"}, status=400)

async def handle_remote_key(request):
    global active_remote, connection_status
    if not active_remote or connection_status != "connected":
        return web.json_response({"success": False, "error": "Televizorga ulanmagan"}, status=400)

    try:
        body = await request.json()
        key_code = body.get("key", "")
        direction = body.get("direction", "click") # click, press, release

        # Map common key aliases to androidtvremote2 RemoteKeyCode values
        key_map = {
            "UP": "DPAD_UP",
            "DOWN": "DPAD_DOWN",
            "LEFT": "DPAD_LEFT",
            "RIGHT": "DPAD_RIGHT",
            "OK": "DPAD_CENTER",
            "SELECT": "DPAD_CENTER",
            "ENTER": "DPAD_CENTER",
            "HOME": "HOME",
            "BACK": "BACK",
            "POWER": "POWER",
            "VOL_UP": "VOLUME_UP",
            "VOL_DOWN": "VOLUME_DOWN",
            "MUTE": "VOLUME_MUTE",
            "PLAY_PAUSE": "MEDIA_PLAY_PAUSE",
            "PLAY": "MEDIA_PLAY",
            "PAUSE": "MEDIA_PAUSE",
            "STOP": "MEDIA_STOP",
            "NEXT": "MEDIA_NEXT",
            "PREV": "MEDIA_PREVIOUS",
            "REWIND": "MEDIA_REWIND",
            "FAST_FORWARD": "MEDIA_FAST_FORWARD",
            "SETTINGS": "SETTINGS",
            "INFO": "INFO",
            "CH_UP": "CHANNEL_UP",
            "CH_DOWN": "CHANNEL_DOWN",
        }

        final_key = key_map.get(key_code.upper(), key_code.upper())
        dir_val = 3 if direction == "click" else (1 if direction == "press" else 2)

        logger.info(f"Sending key: {final_key}")
        active_remote.send_key_command(final_key, dir_val)
        return web.json_response({"success": True, "key": final_key})
    except Exception as e:
        logger.error(f"Send key error: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_remote_app(request):
    global active_remote, connection_status
    if not active_remote or connection_status != "connected":
        return web.json_response({"success": False, "error": "Televizorga ulanmagan"}, status=400)

    try:
        body = await request.json()
        app_name = body.get("app", "").lower()

        app_links = {
            "youtube": "https://www.youtube.com",
            "netflix": "https://www.netflix.com/title",
            "prime": "https://www.primevideo.com",
            "disney": "https://www.disneyplus.com",
            "spotify": "https://open.spotify.com",
            "twitch": "https://www.twitch.tv",
            "playstore": "https://play.google.com/store/apps",
            "settings": "android.settings.SETTINGS"
        }

        app_target = app_links.get(app_name, app_name)
        logger.info(f"Launching app: {app_name} -> {app_target}")
        active_remote.send_launch_app_command(app_target)
        return web.json_response({"success": True, "app": app_name})
    except Exception as e:
        logger.error(f"Send app error: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_remote_text(request):
    global active_remote, connection_status
    if not active_remote or connection_status != "connected":
        return web.json_response({"success": False, "error": "Televizorga ulanmagan"}, status=400)

    try:
        body = await request.json()
        text = body.get("text", "")
        if text:
            logger.info(f"Sending text to GTV: {text}")
            active_remote.send_text(text)
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Send text error: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_disconnect(request):
    global active_remote, connection_status, current_ip
    if active_remote:
        try:
            active_remote.disconnect()
        except Exception:
            pass
        active_remote = None
    connection_status = "disconnected"
    current_ip = None
    return web.json_response({"success": True})

# --- Server Setup ---

def create_app():
    ensure_certificates()
    app = web.Application()
    
    # Routes
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/status", handle_get_status)
    app.router.add_get("/api/discover", handle_discover)
    app.router.add_post("/api/pair/start", handle_pair_start)
    app.router.add_post("/api/pair/finish", handle_pair_finish)
    app.router.add_post("/api/remote/key", handle_remote_key)
    app.router.add_post("/api/remote/app", handle_remote_app)
    app.router.add_post("/api/remote/text", handle_remote_text)
    app.router.add_post("/api/disconnect", handle_disconnect)

    # Static assets
    app.router.add_static("/static", STATIC_DIR)
    return app

if __name__ == "__main__":
    port = 5050
    print("=" * 60)
    print(f" 🚀 Google TV Remote Web Controller tayyor!")
    print(f" 🌐 Brauzerda oching: http://localhost:{port}")
    print("=" * 60)
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=port)
