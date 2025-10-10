from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64


def encrypt_aes(plaintext: str) -> str:
    # Step 1: Base64 decode the key string
    key_str_b64 = "QWR2Z1ZNM1laZVFFY3B3Ug=="
    # Decode from Base64 to bytes
    decoded_key_bytes = base64.b64decode(key_str_b64)
    # Interpret those bytes as UTF-8 string -> this is the actual key string
    key_str = decoded_key_bytes.decode(
        "utf-8"
    )  # Result: 'AdvGVM3YZeQEc pwR' (16 chars)

    # Step 2: Use first 16 bytes of UTF-8 encoding of key_str as AES key
    key = key_str.encode(
        "utf-8"
    )  # UTF-8 encode the string to bytes (should be 16 bytes)

    # Step 3: Encrypt plaintext using AES-128-ECB with PKCS7 padding
    cipher = AES.new(key, AES.MODE_ECB)
    plaintext_bytes = plaintext.encode("utf-8")
    padded_plaintext = pad(plaintext_bytes, AES.block_size, style="pkcs7")
    ciphertext_bytes = cipher.encrypt(padded_plaintext)

    # Step 4: Return Base64-encoded ciphertext (CryptoJS default format)
    return base64.b64encode(ciphertext_bytes).decode("utf-8")


def decrypt_aes(ciphertext_b64: str) -> str:
    """
    解密由 encrypt_aes 加密的文本。

    :param ciphertext_b64: 被加密后并 Base64 编码的字符串
    :return: 解密后的原始明文字符串
    """
    if not ciphertext_b64:
        return ""
    # Step 1: Base64 decode the key string (same as in encrypt_aes)
    key_str_b64 = "QWR2Z1ZNM1laZVFFY3B3Ug=="
    decoded_key_bytes = base64.b64decode(key_str_b64)
    key_str = decoded_key_bytes.decode("utf-8")  # 得到 'AdvGVM3YZeQEc pwR'

    # Step 2: 使用 UTF-8 编码得到 16 字节密钥
    key = key_str.encode("utf-8")  # 必须是 16 字节（AES-128）

    # Step 3: Base64 解码输入的密文
    ciphertext_bytes = base64.b64decode(ciphertext_b64)

    # Step 4: 使用 AES-ECB 模式解密
    cipher = AES.new(key, AES.MODE_ECB)
    padded_plaintext = cipher.decrypt(ciphertext_bytes)

    # Step 5: 移除 PKCS7 填充
    plaintext_bytes = unpad(padded_plaintext, AES.block_size, style="pkcs7")

    # Step 6: 返回 UTF-8 解码后的原始字符串
    return plaintext_bytes.decode("utf-8")
