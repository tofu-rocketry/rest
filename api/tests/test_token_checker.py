"""This module tests the JSON Web Token validation."""

import logging
import unittest
import time

from jose import jwt
from django.test import TestCase
from mock import patch

from api.utils.TokenChecker import TokenChecker


# Using unittest and not django.test as no need for overhead of database
class TokenCheckerTest(TestCase):
    """Tests the JSON Web Token validation."""

    def setUp(self):
        """Create a new TokenChecker and disable logging."""
        self._token_checker = TokenChecker(None, None)
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        """Re-enable logging."""
        logging.disable(logging.NOTSET)

    @patch.object(TokenChecker, '_get_issuer_public_key')
    def test_token_cache(self, mock_get_issuer_public_key):
        """
        Check a cached token is granted access.

        Method does this by checking a token is valid twice, the first time
        the token is validate and stored in a cache, the second time access
        should be granted because the token is in the cache, not because the
        token is valid.
        """
        # Mock the external call to retrieve the IAM public key
        # used in the _verify_token and is_token_valid call
        mock_get_issuer_public_key.return_value = PUBLIC_KEY

        payload_list = []

        # This payload will be valid as we will sign it with PRIVATE_KEY
        payload = {
            'iss': 'https://iam-test.idc.eu/',
            'jti': '098cb343-c45e-490d-8aa0-ce1873cdc5f8',
            'iat': int(time.time()) - 2000000,
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36',
            'exp': int(time.time()) + 200000}

        # Add the same token twice, this is what tests the cache functionality
        payload_list = [payload, payload]

        for payload in payload_list:
            token = self._create_token(payload, PRIVATE_KEY)
            with self.settings(IAM_HOSTNAME_LIST='iam-test.idc.eu'):
                self.assertTrue(
                    self._token_checker.is_token_valid(token),
                    "Token with payload %s should not be accepted!" % payload)

    @patch.object(TokenChecker, '_get_issuer_public_key')
    def test_token_cache_mis_matche(self, mock_get_issuer_public_key):
        """
        Check tokens with the same subject are handled correctly.

        Having a token cached for the sub should not be sufficent to grant
        access, the tokens must match.
        """
        # Mock the external call to retrieve the IAM public key
        # used in the _verify_token and is_token_valid call
        mock_get_issuer_public_key.return_value = PUBLIC_KEY

        payload_list = []

        # This payload will be valid as we will sign it with PRIVATE_KEY
        payload1 = {
            'iss': 'https://iam-test.idc.eu/',
            'jti': '098cb343-c45e-490d-8aa0-ce1873cdc5f8',
            'iat': int(time.time()) - 2000000,
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36',
            'exp': int(time.time()) + 200000}

        # This payload has a subject that will be in the cache, but this
        # new token is not. We need to ensure this invalid token does not
        # get granted rights based only on it's sub being in the cache
        payload2 = {
            'iss': 'https://iam-test.idc.eu/',
            'jti': '098cb343-c45e-490d-8aa0-ce1873cdc5f8',
            'iat': int(time.time()) - 2000000,
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36',
            'exp': int(time.time()) - 200}

        token1 = self._create_token(payload1, PRIVATE_KEY)
        token2 = self._create_token(payload2, PRIVATE_KEY)

        with self.settings(IAM_HOSTNAME_LIST='iam-test.idc.eu'):
            self.assertTrue(
                self._token_checker.is_token_valid(token1),
                "Token with payload %s should not be accepted!" % payload1)

            self.assertFalse(
                 self._token_checker.is_token_valid(token2),
                 "Token with payload %s should not be accepted!" % payload2)

    @patch.object(TokenChecker, '_get_issuer_public_key')
    def test_valid_token(self, mock_get_issuer_public_key):
        """Check a valid and properly signed token is accepted."""
        # Mock the external call to retrieve the IAM public key
        # used in the _verify_token and is_token_valid call
        mock_get_issuer_public_key.return_value = PUBLIC_KEY

        payload_list = []

        # This payload will be valid as we will sign it with PRIVATE_KEY
        payload = {
            'iss': 'https://iam-test.idc.eu/',
            'jti': '098cb343-c45e-490d-8aa0-ce1873cdc5f8',
            'iat': int(time.time()) - 2000000,
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36',
            'exp': int(time.time()) + 200000}

        token = self._create_token(payload, PRIVATE_KEY)

        with self.settings(IAM_HOSTNAME_LIST='iam-test.idc.eu'):
            self.assertTrue(
                self._token_checker.is_token_valid(token),
                "Token with payload %s should be accepted!" % payload)

    @patch.object(TokenChecker, '_get_issuer_public_key')
    def test_verify_token(self, mock_get_issuer_public_key):
        """
        Check a mis-signed/'forged' token is detected.

        Both by:
         - _verify_token
         - is_token_valid

        The first method checks wether the key is properly signed
        The second method detemines wether the token is invalid
        """
        # Mock the external call to retrieve the IAM public key
        # used in the _verify_token and is_token_valid call
        mock_get_issuer_public_key.return_value = PUBLIC_KEY

        payload_list = []

        # This payload would be valid if properly signed, but we are going to
        # sign it with FORGED_PRIVATE_KEY which will not match the PUBLIC_KEY
        payload_list.append({
            'iss': 'https://iam-test.idc.eu/',
            'jti': '098cb343-c45e-490d-8aa0-ce1873cdc5f8',
            'iat': int(time.time()) - 2000000,
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36',
            'exp': int(time.time()) + 200000})

        for payload in payload_list:
            token = self._create_token(payload, FORGED_PRIVATE_KEY)
            with self.settings(IAM_HOSTNAME_LIST='iam-test.idc.eu'):
                self.assertFalse(
                    self._token_checker._verify_token(token, payload['iss']),
                    "Payload %s should not be accepted!" % payload)

                self.assertFalse(
                    self._token_checker.is_token_valid(token),
                    "Token with payload %s should not be accepted!" % payload)

    def test_is_token_issuer_trusted(self):
        """
        Check an untrusted 'issuer' (or missing 'issuer') is detected.

        Both by:
         - _is_token_issuer_trusted
         - is_token_valid

        The first method checks wether the issuer is
        in settings.IAM_HOSTNAME_LIST
        The second method detemines wether the token is invalid
        """
        payload_list = []

        # Add a payload without 'iss' field.
        # to test we reject these as we cannot
        # tell where it came from (so can't verify it)
        payload_list.append({
            'jti': '098cb343-c45e-490d-8aa0-ce1873cdc5f8',
            'iat': int(time.time()) - 2000000,
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36',
            'exp': int(time.time()) + 200000})

        # Add a payload with a malicious 'iss' field.
        # to test we reject these as we do not wantt
        # to attempt to verify it
        payload_list.append({
            'iss': 'https://malicious-iam.idc.biz/',
            'jti': '098cb343-c45e-490d-8aa0-ce1873cdc5f8',
            'iat': int(time.time()) - 2000000,
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36',
            'exp': int(time.time()) + 200000})

        for payload in payload_list:
            token = self._create_token(payload, PRIVATE_KEY)

            with self.settings(IAM_HOSTNAME_LIST='iam-test.idc.eu'):
                self.assertFalse(
                    self._token_checker._is_token_issuer_trusted(payload),
                    "Payload %s should not be accepted!" % payload)

                self.assertFalse(
                    self._token_checker.is_token_valid(token),
                    "Token with payload %s should not be accepted!" % payload)

    def test_is_token_json_temporally_valid(self):
        """
        Check that temporally invalid payload/token is detected.

        Both by:
         - _is_token_json_temporally_valid
         - is_token_valid

        The first method checks the temporal validity of the payload
        The second method detemines wether the token is invalid
        """
        payload_list = []

        # Add a payload wihtout 'iat' or 'exp' to the payload list
        # to test we reject these (as we are choosing to)
        payload_list.append({
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36',
            'iss': 'https://iam-test.indigo-datacloud.eu/',
            'jti': '714892f5-014f-43ad-bea0-fa47579db222'})

        # Add a payload without 'exp' to the payload_list
        # to test we reject these (as we are choosing to)
        payload_list.append({
            'iss': 'https://iam-test.indigo-datacloud.eu/',
            'jti': '098cb343-c45e-490d-8aa0-ce1873cdc5f8',
            'iat': int(time.time()) - 2000000,
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36'})

        # Add a payload without 'iat'
        # to test we reject these (as we are choosing to)
        payload_list.append({
            'iss': 'https://iam-test.indigo-datacloud.eu/',
            'jti': '098cb343-c45e-490d-8aa0-ce1873cdc5f8',
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36',
            'exp': int(time.time()) + 200000})

        # Add a payload with an 'iat' and 'exp' in the past
        # (e.g. they have expired) to test we are
        # rejecting these
        payload_list.append({
            'iss': 'https://iam-test.indigo-datacloud.eu/',
            'jti': '098cb343-c45e-490d-8aa0-ce1873cdc5f8',
            'iat': int(time.time()) - 2000000,
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36',
            'exp': int(time.time()) - 200000})

        # Add a payload with an 'iat' and 'exp' in the future
        # to test we are rejecting these (as we should as they
        # are not yet valid)
        payload_list.append({
            'iss': 'https://iam-test.indigo-datacloud.eu/',
            'jti': '098cb343-c45e-490d-8aa0-ce1873cdc5f8',
            'iat': int(time.time()) + 200000,
            'sub': 'ac2f23e0-8103-4581-8014-e0e82c486e36',
            'exp': int(time.time()) + 2000000})

        for payload in payload_list:
            # Assert the underlying helper method reponsible for
            # checking temporal validity returns False when passed
            # temporally invalid payloads
            self.assertFalse(
                self._token_checker._is_token_json_temporally_valid(payload),
                "Payload %s should not be accepted!" % payload)

            # Assert the wrapper method is_token_valid reutrns
            # False when passed temporally invalid tokens
            token = self._create_token(payload, PRIVATE_KEY)
            self.assertFalse(
                self._token_checker.is_token_valid(token),
                "Token with payload %s should not be accepted!" % payload)

    def _create_token(self, payload, key):
        """Return a token, signed by key, correspond to the payload."""
        return jwt.encode(payload, key, algorithm='RS256')

# Used to sign tokens
PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAqxAx1H7MabcEYhis3SJoaA3tq6wUgzKzv4c16nAW4yT21P8O
lL9qKYkzWuJWWiI90ecEHONEjDI+dFfaj/bK2O0jDT1NqVZbn2kW3sXaqUs4lUIg
5iPXysknitQjQsO1AmLZXFMNSPCKhBpMPxqG9vBMSxVMIXxXMZXeFpFIOqHFXgtq
+KmktwB2Aj/91NlSSj+Lw7bVSaZZNok/kuN/q43A6LS9uRHCQy9aeU0G8rZoqFSf
F6LypFBN8iZxaw8zlUKy2NYpu6opNUMhTxP7JmEy6yr4kMY7LUNRAKoP4tpgwwgt
hnecyprGGr93vh2qifP+bV3J3oa+ub1+jql63QIBIwKCAQAJxmk/V7PoyKEqLUu0
3WUNQp/d7JN1NhjmX39se28Fqlc/XwglwcuNWEwT0mtVm46BBeL6ViEslSgj58NY
rwRG6PqwTKVaIjEfDVHDlkcCXBHcpLFsPI/89Y07IhCkurni4RO8IgDCVuNYAYCz
JhZXQO5qsMKFkhOcbva/dgQgm2+yX6i1lFYNstpdr8ODBhiT6Tn7B5CONbLICJFd
7SdVAORFgdOvRLHkLPcL4I6x0hautCvEf2x47kRaLGtPMsFJQSZYl+Z81whwrJTM
zGTLH4kM6qHlIhABYhqME5bCVzHYmvXW+uIgVLznfIzQFyewRdMJZzCp0XxqjOkX
yixLAoGBANbKpZVf2giL26RpUsZ8waIFc7tQAzWSqwF384XPFn8tdN1DBT3R2rQk
8gnjX07Z6YrxkEvAhb7hDgB09EGPx1nDEXnFk1Y2xXePBccdSVQvjc/ExX0YGtBi
ZCbiJW5+ORx8olxkNiEVUvik62470fOkWtrwO6qq77lc5QQVKlopAoGBAMvh280v
K7o7auQxaVnjLQIoWlnKrz3+T58R/8nYFtAuiUjlT4dsBOUFKm1GE/bw8FDFc1Vo
Z0l++KFTKNnxT6NQPRoE4JH8MZ3ycS4x0cMUK4TEW2pO11KyqlmLLdMbq1v3zgLw
GwZ/fOOi0GlItoBY0zZYlEuXxQQUNotZLRmVAoGBAMRhgXKgx1hFWxn55UfChSZr
Yn9fGOCGGLDissN7gkhkExNwedIe89fnQ7FE6Wyp+hiiWAq+pircZJK0EoUVvZPl
jFITuehsl0i9RxxyjC+2cwcaTik6nCw8s1bAIjki8mMwH2pqQB4/Yc1jlWwZb3+s
Nc98jlLlbXZGTbqXAiaLAoGBAIvOExBa3CfuOqsakWI1YLEFukwzNlZlPelrbZG4
vy+q4cuV7WQs0CgDis6WdBcLnXk28AANE6AcjTtsOUT9PexURyfI1IFcectkat3Z
BN2KLHhMIW135BtzMvuSoxRqvqV2uSaWA+cy2Uui2A2uNAA86JpLXl+4hxi9Zzr7
UiArAoGBALrLwrhYtwOhMoJPK+XlMTJpLFSOUiGcFg06cvDtsUCz1H0Ma1TuHNSJ
/El54J1bGpJ/h212wB+gAHE7nRNJfFn5vPJtqwMv/SW675SA4mlKi2xoBO1NW/sw
FIusZ178P2e/lc+1QJoKkrM7ZKxnDvNj2Lt3B3JmXunXWZpn4i8Q
-----END RSA PRIVATE KEY-----"""

# Used to verify tokens signed with PRIVATE_KEY
PUBLIC_KEY = {"keys": [{"kty": "RSA",
                        "n": ("qxAx1H7MabcEYhis3SJoaA3tq6wUgzKzv4c"
                              "16nAW4yT21P8OlL9qKYkzWuJWWiI90ecEHO"
                              "NEjDI-dFfaj_bK2O0jDT1NqVZbn2kW3sXaq"
                              "Us4lUIg5iPXysknitQjQsO1AmLZXFMNSPCK"
                              "hBpMPxqG9vBMSxVMIXxXMZXeFpFIOqHFXgt"
                              "q-KmktwB2Aj_91NlSSj-Lw7bVSaZZNok_ku"
                              "N_q43A6LS9uRHCQy9aeU0G8rZoqFSfF6Lyp"
                              "FBN8iZxaw8zlUKy2NYpu6opNUMhTxP7JmEy"
                              "6yr4kMY7LUNRAKoP4tpgwwgthnecyprGGr9"
                              "3vh2qifP-bV3J3oa-ub1-jql63Q"),
                        "e": "Iw"}]}

# Used to 'forge' a token that PUBLIC_KEY will not be able to verify
FORGED_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCxHCAbJMUth6NV
5dz3J6p13NY0deuhST4ped3ogFHvfMlj0ehJMxLVe/B5oooyQkaSyA0yc4eBfYxj
W4tmOGyWZic1wLhQUQpXvdVcmt+f26GewnIvWOI4MSg1C+Qg9E4I/eIlpz0jrkbq
q8k/x4pr/c+X8TNiaiZb2Sjp/SFdpwqZ4Eh8u3PPc/B5/mJfvg0T8mrjZ8kQkPcB
SH+JzbzyFuEpa1OqAWeSOaQniyS2SEdW8DT0/AlQcf3UmvR0Dh5N6KltwWdWdocg
1jsLCYa32/8uiBJ3JM/C+vWtBjFGGoHp4msk9VAUnq9oWA5z5NT7G1lpoAj1Hjuu
MnRM9cGnAgMBAAECggEBAIXzrri428TuxHNwMepgfsU77GqrETbgLXqzKEnz24SV
TcAIf3X1gfYjEiL88ybGB5h2Y7zXshIXAboX/9ulK0OpKVi3VO+yC2+HLTsoC6Bd
PeTUTgZPZHF5hF5yiuz9uZOFaahuz4gQBKTynnh1k9TPl1Xk4Kc7f52SJiarA7RP
In7R/YDW6Wxg8fCID1L2McFxlAdHF94oG1qNe1AriaUKZ9MUKaGxmdxuAk3pA1cC
IqTQYHb1zgJ8oFlhqYVubTL/85ADVV1aY0/UKZcwL1xLJ2xifGvbYPUs5gMJ0w0F
zHNdhZ6991/F4Txr9Q3kwZX8uwxFFgWSh2qE2aJno8ECgYEA5OLDb3G6zIpbmAU8
LbfWt/PgsQAa0XtnCrzyz5SnBjPqbesPrg6VxPVdP2/OW+yBvtxmgo3M5xC7LV8C
x1/In90FXa2KfSXj2OENR/ks55BVdKcI+Jmljmum8AkPvdwb42ztpKgSC8BhItKd
G5Ft1B2t6EJZY2SPL8UbUXtAkgcCgYEAxhcx2zPlC+x7Y0oKidZswR3M2iB56One
3dFabzWRA+P7/YA1VM+VPppSDr8AqGpiv0rLh7xK0R6usjmZ1Z/X4oQDF5uiH0uK
DqsXDF61fFjKClfY4WcUzlcolJ8AD9q50o7bc+hc2WEWxbh/iqfzEWYIa3Y+cuUz
XMOZJux+62ECgYBTFREV6fWBe5OF2hifC8VQHqFn/n69nYqoti95NB9wu/WTkqit
aLPqu5nuhfolGfN6wWwgZbKECWm4LW3Hyzf693KUL4M+rDtJpV95ybQIFjc+0ccK
3lLfIKqHJPLm2vfwlMCqbSunwlxAFK1crWxte5x921+xGXZ0Q5sH97JXjwKBgEGa
HODDZu9z+ckAFE1hvdKW0+jJKJaCHVTIqHJ8AvKO5j0l4IOd24dIBDTt/IHJ+bnw
Q0dIjF6FEsXjXZbpwM07euqumBpVIfuJnbBzDReJMCAMx76eLL3JD59oqNSXU0Lw
HK1eHqG/DZOdbl+1D0KLz+4G0teqIEBwZqAFYmMBAoGBANmBGtkC6APqRe5Dzz9F
z5L9Mt9Krz8EI6s43XA4fYhouw07zGY0816BGa7r772duZkfh/J8kuxWRdvseo5G
y3EDz4+nl+tzxzYvbsSNOK8ceJRHNwJQPZuq166svKGLe6tj65MtfvIUTzWUU9FW
OLxDCvBa2CgAJVfUO1MhtX/L
-----END PRIVATE KEY-----"""
