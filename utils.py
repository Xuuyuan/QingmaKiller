"""通用纯函数: 文本格式化、时间戳与站点文本解密"""
import base64
import time

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from config import decrypt_key_b64


def text_format(text):  # 清除不必要的字符 将unicode文本格式化为字符串以便于搜题
    text = str(text.replace('\u3000', '').replace('\xa0', ''))
    for i in [' ', '“', '”', '"', '.', '．']:
        text = text.replace(i, '')
    return text


def gettime():  # 获取现行时间戳
    t = str(time.time())
    return t[0:10] + t[11:14]


def decrypt(text):  # 解密青马易战文本 返回值类型为unicode文本
    if text == '':
        return ''
    key = base64.b64decode(decrypt_key_b64)
    cipher = AES.new(key, AES.MODE_ECB)
    decrypted = cipher.decrypt(base64.b64decode(text))
    decrypted = unpad(decrypted, AES.block_size, style='pkcs7').decode('utf-8')
    return decrypted
