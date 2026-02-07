import hashlib
import random
import string
import execjs
import os

# User Agent used in Dart codebase
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36 Core/1.116.567.400 QQBrowser/19.7.6764.400"

def get_ms_stub(room_id, unique_id):
    """
    Generates the msStub (MD5 hash of parameters).
    Matches getMsStub in Dart.
    """
    params = {
        "live_id": "1",
        "aid": "6383",
        "version_code": "180800",
        "webcast_sdk_version": "1.3.0",
        "room_id": room_id,
        "sub_room_id": "",
        "sub_channel_id": "",
        "did_rule": "3",
        "user_unique_id": unique_id,
        "device_platform": "web",
        "device_type": "",
        "ac": "",
        "identity": "audience",
    }
    
    # Python's dict is insertion ordered since 3.7, but to be safe and match Dart's implicit iteration order
    # (which was likely just insertion order or definition order), we keep it as is.
    # The Dart code does: params.entries.map((e) => "${e.key}=${e.value}").join(',')
    
    sig_params = ",".join([f"{k}={v}" for k, v in params.items()])
    
    # Calculate MD5
    md5 = hashlib.md5()
    md5.update(sig_params.encode('utf-8'))
    return md5.hexdigest()

def generate_ms_token(length=107):
    """
    Generates a random msToken.
    """
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def get_signature(room_id, unique_id):
    """
    Generates the X-Bogus signature using the extracted JS SDK.
    """
    js_path = os.path.join(os.path.dirname(__file__), 'douyin_sdk.js')
    
    if not os.path.exists(js_path):
        raise FileNotFoundError(f"JS SDK file not found at {js_path}. Please run extract_js.py first.")
        
    with open(js_path, 'r', encoding='utf-8') as f:
        js_code = f.read()
    
    # Initialize JS runtime
    ctx = execjs.compile(js_code)
    
    ms_stub = get_ms_stub(room_id, unique_id)
    
    print(f"Generating signature for Room ID: {room_id}, User ID: {unique_id}")
    print(f"Calculated msStub: {ms_stub}")
    
    try:
        signature = ctx.call("getMSSDKSignature", ms_stub, DEFAULT_USER_AGENT)
        
        # Retry logic if signature contains '-' or '=' (matching Dart implementation)
        while '-' in signature or '=' in signature:
            print("Signature contained invalid chars, retrying...")
            signature = ctx.call("getMSSDKSignature", ms_stub, DEFAULT_USER_AGENT)
            
        return signature
    except Exception as e:
        print(f"JS Execution Error: {e}")
        return None

if __name__ == "__main__":
    # Test values
    TEST_ROOM_ID = "7376429659866598196" # Example ID
    TEST_USER_ID = "123456789012" # Random user ID
    
    sig = get_signature(TEST_ROOM_ID, TEST_USER_ID)
    print(f"Generated Signature: {sig}")
    
    token = generate_ms_token()
    print(f"Generated msToken: {token}")
