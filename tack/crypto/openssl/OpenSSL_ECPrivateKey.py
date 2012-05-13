import math, ctypes
from tack.compat import a2b_hex
from tack.compat import bytesToStr
from tack.crypto.ASN1 import toAsn1IntBytes, asn1Length, ASN1Parser
from tack.crypto.Digest import Digest
from .OpenSSL_ECPublicKey import OpenSSL_ECPublicKey
from .OpenSSL import openssl as o
from tack.util.PEMEncoder import PEMEncoder

class OpenSSL_ECPrivateKey:
    
    @staticmethod
    def generateECKeyPair():
        try:
            ec_key, ec_group = None, None

            # Generate the new key
            ec_key = o.EC_KEY_new_by_curve_name(o.OBJ_txt2nid("prime256v1"))
            o.EC_KEY_generate_key(ec_key)

            # Extract the key's public and private values as byte strings
            pubBuf = bytesToStr(bytearray(1+64)) # [0x04] ...
            privBuf = bytesToStr(bytearray(32))

            ec_point = o.EC_KEY_get0_public_key(ec_key)
            ec_group = o.EC_GROUP_new_by_curve_name(o.OBJ_txt2nid("prime256v1"))            
            o.EC_POINT_point2oct(ec_group, ec_point, o.POINT_CONVERSION_UNCOMPRESSED, pubBuf, 65, None)

            bignum = o.EC_KEY_get0_private_key(ec_key)
            privLen = o.BN_bn2bin(bignum, privBuf)

            # Convert the public and private keys into fixed-length 64 and 32 byte arrays
            # Leading zeros are added to priv key, leading byte (0x04) stripped from pub key
            rawPublicKey =  bytearray(pubBuf[1:65])
            rawPrivateKey = bytearray(32-privLen) + bytearray(privBuf[:privLen])

            return (OpenSSL_ECPublicKey(rawPublicKey, ec_key), 
                    OpenSSL_ECPrivateKey(rawPrivateKey, rawPublicKey, ec_key))
        finally:
            o.EC_KEY_free(ec_key)
            o.EC_GROUP_free(ec_group)
    

    def __init__(self, rawPrivateKey, rawPublicKey, ec_key=None):
        self.ec_key = None # In case of early destruction
        assert(rawPrivateKey is not None and rawPublicKey is not None)
        assert(len(rawPrivateKey)==32 and len(rawPublicKey) == 64)

        self.rawPrivateKey = rawPrivateKey
        self.rawPublicKey  = rawPublicKey
        if ec_key:
            self.ec_key = o.EC_KEY_dup(ec_key)
        else:
            self.ec_key =  self._constructEcFromRawKey(self.rawPrivateKey)

    def __del__(self):
        o.EC_KEY_free(self.ec_key)

    def sign(self, data):        
        try:
            ecdsa_sig = None

            # Hash and apply ECDSA
            hashBuf = bytesToStr(Digest.SHA256(data))
            ecdsa_sig = o.ECDSA_do_sign(hashBuf, 32, self.ec_key)
            
            # Encode the signature into 64 bytes
            rBuf = bytesToStr(bytearray(32))
            sBuf = bytesToStr(bytearray(32))
            
            rLen = o.BN_bn2bin(ecdsa_sig.contents.r, rBuf)
            sLen = o.BN_bn2bin(ecdsa_sig.contents.s, sBuf)
            
            rBytes = bytearray(32-rLen) + bytearray(rBuf[:rLen])
            sBytes = bytearray(32-sLen) + bytearray(sBuf[:sLen])
            sigBytes = rBytes + sBytes              
        finally:
            o.ECDSA_SIG_free(ecdsa_sig)

        # Double-check the signature before returning
        assert(OpenSSL_ECPublicKey(self.rawPublicKey).verify(data, sigBytes))
        return sigBytes

    def getRawKey(self):
        return self.rawPrivateKey
        
    def _constructEcFromRawKey(self, rawPrivateKey):
        try:
            privBignum, ec_key = None, None
            
            ec_key = o.EC_KEY_new_by_curve_name(o.OBJ_txt2nid("prime256v1"))
            privBuf = bytesToStr(rawPrivateKey)
            privBignum = o.BN_new() # needs free
            o.BN_bin2bn(privBuf, 32, privBignum)     
            o.EC_KEY_set_private_key(ec_key, privBignum)            
            return o.EC_KEY_dup(ec_key)
        finally:
            o.BN_free(privBignum)
            o.EC_KEY_free(ec_key)


