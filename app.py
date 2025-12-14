from flask import Flask, render_template, jsonify, request, send_file, session
import json
import os
import subprocess
import tempfile
from urllib.parse import urlparse
import webbrowser
from threading import Timer
import requests
import time
import shutil
import re
import base64
import zipfile
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from collections import defaultdict
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Rate limiting for API endpoints
rate_limit_store = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # 60 seconds
RATE_LIMIT_MAX_REQUESTS = 10  # Max 10 requests per window

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_id = request.remote_addr
        now = time.time()
        
        # Clean old entries
        rate_limit_store[client_id] = [
            req_time for req_time in rate_limit_store[client_id]
            if now - req_time < RATE_LIMIT_WINDOW
        ]
        
        # Check rate limit
        if len(rate_limit_store[client_id]) >= RATE_LIMIT_MAX_REQUESTS:
            return jsonify({
                "error": "Rate limit exceeded. Please wait before making more requests."
            }), 429
        
        # Add current request
        rate_limit_store[client_id].append(now)
        
        return f(*args, **kwargs)
    return decorated_function

CREDENTIALS_FILE = 'steam_credentials.json'

def get_encryption_key():
    """Generate or retrieve encryption key for credentials"""
    key_file = 'encryption.key'
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

def encrypt_credentials(username, password):
    """Encrypt Steam credentials"""
    key = get_encryption_key()
    f = Fernet(key)
    encrypted_username = f.encrypt(username.encode())
    encrypted_password = f.encrypt(password.encode())
    return base64.b64encode(encrypted_username).decode(), base64.b64encode(encrypted_password).decode()

def decrypt_credentials(encrypted_username, encrypted_password):
    """Decrypt Steam credentials"""
    key = get_encryption_key()
    f = Fernet(key)
    username = f.decrypt(base64.b64decode(encrypted_username)).decode()
    password = f.decrypt(base64.b64decode(encrypted_password)).decode()
    return username, password

def save_credentials(username, password, profile_info=None):
    """Save encrypted credentials to file"""
    enc_user, enc_pass = encrypt_credentials(username, password)
    data = {
        'username': enc_user,
        'password': enc_pass,
        'timestamp': time.time()
    }
    if profile_info:
        data['profile_name'] = profile_info.get('profile_name', username)
        data['steamid'] = profile_info.get('steamid')
        data['avatar_url'] = profile_info.get('avatar_url')
    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump(data, f)

def load_credentials():
    """Load and decrypt credentials from file"""
    if not os.path.exists(CREDENTIALS_FILE):
        return None, None, None
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            data = json.load(f)
        username, password = decrypt_credentials(data['username'], data['password'])
        profile_info = {
            'username': username,
            'profile_name': data.get('profile_name', username),
            'steamid': data.get('steamid'),
            'avatar_url': data.get('avatar_url')
        }
        return username, password, profile_info
    except:
        return None, None, None

def clear_credentials():
    """Clear saved credentials"""
    if os.path.exists(CREDENTIALS_FILE):
        os.remove(CREDENTIALS_FILE)

def get_steam_avatar_url(steamid):
    """Get Steam profile avatar URL from SteamID"""
    if not steamid:
        return None
    
    try:
        url = f"https://steamcommunity.com/profiles/{steamid}/?xml=1"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            avatar_match = re.search(r'<avatarFull><!\[CDATA\[(.*?)\]\]></avatarFull>', response.text)
            if avatar_match:
                return avatar_match.group(1)
    except:
        pass
    
    return None

def get_steam_profile_info(username, password):
    """Get Steam profile information using SteamCMD"""
    steamcmd_path = find_steamcmd()
    if not steamcmd_path:
        return None
    
    try:
        cmd = [
            steamcmd_path,
            '+login', username, password,
            '+app_info_print', '1533390',
            '+quit'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        
        profile_info = {
            'username': username,
            'steamid': None,
            'profile_name': username,
            'avatar_url': None
        }
        
        steamid_match = re.search(r'SteamID:\s*(\d+)', output, re.IGNORECASE)
        if steamid_match:
            steamid = steamid_match.group(1)
            profile_info['steamid'] = steamid
            profile_info['avatar_url'] = get_steam_avatar_url(steamid)
        
        name_match = re.search(r'AccountName:\s*(\S+)', output, re.IGNORECASE)
        if name_match:
            profile_info['profile_name'] = name_match.group(1)
        
        return profile_info
    except:
        return {'username': username, 'steamid': None, 'profile_name': username, 'avatar_url': None}

def validate_steam_credentials(username, password):
    """Validate Steam credentials using SteamCMD"""
    steamcmd_path = find_steamcmd()
    if not steamcmd_path:
        profile_info = {'username': username, 'steamid': None, 'profile_name': username, 'avatar_url': None}
        return True, "Credentials saved (SteamCMD not available for validation, will be validated on download)", profile_info
    
    try:
        cmd = [
            steamcmd_path,
            '+login', username, password,
            '+quit'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        
        if any(term in output for term in ['Invalid Password', 'FAILED', 'LogonDenied', 'password is incorrect', 'Login Failure']):
            return False, "Invalid username or password", None
        
        if 'Steam Guard' in output or 'two-factor' in output.lower() or 'Two-factor' in output:
            return False, "Steam Guard code required. Please check your email or Steam Mobile app.", None
        
        if result.returncode == 0:
            profile_info = get_steam_profile_info(username, password)
            return True, "Credentials validated successfully", profile_info
        
        if 'OK' in output or 'Success' in output or 'Logged in' in output:
            profile_info = get_steam_profile_info(username, password)
            return True, "Credentials validated successfully", profile_info
        
        if 'No subscription' in output or 'subscription' in output.lower():
            profile_info = get_steam_profile_info(username, password)
            return True, "Credentials valid (account may not own Gorilla Tag)", profile_info
        
        profile_info = get_steam_profile_info(username, password)
        return True, "Credentials validated", profile_info
    except subprocess.TimeoutExpired:
        return False, "Validation timeout. Please try again.", None
    except Exception as e:
        return False, f"Validation error: {str(e)}", None

SIZES_CACHE_FILE = 'depot_sizes_cache.json'

def load_size_cache():
    """Load cached depot sizes from file"""
    if os.path.exists(SIZES_CACHE_FILE):
        try:
            with open(SIZES_CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_size_cache(cache):
    """Save depot sizes cache to file"""
    try:
        with open(SIZES_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except:
        pass

def format_size(size_bytes):
    """Format bytes to human readable size"""
    if size_bytes is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def download_steamcmd():
    """Auto-download SteamCMD if not found"""
    steamcmd_dir = "steamcmd"
    steamcmd_path = os.path.join(steamcmd_dir, "steamcmd.exe")
    
    if os.path.exists(steamcmd_path):
        return steamcmd_path
    
    try:
        if not os.path.exists(steamcmd_dir):
            os.makedirs(steamcmd_dir)
        
        zip_path = os.path.join(steamcmd_dir, "steamcmd.zip")
        url = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
        
        print("Downloading SteamCMD...")
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(steamcmd_dir)
            
            if os.path.exists(zip_path):
                os.remove(zip_path)
            
            if os.path.exists(steamcmd_path):
                print("SteamCMD downloaded successfully!")
                return steamcmd_path
    except Exception as e:
        print(f"Error downloading SteamCMD: {e}")
    
    return None

def find_steamcmd():
    possible_paths = [
        "steamcmd.exe",
        "steamcmd\\steamcmd.exe",
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam", "steamcmd.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Steam", "steamcmd.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Steam", "steamcmd.exe"),
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            return path
    
    try:
        result = subprocess.run(['where', 'steamcmd.exe'], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    
    downloaded = download_steamcmd()
    if downloaded:
        return downloaded
    
    return None

def get_depot_size_from_steamcmd(depot_id, app_id=1533390, depot_number=1533391):
    """Get depot size using SteamCMD by parsing download output"""
    steamcmd_path = find_steamcmd()
    if not steamcmd_path:
        return None
    
    try:
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Run SteamCMD to download depot
            # SteamCMD shows size information in its output
            cmd = [
                steamcmd_path,
                '+force_install_dir', temp_dir,
                '+login', 'anonymous',
                '+download_depot', str(app_id), str(depot_number), str(depot_id),
                '+quit'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            # Try to parse size from SteamCMD output
            output = result.stdout + result.stderr
            
            # Look for size patterns in output (e.g., "Downloading depot X (Y bytes)")
            # SteamCMD output format varies, so try multiple patterns
            size_patterns = [
                r'(\d+)\s*bytes',
                r'(\d+)\s*MB',
                r'(\d+)\s*KB',
                r'Size:\s*(\d+)',
                r'depot.*?(\d+)\s*bytes',
            ]
            
            for pattern in size_patterns:
                matches = re.findall(pattern, output, re.IGNORECASE)
                if matches:
                    # Try to find the largest number (likely the total size)
                    sizes = [int(m.replace(',', '')) for m in matches if m.replace(',', '').isdigit()]
                    if sizes:
                        # If we found sizes in bytes, return the largest
                        # If in MB/KB, convert to bytes
                        max_size = max(sizes)
                        # Check if it's a reasonable depot size (between 1MB and 50GB)
                        if 1048576 <= max_size <= 53687091200:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            return max_size
            
            # If parsing output didn't work, calculate from downloaded files
            depot_path = os.path.join(temp_dir, 'steamapps', 'content', f'app_{app_id}', f'depot_{depot_number}')
            
            if os.path.exists(depot_path):
                total_size = 0
                for root, dirs, files in os.walk(depot_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            total_size += os.path.getsize(file_path)
                        except:
                            pass
                
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                if total_size > 0:
                    return total_size
            
            # Clean up
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        except subprocess.TimeoutExpired:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"Error getting depot size: {e}")
        
        return None
    except Exception as e:
        print(f"Error querying SteamCMD: {e}")
        return None

def get_depot_size_from_manifest(depot_id, app_id=1533390, depot_number=1533391):
    """Get depot size by querying Steam's manifest CDN"""
    try:
        # Try to get manifest info from Steam's CDN
        # Steam stores manifests but accessing them directly is complex
        # For now, rely on SteamCMD method
        return None
    except Exception as e:
        print(f"Error getting manifest size: {e}")
        return None

def get_depot_size_from_api(depot_id, app_id=1533390, depot_number=1533391):
    """Get depot size using Steam Web API (fallback method)"""
    try:
        # Steam's public API doesn't provide depot sizes directly
        # This is a placeholder for future API integration
        # For now, return None and rely on SteamCMD method
        return None
    except Exception as e:
        print(f"Error querying for depot size: {e}")
        return None

def get_depot_size(depot_id, app_id=1533390, depot_number=1533391):
    """Get depot size using SteamCMD (primary method)"""
    cache = load_size_cache()
    
    # Check cache first
    if depot_id in cache:
        cached_data = cache[depot_id]
        # Cache valid for 30 days (sizes don't change often)
        if time.time() - cached_data.get('timestamp', 0) < 2592000:
            cached_size = cached_data.get('size')
            if cached_size is not None:
                return cached_size
    
    size = None
    
    # Try SteamCMD first (most reliable method)
    steamcmd_size = get_depot_size_from_steamcmd(depot_id, app_id, depot_number)
    if steamcmd_size:
        size = steamcmd_size
    else:
        # Fallback to API method (though it likely won't work)
        api_size = get_depot_size_from_api(depot_id, app_id, depot_number)
        if api_size:
            size = api_size
    
    # Cache the result (even if None, but with shorter expiry)
    cache[depot_id] = {
        'size': size,
        'timestamp': time.time()
    }
    save_size_cache(cache)
    
    return size

@app.route('/api/depot_size/<depot_id>')
@rate_limit
def api_depot_size(depot_id):
    """API endpoint to get depot size"""
    cache = load_size_cache()
    
    if depot_id in cache:
        cached_data = cache[depot_id]
        if time.time() - cached_data.get('timestamp', 0) < 2592000:
            size = cached_data.get('size')
            return jsonify({
                'depot_id': depot_id,
                'size': size,
                'formatted_size': format_size(size)
            })
    
    return jsonify({
        'depot_id': depot_id,
        'size': None,
        'formatted_size': 'Calculating...'
    })

@app.route('/api/update_depot_size', methods=['POST'])
def api_update_depot_size():
    """Update depot size after download"""
    data = request.json
    depot_id = data.get('depot_id')
    size = data.get('size')
    
    if not depot_id or not size:
        return jsonify({"error": "depot_id and size are required"}), 400
    
    try:
        size = int(size)
        cache = load_size_cache()
        cache[depot_id] = {
            'size': size,
            'timestamp': time.time()
        }
        save_size_cache(cache)
        return jsonify({
            "success": True,
            "depot_id": depot_id,
            "formatted_size": format_size(size)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/update_sizes')
@rate_limit
def api_update_sizes():
    """Get sizes for all Steam depots"""
    sizes = {}
    cache = load_size_cache()
    
    for year, updates in UPDATES_DATA.items():
        for update in updates:
            if update.get('type') == 'steam' and 'depot' in update:
                depot_id = update['depot']
                if depot_id in cache:
                    cached_data = cache[depot_id]
                    if time.time() - cached_data.get('timestamp', 0) < 2592000:
                        sizes[depot_id] = format_size(cache[depot_id].get('size'))
                    else:
                        sizes[depot_id] = "Calculating..."
                else:
                    sizes[depot_id] = "Calculating..."
    
    return jsonify(sizes)

UPDATES_DATA = {
    "2021": [
        {"name": "OLDEST GTAG VERSION PC", "link": "https://drive.google.com/file/d/18-mttlNI8M9BgMLNRLO10BYpopxYFnhI/view", "type": "drive"},
        {"name": "JAN 29 2020", "link": "https://drive.google.com/file/d/1acnOAOSe4gftl73qdGYntkKt1bWozTri/view?usp=sharing", "type": "drive"},
        {"name": "GORILLA LOCOMOTOION FEB 2020", "link": "https://drive.google.com/file/d/1aeAvpU0e-hAJHqRaBFtB0AE-M1SikioN/view?usp=sharing", "type": "drive"},
        {"name": "GORILLA TEST FEBUARY FEB 2020", "link": "https://drive.google.com/file/d/1RrBCiYsEcIndCpukqz9ni6aDe9a48xhh/view?usp=sharing", "type": "drive"},
        {"name": "MULTIPLAYER INTRODUCED", "link": "https://cdn.discordapp.com/attachments/671857084291219505/714739535338274846/GorillaTagMay25final.zip?ex=66957650&is=669424d0&hm=7beaf458284e168dc861ff4f2ec6b16d57b5fca4068f8b91a6b45b53f2ab6550&", "type": "direct"},
        {"name": "REFINED MOVEMENT", "link": "https://cdn.discordapp.com/attachments/671857084291219505/715295797197144074/GorillaTagMay26Final.apk?ex=6695821f&is=6694309f&hm=716df5b4396c5239ed5b14e2f338883bf269792747d902ce88bea5506c471e3b&", "type": "direct"},
        {"name": "GTAG STEAM RELEASE (2021)", "depot": "8480223242740007278", "type": "steam"},
        {"name": "HAT ROOM COSMETICS RELEASE", "depot": "5830392302374695549", "type": "steam"},
        {"name": "SLIPPERY WALLS INTRODUCED", "depot": "7345723381055924397", "type": "steam"},
        {"name": "CANYON RELEASE", "depot": "2519821153393002943", "type": "steam"},
        {"name": "HITSOUND UPDATE", "depot": "1831142320395008381", "type": "steam"},
        {"name": "FOREST MUSIC", "depot": "8786485081868183496", "type": "steam"},
        {"name": "CITY RELEASE", "depot": "8486188048224112520", "type": "steam"},
        {"name": "HALLOWEEN 2021", "depot": "8773026304241958081", "type": "steam"},
        {"name": "FALL 2021", "depot": "6068761472691252176", "type": "steam"},
        {"name": "QUEST SUPPORTER PACK RELEASE", "depot": "2952807174378250716", "type": "steam"},
        {"name": "CHRISTMAS 2021", "depot": "1790232358016968157", "type": "steam"},
        {"name": "HUNT RELEASE", "depot": "977662270706390562", "type": "steam"},
    ],
    "2022": [
        {"name": "WINTER 2022", "depot": "8111326296022235960", "type": "steam"},
        {"name": "VALENTINES 2022", "depot": "3402940780410030277", "type": "steam"},
        {"name": "GT1", "depot": "3644302578111614762", "type": "steam"},
        {"name": "HOUSE 2022", "depot": "7171810605217611623", "type": "steam"},
        {"name": "MOUNTAINS RELEASE", "depot": "9222093099666950138", "type": "steam"},
        {"name": "COMP COURSE RELEASE", "depot": "2472938543210547501", "type": "steam"},
        {"name": "SPRING 2022", "depot": "3587467932664632345", "type": "steam"},
        {"name": "APRIL FOOLS 2022", "depot": "3335121328833824494", "type": "steam"},
        {"name": "RAINY 2022", "depot": "3231295228942758020", "type": "steam"},
        {"name": "MUSIC 2022", "depot": "2283373238264001065", "type": "steam"},
        {"name": "SUMMER 2022", "depot": "6212573569393666544", "type": "steam"},
        {"name": "PAINTBRAWL RELEASE AND UPDATE 2022", "depot": "974246606874981992", "type": "steam"},
        {"name": "HALLOWEEN 2022", "depot": "6724256960126827536", "type": "steam"},
        {"name": "HALLOWEEN 2021 FLASHBACK", "depot": "5179014763499843236", "type": "steam"},
        {"name": "FALL 2022", "depot": "2826399377161966619", "type": "steam"},
        {"name": "FALL 2021 FLASHBACK", "depot": "7858704770131804870", "type": "steam"},
        {"name": "LAUNCH DAY", "depot": "9211530748056500720", "type": "steam"},
        {"name": "CHRISTMAS 2022", "depot": "7846756673248360873", "type": "steam"},
        {"name": "CHRISTMAS 2021 FLASHBACK", "depot": "5272615492296865291", "type": "steam"},
    ],
    "2023": [
        {"name": "JAN WINTER 2023", "depot": "1024065649513604747", "type": "steam"},
        {"name": "GT2", "depot": "8226996632576406070", "type": "steam"},
        {"name": "FEB WINTER 2023", "depot": "4849975928796061895", "type": "steam"},
        {"name": "WINTER 2022 FLASH BACK", "depot": "5234510482746716599", "type": "steam"},
        {"name": "BASEMENT 2023", "depot": "2836752869553824621", "type": "steam"},
        {"name": "EARLY SPRING 2022 FLASHBACK", "depot": "8953216585901271401", "type": "steam"},
        {"name": "SPRING 2023", "depot": "5487763777743744746", "type": "steam"},
        {"name": "CANYONS REVAMP/HOUSEHOLD FLASHBACK", "depot": "5296372619910715608", "type": "steam"},
        {"name": "SUMMER SPLASH 2023/BEACH RELEASE", "depot": "6583276257667612942", "type": "steam"},
        {"name": "RAINY FLASHBACK", "depot": "3197800337588223997", "type": "steam"},
        {"name": "MUSIC 2022 FLASHBACK", "depot": "5909999775995420795", "type": "steam"},
        {"name": "SUMMER CELEBRATION 2023", "depot": "1161533665635074987", "type": "steam"},
        {"name": "SUMMER 2022 FLASHBACK", "depot": "4598513446787189059", "type": "steam"},
        {"name": "CAVES REVAMP", "depot": "4517667507007620373", "type": "steam"},
        {"name": "PAINTBRAWL FLASH BACK", "depot": "910642836555163397", "type": "steam"},
        {"name": "BACK TO SCHOOL", "depot": "5178239895382560605", "type": "steam"},
        {"name": "LAUNCH DAY FLASHBACK", "depot": "4429018437186357961", "type": "steam"},
        {"name": "FOREST LAVA", "depot": "7879805303656311610", "type": "steam"},
        {"name": "#WEAREVR COSMETICS", "depot": "3030091361693161265", "type": "steam"},
        {"name": "HALLOWEEN 2023", "depot": "6155112443238526399", "type": "steam"},
        {"name": "HALLOWEEN 2022+2021 FLASHBACK", "depot": "633386999691306534", "type": "steam"},
        {"name": "FALL 2023", "depot": "3182699544820941765", "type": "steam"},
        {"name": "FALL 2022+2021 FLASHBACK", "depot": "413034153916417182", "type": "steam"},
        {"name": "CHRISTMAS 2023", "depot": "7362717951501930919", "type": "steam"},
        {"name": "CHRISTMAS 2022 FLASHBACK", "depot": "5702136978519485499", "type": "steam"},
        {"name": "CHRISTMAS 2021 FLASH BACK", "depot": "2378291872476521279", "type": "steam"},
    ],
    "2024": [
        {"name": "SCIENCE 2024", "depot": "352194209707137278", "type": "steam"},
        {"name": "WINTER FLASHBACK", "depot": "3028185287726525781", "type": "steam"},
        {"name": "I LAVA YOU (VALENTINES) 2024", "depot": "1372005950454291233", "type": "steam"},
        {"name": "VALENTINES FLASHABCK", "depot": "8167245949716432329", "type": "steam"},
        {"name": "NOWRUZ 2024", "depot": "2240085398563766746", "type": "steam"},
        {"name": "SPRING FLASHBACK", "depot": "916527175228470509", "type": "steam"},
        {"name": "CLOUDS REVAMP", "depot": "2012969860441050604", "type": "steam"},
        {"name": "APRIL SHOWERS", "depot": "8527275474402577505", "type": "steam"},
        {"name": "MAZES AND MONKEYS", "depot": "674120886711990235", "type": "steam"},
        {"name": "MEDIVAL MELODIES FLASHBACK", "depot": "2588790404729352981", "type": "steam"},
        {"name": "PRIDE JAM", "depot": "8529762468897318010", "type": "steam"},
        {"name": "WET N WILD WEST", "depot": "8322576807180634055", "type": "steam"},
        {"name": "METROPOLIS", "depot": "8612738834665184533", "type": "steam"},
        {"name": "METROPOLIS FLASHBACK", "depot": "7850954751661121894", "type": "steam"},
        {"name": "CANT SEA ME", "depot": "3448609575458502088", "type": "steam"},
        {"name": "CAVES REVAMP FLASHBACK", "depot": "3071126083813386889", "type": "steam"},
        {"name": "ARCADE UPDATE", "depot": "3313958184175746550", "type": "steam"},
        {"name": "ARCADE FIXXED", "depot": "872909814478720200", "type": "steam"},
        {"name": "SCHOOL SPIRT FLASHBACK", "depot": "8146295576575697770", "type": "steam"},
        {"name": "BAYOU BOOGIE", "depot": "3935186219455191051", "type": "steam"},
        {"name": "WAXING GIBBONS/HALLOWEEN 2024", "depot": "2154055295465731703", "type": "steam"},
        {"name": "MOONKE MADNESS/HALLOWEEN 2024 FLASHBACK", "depot": "909211820069127157", "type": "steam"},
        {"name": "MONKE BLOCKS", "depot": "1109136838068279011", "type": "steam"},
        {"name": "HOLIDAY UPDATE", "depot": "5305547345255411805", "type": "steam"},
        {"name": "HOLIDAY UPDATE FIXXED", "depot": "6584850097575841067", "type": "steam"},
    ],
    "2025": [
        {"name": "SNOWBALL FIGHT", "depot": "1367215994416166011", "type": "steam"},
        {"name": "MONKE BIZ", "depot": "8125101906352587258", "type": "steam"},
        {"name": "HOVERBOARD UPDATE", "depot": "7557306701998880810", "type": "steam"},
        {"name": "HOVERBOARD UPDATE FIXXED", "depot": "4014145989704722349", "type": "steam"},
        {"name": "MONKE BLOCKS PLATFORMING UPDATE", "depot": "2777016323909696400", "type": "steam"},
        {"name": "CRITTERS UPDATE", "depot": "2016622786773439965", "type": "steam"},
        {"name": "CRITTERS FIXXED", "depot": "3910221862130980014", "type": "steam"},
        {"name": "EGGY CRITTERS", "depot": "2165851274764079687", "type": "steam"},
        {"name": "GHOST REACTOR", "depot": "6362658578435958263", "type": "steam"},
        {"name": "SHARE MY BLOCKS", "depot": "25233329490798591", "type": "steam"},
        {"name": "☢️ Ghost Reactor Update: SYSTEM ESCALATION DETECTED 👻", "depot": "3356080249422329161", "type": "steam"},
        {"name": "PROP HAUNT", "depot": "2563509527335067888", "type": "steam"},
        {"name": "PROP HAUNT FIXXED", "depot": "7415758057019556819", "type": "steam"},
        {"name": "CREATOR FEST", "depot": "589416171898258913", "type": "steam"},
        {"name": "CREATOR FEST FIXXED", "depot": "2299045476431056353", "type": "steam"},
        {"name": "RANKED MODE", "depot": "3043321800655748912", "type": "steam"},
        {"name": "TAKE MY HAND", "depot": "6335800595095137011", "type": "steam"},
        {"name": "KITE FEST", "depot": "4896186935762350060", "type": "steam"},
        {"name": "HEAT WAVE", "depot": "8003541390110438090", "type": "steam"},
    ]
}

@app.route('/')
def index():
    # Check if user has saved credentials
    username, _, profile_info = load_credentials()
    logged_in = username is not None
    profile_name = profile_info.get('profile_name', username) if profile_info else username
    steamid = profile_info.get('steamid') if profile_info else None
    avatar_url = profile_info.get('avatar_url') if profile_info else None
    
    if steamid and not avatar_url:
        avatar_url = get_steam_avatar_url(steamid)
        if avatar_url and profile_info:
            profile_info['avatar_url'] = avatar_url
            try:
                with open(CREDENTIALS_FILE, 'r') as f:
                    data = json.load(f)
                data['avatar_url'] = avatar_url
                with open(CREDENTIALS_FILE, 'w') as f:
                    json.dump(data, f)
            except:
                pass
    
    return render_template('index.html', updates=UPDATES_DATA, logged_in=logged_in, username=username, profile_name=profile_name, steamid=steamid, avatar_url=avatar_url)

@app.route('/api/login', methods=['POST'])
def api_login():
    """Handle Steam login with validation"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    
    is_valid, message, profile_info = validate_steam_credentials(username, password)
    
    if not is_valid:
        return jsonify({"error": message}), 400
    
    save_credentials(username, password, profile_info)
    session['steam_logged_in'] = True
    session['steam_username'] = username
    if profile_info:
        session['steam_profile_name'] = profile_info.get('profile_name', username)
        session['steam_id'] = profile_info.get('steamid')
    
    return jsonify({
        "success": True, 
        "username": username,
        "profile_name": profile_info.get('profile_name', username) if profile_info else username,
        "steamid": profile_info.get('steamid') if profile_info else None,
        "avatar_url": profile_info.get('avatar_url') if profile_info else None,
        "message": message
    })

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Handle logout"""
    clear_credentials()
    session.pop('steam_logged_in', None)
    session.pop('steam_username', None)
    return jsonify({"success": True})

@app.route('/api/profile')
def api_profile():
    """Get current profile info"""
    username, _, profile_info = load_credentials()
    if username and profile_info:
        steamid = profile_info.get('steamid')
        avatar_url = profile_info.get('avatar_url')
        if steamid and not avatar_url:
            avatar_url = get_steam_avatar_url(steamid)
            if avatar_url:
                profile_info['avatar_url'] = avatar_url
                try:
                    with open(CREDENTIALS_FILE, 'r') as f:
                        data = json.load(f)
                    data['avatar_url'] = avatar_url
                    with open(CREDENTIALS_FILE, 'w') as f:
                        json.dump(data, f)
                except:
                    pass
        return jsonify({
            "logged_in": True,
            "username": username,
            "profile_name": profile_info.get('profile_name', username),
            "steamid": steamid,
            "avatar_url": avatar_url
        })
    return jsonify({
        "logged_in": False,
        "username": None
    })

@app.route('/download/<year>/<int:index>')
def download_update(year, index):
    """Handle download requests"""
    if year not in UPDATES_DATA or index >= len(UPDATES_DATA[year]):
        return jsonify({"error": "Update not found"}), 404
    
    update = UPDATES_DATA[year][index]
    
    if update["type"] == "steam":
        username, password, _ = load_credentials()
        depot_id = update["depot"]
        
        steamcmd_setup = """REM Try to find steamcmd.exe in common locations
set STEAMCMD_PATH=
if exist "steamcmd.exe" set STEAMCMD_PATH=steamcmd.exe
if exist "steamcmd\\steamcmd.exe" set STEAMCMD_PATH=steamcmd\\steamcmd.exe
if exist "%ProgramFiles(x86)%\\Steam\\steamcmd.exe" set STEAMCMD_PATH=%ProgramFiles(x86)%\\Steam\\steamcmd.exe
if exist "%ProgramFiles%\\Steam\\steamcmd.exe" set STEAMCMD_PATH=%ProgramFiles%\\Steam\\steamcmd.exe
if exist "%LOCALAPPDATA%\\Steam\\steamcmd.exe" set STEAMCMD_PATH=%LOCALAPPDATA%\\Steam\\steamcmd.exe

REM Check if steamcmd is in PATH
where steamcmd.exe >nul 2>&1
if !errorlevel! equ 0 set STEAMCMD_PATH=steamcmd.exe

REM If SteamCMD not found, download it automatically
if "!STEAMCMD_PATH!"=="" (
    echo.
    echo SteamCMD not found. Downloading automatically...
    echo.
    
    REM Create steamcmd directory if it doesn't exist
    if not exist "steamcmd" mkdir steamcmd
    
    REM Download SteamCMD using PowerShell
    powershell -Command "& {$ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip' -OutFile 'steamcmd\\steamcmd.zip'}"
    
    if !errorlevel! neq 0 (
        echo.
        echo ERROR: Failed to download SteamCMD!
        echo.
        echo Please manually download SteamCMD from:
        echo https://developer.valvesoftware.com/wiki/SteamCMD
        echo.
        echo Extract it to a folder named "steamcmd" in the same directory as this script.
        echo.
        pause
        exit /b 1
    )
    
    echo Extracting SteamCMD...
    powershell -Command "Expand-Archive -Path 'steamcmd\\steamcmd.zip' -DestinationPath 'steamcmd' -Force"
    
    if !errorlevel! neq 0 (
        echo.
        echo ERROR: Failed to extract SteamCMD!
        echo.
        echo Please manually extract steamcmd.zip to the steamcmd folder.
        echo.
        pause
        exit /b 1
    )
    
    REM Clean up zip file
    if exist "steamcmd\\steamcmd.zip" del "steamcmd\\steamcmd.zip"
    
    REM Check if steamcmd.exe now exists
    if exist "steamcmd\\steamcmd.exe" (
        set STEAMCMD_PATH=steamcmd\\steamcmd.exe
        echo.
        echo SteamCMD downloaded and extracted successfully!
        echo.
    ) else (
        echo.
        echo ERROR: SteamCMD extraction failed or steamcmd.exe not found!
        echo.
        echo Please manually download and extract SteamCMD from:
        echo https://developer.valvesoftware.com/wiki/SteamCMD
        echo.
        pause
        exit /b 1
    )
)"""
        
        if username and password:
            script_content = f"""@echo off
setlocal enabledelayedexpansion

{steamcmd_setup}

echo.
echo ========================================
echo Downloading: {update['name']}
echo Depot ID: {depot_id}
echo ========================================
echo.
echo Using saved Steam credentials for: {username}
echo.
echo Attempting to login to Steam...
echo (If you have Steam Guard enabled, you may need to enter a code)
echo.

REM Try to login and download using saved credentials
"!STEAMCMD_PATH!" +login "{username}" "{password}" +download_depot 1533390 1533391 {depot_id} +quit

set DOWNLOAD_SUCCESS=0
if !errorlevel! equ 0 (
    set DOWNLOAD_SUCCESS=1
)

if !DOWNLOAD_SUCCESS! equ 0 (
    echo.
    echo ========================================
    echo DOWNLOAD FAILED!
    echo ========================================
    echo.
    echo Possible reasons:
    echo - Incorrect username or password
    echo - Steam Guard code required (check email/Steam Mobile app)
    echo   If Steam Guard is enabled, you may need to run SteamCMD interactively
    echo - Account doesn't own Gorilla Tag on Steam
    echo - Account is restricted or banned
    echo - Network connection issues
    echo.
    echo TIP: Update your credentials in the Profile section if they are incorrect.
    echo.
    echo Would you like to try with different credentials? (Y/N)
    set /p RETRY="Enter Y to retry with manual credentials, N to exit: "
    if /i "!RETRY!"=="Y" goto :manual_login
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo DOWNLOAD COMPLETE!
    echo ========================================
    echo.
    echo The depot has been downloaded successfully!
    echo.
    echo Location: steamapps\\content\\app_1533390\\depot_1533391\\
    echo.
    echo Calculating depot size and updating server...
    
    REM Calculate depot size
    set DEPOT_SIZE=0
    set DEPOT_PATH=steamapps\\content\\app_1533390\\depot_1533391
    
    if exist "!DEPOT_PATH!" (
        for /r "!DEPOT_PATH!" %%f in (*) do (
            set /a DEPOT_SIZE+=%%~zf
        )
    )
    
    REM Report size back to server
    if !DEPOT_SIZE! gtr 0 (
        echo Reporting size to server: !DEPOT_SIZE! bytes
        powershell -Command "$ProgressPreference = 'SilentlyContinue'; $body = @{{depot_id='{depot_id}'; size=!DEPOT_SIZE!}} | ConvertTo-Json; Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/update_depot_size' -Method POST -Body $body -ContentType 'application/json' -ErrorAction SilentlyContinue"
    )
    
    echo.
    echo You can find the files in the directory where this script is located.
    echo.
)
goto :end

:manual_login
echo.
echo Please enter your Steam credentials manually:
echo.
set /p MANUAL_USERNAME="Steam Username: "
if "!MANUAL_USERNAME!"=="" (
    echo ERROR: Username cannot be empty!
    pause
    exit /b 1
)

echo.
set /p MANUAL_PASSWORD="Steam Password: "
if "!MANUAL_PASSWORD!"=="" (
    echo ERROR: Password cannot be empty!
    pause
    exit /b 1
)

echo.
echo Attempting to login with manual credentials...
"!STEAMCMD_PATH!" +login "!MANUAL_USERNAME!" "!MANUAL_PASSWORD!" +download_depot 1533390 1533391 {depot_id} +quit

set MANUAL_SUCCESS=0
if !errorlevel! equ 0 (
    set MANUAL_SUCCESS=1
)

set MANUAL_PASSWORD=

if !MANUAL_SUCCESS! equ 0 (
    echo.
    echo Manual login failed. Please check your credentials.
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo DOWNLOAD COMPLETE!
    echo ========================================
    echo.
    echo The depot has been downloaded successfully!
    echo.
    echo Location: steamapps\\content\\app_1533390\\depot_1533391\\
    echo.
    echo Calculating depot size and updating server...
    
    REM Calculate depot size
    set DEPOT_SIZE=0
    set DEPOT_PATH=steamapps\\content\\app_1533390\\depot_1533391
    
    if exist "!DEPOT_PATH!" (
        for /r "!DEPOT_PATH!" %%f in (*) do (
            set /a DEPOT_SIZE+=%%~zf
        )
    )
    
    REM Report size back to server
    if !DEPOT_SIZE! gtr 0 (
        echo Reporting size to server: !DEPOT_SIZE! bytes
        powershell -Command "$ProgressPreference = 'SilentlyContinue'; $body = @{{depot_id='{depot_id}'; size=!DEPOT_SIZE!}} | ConvertTo-Json; Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/update_depot_size' -Method POST -Body $body -ContentType 'application/json' -ErrorAction SilentlyContinue"
    )
    echo.
)
goto :end

:end
echo.
pause
"""
        else:
            script_content = f"""@echo off
setlocal enabledelayedexpansion

{steamcmd_setup}

echo.
echo ========================================
echo Downloading: {update['name']}
echo Depot ID: {depot_id}
echo ========================================
echo.
echo NOTE: No saved Steam credentials found (Guest Account Mode)
echo.
echo You need to enter your Steam credentials to download this depot.
echo You must own Gorilla Tag on your Steam account.
echo.
echo TIP: Login in the Profile section on the website to save credentials
echo      for future downloads and avoid entering them each time.
echo.
echo ========================================
echo Please enter your Steam credentials:
echo ========================================
echo.
set /p STEAM_USERNAME="Steam Username: "
if "!STEAM_USERNAME!"=="" (
    echo.
    echo ERROR: Username cannot be empty!
    echo.
    pause
    exit /b 1
)

echo.
set /p STEAM_PASSWORD="Steam Password: "
if "!STEAM_PASSWORD!"=="" (
    echo.
    echo ERROR: Password cannot be empty!
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Attempting to login to Steam...
echo ========================================
echo.
echo If you have Steam Guard enabled, you may need to enter a code.
echo Check your email or Steam Mobile app for the authentication code.
echo.

REM Try to login and download
"!STEAMCMD_PATH!" +login "!STEAM_USERNAME!" "!STEAM_PASSWORD!" +download_depot 1533390 1533391 {depot_id} +quit

set DOWNLOAD_SUCCESS=0
if !errorlevel! equ 0 (
    set DOWNLOAD_SUCCESS=1
)

REM Clear password from memory (as much as possible in batch)
set STEAM_PASSWORD=

if !DOWNLOAD_SUCCESS! equ 0 (
    echo.
    echo ========================================
    echo DOWNLOAD FAILED!
    echo ========================================
    echo.
    echo Possible reasons:
    echo - Incorrect username or password
    echo - Steam Guard code required (check email/Steam Mobile app)
    echo   If Steam Guard is enabled, you may need to run SteamCMD interactively
    echo - Account doesn't own Gorilla Tag on Steam
    echo - Account is restricted or banned
    echo - Network connection issues
    echo.
    echo ========================================
    echo TIPS:
    echo ========================================
    echo 1. Login in the Profile section on the website to save credentials
    echo 2. Make sure you own Gorilla Tag on your Steam account
    echo 3. If Steam Guard is enabled, check your email/Steam Mobile app
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo DOWNLOAD COMPLETE!
    echo ========================================
    echo.
    echo The depot has been downloaded successfully!
    echo.
    echo Location: steamapps\\content\\app_1533390\\depot_1533391\\
    echo.
    echo Calculating depot size and updating server...
    
    REM Calculate depot size
    set DEPOT_SIZE=0
    set DEPOT_PATH=steamapps\\content\\app_1533390\\depot_1533391
    
    if exist "!DEPOT_PATH!" (
        for /r "!DEPOT_PATH!" %%f in (*) do (
            set /a DEPOT_SIZE+=%%~zf
        )
    )
    
    REM Report size back to server
    if !DEPOT_SIZE! gtr 0 (
        echo Reporting size to server: !DEPOT_SIZE! bytes
        powershell -Command "$ProgressPreference = 'SilentlyContinue'; $body = @{{depot_id='{depot_id}'; size=!DEPOT_SIZE!}} | ConvertTo-Json; Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/update_depot_size' -Method POST -Body $body -ContentType 'application/json' -ErrorAction SilentlyContinue"
    )
    
    echo.
    echo You can find the files in the directory where this script is located.
    echo.
    echo TIP: Login in the Profile section on the website to save your
    echo      credentials and avoid entering them each time.
    echo.
)
echo.
pause
"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False, encoding='utf-8')
        temp_file.write(script_content)
        temp_file.close()
        return send_file(temp_file.name, as_attachment=True, download_name=f"{update['name'].replace('/', '_').replace(':', '')}.bat")
    
    elif update["type"] == "drive":
        # Redirect to Google Drive
        return jsonify({"redirect": update["link"]})
    
    elif update["type"] == "direct":
        return jsonify({"redirect": update["link"]})
    
    return jsonify({"error": "Unknown download type"}), 400

@app.route('/api/updates')
def api_updates():
    return jsonify(UPDATES_DATA)

if __name__ == '__main__':
    def open_browser():
        try:
            webbrowser.open('http://127.0.0.1:5000')
        except:
            pass
    
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        Timer(1.5, open_browser).start()
    
    print("Starting Gorilla Tag Update Archive server...")
    print("Server will open in your browser automatically.")
    print("Press Ctrl+C to stop the server.")
    app.run(debug=True, port=5000)

