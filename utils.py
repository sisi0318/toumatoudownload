import time
import requests
import re
import os
import json
import urllib3
import base64
import gzip
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from config import CONFIG

sixgodapi = "https://fq.0013107.xyz/api/core_sixgod" #魔法？
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

def core_sixgod(surl, params=None, devices=None, data=None, header=None, log=False):
    body = {
        "surl": surl,
        "params": params or {},
        "devices": devices or {},
        "data": data or {},
        "header": header or {},
    }
    response = requests.post(sixgodapi, json=body)
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} {response.text}")
    response_data = response.json()
    return response_data["headers"], response_data["sign_url"]

okp = ["ac25", "c67d", "dd8f", "38c1", "b37a", "2348", "828e", "222e"]
def grk():
    return "".join(okp)

class FqCrypto:
    def __init__(self, key):
        self.key = bytes.fromhex(key)
        if len(self.key) != 16:
            raise ValueError(f"Key length mismatch! key: {self.key.hex()}")
        self.cipher_mode = AES.MODE_CBC
    def encrypt(self, data, iv):
        cipher = AES.new(self.key, self.cipher_mode, iv)
        return cipher.encrypt(pad(data, AES.block_size))
    def decrypt(self, data):
        iv = data[:16]
        ct = data[16:]
        cipher = AES.new(self.key, self.cipher_mode, iv)
        return unpad(cipher.decrypt(ct), AES.block_size)
    def new_register_key_content(self, device_id, str_val):
        if not str_val.isdigit() or not device_id.isdigit():
            raise ValueError(f"Parse failed\ndevice_id: {device_id}\nstr_val:{str_val}")
        combined_bytes = int(device_id).to_bytes(8, 'little') + int(str_val).to_bytes(8, 'little')
        iv = get_random_bytes(16)
        enc_data = self.encrypt(combined_bytes, iv)
        return base64.b64encode(iv + enc_data).decode('utf-8')

class FqVariable:
    def __init__(self, install_id, device_id, aid, update_version_code):
        self.install_id = install_id
        self.device_id = device_id
        self.aid = aid
        self.update_version_code = update_version_code

class FqReq:
    def __init__(self, var):
        self.var = var
        self.session = requests.Session()
    def batch_get(self, item_ids, download=False):
        """批量获取章节内容，item_ids为list或str，自动分批，每批最多30个"""
        headers = {"Cookie": f"install_id={self.var.install_id}"}
        url = "https://api5-normal-sinfonlineb.fqnovel.com/reading/reader/batch_full/v"
        if isinstance(item_ids, str):
            item_ids = [item_ids]
        results = {"data": {}}
        batch_size = 30
        for i in range(0, len(item_ids), batch_size):
            batch = item_ids[i:i+batch_size]
            params = {
                "item_ids": ",".join(batch),
                "key_register_ts": "0",
                "req_type": "0" if download else "1",
                "iid": self.var.install_id,
                "device_id": self.var.device_id,
                "aid": self.var.aid,
                "version_code": "66932",
                "version_name": "6.6.9.32",
                "device_platform": "android",
                "os": "android",
                "ssmix": "a",
                "update_version_code": self.var.update_version_code
            }
            sign_headers, sign_urls = core_sixgod(surl=url, params=params, header=headers)
            response = self.session.get(url=sign_urls, headers=sign_headers, timeout=5)
            response.raise_for_status()
            ret_arr = response.json()
            if "data" in ret_arr:
                results["data"].update(ret_arr["data"])
        return results
    def get_register_key(self):
        headers = {
            "Cookie": f"install_id={self.var.install_id}",
            "Content-Type": "application/json"
        }
        url = "https://api5-normal-sinfonlineb.fqnovel.com/reading/crypt/registerkey"
        params = {"aid": self.var.aid}
        crypto = FqCrypto(grk())
        payload = json.dumps({
            "content": crypto.new_register_key_content(self.var.device_id, "0"),
            "keyver": 1
        }).encode('utf-8')
        response = self.session.post(url, headers=headers, params=params, data=payload, verify=False)
        response.raise_for_status()
        ret_arr = response.json()
        key_str = ret_arr['data']['key']
        byte_key = crypto.decrypt(base64.b64decode(key_str))
        print(f"获取解密密钥成功: {byte_key.hex()}")
        return byte_key.hex()
    def get_decrypt_contents(self, res_arr, register_key=None):
        key = register_key if register_key else self.get_register_key()
        crypto = FqCrypto(key)
        for item_id, content in res_arr['data'].items():
            byte_content = crypto.decrypt(base64.b64decode(content['content']))
            s = gzip.decompress(byte_content).decode('utf-8')
            res_arr['data'][item_id]['originContent'] = s
        return res_arr

def save_status(save_path, downloaded):
    status_file = os.path.join(save_path, CONFIG["status_file"])
    with open(status_file, 'w', encoding='utf-8') as f:
        json.dump(list(downloaded), f, ensure_ascii=False, indent=2)

def load_status(save_path):
    status_file = os.path.join(save_path, CONFIG["status_file"])
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except Exception:
            pass
    return set()

def down_text(chapter_ids, book_id=None, client=None, register_key=None):
    """批量下载章节内容，chapter_ids可为str或list，支持client和register_key复用"""
    try:
        if hasattr(down_text, "last_request_time"):
            elapsed = time.time() - down_text.last_request_time
            if elapsed < CONFIG["request_rate_limit"]:
                time.sleep(CONFIG["request_rate_limit"] - elapsed)
        down_text.last_request_time = time.time()
        if client is None:
            var = FqVariable(
                CONFIG["official_api"]["install_id"],
                CONFIG["official_api"]["device_id"],
                CONFIG["official_api"]["aid"],
                CONFIG["official_api"]["update_version_code"]
            )
            client = FqReq(var)
        if register_key is None:
            register_key = client.get_register_key()
        if isinstance(chapter_ids, str):
            chapter_ids = [chapter_ids]
        batch_res_arr = client.batch_get(chapter_ids, False)
        res = client.get_decrypt_contents(batch_res_arr, register_key=register_key)
        result_list = []
        for cid in chapter_ids:
            v = res['data'].get(cid)
            if not v:
                result_list.append((None, None))
                continue
            content = v['originContent']
            chapter_title = v['title']
            if chapter_title and re.match(r'^第[0-9]+章', chapter_title):
                chapter_title = re.sub(r'^第[0-9]+章\s*', '', chapter_title)
            content = re.sub(r'<header>.*?</header>', '', content, flags=re.DOTALL)
            content = re.sub(r'<footer>.*?</footer>', '', content, flags=re.DOTALL)
            content = re.sub(r'</?article>', '', content)
            content = re.sub(r'<p[^>]*>', '\n    ', content)
            content = re.sub(r'</p>', '', content)
            content = re.sub(r'<[^>]+>', '', content)
            content = re.sub(r'\\u003c|\\u003e', '', content)
            if chapter_title and content.startswith(chapter_title):
                content = content[len(chapter_title):].lstrip()
            content = re.sub(r'\n{3,}', '\n\n', content).strip()
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            formatted_content = '\n'.join(['    ' + line for line in lines])
            result_list.append((chapter_title, formatted_content))
        if len(result_list) == 1:
            return result_list[0]
        return result_list
    except requests.RequestException as e:
        print(f"官方API网络请求失败: {str(e)}")
        if isinstance(chapter_ids, list):
            return [(None, None)] * len(chapter_ids)
        return None, None