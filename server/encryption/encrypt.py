from Crypto.Cipher import AES
import base64
import os
import glob
import sys
import numpy as np

# the block size for the cipher object; must be 16, 24, or 32 for AES
BLOCK_SIZE = 32
# the character used for padding--with a block cipher such as AES, the value
# you encrypt must be a multiple of BLOCK_SIZE in length.  This character is
# used to ensure that your value is always a multiple of BLOCK_SIZE
PADDING = '{'
# one-liner to sufficiently pad the text to be encrypted
pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * PADDING
# one-liners to encrypt/encode and decrypt/decode a string
# encrypt with AES, encode with base64
encode_aes = lambda c, s: c.encrypt(pad(s))
decode_aes = lambda c, e: c.decrypt(e).rstrip(PADDING)
create_cipher=lambda secret: AES.new(secret)

def create_secret(output_path=None):
    secret = os.urandom(BLOCK_SIZE)
    if output_path:
        with open(output_path, 'w+') as f:
            f.write(secret)
    return secret
    

if __name__ == '__main__':
    sys.path.append('..')
    from MyUtils import create_dir
    from demo_config import Config
    import cv2
    import pdb
    with open(os.path.join('..',Config.SECRET_KEY_FILE_PATH),'r') as f:
        secret=f.read()
    # generate a random secret key
    cipher=create_cipher(secret)
    tfs = glob.glob('../encrypted/*.jpg')
    output_dir=sys.argv[1]
    create_dir(output_dir)
    for tf in tfs:
        d = open(tf,'r').read()
        decoded = decode_aes(cipher, d)
        np_data=np.fromstring(decoded, dtype=np.uint8)
#        pdb.set_trace()
        bgr_img=cv2.imdecode(np_data,cv2.IMREAD_COLOR)
        cv2.imwrite(os.path.join(output_dir,os.path.basename(tf)), bgr_img)
        # with open(), 'w+') as f:
        #     cv2.imwrite(f, bgr_img)            
            
    # print 'Encrypted string:', encoded
    # # decode the encoded string
    # decoded = decode_aes(cipher, encoded)
    # print 'Decrypted string:', decoded
